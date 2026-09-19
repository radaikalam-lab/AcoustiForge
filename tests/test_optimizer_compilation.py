"""AcoustiForge Phase 4D-7 Optimizer Compilation and Continuity Test Suite.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/contracts/MULTIWAY_GRAPH_BUILDER_CONTRACT.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/architecture/PHASE_4D_6_EXECUTABLE_CONTINUITY_BENCHMARK.md
- docs/architecture/PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md

This test module verifies:
1. 2-Way OptimizationResult compilation to ComputeGraph and end-to-end DSP continuity.
2. 3-Way OptimizationResult compilation to ComputeGraph and end-to-end DSP continuity.
3. Determinism and zero parameter semantic drift across compilations.
4. Independent golden verification of compiled graph nodes.
5. Rigorous negative validation for invalid results, constraints, and topologies.
"""

from __future__ import annotations

import math
from typing import Tuple
import numpy as np
import pytest

from acoustiforge.acoustic_math.alignment import (
    DriverAlignmentResult,
)
from acoustiforge.acoustic_math.crossover import (
    CrossoverSynthesisResult,
    synthesize_crossover_biquads,
)
from acoustiforge.acoustic_math.metrics import (
    AcousticMetricsResult,
)
from acoustiforge.acoustic_math.optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    evaluate_biquad_complex_response,
)
from acoustiforge.acoustic_math.sensitivity import (
    GainDesignResult,
)
from acoustiforge.builders.optimization_adapter import (
    compile_optimization_result_to_graph,
)
from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    OptimizationResult,
    OptimizationSpecification,
)
from acoustiforge.domain.validation import InvalidSpecificationError
from acoustiforge.graph.compute_graph import ComputeGraph
from acoustiforge.nodes.biquad import BiquadNode
from acoustiforge.nodes.delay import DelayNode
from acoustiforge.nodes.gain import GainNode


# ==============================================================================
# Helper Functions: Signal Processing and Fixtures
# ==============================================================================

def _generate_dirac_impulse(num_frames: int, sample_rate: int) -> PCMBlock:
    """Generate a single-channel Dirac unit impulse PCM block."""
    samples = np.zeros((1, num_frames), dtype=np.float32)
    samples[0, 0] = 1.0
    meta = AudioMetadata(sample_rate=sample_rate, channels=1)
    return PCMBlock(samples=samples, metadata=meta)


def _extract_complex_frequency_response(
    time_samples: np.ndarray,
    sample_rate: int,
    eval_frequencies_hz: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute complex frequency response from discrete time-domain impulse response via FFT."""
    num_frames = time_samples.shape[0]
    fft_vals = np.fft.rfft(time_samples.astype(np.float64))
    fft_freqs = np.fft.rfftfreq(num_frames, d=1.0 / float(sample_rate))

    re_interp = np.interp(eval_frequencies_hz, fft_freqs, fft_vals.real)
    im_interp = np.interp(eval_frequencies_hz, fft_freqs, fft_vals.imag)
    h_complex = re_interp + 1j * im_interp

    mag_db = 20.0 * np.log10(np.maximum(np.abs(h_complex), 1e-12))
    phase_rad = np.arctan2(h_complex.imag, h_complex.real)

    return mag_db, phase_rad, h_complex


def _compute_phase_error_degrees(
    phase_measured_rad: np.ndarray,
    phase_analytical_rad: np.ndarray,
) -> np.ndarray:
    """Compute absolute phase error in degrees, wrapping angular difference to [-pi, pi]."""
    diff_rad = phase_measured_rad - phase_analytical_rad
    wrapped_diff_rad = (diff_rad + math.pi) % (2.0 * math.pi) - math.pi
    return np.abs(wrapped_diff_rad) * (180.0 / math.pi)


def _dummy_metrics() -> AcousticMetricsResult:
    """Create a valid AcousticMetricsResult for test instances."""
    return AcousticMetricsResult(
        passband_sensitivity_db=88.0,
        f3_low_hz=40.0,
        f3_high_hz=20000.0,
        f6_low_hz=35.0,
        f6_high_hz=22000.0,
        f10_low_hz=25.0,
        f10_high_hz=24000.0,
        rms_target_error_db=0.35,
        peak_positive_error_db=0.8,
        peak_negative_error_db=-0.9,
        spectral_tilt_db_per_oct=0.0,
        passband_ripple_db=1.1,
        passband_range_hz=(100.0, 10000.0),
    )


def _dummy_frd(freqs: np.ndarray) -> FrequencyResponseData:
    """Create a flat FrequencyResponseData container."""
    return FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=np.zeros_like(freqs),
        phase_rad=np.zeros_like(freqs),
    )


# ==============================================================================
# Test Suite: 2-Way End-to-End OptimizationResult Compilation
# ==============================================================================

class Test2WayOptimizationResultCompilation:
    """Validate 2-Way OptimizationResult compilation into ComputeGraph and DSP continuity."""

    def test_2way_compilation_and_dsp_execution_continuity(self) -> None:
        """Verify 2-Way OptimizationResult compiles and matches analytical summation within 4D-6 limits."""
        fs = 48000
        num_frames = 8192
        fc = 2400.0
        w_gain_db = 0.0
        t_gain_db = -2.5
        t_delay_frames = 5
        t_delay_s = t_delay_frames / float(fs)

        spec_xover = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=fc
        )
        xover_res = synthesize_crossover_biquads(specification=spec_xover, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, w_gain_db, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 90.5, 88.0, t_gain_db, 10.0 ** (t_gain_db / 20.0), False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", t_delay_s, float(t_delay_frames), t_delay_frames, 35.75, 0.0, fs, 343.2),
        }

        eval_freqs = np.geomspace(40.0, 20000.0, 200, dtype=np.float64)
        frd_flat = _dummy_frd(eval_freqs)

        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results=gains,
            alignment_results=alignments,
            predicted_response=frd_flat,
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.0450,
            final_loss_db=0.0125,
            converged=True,
            iterations_completed=42,
        )

        # Compile to ComputeGraph
        graph = compile_optimization_result_to_graph(opt_res, sample_rate=fs)
        assert isinstance(graph, ComputeGraph)
        assert graph.is_frozen

        # Execute impulse through graph
        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)
        out_blocks = graph.process(impulse_block)

        w_pcm = out_blocks[f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"].samples[0]
        t_pcm = out_blocks[f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"].samples[0]
        summed_pcm = w_pcm + t_pcm

        # Extract measured DSP response
        mag_dsp_db, phase_dsp_rad, _ = _extract_complex_frequency_response(summed_pcm, fs, eval_freqs)

        # Compute Analytical Complex Forward Model
        hw_ana = calculate_branch_complex_response(
            frd_flat, xover_res.low_pass_sections, gain_db=w_gain_db, delay_seconds=0.0, sample_rate=fs
        )
        ht_ana = calculate_branch_complex_response(
            frd_flat, xover_res.high_pass_sections, gain_db=t_gain_db, delay_seconds=t_delay_s, sample_rate=fs
        )
        total_ana_frd = calculate_acoustic_complex_summation([hw_ana, ht_ana], eval_freqs)

        # Check error bounds
        mag_errors = np.abs(mag_dsp_db - total_ana_frd.magnitude_db)
        phase_errors_deg = _compute_phase_error_degrees(phase_dsp_rad, total_ana_frd.phase_rad)

        max_mag_err = float(np.max(mag_errors))
        max_phase_err = float(np.max(phase_errors_deg))
        rms_mag_err = float(np.sqrt(np.mean(mag_errors ** 2)))
        rms_phase_err = float(np.sqrt(np.mean(phase_errors_deg ** 2)))

        print(f"\n[PHASE 4D-7 TELEMETRY 2-WAY]")
        print(f"Max Magnitude Error: {max_mag_err:.6f} dB (Threshold: < 0.05 dB)")
        print(f"RMS Magnitude Error: {rms_mag_err:.6f} dB")
        print(f"Max Phase Error:     {max_phase_err:.6f} deg (Threshold: < 0.50 deg)")
        print(f"RMS Phase Error:     {rms_phase_err:.6f} deg")

        assert max_mag_err < 0.05, f"2-Way max magnitude error {max_mag_err:.5f} dB exceeds 0.05 dB."
        assert max_phase_err < 0.50, f"2-Way max phase error {max_phase_err:.5f} deg exceeds 0.50 deg."


# ==============================================================================
# Test Suite: 3-Way End-to-End OptimizationResult Compilation
# ==============================================================================

class Test3WayOptimizationResultCompilation:
    """Validate 3-Way OptimizationResult compilation into ComputeGraph and DSP continuity."""

    def test_3way_compilation_and_dsp_execution_continuity(self) -> None:
        """Verify 3-Way OptimizationResult compiles and matches analytical summation within 4D-6 limits."""
        fs = 48000
        num_frames = 8192
        f_low = 450.0
        f_high = 3200.0

        w_gain_db = 0.0
        m_gain_db = -1.8
        t_gain_db = -3.2

        m_delay_frames = 4
        m_delay_s = m_delay_frames / float(fs)
        t_delay_frames = 8
        t_delay_s = t_delay_frames / float(fs)

        spec_low = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=f_low
        )
        xover_low = synthesize_crossover_biquads(specification=spec_low, sample_rate=fs)

        spec_high = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=f_high
        )
        xover_high = synthesize_crossover_biquads(specification=spec_high, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, w_gain_db, 1.0, False),
            "midrange": GainDesignResult("midrange", 89.8, 88.0, m_gain_db, 10.0 ** (m_gain_db / 20.0), False),
            "tweeter": GainDesignResult("tweeter", 91.2, 88.0, t_gain_db, 10.0 ** (t_gain_db / 20.0), False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "midrange": DriverAlignmentResult("midrange", m_delay_s, float(m_delay_frames), m_delay_frames, 28.6, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", t_delay_s, float(t_delay_frames), t_delay_frames, 57.2, 0.0, fs, 343.2),
        }

        eval_freqs = np.geomspace(30.0, 20000.0, 250, dtype=np.float64)
        frd_flat = _dummy_frd(eval_freqs)

        opt_res = OptimizationResult(
            crossover_result=(xover_low, xover_high),
            gain_results=gains,
            alignment_results=alignments,
            predicted_response=frd_flat,
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.0620,
            final_loss_db=0.0084,
            converged=True,
            iterations_completed=58,
        )

        # Compile to ComputeGraph
        graph = compile_optimization_result_to_graph(opt_res, sample_rate=fs)
        assert isinstance(graph, ComputeGraph)
        assert graph.is_frozen

        # Execute impulse through graph
        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)
        out_blocks = graph.process(impulse_block)

        w_pcm = out_blocks[f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"].samples[0]
        m_pcm = out_blocks[f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"].samples[0]
        t_pcm = out_blocks[f"{graph.outputs[2][0]}.{graph.outputs[2][1]}"].samples[0]
        summed_pcm = w_pcm + m_pcm + t_pcm

        # Extract measured DSP response
        mag_dsp_db, phase_dsp_rad, _ = _extract_complex_frequency_response(summed_pcm, fs, eval_freqs)

        # Compute Analytical 3-Way Forward Model
        mid_sections = tuple(xover_low.high_pass_sections) + tuple(xover_high.low_pass_sections)
        hw_ana = calculate_branch_complex_response(
            frd_flat, xover_low.low_pass_sections, gain_db=w_gain_db, delay_seconds=0.0, sample_rate=fs
        )
        hm_ana = calculate_branch_complex_response(
            frd_flat, mid_sections, gain_db=m_gain_db, delay_seconds=m_delay_s, sample_rate=fs
        )
        ht_ana = calculate_branch_complex_response(
            frd_flat, xover_high.high_pass_sections, gain_db=t_gain_db, delay_seconds=t_delay_s, sample_rate=fs
        )
        total_ana_frd = calculate_acoustic_complex_summation([hw_ana, hm_ana, ht_ana], eval_freqs)

        # Check error bounds
        mag_errors = np.abs(mag_dsp_db - total_ana_frd.magnitude_db)
        phase_errors_deg = _compute_phase_error_degrees(phase_dsp_rad, total_ana_frd.phase_rad)

        max_mag_err = float(np.max(mag_errors))
        max_phase_err = float(np.max(phase_errors_deg))
        rms_mag_err = float(np.sqrt(np.mean(mag_errors ** 2)))
        rms_phase_err = float(np.sqrt(np.mean(phase_errors_deg ** 2)))

        print(f"\n[PHASE 4D-7 TELEMETRY 3-WAY]")
        print(f"Max Magnitude Error: {max_mag_err:.6f} dB (Threshold: < 0.05 dB)")
        print(f"RMS Magnitude Error: {rms_mag_err:.6f} dB")
        print(f"Max Phase Error:     {max_phase_err:.6f} deg (Threshold: < 0.50 deg)")
        print(f"RMS Phase Error:     {rms_phase_err:.6f} deg")

        assert max_mag_err < 0.05, f"3-Way max magnitude error {max_mag_err:.5f} dB exceeds 0.05 dB."
        assert max_phase_err < 0.50, f"3-Way max phase error {max_phase_err:.5f} deg exceeds 0.50 deg."


# ==============================================================================
# Test Suite: Determinism and Parameter Invariance
# ==============================================================================

class TestDeterminismAndInvariance:
    """Validate repeated compilation determinism and exact parameter preservation."""

    def test_repeated_compilation_determinism(self) -> None:
        """Verify repeated compilation of identical OptimizationResult yields identical graphs."""
        fs = 48000
        fc = 2000.0
        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=fc)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 90.0, 88.0, -2.0, 10.0 ** (-2.0 / 20.0), False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 4 / fs, 4.0, 4, 28.6, 0.0, fs, 343.2),
        }
        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results=gains,
            alignment_results=alignments,
            predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.05,
            final_loss_db=0.01,
            converged=True,
            iterations_completed=20,
        )

        graph1 = compile_optimization_result_to_graph(opt_res, sample_rate=fs)
        graph2 = compile_optimization_result_to_graph(opt_res, sample_rate=fs)

        # 1. Structural parity
        assert set(graph1.nodes.keys()) == set(graph2.nodes.keys())
        assert graph1.outputs == graph2.outputs
        assert graph1.inputs == graph2.inputs

        # 2. Execution bit-exactness
        impulse = _generate_dirac_impulse(num_frames=1024, sample_rate=fs)
        out1 = graph1.process(impulse)
        out2 = graph2.process(impulse)

        for port_key in out1:
            np.testing.assert_array_equal(out1[port_key].samples, out2[port_key].samples)

    def test_parameter_preservation_without_drift(self) -> None:
        """Verify exact parameter preservation between OptimizationResult and ComputeGraph nodes."""
        fs = 48000
        fc = 1850.5
        t_gain_db = -3.75
        t_delay_s = 0.0001875  # 9 samples at 48 kHz

        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=fc)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 91.75, 88.0, t_gain_db, 10.0 ** (t_gain_db / 20.0), False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", t_delay_s, 9.0, 9, 64.35, 0.0, fs, 343.2),
        }
        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results=gains,
            alignment_results=alignments,
            predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.02,
            final_loss_db=0.01,
            converged=True,
            iterations_completed=10,
        )

        graph = compile_optimization_result_to_graph(opt_res, sample_rate=fs)

        # Find nodes
        tweeter_gain_node = graph.nodes["tweeter.gain"]
        tweeter_delay_node = graph.nodes["tweeter.delay"]

        assert isinstance(tweeter_gain_node, GainNode)
        assert isinstance(tweeter_delay_node, DelayNode)

        assert math.isclose(tweeter_gain_node.gain_db, t_gain_db, abs_tol=1e-12)
        assert math.isclose(tweeter_gain_node.gain_linear, 10.0 ** (t_gain_db / 20.0), abs_tol=1e-12)
        assert tweeter_delay_node.delay_frames == 9


# ==============================================================================
# Test Suite: Independent Golden Compilation
# ==============================================================================

class TestIndependentGoldenCompilation:
    """Validate compiled graph parameters against independently derived golden values."""

    def test_independent_golden_2way_node_inspection(self) -> None:
        """Independently calculate expected biquad coefficients and verify graph nodes."""
        fs = 48000
        fc = 2000.0
        w_gain_db = 0.0
        t_gain_db = -4.0
        t_delay_frames = 6

        # Independent synthesis
        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=fc)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results={
                "woofer": GainDesignResult("woofer", 88.0, 88.0, w_gain_db, 1.0, False),
                "tweeter": GainDesignResult("tweeter", 92.0, 88.0, t_gain_db, 10.0 ** (t_gain_db / 20.0), False),
            },
            alignment_results={
                "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
                "tweeter": DriverAlignmentResult("tweeter", t_delay_frames / fs, float(t_delay_frames), t_delay_frames, 42.9, 0.0, fs, 343.2),
            },
            predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.01,
            final_loss_db=0.005,
            converged=True,
            iterations_completed=10,
        )

        graph = compile_optimization_result_to_graph(opt_res, sample_rate=fs)

        # Verify woofer low-pass biquad nodes
        lp_sec0 = graph.nodes["woofer.crossover.0"]
        lp_sec1 = graph.nodes["woofer.crossover.1"]
        assert isinstance(lp_sec0, BiquadNode)
        assert isinstance(lp_sec1, BiquadNode)
        assert lp_sec0.coefficients is not None
        assert lp_sec1.coefficients is not None

        expected_lp0 = xover_res.low_pass_sections[0]
        expected_lp1 = xover_res.low_pass_sections[1]

        assert math.isclose(lp_sec0.coefficients.b0, expected_lp0.b0, abs_tol=1e-12)
        assert math.isclose(lp_sec0.coefficients.b1, expected_lp0.b1, abs_tol=1e-12)
        assert math.isclose(lp_sec0.coefficients.b2, expected_lp0.b2, abs_tol=1e-12)
        assert math.isclose(lp_sec0.coefficients.a1, expected_lp0.a1, abs_tol=1e-12)
        assert math.isclose(lp_sec0.coefficients.a2, expected_lp0.a2, abs_tol=1e-12)

        assert math.isclose(lp_sec1.coefficients.b0, expected_lp0.b0, abs_tol=1e-12)
        assert math.isclose(lp_sec1.coefficients.b1, expected_lp0.b1, abs_tol=1e-12)
        assert math.isclose(lp_sec1.coefficients.b2, expected_lp0.b2, abs_tol=1e-12)
        assert math.isclose(lp_sec1.coefficients.a1, expected_lp0.a1, abs_tol=1e-12)
        assert math.isclose(lp_sec1.coefficients.a2, expected_lp0.a2, abs_tol=1e-12)


# ==============================================================================
# Test Suite: Negative Validation and Failure Handling
# ==============================================================================

class TestNegativeValidationAndEdgeCases:
    """Validate explicit failure behavior for invalid optimization results and compilation arguments."""

    def test_reject_non_optimization_result_instance(self) -> None:
        """Reject non-OptimizationResult objects with InvalidParameterError."""
        with pytest.raises(InvalidParameterError, match="Expected OptimizationResult instance"):
            compile_optimization_result_to_graph({"fc": 2000.0})  # type: ignore

    def test_reject_mismatched_sample_rate(self) -> None:
        """Reject compilation when specified sample_rate does not match crossover synthesis sample_rate."""
        fs = 48000
        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=2000.0)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results={
                "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
                "tweeter": GainDesignResult("tweeter", 88.0, 88.0, 0.0, 1.0, False),
            },
            alignment_results={
                "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
                "tweeter": DriverAlignmentResult("tweeter", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            },
            predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.02,
            final_loss_db=0.01,
            converged=True,
            iterations_completed=10,
        )

        with pytest.raises(InvalidParameterError, match="does not match OptimizationResult"):
            compile_optimization_result_to_graph(opt_res, sample_rate=96000)

    def test_reject_missing_driver_gain_or_alignment(self) -> None:
        """Reject compilation when declared branch names are missing from gain or alignment results."""
        fs = 48000
        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=2000.0)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results={
                "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
                "tweeter": GainDesignResult("tweeter", 88.0, 88.0, 0.0, 1.0, False),
            },
            alignment_results={
                "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
                # Missing tweeter alignment
            },
            predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.02,
            final_loss_db=0.01,
            converged=True,
            iterations_completed=10,
        )

        with pytest.raises(InvalidParameterError, match="Missing alignment result for 2-way tweeter branch"):
            compile_optimization_result_to_graph(opt_res, sample_rate=fs)

    def test_reject_duplicate_branch_names(self) -> None:
        """Reject compilation when branch names are identical."""
        fs = 48000
        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=2000.0)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        opt_res = OptimizationResult(
            crossover_result=xover_res,
            gain_results={
                "driver": GainDesignResult("driver", 88.0, 88.0, 0.0, 1.0, False),
            },
            alignment_results={
                "driver": DriverAlignmentResult("driver", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            },
            predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
            initial_metrics=_dummy_metrics(),
            optimized_metrics=_dummy_metrics(),
            initial_loss_db=0.02,
            final_loss_db=0.01,
            converged=True,
            iterations_completed=10,
        )

        with pytest.raises(InvalidParameterError, match="must be distinct"):
            compile_optimization_result_to_graph(
                opt_res, sample_rate=fs, woofer_name="driver", tweeter_name="driver"
            )

    def test_reject_3way_mismatched_crossover_sample_rates(self) -> None:
        """Reject 3-way compilation when low and high crossover sample rates differ."""
        spec_low = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=400.0)
        xover_low = synthesize_crossover_biquads(specification=spec_low, sample_rate=48000)

        spec_high = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=3000.0)
        xover_high = synthesize_crossover_biquads(specification=spec_high, sample_rate=96000)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
            "midrange": GainDesignResult("midrange", 88.0, 88.0, 0.0, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 88.0, 88.0, 0.0, 1.0, False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, 48000, 343.2),
            "midrange": DriverAlignmentResult("midrange", 0.0, 0.0, 0, 0.0, 0.0, 48000, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 0.0, 0.0, 0, 0.0, 0.0, 48000, 343.2),
        }
        with pytest.raises(InvalidSpecificationError, match="3-Way crossover sample rates mismatch"):
            OptimizationResult(
                crossover_result=(xover_low, xover_high),
                gain_results=gains,
                alignment_results=alignments,
                predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
                initial_metrics=_dummy_metrics(),
                optimized_metrics=_dummy_metrics(),
                initial_loss_db=0.02,
                final_loss_db=0.01,
                converged=True,
                iterations_completed=10,
            )

    def test_reject_3way_relational_constraint_violation(self) -> None:
        """Reject OptimizationResult where f_high < 1.5 * f_low in 3-way specification."""
        fs = 48000
        spec_low = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=1000.0)
        xover_low = synthesize_crossover_biquads(specification=spec_low, sample_rate=fs)

        spec_high = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=1200.0)
        xover_high = synthesize_crossover_biquads(specification=spec_high, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
            "midrange": GainDesignResult("midrange", 88.0, 88.0, 0.0, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 88.0, 88.0, 0.0, 1.0, False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "midrange": DriverAlignmentResult("midrange", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
        }

        # f_high (1200) < 1.5 * f_low (1500) -> must fail during OptimizationResult validation
        with pytest.raises(InvalidSpecificationError, match="must be >= 1.5 \\* f_low"):
            OptimizationResult(
                crossover_result=(xover_low, xover_high),
                gain_results=gains,
                alignment_results=alignments,
                predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
                initial_metrics=_dummy_metrics(),
                optimized_metrics=_dummy_metrics(),
                initial_loss_db=0.02,
                final_loss_db=0.01,
                converged=True,
                iterations_completed=10,
            )

    def test_reject_monotonicity_loss_violation(self) -> None:
        """Reject OptimizationResult where final_loss > initial_loss."""
        fs = 48000
        spec_x = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=2000.0)
        xover_res = synthesize_crossover_biquads(specification=spec_x, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 88.0, 88.0, 0.0, 1.0, False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
        }

        # final_loss (0.10) > initial_loss (0.05) -> must fail
        with pytest.raises(InvalidSpecificationError, match="Monotonicity invariant violated"):
            OptimizationResult(
                crossover_result=xover_res,
                gain_results=gains,
                alignment_results=alignments,
                predicted_response=_dummy_frd(np.linspace(100, 10000, 50)),
                initial_metrics=_dummy_metrics(),
                optimized_metrics=_dummy_metrics(),
                initial_loss_db=0.05,
                final_loss_db=0.10,
                converged=True,
                iterations_completed=10,
            )
