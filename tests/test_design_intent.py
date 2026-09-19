"""Comprehensive Unit, Security, and Integration Tests for AI Design-Intent Package.

Normative Authority:
- docs/architecture/PHASE_5_0_ADAPTIVE_ACOUSTIC_ARCHITECTURE_DISCOVERY.md
- docs/architecture/PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    coordinate_descent_search,
    evaluate_acoustic_target_loss,
)
from acoustiforge.builders.optimization_adapter import compile_optimization_result_to_graph
from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.profiles import DriverProfile
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    OptimizationResult,
    OptimizationSpecification,
)
from acoustiforge.execution.offline import OfflineExecutionBackend
from acoustiforge.execution.interface import StreamConfig
from acoustiforge.extensions.spatial_optimization import (
    MultiPositionOptimizationResult,
    MultiPositionOptimizationSpecification,
    SpatialMeasurementPosition,
    build_multi_position_objective,
    optimize_multi_position,
)
from acoustiforge.intent.adapter import DesignIntentAdapter
from acoustiforge.intent.contracts import (
    ConstraintIntent,
    CrossoverIntent,
    DesignIntent,
    IntentTranslationRecord,
    IntentValidationError,
    SpatialIntent,
    TargetCurveIntent,
    TonalBalanceIntent,
    UnsupportedIntentError,
)
from acoustiforge.intent.provider import (
    IDesignIntentProvider,
    MockDesignIntentProvider,
)


# ==============================================================================
# Fixtures & Synthetic Measurement Helpers
# ==============================================================================

def _create_synthetic_flat_response(
    freqs: np.ndarray,
    level_db: float = 85.0,
    delay_seconds: float = 0.0,
) -> FrequencyResponseData:
    """Create synthetic flat response with optional delay phase."""
    mags = np.full_like(freqs, fill_value=level_db, dtype=np.float64)
    if delay_seconds == 0.0:
        phases = np.zeros_like(freqs, dtype=np.float64)
    else:
        phases = (-2.0 * np.pi * freqs * delay_seconds) % (2.0 * np.pi)
        phases = np.where(phases > np.pi, phases - 2.0 * np.pi, phases)
    return FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags, phase_rad=phases)


@pytest.fixture
def synthetic_spatial_positions() -> tuple[SpatialMeasurementPosition, SpatialMeasurementPosition]:
    """Generate 2 symmetric spatial measurement positions for spatial optimization."""
    freqs = np.geomspace(200.0, 8000.0, 100)
    pos1_w = _create_synthetic_flat_response(freqs, level_db=85.0, delay_seconds=0.0)
    pos1_t = _create_synthetic_flat_response(freqs, level_db=85.0, delay_seconds=0.000100)
    pos1 = SpatialMeasurementPosition("Center", {"woofer": pos1_w, "tweeter": pos1_t}, coordinates=(0.0, 2.0, 1.0))

    pos2_w = _create_synthetic_flat_response(freqs, level_db=85.0, delay_seconds=0.000100)
    pos2_t = _create_synthetic_flat_response(freqs, level_db=85.0, delay_seconds=0.0)
    pos2 = SpatialMeasurementPosition("Right", {"woofer": pos2_w, "tweeter": pos2_t}, coordinates=(0.5, 2.0, 1.0))

    return pos1, pos2


# ==============================================================================
# 1. Intent Contracts & Value Object Tests
# ==============================================================================

def test_design_intent_construction_and_immutability() -> None:
    """Verify that DesignIntent and its sub-intents are frozen and immutable."""
    intent = DesignIntent(
        intent_id="intent-001",
        query_text="create a flat response with 2kHz crossover",
        target_curve=TargetCurveIntent(preset_name="flat", target_spl_db=85.0),
        tonal_balance=TonalBalanceIntent(warmth_db=1.0),
        crossover=CrossoverIntent(family=CrossoverFamily.LINKWITZ_RILEY, order=4, target_frequency_hz=2000.0),
    )

    assert intent.intent_id == "intent-001"
    assert intent.query_text == "create a flat response with 2kHz crossover"
    assert intent.target_curve.preset_name == "flat"
    assert intent.tonal_balance.warmth_db == 1.0
    assert intent.crossover.target_frequency_hz == 2000.0

    # Immutability check
    with pytest.raises(Exception):
        intent.intent_id = "mutated"  # type: ignore

    with pytest.raises(Exception):
        intent.tonal_balance.warmth_db = 2.0  # type: ignore


def test_intent_validation_invalid_parameters_rejected() -> None:
    """Verify that malformed and non-finite parameters fail validation."""
    with pytest.raises(IntentValidationError, match="intent_id must be a non-empty string"):
        DesignIntent(intent_id="", query_text="test")

    with pytest.raises(IntentValidationError, match="finite float"):
        TargetCurveIntent(target_spl_db=float("nan"))

    with pytest.raises(IntentValidationError, match="finite float"):
        TonalBalanceIntent(warmth_db=float("inf"))

    with pytest.raises(IntentValidationError, match="exceeds safety envelope"):
        TonalBalanceIntent(low_shelf_db=30.0)

    with pytest.raises(IntentValidationError, match="Unsupported crossover order"):
        CrossoverIntent(order=3)

    with pytest.raises(IntentValidationError, match="search_band_hz must satisfy"):
        CrossoverIntent(search_band_hz=(3000.0, 1000.0))  # Reversed bounds


# ==============================================================================
# 2. Mock AI Provider Tests
# ==============================================================================

def test_mock_intent_provider_known_queries() -> None:
    """Verify that MockDesignIntentProvider parses controlled queries deterministically."""
    provider = MockDesignIntentProvider()

    # Query 1: Warmth & 2kHz crossover
    intent1 = provider.propose_intent("Design a warm sound with 2 kHz crossover")
    assert isinstance(intent1, DesignIntent)
    assert intent1.tonal_balance.warmth_db == 1.5
    assert intent1.crossover.target_frequency_hz == 2000.0
    assert intent1.crossover.family == CrossoverFamily.LINKWITZ_RILEY

    # Query 2: Spatial sweetspot
    intent2 = provider.propose_intent("Prioritize primary listening position")
    assert intent2.spatial.profile_name == "primary_seat_weighted"

    # Query 3: Low shelf
    intent3 = provider.propose_intent("Add low shelf +3.0 dB")
    assert intent3.tonal_balance.low_shelf_db == 3.0


def test_mock_intent_provider_empty_query_rejected() -> None:
    """Verify that empty or whitespace queries are rejected."""
    provider = MockDesignIntentProvider()
    with pytest.raises(UnsupportedIntentError, match="Query string must be non-empty"):
        provider.propose_intent("   ")


def test_mock_intent_provider_deterministic_reproducibility() -> None:
    """Verify that identical queries produce identical structured intent content."""
    provider_a = MockDesignIntentProvider(default_intent_id_prefix="fixed")
    provider_b = MockDesignIntentProvider(default_intent_id_prefix="fixed")

    query = "Design a neutral flat response with 1500 Hz crossover"
    intent_a = provider_a.propose_intent(query)
    intent_b = provider_b.propose_intent(query)

    assert intent_a.query_text == intent_b.query_text
    assert intent_a.crossover.target_frequency_hz == intent_b.crossover.target_frequency_hz
    assert intent_a.target_curve.preset_name == intent_b.target_curve.preset_name


# ==============================================================================
# 3. Validation Firewall & Adapter Tests
# ==============================================================================

def test_adapter_valid_intent_compilation() -> None:
    """Verify that a valid DesignIntent compiles into an authoritative OptimizationSpecification."""
    intent = DesignIntent(
        intent_id="test-001",
        query_text="Standard 2-way flat design",
        target_curve=TargetCurveIntent(preset_name="flat", target_spl_db=85.0),
        crossover=CrossoverIntent(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            target_frequency_hz=1800.0,
            search_band_hz=(1200.0, 2400.0),
        ),
        constraints=ConstraintIntent(
            frequency_range_hz=(50.0, 18000.0),
            gain_bounds_db=(-6.0, 6.0),
            max_iterations=30,
        ),
    )

    spec, record = DesignIntentAdapter.compile(intent)

    assert isinstance(spec, OptimizationSpecification)
    assert isinstance(record, IntentTranslationRecord)
    assert record.validation_status == "ACCEPTED"
    assert spec.crossover_family == CrossoverFamily.LINKWITZ_RILEY
    assert spec.crossover_order == 4
    assert spec.crossover_bounds_hz == (1200.0, 2400.0)
    assert spec.frequency_range_hz == (50.0, 18000.0)
    assert spec.gain_bounds_db == (-6.0, 6.0)
    assert spec.max_iterations == 30


def test_adapter_validation_firewall_rejection() -> None:
    """Verify that invalid acoustic bounds fail closed with explicit errors."""
    # Contradictory bounds: crossover search band completely outside global frequency range
    invalid_intent = DesignIntent(
        intent_id="invalid-001",
        query_text="Bad bounds",
        crossover=CrossoverIntent(search_band_hz=(100.0, 200.0)),
        constraints=ConstraintIntent(frequency_range_hz=(500.0, 10000.0)),
    )

    with pytest.raises(IntentValidationError, match="must lie strictly within frequency range"):
        DesignIntentAdapter.compile(invalid_intent)


def test_adapter_unsupported_named_presets_rejected() -> None:
    """Verify that unbacked named presets fail closed without inventing fake data."""
    intent_unsupported = DesignIntent(
        intent_id="unsupported-001",
        query_text="Use harman_loudspeaker curve",
        target_curve=TargetCurveIntent(preset_name="harman_loudspeaker"),
    )

    with pytest.raises(UnsupportedIntentError, match="Unsupported target curve preset"):
        DesignIntentAdapter.compile(intent_unsupported)


# ==============================================================================
# 4. Track C Spatial Intent Integration Tests
# ==============================================================================

def test_adapter_spatial_intent_compilation(
    synthetic_spatial_positions: tuple[SpatialMeasurementPosition, SpatialMeasurementPosition],
) -> None:
    """Verify that SpatialIntent compiles into MultiPositionOptimizationSpecification."""
    pos1, pos2 = synthetic_spatial_positions

    intent = DesignIntent(
        intent_id="spatial-001",
        query_text="Optimize for primary seat with secondary listener weighting",
        spatial=SpatialIntent(profile_name="primary_seat_weighted", positions=(pos1, pos2)),
        crossover=CrossoverIntent(target_frequency_hz=2000.0),
    )

    spec, record = DesignIntentAdapter.compile(intent)

    assert isinstance(spec, MultiPositionOptimizationSpecification)
    assert len(spec.positions) == 2
    assert len(spec.spatial_weights) == 2
    # Check weight normalization: sum must equal 1.0
    assert pytest.approx(sum(spec.spatial_weights), abs=1e-6) == 1.0
    # Primary seat should receive 70% weight, secondary 30%
    assert pytest.approx(spec.spatial_weights[0], abs=1e-3) == 0.70
    assert pytest.approx(spec.spatial_weights[1], abs=1e-3) == 0.30


# ==============================================================================
# 5. Security & Isolation Tests
# ==============================================================================

def test_security_untrusted_query_code_injection_inert() -> None:
    """Verify that executable code in query strings is treated strictly as inert text."""
    malicious_query = "__import__('os').system('rm -rf /'); import sys; sys.exit(1)"
    intent = DesignIntent(
        intent_id="sec-001",
        query_text=malicious_query,
        target_curve=TargetCurveIntent(preset_name="flat"),
    )

    spec, record = DesignIntentAdapter.compile(intent)
    assert isinstance(spec, OptimizationSpecification)
    assert record.query_text == malicious_query
    # Ensure no code was executed and spec is a valid, clean domain object
    assert spec.crossover_family in (CrossoverFamily.LINKWITZ_RILEY, CrossoverFamily.BUTTERWORTH)


def test_security_ai_cannot_inject_arbitrary_coefficients_or_nodes() -> None:
    """Verify that DesignIntent cannot inject filter coefficients or graph nodes directly."""
    # DesignIntent schema does not have node or coefficient fields.
    intent = DesignIntent(
        intent_id="sec-002",
        query_text="Direct node injection attempt",
    )
    # Attempting to add arbitrary fields raises AttributeError (slots=True)
    with pytest.raises(AttributeError):
        intent.custom_biquad_coefficients = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]  # type: ignore


# ==============================================================================
# 6. End-to-End Continuity & Deterministic Core Execution Test
# ==============================================================================

def test_end_to_end_ai_intent_to_core_spatial_execution(
    synthetic_spatial_positions: tuple[SpatialMeasurementPosition, SpatialMeasurementPosition],
) -> None:
    """Verify the full pipeline:
    AI Proposal -> DesignIntent -> Adapter -> MultiPositionOptimizationSpecification -> Track C Spatial Optimizer -> OptimizationResult -> ComputeGraph -> PCM Execution.
    """
    pos1, pos2 = synthetic_spatial_positions
    provider = MockDesignIntentProvider()

    # 1. AI proposes intent from query
    query = "Optimize 2-way system with 2 kHz crossover for primary listening position"
    intent = provider.propose_intent(query)

    # 2. Adapter compiles & validates into Core Track C specification
    spec, record = DesignIntentAdapter.compile(intent, spatial_positions=(pos1, pos2))
    assert record.validation_status == "ACCEPTED"
    assert isinstance(spec, MultiPositionOptimizationSpecification)

    # 3. Core Track C optimizer executes deterministically
    opt_result = optimize_multi_position(spec)
    assert isinstance(opt_result, MultiPositionOptimizationResult)
    assert opt_result.converged is True
    assert 1400.0 <= opt_result.crossover_result.crossover_frequency_hz <= 2800.0

    # 4. Wrap into OptimizationResult and compile to frozen ComputeGraph
    from acoustiforge.acoustic_math.metrics import calculate_response_metrics
    primary_resp = opt_result.predicted_responses[pos1.name]
    init_metrics = calculate_response_metrics(primary_resp, spec.target_curve)
    opt_metrics = calculate_response_metrics(primary_resp, spec.target_curve)
    core_opt_result = OptimizationResult(
        crossover_result=opt_result.crossover_result,
        gain_results=opt_result.gain_results,
        alignment_results=opt_result.alignment_results,
        predicted_response=primary_resp,
        initial_metrics=init_metrics,
        optimized_metrics=opt_metrics,
        initial_loss_db=opt_result.initial_loss,
        final_loss_db=opt_result.total_loss,
        converged=opt_result.converged,
        iterations_completed=opt_result.iterations_completed,
    )
    graph = compile_optimization_result_to_graph(core_opt_result, sample_rate=48000, graph_name="AI_Spatial_Graph")
    assert graph.is_frozen is True

    # 5. PCM Execution through Offline Backend
    backend = OfflineExecutionBackend()
    config = StreamConfig(sample_rate=48000, channels=1, block_size=512)
    backend.initialize(graph, config)
    backend.start()

    in_samples = np.zeros((1, 512), dtype=np.float32)
    in_samples[0, 0] = 1.0  # Unit impulse
    in_block = PCMBlock(samples=in_samples, metadata=AudioMetadata(sample_rate=48000, channels=1))

    out_blocks = backend.process(in_block)
    assert isinstance(out_blocks, dict)
    assert len(out_blocks) >= 2
    for port_name, block in out_blocks.items():
        assert isinstance(block, PCMBlock)
        assert block.shape == (1, 512)
        assert np.isfinite(block.samples).all()
    backend.close()


# ==============================================================================
# 7. Independent Analytical Golden Parity Test
# ==============================================================================

def test_independent_golden_parity_between_ai_path_and_direct_path(
    synthetic_spatial_positions: tuple[SpatialMeasurementPosition, SpatialMeasurementPosition],
) -> None:
    """Verify that an AI-derived specification produces optimization results
    mathematically identical to a directly constructed Specification B.
    """
    pos1, pos2 = synthetic_spatial_positions

    # Path A: AI Intent Path
    intent = DesignIntent(
        intent_id="golden-test",
        query_text="Flat target 85dB, 2000Hz LR4 crossover, range 500Hz to 4000Hz",
        target_curve=TargetCurveIntent(preset_name="flat", target_spl_db=85.0),
        crossover=CrossoverIntent(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            target_frequency_hz=2000.0,
            search_band_hz=(1400.0, 2800.0),
        ),
        spatial=SpatialIntent(profile_name="wide_couch_even", positions=(pos1, pos2)),
        constraints=ConstraintIntent(
            frequency_range_hz=(500.0, 4000.0),
            gain_bounds_db=(-6.0, 6.0),
            delay_bounds_seconds=(0.0, 0.0005),
            max_iterations=30,
            convergence_tolerance_db=1e-5,
        ),
    )
    spec_a, _ = DesignIntentAdapter.compile(intent)

    # Path B: Direct Core Specification
    target_b = AcousticTargetCurve("Target_Direct", ((500.0, 85.0), (4000.0, 85.0)))
    spec_b = MultiPositionOptimizationSpecification(
        positions=(pos1, pos2),
        spatial_weights=(0.5, 0.5),
        target_curve=target_b,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(500.0, 4000.0),
        crossover_bounds_hz=(1400.0, 2800.0),
        gain_bounds_db=(-6.0, 6.0),
        delay_bounds_seconds=(0.0, 0.0005),
        sample_rate=48000,
        max_iterations=30,
        convergence_tolerance_db=1e-5,
    )

    # Optimize both specifications
    res_a = optimize_multi_position(spec_a)
    res_b = optimize_multi_position(spec_b)

    # Output parameters must match bit-exact
    assert pytest.approx(res_a.crossover_result.crossover_frequency_hz, abs=1e-6) == res_b.crossover_result.crossover_frequency_hz
    assert pytest.approx(res_a.total_loss, abs=1e-6) == res_b.total_loss
    assert res_a.gain_results["tweeter"].gain_db == pytest.approx(res_b.gain_results["tweeter"].gain_db, abs=1e-6)
    assert res_a.alignment_results["tweeter"].physical_delay_seconds == pytest.approx(
        res_b.alignment_results["tweeter"].physical_delay_seconds, abs=1e-9
    )
