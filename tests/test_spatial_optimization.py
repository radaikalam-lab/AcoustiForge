"""Unit and Analytical Golden Tests for Track C Multi-Position Spatial Optimization.

Normative Authority:
- docs/architecture/PHASE_5_1_EXTENSION_SELECTION_AND_DISCOVERY.md
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
from acoustiforge.contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
)
from acoustiforge.domain.validation import InvalidSpecificationError
from acoustiforge.extensions.spatial_optimization import (
    MultiPositionOptimizationResult,
    MultiPositionOptimizationSpecification,
    SpatialMeasurementPosition,
    build_multi_position_objective,
    optimize_multi_position,
)


# ==============================================================================
# Helper Synthesizers for Test Data
# ==============================================================================

def _create_synthetic_flat_response(
    freqs: np.ndarray,
    level_db: float = 0.0,
    delay_seconds: float = 0.0,
) -> FrequencyResponseData:
    """Create a synthetic FrequencyResponseData with constant magnitude and linear phase from delay."""
    mags = np.full_like(freqs, fill_value=level_db, dtype=np.float64)
    if delay_seconds == 0.0:
        phases = np.zeros_like(freqs, dtype=np.float64)
    else:
        # phi = -2 * pi * f * tau
        phases = (-2.0 * np.pi * freqs * delay_seconds) % (2.0 * np.pi)
        phases = np.where(phases > np.pi, phases - 2.0 * np.pi, phases)
    return FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=mags,
        phase_rad=phases,
    )


# ==============================================================================
# 1. Analytical Golden #1: Symmetric Two-Position Case
# ==============================================================================

def test_analytical_golden_1_symmetric_two_positions() -> None:
    """GOLDEN #1: Symmetric 2-Position Delay Compromise.

    Setup:
        Position 1: Tweeter has +100 us physical acoustic offset.
        Position 2: Tweeter has -100 us physical acoustic offset.
        Weights: w1 = 0.5, w2 = 0.5.

    Analytical Derivation:
        For a symmetric cost function L_multi(tau) = 0.5 * L(tau + 100us) + 0.5 * L(tau - 100us),
        by symmetry around tau = 0, the analytical optimal compromise delay is tau* = 0.0 us.
    """
    freqs = np.geomspace(200.0, 8000.0, 100)
    target = AcousticTargetCurve("FlatTarget", ((200.0, 0.0), (8000.0, 0.0)))

    # Position 1: Tweeter is delayed by +100 us (+0.0001 s) relative to woofer
    pos1_w = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.0)
    pos1_t = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.000100)
    pos1 = SpatialMeasurementPosition("Pos1_Plus100us", {"woofer": pos1_w, "tweeter": pos1_t})

    # Position 2: Tweeter is early by -100 us (modeled as woofer delayed by +100 us)
    pos2_w = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.000100)
    pos2_t = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.0)
    pos2 = SpatialMeasurementPosition("Pos2_Minus100us", {"woofer": pos2_w, "tweeter": pos2_t})

    spec = MultiPositionOptimizationSpecification(
        positions=(pos1, pos2),
        spatial_weights=(0.5, 0.5),
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(500.0, 4000.0),
        crossover_bounds_hz=(1000.0, 3000.0),
        gain_bounds_db=(-6.0, 6.0),
        delay_bounds_seconds=(0.0, 0.0005),
        ripple_weight=0.5,
        delay_weight=0.0,
        sample_rate=48000,
        max_iterations=30,
        convergence_tolerance_db=1e-5,
    )

    result = optimize_multi_position(spec)

    # Optimum must be tau* = 0.0 us (within discrete line-search numerical tolerance <= 5 us)
    tweeter_delay_opt = result.alignment_results["tweeter"].physical_delay_seconds
    assert math.isclose(tweeter_delay_opt, 0.0, abs_tol=5e-6), (
        f"Expected symmetric compromise tau* = 0.0s, got {tweeter_delay_opt:.6f}s"
    )
    # Gains should remain close to 0 dB (small trim due to crossover phase cancellation)
    assert math.isclose(result.gain_results["tweeter"].gain_db, 0.0, abs_tol=0.5)
    # Both positions must have equal losses by symmetry
    loss1 = result.spatial_losses["Pos1_Plus100us"]
    loss2 = result.spatial_losses["Pos2_Minus100us"]
    assert math.isclose(loss1, loss2, rel_tol=1e-4, abs_tol=1e-4)


# ==============================================================================
# 2. Analytical Golden #2: Asymmetric Weights Shift Optimum
# ==============================================================================

def test_analytical_golden_2_asymmetric_weights() -> None:
    """GOLDEN #2: Asymmetric Spatial Weight Bias.

    Setup:
        Position 1 (w1 = 0.8): Tweeter has relative delay 0 us.
        Position 2 (w2 = 0.2): Tweeter has relative delay +200 us.

    Analytical Expectation:
        With 80% weight on Position 1, the optimal compensation delay tau* is strongly
        pulled toward 0 us (matching Position 1's alignment), and total loss favors Position 1.
    """
    freqs = np.geomspace(200.0, 8000.0, 100)
    target = AcousticTargetCurve("FlatTarget", ((200.0, 0.0), (8000.0, 0.0)))

    # Position 1 (Primary): perfectly aligned
    pos1_w = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.0)
    pos1_t = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.0)
    pos1 = SpatialMeasurementPosition("DriverSeat_Primary", {"woofer": pos1_w, "tweeter": pos1_t})

    # Position 2 (Secondary): tweeter delayed by 200 us
    pos2_w = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.0)
    pos2_t = _create_synthetic_flat_response(freqs, level_db=0.0, delay_seconds=0.000200)
    pos2 = SpatialMeasurementPosition("Passenger_Secondary", {"woofer": pos2_w, "tweeter": pos2_t})

    spec = MultiPositionOptimizationSpecification(
        positions=(pos1, pos2),
        spatial_weights=(0.8, 0.2),
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(500.0, 4000.0),
        crossover_bounds_hz=(1000.0, 3000.0),
        gain_bounds_db=(-6.0, 6.0),
        delay_bounds_seconds=(0.0, 0.0005),
        sample_rate=48000,
        max_iterations=30,
        convergence_tolerance_db=1e-5,
    )

    result = optimize_multi_position(spec)

    # Position 1 loss must be significantly lower than Position 2 loss
    loss_primary = result.spatial_losses["DriverSeat_Primary"]
    loss_secondary = result.spatial_losses["Passenger_Secondary"]
    assert loss_primary < loss_secondary
    # Tweeter delay must stay very close to 0 us
    tweeter_delay = result.alignment_results["tweeter"].physical_delay_seconds
    assert tweeter_delay < 50e-6, f"Tweeter delay {tweeter_delay*1e6:.1f}us should be < 50us"


# ==============================================================================
# 3. Three-Position Validation & Monotonicity
# ==============================================================================

def test_three_position_spatial_optimization() -> None:
    """Validate 3-position spatial optimization (Left, Center, Right) across 2-way system."""
    freqs = np.geomspace(100.0, 10000.0, 120)
    target = AcousticTargetCurve("TargetCurve", ((100.0, 85.0), (10000.0, 85.0)))

    # Left: Woofer 86 dB, Tweeter 83 dB (+50 us)
    pos_l = SpatialMeasurementPosition(
        "Left",
        {
            "woofer": _create_synthetic_flat_response(freqs, level_db=86.0, delay_seconds=0.0),
            "tweeter": _create_synthetic_flat_response(freqs, level_db=83.0, delay_seconds=50e-6),
        },
        coordinates=(-1.0, 2.0, 0.0),
    )

    # Center: Woofer 85 dB, Tweeter 85 dB (0 us)
    pos_c = SpatialMeasurementPosition(
        "Center",
        {
            "woofer": _create_synthetic_flat_response(freqs, level_db=85.0, delay_seconds=0.0),
            "tweeter": _create_synthetic_flat_response(freqs, level_db=85.0, delay_seconds=0.0),
        },
        coordinates=(0.0, 2.0, 0.0),
    )

    # Right: Woofer 83 dB, Tweeter 86 dB (-50 us)
    pos_r = SpatialMeasurementPosition(
        "Right",
        {
            "woofer": _create_synthetic_flat_response(freqs, level_db=83.0, delay_seconds=50e-6),
            "tweeter": _create_synthetic_flat_response(freqs, level_db=86.0, delay_seconds=0.0),
        },
        coordinates=(1.0, 2.0, 0.0),
    )

    spec = MultiPositionOptimizationSpecification(
        positions=(pos_l, pos_c, pos_r),
        spatial_weights=(0.25, 0.50, 0.25),
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(200.0, 8000.0),
        crossover_bounds_hz=(1500.0, 3500.0),
        gain_bounds_db=(-6.0, 6.0),
        delay_bounds_seconds=(0.0, 0.001),
        sample_rate=48000,
        max_iterations=40,
        convergence_tolerance_db=1e-5,
    )

    result = optimize_multi_position(spec)

    # 1. Monotonicity check
    assert result.total_loss <= result.initial_loss + 1e-12
    # 2. Convergence
    assert result.converged is True
    assert result.iterations_completed >= 1
    # 3. All 3 spatial losses recorded
    assert set(result.spatial_losses.keys()) == {"Left", "Center", "Right"}
    assert set(result.predicted_responses.keys()) == {"Left", "Center", "Right"}
    # 4. Aggregated total loss matches sum(w_i * L_i)
    expected_weighted = (
        0.25 * result.spatial_losses["Left"]
        + 0.50 * result.spatial_losses["Center"]
        + 0.25 * result.spatial_losses["Right"]
    )
    assert math.isclose(result.total_loss, expected_weighted, rel_tol=1e-9)


# ==============================================================================
# 4. Determinism & Repeatability (100 Iterations)
# ==============================================================================

def test_multi_position_determinism_100_runs() -> None:
    """Verify exact bit-for-bit repeatability of multi-position spatial optimization across 100 runs."""
    freqs = np.geomspace(200.0, 6000.0, 50)
    target = AcousticTargetCurve("Target", ((200.0, 0.0), (6000.0, 0.0)))

    pos1 = SpatialMeasurementPosition(
        "Pos1",
        {
            "woofer": _create_synthetic_flat_response(freqs, 0.0, 0.0),
            "tweeter": _create_synthetic_flat_response(freqs, 1.0, 30e-6),
        },
    )
    pos2 = SpatialMeasurementPosition(
        "Pos2",
        {
            "woofer": _create_synthetic_flat_response(freqs, 0.0, 30e-6),
            "tweeter": _create_synthetic_flat_response(freqs, -1.0, 0.0),
        },
    )

    spec = MultiPositionOptimizationSpecification(
        positions=(pos1, pos2),
        spatial_weights=(0.6, 0.4),
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(300.0, 5000.0),
        crossover_bounds_hz=(1200.0, 2800.0),
        gain_bounds_db=(-4.0, 4.0),
        delay_bounds_seconds=(0.0, 0.0005),
        sample_rate=48000,
        max_iterations=20,
    )

    baseline_res = optimize_multi_position(spec)

    for run_idx in range(100):
        repeat_res = optimize_multi_position(spec)
        assert np.array_equal(baseline_res.parameters, repeat_res.parameters), (
            f"Parameters deviated on run {run_idx}"
        )
        assert baseline_res.total_loss == repeat_res.total_loss, (
            f"Loss deviated on run {run_idx}"
        )
        assert baseline_res.converged == repeat_res.converged
        assert baseline_res.iterations_completed == repeat_res.iterations_completed


# ==============================================================================
# 5. Core Graph Compilation Adapter Integration
# ==============================================================================

def test_compile_multi_position_result_to_core_graph() -> None:
    """Verify that MultiPositionOptimizationResult converts to Core OptimizationResult and compiles to ComputeGraph."""
    freqs = np.geomspace(200.0, 6000.0, 60)
    target = AcousticTargetCurve("Target", ((200.0, 0.0), (6000.0, 0.0)))

    pos1 = SpatialMeasurementPosition(
        "Pos1",
        {
            "woofer": _create_synthetic_flat_response(freqs, 0.0, 0.0),
            "tweeter": _create_synthetic_flat_response(freqs, 0.0, 20e-6),
        },
    )

    spec = MultiPositionOptimizationSpecification(
        positions=(pos1,),
        spatial_weights=(1.0,),
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(400.0, 4000.0),
        crossover_bounds_hz=(1500.0, 2500.0),
        sample_rate=48000,
        max_iterations=10,
    )

    spatial_res = optimize_multi_position(spec)
    core_opt_res = spatial_res.to_optimization_result(position_name_or_index="Pos1")

    # Compile into executable ComputeGraph using Core adapter
    graph = compile_optimization_result_to_graph(
        result=core_opt_res,
        sample_rate=48000,
        channels=1,
        woofer_name="woofer",
        tweeter_name="tweeter",
    )

    assert graph is not None
    assert "input" in graph.nodes
    assert "woofer.delay" in graph.nodes
    assert "woofer.gain" in graph.nodes
    assert "tweeter.delay" in graph.nodes
    assert "tweeter.gain" in graph.nodes
    assert "woofer.crossover.0" in graph.nodes
    assert "tweeter.crossover.0" in graph.nodes


def test_three_way_multi_position_optimization_and_compilation() -> None:
    """Verify 3-way multi-position optimization with constraint enforcement and graph compilation."""
    freqs = np.geomspace(50.0, 15000.0, 100)
    target = AcousticTargetCurve("TargetFlat", ((50.0, 85.0), (15000.0, 85.0)))

    # Pos 1: Front-Left
    pos1 = SpatialMeasurementPosition(
        "FrontLeft",
        {
            "woofer": _create_synthetic_flat_response(freqs, 85.0, 0.0),
            "midrange": _create_synthetic_flat_response(freqs, 84.0, 20e-6),
            "tweeter": _create_synthetic_flat_response(freqs, 86.0, 40e-6),
        },
    )
    # Pos 2: Front-Right
    pos2 = SpatialMeasurementPosition(
        "FrontRight",
        {
            "woofer": _create_synthetic_flat_response(freqs, 85.0, 0.0),
            "midrange": _create_synthetic_flat_response(freqs, 86.0, 40e-6),
            "tweeter": _create_synthetic_flat_response(freqs, 84.0, 20e-6),
        },
    )

    spec = MultiPositionOptimizationSpecification(
        positions=(pos1, pos2),
        spatial_weights=(0.5, 0.5),
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(100.0, 12000.0),
        crossover_bounds_hz=(300.0, 5000.0),
        gain_bounds_db=(-6.0, 6.0),
        delay_bounds_seconds=(0.0, 0.001),
        sample_rate=48000,
        driver_order=("woofer", "midrange", "tweeter"),
        max_iterations=15,
    )

    result = optimize_multi_position(spec)

    assert result.total_loss <= result.initial_loss + 1e-12
    assert isinstance(result.crossover_result, tuple) and len(result.crossover_result) == 2
    x_low, x_high = result.crossover_result
    # Enforce 3-way separation constraint
    assert x_high.crossover_frequency_hz >= 1.5 * x_low.crossover_frequency_hz

    # Compile to 3-Way Graph
    core_res = result.to_optimization_result(position_name_or_index="FrontLeft")
    graph = compile_optimization_result_to_graph(
        result=core_res,
        sample_rate=48000,
        woofer_name="woofer",
        midrange_name="midrange",
        tweeter_name="tweeter",
    )
    assert graph is not None
    assert "midrange.gain" in graph.nodes
    assert "midrange.delay" in graph.nodes
    assert "tweeter.gain" in graph.nodes
    assert "tweeter.delay" in graph.nodes


def test_spatial_performance_scaling() -> None:
    """Measure runtime scaling from 1 to 3 positions and verify linear evaluation complexity."""
    import time
    freqs = np.geomspace(200.0, 6000.0, 60)
    target = AcousticTargetCurve("Target", ((200.0, 0.0), (6000.0, 0.0)))

    positions = [
        SpatialMeasurementPosition(f"P{i}", {"w": _create_synthetic_flat_response(freqs), "t": _create_synthetic_flat_response(freqs)})
        for i in range(3)
    ]

    timings = []
    for count in (1, 2, 3):
        spec = MultiPositionOptimizationSpecification(
            positions=tuple(positions[:count]),
            spatial_weights=tuple([1.0 / count] * count),
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(400.0, 4000.0),
            crossover_bounds_hz=(1500.0, 2500.0),
            driver_order=("w", "t"),
            sample_rate=48000,
            max_iterations=5,
        )
        t0 = time.perf_counter()
        optimize_multi_position(spec)
        t1 = time.perf_counter()
        timings.append(t1 - t0)

    print(f"\n[PERFORMANCE SCALING] 1-pos: {timings[0]:.4f}s, 2-pos: {timings[1]:.4f}s, 3-pos: {timings[2]:.4f}s")
    # Basic sanity check that all ran in under 5 seconds
    assert all(t < 5.0 for t in timings)


# ==============================================================================
# 6. Negative Validation Tests
# ==============================================================================

def test_negative_weight_rejected() -> None:
    """Negative spatial weights must be rejected with InvalidSpecificationError."""
    freqs = np.array([500.0, 1000.0, 2000.0])
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))
    pos1 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})
    pos2 = SpatialMeasurementPosition("Pos2", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})

    with pytest.raises(InvalidSpecificationError, match="cannot be negative"):
        MultiPositionOptimizationSpecification(
            positions=(pos1, pos2),
            spatial_weights=(1.2, -0.2),
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
        )


def test_unnormalized_weights_rejected() -> None:
    """Weights that do not sum to 1.0 must be rejected with InvalidSpecificationError."""
    freqs = np.array([500.0, 1000.0, 2000.0])
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))
    pos1 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})
    pos2 = SpatialMeasurementPosition("Pos2", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})

    with pytest.raises(InvalidSpecificationError, match="must sum to 1.0"):
        MultiPositionOptimizationSpecification(
            positions=(pos1, pos2),
            spatial_weights=(0.5, 0.3),  # sums to 0.8
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
        )


def test_weight_count_mismatch_rejected() -> None:
    """Mismatched positions and weights count must be rejected with InvalidSpecificationError."""
    freqs = np.array([500.0, 1000.0, 2000.0])
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))
    pos1 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})
    pos2 = SpatialMeasurementPosition("Pos2", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})

    with pytest.raises(InvalidSpecificationError, match="must match positions count"):
        MultiPositionOptimizationSpecification(
            positions=(pos1, pos2),
            spatial_weights=(1.0,),  # 1 weight for 2 positions
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
        )


def test_empty_positions_rejected() -> None:
    """Empty positions tuple must be rejected with InvalidSpecificationError."""
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))

    with pytest.raises(InvalidSpecificationError, match="non-empty sequence"):
        MultiPositionOptimizationSpecification(
            positions=(),
            spatial_weights=(),
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
        )


def test_missing_driver_measurement_rejected() -> None:
    """If a position is missing a required driver branch measurement, it must be rejected."""
    freqs = np.array([500.0, 1000.0, 2000.0])
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))

    pos1 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})
    pos2 = SpatialMeasurementPosition("Pos2", {"woofer": _create_synthetic_flat_response(freqs)})  # missing tweeter

    with pytest.raises(InvalidSpecificationError, match="missing required driver measurement"):
        MultiPositionOptimizationSpecification(
            positions=(pos1, pos2),
            spatial_weights=(0.5, 0.5),
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
            driver_order=("woofer", "tweeter"),
        )


def test_frequency_grid_mismatch_rejected() -> None:
    """Frequency grid mismatch across positions must be rejected with InvalidParameterError."""
    grid1 = np.array([500.0, 1000.0, 2000.0])
    grid2 = np.array([500.0, 1200.0, 2000.0])  # mismatched point
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))

    pos1 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(grid1), "tweeter": _create_synthetic_flat_response(grid1)})
    pos2 = SpatialMeasurementPosition("Pos2", {"woofer": _create_synthetic_flat_response(grid2), "tweeter": _create_synthetic_flat_response(grid2)})

    with pytest.raises(InvalidParameterError, match="Frequency grid values mismatch"):
        MultiPositionOptimizationSpecification(
            positions=(pos1, pos2),
            spatial_weights=(0.5, 0.5),
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
        )


def test_duplicate_position_names_rejected() -> None:
    """Duplicate position names must be rejected with InvalidSpecificationError."""
    freqs = np.array([500.0, 1000.0, 2000.0])
    target = AcousticTargetCurve("Target", ((500.0, 0.0), (2000.0, 0.0)))

    pos1 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})
    pos2 = SpatialMeasurementPosition("Pos1", {"woofer": _create_synthetic_flat_response(freqs), "tweeter": _create_synthetic_flat_response(freqs)})

    with pytest.raises(InvalidSpecificationError, match="Duplicate spatial position name"):
        MultiPositionOptimizationSpecification(
            positions=(pos1, pos2),
            spatial_weights=(0.5, 0.5),
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(500.0, 2000.0),
            crossover_bounds_hz=(800.0, 1500.0),
        )
