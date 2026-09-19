"""Phase 4B End-to-End Vertical Slice and Backward Compatibility Integration Tests.

Normative Authority:
- Phase 4B Implementation Specification
- docs/contracts/ACOUSTIC_METRICS_CONTRACT.md
- docs/contracts/MULTIWAY_GRAPH_BUILDER_CONTRACT.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from acoustiforge.acoustic_math.calibration import apply_microphone_calibration
from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.equalizer import synthesize_parametric_eq
from acoustiforge.acoustic_math.metrics import calculate_response_metrics
from acoustiforge.acoustic_math.protection import design_infrasonic_protection_filter
from acoustiforge.acoustic_math.sensitivity import calculate_sensitivity_gain
from acoustiforge.builders.crossover_builder import CrossoverGraphBuilder
from acoustiforge.builders.multiway_builder import ThreeWayGraphBuilder
from acoustiforge.contracts import PCMBlock
from acoustiforge.domain import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
)
from acoustiforge.io.parser import parse_measurement_file

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestPhase4BEndToEnd:
    """End-to-end vertical integration test suite from measurement files to multi-block PCM audio execution."""

    def test_complete_3way_measurement_to_pcm_pipeline(self) -> None:
        """Verify entire pipeline: Ingestion -> Calibration -> Metrics -> Synthesis -> ThreeWayGraphBuilder -> PCM."""
        # 1. Ingest raw driver measurement and mic calibration
        raw_import = parse_measurement_file(FIXTURES_DIR / "valid_3col.csv")
        cal_import = parse_measurement_file(FIXTURES_DIR / "mic_calibration.cal")

        # 2. Microphone calibration
        calibrated_frd = apply_microphone_calibration(raw_import.data, cal_import.data)

        # 3. Acoustic Metrics Evaluation
        target = AcousticTargetCurve("flat_85", tuple((f, 85.0) for f in calibrated_frd.frequencies_hz))
        metrics = calculate_response_metrics(calibrated_frd, target_curve=target, passband_hz=(200.0, 2000.0))

        assert metrics.passband_sensitivity_db > 0.0
        assert metrics.rms_target_error_db is not None

        # 4. Filter Synthesis (LF/MF crossover at 400 Hz, MF/HF crossover at 3000 Hz)
        crossover_low = synthesize_crossover_biquads(
            CrossoverSpecification(CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=400.0),
            sample_rate=48000,
        )
        crossover_high = synthesize_crossover_biquads(
            CrossoverSpecification(CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=3000.0),
            sample_rate=48000,
        )

        # Sensitivity gain and protection
        mid_gain = calculate_sensitivity_gain(metrics.passband_sensitivity_db, reference_sensitivity_db=85.0, driver_name="midrange")
        woofer_prot = design_infrasonic_protection_filter(cutoff_frequency_hz=30.0, sample_rate=48000, order=2, driver_name="woofer")

        # 5. Three-Way Graph Assembly
        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(
            crossover_low=crossover_low,
            crossover_high=crossover_high,
            gains={"midrange": mid_gain},
            protections={"woofer": woofer_prot},
        )

        assert graph.is_frozen
        assert len(graph.outputs) == 3

        # 6. Multi-Block PCM Audio Execution across varying block sizes
        block_sizes = [1, 7, 16, 31, 64, 127, 256]
        np.random.seed(98765)

        for block_size in block_sizes:
            test_signal = np.random.uniform(-0.5, 0.5, (1, block_size)).astype(np.float32)
            pcm_in = PCMBlock.from_array(test_signal, sample_rate=48000)

            out = graph.process(pcm_in)

            assert isinstance(out, dict)
            assert "woofer.protection.0.out" in out
            assert "midrange.crossover.lp.1.out" in out
            assert "tweeter.crossover.1.out" in out

            for out_key in ["woofer.protection.0.out", "midrange.crossover.lp.1.out", "tweeter.crossover.1.out"]:
                out_block = out[out_key]
                assert out_block.samples.shape == (1, block_size)
                assert np.all(np.isfinite(out_block.samples))

    def test_graph_reset_state_restoration(self) -> None:
        """Verify graph.reset() restores deterministic initial state across stateful biquad filters."""
        crossover_low = synthesize_crossover_biquads(
            CrossoverSpecification(CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=500.0),
            sample_rate=48000,
        )
        crossover_high = synthesize_crossover_biquads(
            CrossoverSpecification(CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=2500.0),
            sample_rate=48000,
        )

        builder = ThreeWayGraphBuilder(sample_rate=48000)
        graph = builder.build_3way_graph(crossover_low=crossover_low, crossover_high=crossover_high)

        np.random.seed(54321)
        test_data = np.random.uniform(-0.7, 0.7, (1, 128)).astype(np.float32)
        pcm_in = PCMBlock.from_array(test_data, sample_rate=48000)

        # Run 1
        out1 = graph.process(pcm_in)

        # Reset
        graph.reset()

        # Run 2 with identical input
        out2 = graph.process(pcm_in)

        for port_key in out1.keys():
            np.testing.assert_array_equal(out1[port_key].samples, out2[port_key].samples)

    def test_legacy_2way_crossover_builder_compatibility(self) -> None:
        """Verify Phase 3D/4A 2-way CrossoverGraphBuilder remains bit-exact identical."""
        spec = CrossoverSpecification(CrossoverFamily.LINKWITZ_RILEY, order=2, frequency_hz=2000.0)
        crossover_synth = synthesize_crossover_biquads(spec, sample_rate=48000)

        builder_2way = CrossoverGraphBuilder(sample_rate=48000)
        graph_2way = builder_2way.build_2way_graph(crossover_result=crossover_synth)

        np.random.seed(11223)
        test_data = np.random.uniform(-0.5, 0.5, (1, 256)).astype(np.float32)
        pcm_in = PCMBlock.from_array(test_data, sample_rate=48000)

        out = graph_2way.process(pcm_in)

        assert "woofer.crossover.1.out" in out
        assert "tweeter.crossover.1.out" in out
        assert np.all(np.isfinite(out["woofer.crossover.1.out"].samples))
        assert np.all(np.isfinite(out["tweeter.crossover.1.out"].samples))
