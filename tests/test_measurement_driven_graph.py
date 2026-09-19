"""Tests for Measurement-Driven EQ Integration and Backward Compatibility.

Normative Authority:
- Phase 4A Implementation Specification
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
- docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md
- docs/contracts/MICROPHONE_CALIBRATION_CONTRACT.md
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from acoustiforge.acoustic_math.calibration import (
    CalibrationBoundaryPolicy,
    apply_microphone_calibration,
)
from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.equalizer import synthesize_parametric_eq
from acoustiforge.builders.crossover_builder import CrossoverGraphBuilder
from acoustiforge.contracts import PCMBlock
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
    FrequencyResponseData,
)
from acoustiforge.io.parser import parse_measurement_file

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestMeasurementDrivenGraph:
    """Test suite verifying measurement ingestion -> calibration -> EQ -> graph builder -> PCM execution."""

    @pytest.fixture
    def crossover_synth(self):
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=2,
            frequency_hz=2000.0,
        )
        return synthesize_crossover_biquads(spec, sample_rate=48000)

    def test_backward_compatibility_when_equalizers_none(self, crossover_synth) -> None:
        """Verify equalizers=None preserves Phase 3D topology, schedule, latency, and bit-exact PCM."""
        builder = CrossoverGraphBuilder(sample_rate=48000)

        # 1. Build graph with equalizers omitted (default)
        graph_default = builder.build_2way_graph(crossover_result=crossover_synth)

        # 2. Build graph with explicit equalizers=None
        graph_explicit = builder.build_2way_graph(
            crossover_result=crossover_synth,
            equalizers=None,
        )

        # Verify exact node match
        assert set(graph_default.nodes.keys()) == set(graph_explicit.nodes.keys())
        assert graph_default.schedule == graph_explicit.schedule

        # Verify bit-exact PCM execution across multiple blocks
        np.random.seed(42)
        test_audio = np.random.uniform(-0.5, 0.5, (1, 512)).astype(np.float32)
        pcm_in = PCMBlock.from_array(test_audio, sample_rate=48000)

        out_def = graph_default.process(pcm_in)
        out_exp = graph_explicit.process(pcm_in)

        np.testing.assert_array_equal(out_def["woofer.crossover.1.out"].samples, out_exp["woofer.crossover.1.out"].samples)
        np.testing.assert_array_equal(out_def["tweeter.crossover.1.out"].samples, out_exp["tweeter.crossover.1.out"].samples)

    def test_eq_graph_insertion_topology_and_node_ids(self, crossover_synth) -> None:
        """Verify deterministic node IDs and topological ordering when EQ is applied."""
        freqs = np.geomspace(20.0, 20000.0, 100)
        # Transducer has a 6 dB resonance peak at 1000 Hz
        mags = 85.0 + 6.0 * np.exp(-0.5 * ((np.log(freqs) - np.log(1000.0)) / 0.2) ** 2)
        measured_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        points = tuple((float(f), 85.0) for f in freqs)
        flat_target = AcousticTargetCurve(
            name="flat_target",
            points=points,
        )

        budget = EqualizerBudget(max_bands=2, max_boost_db=3.0, max_cut_db=12.0)

        eq_woofer = synthesize_parametric_eq(
            measurement=measured_frd,
            budget=budget,
            sample_rate=48000,
            target_curve=flat_target,
        )

        assert len(eq_woofer.sections) > 0

        builder = CrossoverGraphBuilder(sample_rate=48000)
        graph = builder.build_2way_graph(
            crossover_result=crossover_synth,
            equalizers={"woofer": eq_woofer},
        )

        # Verify woofer EQ node exists with expected ID
        assert "woofer.eq.0" in graph.nodes
        assert "tweeter.eq.0" not in graph.nodes  # tweeter had no EQ

        # Verify execution order in schedule: input -> woofer.delay -> woofer.gain -> woofer.eq.0 -> woofer.crossover.0
        schedule = list(graph.schedule)
        idx_input = schedule.index("input")
        idx_delay = schedule.index("woofer.delay")
        idx_gain = schedule.index("woofer.gain")
        idx_eq = schedule.index("woofer.eq.0")
        idx_xo = schedule.index("woofer.crossover.0")

        assert idx_input < idx_delay < idx_gain < idx_eq < idx_xo

    def test_sample_rate_mismatch_rejection(self, crossover_synth) -> None:
        """Verify sample rate mismatch between builder and EQ synthesis result is rejected."""
        freqs = np.geomspace(20.0, 20000.0, 50)
        mags = np.full_like(freqs, 85.0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)
        points = tuple((float(f), 85.0) for f in freqs)
        target = AcousticTargetCurve("flat", points)
        budget = EqualizerBudget(max_bands=1)

        # Synthesize EQ at 44100 Hz
        eq_44k = synthesize_parametric_eq(
            measurement=frd,
            budget=budget,
            sample_rate=44100,
            target_curve=target,
        )

        # Builder configured for 48000 Hz
        builder = CrossoverGraphBuilder(sample_rate=48000)

        with pytest.raises(InvalidParameterError, match="sample rate"):
            builder.build_2way_graph(
                crossover_result=crossover_synth,
                equalizers={"woofer": eq_44k},
            )

    def test_end_to_end_vertical_slice(self) -> None:
        """Complete vertical slice test from raw measurement file to multi-block PCM execution."""
        # 1. File ingestion
        raw_import = parse_measurement_file(FIXTURES_DIR / "valid_3col.csv")
        assert raw_import.source_format == "csv"
        assert len(raw_import.header_comments) > 0

        cal_import = parse_measurement_file(FIXTURES_DIR / "mic_calibration.cal")
        assert cal_import.source_format == "cal"

        # 2. Microphone calibration
        calibrated_frd = apply_microphone_calibration(
            raw_measurement=raw_import.data,
            calibration_data=cal_import.data,
            boundary_policy=CalibrationBoundaryPolicy.CLAMP,
        )

        # 3. Acoustic Target Evaluation & EQ Synthesis
        points = tuple((float(f), 85.0) for f in calibrated_frd.frequencies_hz)
        target = AcousticTargetCurve(
            name="flat_85db",
            points=points,
        )
        budget = EqualizerBudget(max_bands=3, max_boost_db=4.0, max_cut_db=12.0)

        woofer_eq = synthesize_parametric_eq(
            measurement=calibrated_frd,
            budget=budget,
            sample_rate=48000,
            target_curve=target,
        )

        # 4. Crossover filter synthesis
        crossover_spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=1800.0,
        )
        crossover_synth = synthesize_crossover_biquads(crossover_spec, sample_rate=48000)

        # 5. Graph construction
        builder = CrossoverGraphBuilder(sample_rate=48000)
        graph = builder.build_2way_graph(
            crossover_result=crossover_synth,
            equalizers={"woofer": woofer_eq},
        )

        assert graph.is_frozen
        assert "woofer.eq.0" in graph.nodes

        # 6. Multi-block PCM Execution
        np.random.seed(12345)
        for block_idx in range(5):
            input_signal = np.random.uniform(-0.8, 0.8, (1, 256)).astype(np.float32)
            pcm_block = PCMBlock.from_array(input_signal, sample_rate=48000)

            out = graph.process(pcm_block)

            assert "woofer.crossover.1.out" in out
            assert "tweeter.crossover.1.out" in out

            w_data = out["woofer.crossover.1.out"].samples
            t_data = out["tweeter.crossover.1.out"].samples

            assert w_data.shape == (1, 256)
            assert t_data.shape == (1, 256)
            assert np.all(np.isfinite(w_data))
            assert np.all(np.isfinite(t_data))
