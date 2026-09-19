"""AcoustiForge Phase 4D-6 End-to-End Executable Continuity Benchmark.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
- docs/architecture/PHASE_4D_5_REVIEW_AND_FORWARD_REQUIREMENTS.md

This test module verifies the semantic continuity between the mathematical
acoustic forward model (Layer 1) and the executable DSP ComputeGraph (Layer 0)
processing raw float32 PCM samples:
1. Pure Gain Branch Continuity
2. Pure Delay Branch Continuity
3. Biquad Crossover Filter Branch Continuity (Low-pass & High-pass)
4. Full 2-Way Combined Acoustic Summation Continuity
5. Multi-Tone / Steady-State Sinusoidal Probe Verification
6. Full 3-Way Multi-Branch System Graph Execution Continuity
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.alignment import (
    DriverAlignmentResult,
    calculate_driver_alignment,
)
from acoustiforge.acoustic_math.crossover import (
    synthesize_crossover_biquads,
)
from acoustiforge.acoustic_math.optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    driver_response_to_complex,
    evaluate_biquad_complex_response,
)
from acoustiforge.acoustic_math.sensitivity import (
    GainDesignResult,
    calculate_sensitivity_gain,
)
from acoustiforge.builders.crossover_builder import CrossoverGraphBuilder
from acoustiforge.builders.multiway_builder import ThreeWayGraphBuilder
from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import (
    CrossoverFamily,
    CrossoverSpecification,
)
from acoustiforge.nodes.biquad import BiquadCoefficients, BiquadNode
from acoustiforge.nodes.delay import DelayNode
from acoustiforge.nodes.gain import GainNode


# ==============================================================================
# Helper Functions: Signal Generation and Frequency Response Extraction
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
    """Compute complex frequency response from discrete time-domain impulse response via FFT.

    Returns:
        (interpolated_mag_db, interpolated_phase_rad, complex_phasors_at_eval_freqs)
    """
    num_frames = time_samples.shape[0]
    fft_vals = np.fft.rfft(time_samples.astype(np.float64))
    fft_freqs = np.fft.rfftfreq(num_frames, d=1.0 / float(sample_rate))

    # Real and Imag interpolation over evaluation frequencies
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
    """Compute absolute phase error in degrees, robustly handling +/- pi circular wrapping."""
    diff_rad = phase_measured_rad - phase_analytical_rad
    # Wrap angular difference to [-pi, pi]
    wrapped_diff_rad = (diff_rad + math.pi) % (2.0 * math.pi) - math.pi
    return np.abs(wrapped_diff_rad) * (180.0 / math.pi)


# ==============================================================================
# Experiment A: Pure Gain Branch Continuity
# ==============================================================================

class TestExperimentAGainContinuity:
    """Verify that GainNode PCM execution exactly matches the analytical gain formula."""

    def test_pure_gain_pcm_continuity(self) -> None:
        """Verify GainNode attenuation (-6.0206 dB) matches analytical formula within 0.001 dB."""
        fs = 48000
        num_frames = 1024
        gain_db = -6.020599913279624

        gain_node = GainNode(gain_db=gain_db, sample_rate=fs, channels=1)
        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)

        out_block = gain_node.process(impulse_block)
        y = out_block.samples[0]

        # Analytical linear gain
        expected_g_linear = 10.0 ** (gain_db / 20.0)  # 0.5

        # Check sample-domain output
        assert np.isclose(y[0], expected_g_linear, atol=1e-6)
        assert np.all(y[1:] == 0.0)

        # Check frequency-domain continuity
        freqs = np.linspace(20.0, 20000.0, 100, dtype=np.float64)
        mag_db, phase_rad, h_c = _extract_complex_frequency_response(y, fs, freqs)

        mag_error = np.abs(mag_db - gain_db)
        phase_error = np.abs(phase_rad) * (180.0 / math.pi)

        assert np.max(mag_error) < 0.001, f"Max gain magnitude error {np.max(mag_error)} dB exceeds 0.001 dB"
        assert np.max(phase_error) < 0.01, f"Max gain phase error {np.max(phase_error)} deg exceeds 0.01 deg"


# ==============================================================================
# Experiment B: Pure Delay Branch Continuity
# ==============================================================================

class TestExperimentBDelayContinuity:
    """Verify that DelayNode PCM execution has identical phase rotation as analytical exp(-j 2pi f tau)."""

    def test_pure_delay_pcm_phase_continuity(self) -> None:
        """Verify DelayNode (D = 12 samples = 250 us at 48 kHz) matches analytical phase."""
        fs = 48000
        delay_frames = 12
        tau_seconds = delay_frames / float(fs)  # 0.00025 s
        num_frames = 8192

        delay_node = DelayNode(delay_frames=delay_frames, sample_rate=fs, channels=1)
        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)

        out_block = delay_node.process(impulse_block)
        y = out_block.samples[0]

        # In time domain, impulse is shifted to index 12
        assert y[delay_frames] == 1.0
        assert np.sum(np.abs(y)) == 1.0

        # Frequency domain evaluation
        freqs = np.linspace(50.0, 20000.0, 200, dtype=np.float64)
        mag_db, phase_measured_rad, h_c = _extract_complex_frequency_response(y, fs, freqs)

        # Analytical delay phase: -2*pi*f*tau
        phase_analytical_rad = -2.0 * math.pi * freqs * tau_seconds
        # Wrap analytical phase to [-pi, pi]
        phase_analytical_wrapped = (phase_analytical_rad + math.pi) % (2.0 * math.pi) - math.pi

        mag_error = np.abs(mag_db - 0.0)
        phase_error_deg = _compute_phase_error_degrees(phase_measured_rad, phase_analytical_wrapped)

        assert np.max(mag_error) < 0.01, f"Max delay magnitude error {np.max(mag_error)} dB exceeds 0.01 dB"
        assert np.max(phase_error_deg) < 0.05, f"Max delay phase error {np.max(phase_error_deg)} deg exceeds 0.05 deg"


# ==============================================================================
# Experiment C: Biquad Crossover Branch Continuity (Low-Pass & High-Pass)
# ==============================================================================

class TestExperimentCBiquadCrossoverContinuity:
    """Verify that executable BiquadNode cascades match analytical evaluate_biquad_complex_response."""

    def test_crossover_biquad_cascade_pcm_continuity(self) -> None:
        """Verify 4th-order Linkwitz-Riley crossover (2 cascaded biquads per branch at 2500 Hz)."""
        fs = 48000
        num_frames = 8192
        fc = 2500.0

        spec = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=fc)
        crossover_res = synthesize_crossover_biquads(specification=spec, sample_rate=fs)

        builder = CrossoverGraphBuilder(sample_rate=fs, woofer_name="woofer", tweeter_name="tweeter")
        graph = builder.build_2way_graph(crossover_result=crossover_res)

        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)
        out_blocks = graph.process(impulse_block)

        woofer_out = out_blocks[f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"].samples[0]
        tweeter_out = out_blocks[f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"].samples[0]

        # Evaluation frequencies: 50 Hz to 20 kHz (150 points)
        freqs = np.geomspace(50.0, 20000.0, 150, dtype=np.float64)

        # 1. Measured DSP Responses
        mag_w_dsp, phase_w_dsp, _ = _extract_complex_frequency_response(woofer_out, fs, freqs)
        mag_t_dsp, phase_t_dsp, _ = _extract_complex_frequency_response(tweeter_out, fs, freqs)

        # 2. Analytical Forward Model Responses
        h_w_analytical = evaluate_biquad_complex_response(crossover_res.low_pass_sections, freqs, fs)
        h_t_analytical = evaluate_biquad_complex_response(crossover_res.high_pass_sections, freqs, fs)

        mag_w_ana = 20.0 * np.log10(np.maximum(np.abs(h_w_analytical), 1e-12))
        phase_w_ana = np.arctan2(h_w_analytical.imag, h_w_analytical.real)

        mag_t_ana = 20.0 * np.log10(np.maximum(np.abs(h_t_analytical), 1e-12))
        phase_t_ana = np.arctan2(h_t_analytical.imag, h_t_analytical.real)

        # 3. Assert High-Fidelity Continuity (< 0.05 dB magnitude, < 0.5 deg phase across active bands)
        # Woofer in passband and transition (50 Hz to 5000 Hz)
        w_mask = freqs <= 5000.0
        w_mag_err = np.max(np.abs(mag_w_dsp[w_mask] - mag_w_ana[w_mask]))
        w_phase_err = np.max(_compute_phase_error_degrees(phase_w_dsp[w_mask], phase_w_ana[w_mask]))
        assert w_mag_err < 0.05, f"Woofer max magnitude error {w_mag_err:.4f} dB exceeds 0.05 dB"
        assert w_phase_err < 0.5, f"Woofer max phase error {w_phase_err:.4f} deg exceeds 0.5 deg"

        # Tweeter in transition and passband (1000 Hz to 20000 Hz)
        t_mask = freqs >= 1000.0
        t_mag_err = np.max(np.abs(mag_t_dsp[t_mask] - mag_t_ana[t_mask]))
        t_phase_err = np.max(_compute_phase_error_degrees(phase_t_dsp[t_mask], phase_t_ana[t_mask]))
        assert t_mag_err < 0.05, f"Tweeter max magnitude error {t_mag_err:.4f} dB exceeds 0.05 dB"
        assert t_phase_err < 0.5, f"Tweeter max phase error {t_phase_err:.4f} deg exceeds 0.5 deg"


# ==============================================================================
# Experiment D: Full 2-Way Combined Acoustic Summation Continuity
# ==============================================================================

class TestExperimentD2WayCombinedSummationContinuity:
    """Verify that full 2-way graph execution (Gain + Delay + Crossover + Sum) matches analytical summation."""

    def test_2way_combined_system_dsp_vs_analytical_parity(self) -> None:
        """Construct full 2-way system:

        - Woofer: Gain = -0.5 dB, Delay = 0 frames, LR4 Low-pass at 2200 Hz
        - Tweeter: Gain = -3.0 dB, Delay = 6 frames (125 us), LR4 High-pass at 2200 Hz
        Execute impulse through ComputeGraph, sum outputs, and compare with analytical summation.
        """
        fs = 48000
        num_frames = 8192
        fc = 2200.0
        w_gain_db = -0.5
        t_gain_db = -3.0
        t_delay_frames = 6
        t_delay_s = t_delay_frames / float(fs)  # 125 us

        spec = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=fc)
        crossover_res = synthesize_crossover_biquads(specification=spec, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 90.0, 89.5, w_gain_db, 10.0**(w_gain_db/20.0), False),
            "tweeter": GainDesignResult("tweeter", 93.0, 90.0, t_gain_db, 10.0**(t_gain_db/20.0), False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", t_delay_s, float(t_delay_frames), t_delay_frames, 42.9, 0.0, fs, 343.2),
        }

        builder = CrossoverGraphBuilder(sample_rate=fs, woofer_name="woofer", tweeter_name="tweeter")
        graph = builder.build_2way_graph(
            crossover_result=crossover_res,
            gains=gains,
            alignments=alignments,
        )

        # 1. Execute PCM Block
        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)
        out_blocks = graph.process(impulse_block)

        w_pcm = out_blocks[f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"].samples[0]
        t_pcm = out_blocks[f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"].samples[0]
        summed_pcm = w_pcm + t_pcm

        # 2. Extract DSP Frequency Response
        freqs = np.geomspace(40.0, 20000.0, 200, dtype=np.float64)
        mag_dsp_db, phase_dsp_rad, h_dsp = _extract_complex_frequency_response(summed_pcm, fs, freqs)

        # 3. Compute Analytical Complex Forward Model
        frd_flat = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))
        hw_ana = calculate_branch_complex_response(
            frd_flat, crossover_res.low_pass_sections, gain_db=w_gain_db, delay_seconds=0.0, sample_rate=fs
        )
        ht_ana = calculate_branch_complex_response(
            frd_flat, crossover_res.high_pass_sections, gain_db=t_gain_db, delay_seconds=t_delay_s, sample_rate=fs
        )
        total_ana_frd = calculate_acoustic_complex_summation([hw_ana, ht_ana], freqs)

        # 4. Error Metrics
        mag_errors = np.abs(mag_dsp_db - total_ana_frd.magnitude_db)
        phase_errors_deg = _compute_phase_error_degrees(phase_dsp_rad, total_ana_frd.phase_rad)

        max_mag_err = float(np.max(mag_errors))
        rms_mag_err = float(np.sqrt(np.mean(mag_errors ** 2)))

        max_phase_err = float(np.max(phase_errors_deg))
        rms_phase_err = float(np.sqrt(np.mean(phase_errors_deg ** 2)))

        print(f"\n[CONTINUITY TELEMETRY 2-WAY]")
        print(f"Max Magnitude Error: {max_mag_err:.5f} dB (Threshold: < 0.05 dB)")
        print(f"RMS Magnitude Error: {rms_mag_err:.5f} dB")
        print(f"Max Phase Error:     {max_phase_err:.5f} deg (Threshold: < 0.50 deg)")
        print(f"RMS Phase Error:     {rms_phase_err:.5f} deg")

        # 5. Acceptance Assertions
        assert max_mag_err < 0.05, f"Max magnitude error {max_mag_err:.4f} dB exceeds 0.05 dB target."
        assert max_phase_err < 0.50, f"Max phase error {max_phase_err:.4f} deg exceeds 0.50 deg target."


# ==============================================================================
# Experiment E: Multi-Tone Steady-State Sinusoidal Probe Verification
# ==============================================================================

class TestExperimentEMultiToneProbeVerification:
    """Verify continuous sinusoidal steady-state response through ComputeGraph against analytical phasor."""

    def test_steady_state_sinusoidal_probe(self) -> None:
        """Inject pure sine wave at crossover frequency (2000 Hz) and verify amplitude/phase matching."""
        fs = 48000
        test_freq = 2000.0
        duration_s = 0.1  # 100 ms = 4800 samples
        num_frames = int(duration_s * fs)
        t = np.arange(num_frames, dtype=np.float64) / float(fs)

        # Generate continuous input sine wave: x(t) = sin(2 * pi * f * t)
        input_sine = np.sin(2.0 * math.pi * test_freq * t).astype(np.float32)
        meta = AudioMetadata(sample_rate=fs, channels=1)
        input_block = PCMBlock(samples=np.expand_dims(input_sine, axis=0), metadata=meta)

        # Build 2-way graph with LR4 crossover at 2000 Hz
        spec = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=test_freq)
        crossover_res = synthesize_crossover_biquads(specification=spec, sample_rate=fs)
        builder = CrossoverGraphBuilder(sample_rate=fs, woofer_name="w", tweeter_name="t")
        graph = builder.build_2way_graph(crossover_result=crossover_res)

        out_blocks = graph.process(input_block)
        w_pcm = out_blocks[f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"].samples[0]
        t_pcm = out_blocks[f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"].samples[0]
        summed_pcm = w_pcm + t_pcm

        # Take steady-state segment (last 2000 samples after filter warm-up)
        steady_out = summed_pcm[2000:].astype(np.float64)
        steady_in = input_sine[2000:].astype(np.float64)

        # Measure peak amplitude of steady-state output
        out_rms = np.sqrt(np.mean(steady_out ** 2))
        in_rms = np.sqrt(np.mean(steady_in ** 2))
        measured_gain_linear = out_rms / in_rms
        measured_gain_db = 20.0 * np.log10(measured_gain_linear)

        # For LR4 at crossover frequency, low-pass and high-pass each output -6.02 dB in phase,
        # summing to exactly 0 dB (gain = 1.0)
        assert np.isclose(measured_gain_db, 0.0, atol=0.05)


# ==============================================================================
# Experiment F: Full 3-Way Multi-Branch System Graph Execution Continuity
# ==============================================================================

class TestExperimentF3WaySystemContinuity:
    """Verify that a 3-way loudspeaker ComputeGraph (Woofer/Mid/Tweeter) matches analytical 3-way summation."""

    def test_3way_system_dsp_vs_analytical_parity(self) -> None:
        """Construct 3-way system:

        - Crossover Low: 400 Hz (LR4)
        - Crossover High: 3500 Hz (LR4)
        - Woofer: Gain = 0 dB, Delay = 0 frames
        - Midrange: Gain = -1.5 dB, Delay = 3 frames (62.5 us)
        - Tweeter: Gain = -2.5 dB, Delay = 7 frames (145.8 us)
        Execute impulse, sum 3 branches, and compare with analytical 3-way summation.
        """
        fs = 48000
        num_frames = 8192
        f_low = 400.0
        f_high = 3500.0

        spec_low = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=f_low)
        xover_low = synthesize_crossover_biquads(specification=spec_low, sample_rate=fs)

        spec_high = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=f_high)
        xover_high = synthesize_crossover_biquads(specification=spec_high, sample_rate=fs)

        gains = {
            "woofer": GainDesignResult("woofer", 88.0, 88.0, 0.0, 1.0, False),
            "midrange": GainDesignResult("midrange", 89.5, 88.0, -1.5, 10.0**(-1.5/20.0), False),
            "tweeter": GainDesignResult("tweeter", 90.5, 88.0, -2.5, 10.0**(-2.5/20.0), False),
        }
        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 0.0, 0.0, fs, 343.2),
            "midrange": DriverAlignmentResult("midrange", 3/fs, 3.0, 3, 21.4, 0.0, fs, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 7/fs, 7.0, 7, 50.0, 0.0, fs, 343.2),
        }

        builder = ThreeWayGraphBuilder(
            sample_rate=fs,
            woofer_name="woofer",
            midrange_name="midrange",
            tweeter_name="tweeter",
        )
        graph = builder.build_3way_graph(
            crossover_low=xover_low,
            crossover_high=xover_high,
            gains=gains,
            alignments=alignments,
        )

        # 1. Execute PCM Block
        impulse_block = _generate_dirac_impulse(num_frames=num_frames, sample_rate=fs)
        out_blocks = graph.process(impulse_block)

        w_pcm = out_blocks[f"{graph.outputs[0][0]}.{graph.outputs[0][1]}"].samples[0]
        m_pcm = out_blocks[f"{graph.outputs[1][0]}.{graph.outputs[1][1]}"].samples[0]
        t_pcm = out_blocks[f"{graph.outputs[2][0]}.{graph.outputs[2][1]}"].samples[0]
        summed_pcm = w_pcm + m_pcm + t_pcm

        # 2. Extract DSP Frequency Response
        freqs = np.geomspace(30.0, 20000.0, 250, dtype=np.float64)
        mag_dsp_db, phase_dsp_rad, h_dsp = _extract_complex_frequency_response(summed_pcm, fs, freqs)

        # 3. Compute Analytical 3-Way Forward Model
        # Midrange bandpass is cascaded highpass(low_xover) and lowpass(high_xover)
        mid_sections = tuple(xover_low.high_pass_sections) + tuple(xover_high.low_pass_sections)

        frd_flat = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))
        hw_ana = calculate_branch_complex_response(
            frd_flat, xover_low.low_pass_sections, gain_db=0.0, delay_seconds=0.0, sample_rate=fs
        )
        hm_ana = calculate_branch_complex_response(
            frd_flat, mid_sections, gain_db=-1.5, delay_seconds=3/float(fs), sample_rate=fs
        )
        ht_ana = calculate_branch_complex_response(
            frd_flat, xover_high.high_pass_sections, gain_db=-2.5, delay_seconds=7/float(fs), sample_rate=fs
        )
        total_ana_frd = calculate_acoustic_complex_summation([hw_ana, hm_ana, ht_ana], freqs)

        # 4. Error Metrics
        mag_errors = np.abs(mag_dsp_db - total_ana_frd.magnitude_db)
        phase_errors_deg = _compute_phase_error_degrees(phase_dsp_rad, total_ana_frd.phase_rad)

        max_mag_err = float(np.max(mag_errors))
        rms_mag_err = float(np.sqrt(np.mean(mag_errors ** 2)))

        max_phase_err = float(np.max(phase_errors_deg))
        rms_phase_err = float(np.sqrt(np.mean(phase_errors_deg ** 2)))

        print(f"\n[CONTINUITY TELEMETRY 3-WAY]")
        print(f"Max Magnitude Error: {max_mag_err:.5f} dB (Threshold: < 0.05 dB)")
        print(f"RMS Magnitude Error: {rms_mag_err:.5f} dB")
        print(f"Max Phase Error:     {max_phase_err:.5f} deg (Threshold: < 0.50 deg)")
        print(f"RMS Phase Error:     {rms_phase_err:.5f} deg")

        # 5. Acceptance Assertions
        assert max_mag_err < 0.05, f"3-Way max magnitude error {max_mag_err:.4f} dB exceeds 0.05 dB target."
        assert max_phase_err < 0.50, f"3-Way max phase error {max_phase_err:.4f} deg exceeds 0.50 deg target."
