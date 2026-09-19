"""AcoustiForge Phase 4D-4 Forward-Model Transparency & Inspectability Benchmark.

Normative Authority:
- docs/architecture/ACOUSTIFORGE_OOTB_CAPABILITY_AUDIT.md
- docs/architecture/ACOUSTIFORGE_OUTPUT_QUALITY_AND_CONTROL_EDGE_EXPERIMENT.md
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)

This test module implements Experiment A (Forward-Model Transparency) and
Experiment C (Physical-Acoustic Phase Cancellation) using an independent
analytical golden reference that does NOT import acoustiforge.acoustic_math.
"""

from __future__ import annotations

import math
import time
from typing import Sequence, Tuple
import numpy as np
import pytest

from acoustiforge.acoustic_math.optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    complex_response_to_frequency_response_data,
    driver_response_to_complex,
    evaluate_acoustic_target_loss,
    evaluate_biquad_complex_response,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import AcousticTargetCurve
from acoustiforge.nodes.biquad import BiquadCoefficients


# ==============================================================================
# Independent Analytical Golden Reference Implementations (Pure Math / No Forge Math)
# ==============================================================================

def _golden_biquad_transfer_function(
    bq: BiquadCoefficients,
    frequencies_hz: np.ndarray,
    sample_rate: int,
) -> np.ndarray:
    """Independently evaluate biquad transfer function H(z) on unit circle.

    Golden Equation:
        z^-1 = exp(-j * 2 * pi * f / fs) = cos(w) - j sin(w)
        H(f) = (b0 + b1 z^-1 + b2 z^-2) / (1 + a1 z^-1 + a2 z^-2)
    """
    w = 2.0 * math.pi * frequencies_hz / float(sample_rate)
    z_inv1 = np.cos(w) - 1j * np.sin(w)
    z_inv2 = np.cos(2.0 * w) - 1j * np.sin(2.0 * w)

    num = bq.b0 + bq.b1 * z_inv1 + bq.b2 * z_inv2
    den = 1.0 + bq.a1 * z_inv1 + bq.a2 * z_inv2
    return num / den


def _golden_branch_response(
    driver_complex: np.ndarray,
    biquads: Sequence[BiquadCoefficients],
    gain_db: float,
    delay_seconds: float,
    frequencies_hz: np.ndarray,
    sample_rate: int,
) -> Tuple[np.ndarray, np.ndarray, float, np.ndarray, np.ndarray]:
    """Independently calculate all 5 intermediate branch components.

    Returns:
        (h_driver, h_filter, g_linear, h_delay, h_branch)
    """
    # 1. Driver complex
    h_driver = np.asarray(driver_complex, dtype=np.complex128)

    # 2. Filter cascade
    h_filter = np.ones(frequencies_hz.shape[0], dtype=np.complex128)
    for bq in biquads:
        h_filter *= _golden_biquad_transfer_function(bq, frequencies_hz, sample_rate)

    # 3. Linear gain
    g_linear = 10.0 ** (gain_db / 20.0)

    # 4. Delay phasor: exp(-j * 2 * pi * f * tau)
    if delay_seconds == 0.0:
        h_delay = np.ones(frequencies_hz.shape[0], dtype=np.complex128)
    else:
        w_tau = 2.0 * math.pi * frequencies_hz * delay_seconds
        h_delay = np.cos(w_tau) - 1j * np.sin(w_tau)

    # 5. Branch response
    h_branch = h_driver * h_filter * g_linear * h_delay
    return h_driver, h_filter, g_linear, h_delay, h_branch


# ==============================================================================
# Experiment A: Forward Model Transparency & Intermediate State Inspectability
# ==============================================================================

class TestExperimentAForwardModelTransparency:
    """Experiment A: 2-Way synthetic system forward-model verification against analytical golden."""

    def test_2way_intermediate_state_transparency_and_analytical_parity(self) -> None:
        """Verify all 6 transfer function states (H_driver, H_filter, gain, delay, H_branch, H_total)

        match independent analytical goldens to machine precision (< 1e-12).
        """
        sample_rate = 48000
        # Log-spaced grid of 100 points from 20 Hz to 20 kHz
        freqs = np.geomspace(20.0, 20000.0, 100, dtype=np.float64)

        # 1. Analytically define 2-way drivers:
        # Woofer: 1st-order low-pass roll-off at 2000 Hz: H_w(f) = 1 / (1 + j(f / 2000))
        f_w = 2000.0
        h_w_golden = 1.0 / (1.0 + 1j * (freqs / f_w))
        w_mag_db = 20.0 * np.log10(np.abs(h_w_golden))
        w_phase_rad = np.arctan2(h_w_golden.imag, h_w_golden.real)
        woofer_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=w_mag_db, phase_rad=w_phase_rad)

        # Tweeter: 1st-order high-pass roll-off at 2000 Hz: H_t(f) = j(f / 2000) / (1 + j(f / 2000))
        f_t = 2000.0
        h_t_golden = (1j * (freqs / f_t)) / (1.0 + 1j * (freqs / f_t))
        t_mag_db = 20.0 * np.log10(np.abs(h_t_golden))
        t_phase_rad = np.arctan2(h_t_golden.imag, h_t_golden.real)
        tweeter_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=t_mag_db, phase_rad=t_phase_rad)

        # 2. Branch filter coefficients (2nd-order Butterworth LP for woofer, HP for tweeter at 2000 Hz)
        # Manually specified RBJ Butterworth coefficients at 2000 Hz, Q = 1/sqrt(2), fs = 48000 Hz
        w0 = 2.0 * math.pi * 2000.0 / float(sample_rate)
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * (1.0 / math.sqrt(2.0)))
        a0 = 1.0 + alpha

        # Butterworth LP
        lp_b0 = ((1.0 - cos_w0) / 2.0) / a0
        lp_b1 = (1.0 - cos_w0) / a0
        lp_b2 = ((1.0 - cos_w0) / 2.0) / a0
        lp_a1 = (-2.0 * cos_w0) / a0
        lp_a2 = (1.0 - alpha) / a0
        lp_biquad = BiquadCoefficients(b0=lp_b0, b1=lp_b1, b2=lp_b2, a1=lp_a1, a2=lp_a2)

        # Butterworth HP
        hp_b0 = ((1.0 + cos_w0) / 2.0) / a0
        hp_b1 = (-(1.0 + cos_w0)) / a0
        hp_b2 = ((1.0 + cos_w0) / 2.0) / a0
        hp_a1 = (-2.0 * cos_w0) / a0
        hp_a2 = (1.0 - alpha) / a0
        hp_biquad = BiquadCoefficients(b0=hp_b0, b1=hp_b1, b2=hp_b2, a1=hp_a1, a2=hp_a2)

        # Branch parameters
        woofer_gain_db = -0.5
        woofer_delay_s = 0.0
        tweeter_gain_db = -1.2
        tweeter_delay_s = 4.5e-5  # 45 microseconds

        # 3. Compute AcoustiForge intermediate states via public API
        h_w_driver_forge = driver_response_to_complex(woofer_frd)
        h_t_driver_forge = driver_response_to_complex(tweeter_frd)

        h_w_filter_forge = evaluate_biquad_complex_response([lp_biquad], freqs, sample_rate)
        h_t_filter_forge = evaluate_biquad_complex_response([hp_biquad], freqs, sample_rate)

        h_w_branch_forge = calculate_branch_complex_response(
            woofer_frd, [lp_biquad], gain_db=woofer_gain_db, delay_seconds=woofer_delay_s, sample_rate=sample_rate
        )
        h_t_branch_forge = calculate_branch_complex_response(
            tweeter_frd, [hp_biquad], gain_db=tweeter_gain_db, delay_seconds=tweeter_delay_s, sample_rate=sample_rate
        )

        total_frd_forge = calculate_acoustic_complex_summation(
            [h_w_branch_forge, h_t_branch_forge], freqs
        )

        # 4. Compute Independent Golden Intermediate States
        _, h_w_filt_gold, g_w_gold, d_w_gold, h_w_branch_gold = _golden_branch_response(
            h_w_golden, [lp_biquad], woofer_gain_db, woofer_delay_s, freqs, sample_rate
        )
        _, h_t_filt_gold, g_t_gold, d_t_gold, h_t_branch_gold = _golden_branch_response(
            h_t_golden, [hp_biquad], tweeter_gain_db, tweeter_delay_s, freqs, sample_rate
        )
        h_total_gold = h_w_branch_gold + h_t_branch_gold
        mag_gold_db = 20.0 * np.log10(np.maximum(np.abs(h_total_gold), 1e-12))
        phase_gold_rad = np.arctan2(h_total_gold.imag, h_total_gold.real)

        # 5. Assert Machine-Precision Parity Across All Intermediate States (< 1e-12)
        # Driver responses
        assert np.allclose(h_w_driver_forge, h_w_golden, atol=1e-12, rtol=1e-12)
        assert np.allclose(h_t_driver_forge, h_t_golden, atol=1e-12, rtol=1e-12)

        # Filter responses
        assert np.allclose(h_w_filter_forge, h_w_filt_gold, atol=1e-12, rtol=1e-12)
        assert np.allclose(h_t_filter_forge, h_t_filt_gold, atol=1e-12, rtol=1e-12)

        # Branch responses
        assert np.allclose(h_w_branch_forge, h_w_branch_gold, atol=1e-12, rtol=1e-12)
        assert np.allclose(h_t_branch_forge, h_t_branch_gold, atol=1e-12, rtol=1e-12)

        # Total complex summation
        h_total_forge = h_w_branch_forge + h_t_branch_forge
        assert np.allclose(h_total_forge, h_total_gold, atol=1e-12, rtol=1e-12)

        # Total magnitude and phase
        assert np.allclose(total_frd_forge.magnitude_db, mag_gold_db, atol=1e-12, rtol=1e-12)
        assert np.allclose(total_frd_forge.phase_rad, phase_gold_rad, atol=1e-12, rtol=1e-12)

        # Target error inspectability
        target_curve = AcousticTargetCurve("Flat_85dB", ((20.0, 85.0), (20000.0, 85.0)))
        loss = evaluate_acoustic_target_loss(total_frd_forge, target_curve, (100.0, 10000.0))
        assert math.isfinite(loss)
        assert loss > 0.0


# ==============================================================================
# Experiment C: Physical-Acoustic Phase Cancellation vs Magnitude-Only Blindness
# ==============================================================================

class TestExperimentCPhaseCancellation:
    """Experiment C: Demonstrate physical phase cancellation notch vs magnitude-only approximation."""

    def test_ideal_cancellation_analytical_notch(self) -> None:
        """Verify exact mathematical cancellation (180 deg) drops to the normative -240.0 dB floor."""
        freqs = np.array([1000.0, 2500.0, 5000.0], dtype=np.float64)
        h1 = np.array([1.0 + 0j, 1.0 + 0j, 1.0 + 0j], dtype=np.complex128)
        h2 = np.array([-1.0 + 0j, -1.0 + 0j, -1.0 + 0j], dtype=np.complex128)

        # Complex acoustic summation
        res_complex = calculate_acoustic_complex_summation([h1, h2], freqs)
        assert np.allclose(res_complex.magnitude_db, -240.0, atol=1e-12)

        # Magnitude-only naive summation
        mag_naive = np.sqrt(np.abs(h1) ** 2 + np.abs(h2) ** 2)
        mag_naive_db = 20.0 * np.log10(mag_naive)
        assert np.allclose(mag_naive_db, 20.0 * math.log10(math.sqrt(2.0)), atol=1e-12)  # +3.01 dB

    def test_frequency_dependent_delay_cancellation_comb_notch(self) -> None:
        """Verify frequency-dependent acoustic delay cancellation (tau = 200 us at 2500 Hz).

        At 2500 Hz, tau = 200 us produces exactly Delta phi = 2*pi*(2500)*(0.0002) = pi rad (180 deg).
        - Naive magnitude-only summation predicts flat +3.01 dB across all frequencies.
        - AcoustiForge complex summation predicts a deep cancellation notch (> 100 dB deep) at 2500 Hz.
        - Delay-compensated summation restores in-phase +6.02 dB summation at 2500 Hz.
        """
        # Dense linear grid around 2500 Hz (from 2000 Hz to 3000 Hz)
        freqs = np.linspace(2000.0, 3000.0, 501, dtype=np.float64)
        tau = 2.0e-4  # 200 microseconds

        # Two flat unit-gain drivers (0 dB SPL, 0 phase)
        frd1 = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))
        frd2 = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))

        # 1. Naive magnitude-only summation:
        mag_naive_linear = np.sqrt(1.0**2 + 1.0**2)
        mag_naive_db = 20.0 * math.log10(mag_naive_linear)  # +3.0103 dB flat

        # 2. AcoustiForge complex acoustic summation with tau = 200 us:
        h1 = calculate_branch_complex_response(frd1, gain_db=0.0, delay_seconds=0.0)
        h2 = calculate_branch_complex_response(frd2, gain_db=0.0, delay_seconds=tau)
        sum_delayed = calculate_acoustic_complex_summation([h1, h2], freqs)

        # Locate 2500 Hz index
        idx_2500 = np.argmin(np.abs(freqs - 2500.0))
        assert abs(freqs[idx_2500] - 2500.0) < 1e-6

        # Complex response at 2500 Hz must be at the cancellation floor
        mag_at_2500_db = sum_delayed.magnitude_db[idx_2500]
        assert mag_at_2500_db < -100.0  # Destructive cancellation notch (floor or near floor)

        # Difference between naive prediction and complex reality at 2500 Hz is > 100 dB!
        error_naive_vs_reality = mag_naive_db - mag_at_2500_db
        assert error_naive_vs_reality > 100.0

        # 3. AcoustiForge Delay Compensation: add 200 us delay to branch 1 (or invert)
        # When both branches have identical 200 us delay, they sum in-phase:
        h1_comp = calculate_branch_complex_response(frd1, gain_db=0.0, delay_seconds=tau)
        sum_compensated = calculate_acoustic_complex_summation([h1_comp, h2], freqs)

        # At 2500 Hz, in-phase summation yields 20 * log10(2) = +6.0206 dB
        mag_comp_at_2500 = sum_compensated.magnitude_db[idx_2500]
        assert np.isclose(mag_comp_at_2500, 20.0 * math.log10(2.0), atol=1e-6)


# ==============================================================================
# Numerical Determinism & Repeatability Verification (100 Iterations)
# ==============================================================================

class TestNumericalDeterminismBenchmark:
    """Verify 100% bit-exact determinism across 100 repeated executions of the 2-way forward model."""

    def test_100_repeated_runs_bit_exact_reproducibility(self) -> None:
        """Run identical 2-way complex summation 100 times and verify zero variance."""
        freqs = np.geomspace(20.0, 20000.0, 200, dtype=np.float64)
        sample_rate = 48000

        frd_w = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))
        frd_t = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))

        baseline_frd = None

        for iteration in range(100):
            h_w = calculate_branch_complex_response(frd_w, gain_db=-1.5, delay_seconds=0.0)
            h_t = calculate_branch_complex_response(frd_t, gain_db=-2.0, delay_seconds=3.5e-5)
            res = calculate_acoustic_complex_summation([h_w, h_t], freqs)

            if baseline_frd is None:
                baseline_frd = res
            else:
                # Assert bit-exact identity across all 100 runs
                assert np.array_equal(res.magnitude_db, baseline_frd.magnitude_db)
                assert np.array_equal(res.phase_rad, baseline_frd.phase_rad)


# ==============================================================================
# Performance Benchmark: 1000-Point 2-Way Complex Forward Model
# ==============================================================================

class TestForwardModelPerformanceBenchmark:
    """Benchmark raw execution speed of the 1000-point 2-way complex forward model."""

    def test_1000_point_2way_summation_performance(self) -> None:
        """Measure latency of a 1000-point 2-way complex summation across 500 repetitions."""
        freqs = np.geomspace(20.0, 20000.0, 1000, dtype=np.float64)
        sample_rate = 48000

        # Construct biquads
        bq_w = BiquadCoefficients(b0=0.1, b1=0.2, b2=0.1, a1=-0.5, a2=0.2)
        bq_t = BiquadCoefficients(b0=0.5, b1=-0.5, b2=0.0, a1=-0.3, a2=0.1)

        frd_w = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))
        frd_t = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros_like(freqs), phase_rad=np.zeros_like(freqs))

        # Warm-up
        for _ in range(10):
            hw = calculate_branch_complex_response(frd_w, [bq_w], gain_db=0.0, delay_seconds=0.0, sample_rate=sample_rate)
            ht = calculate_branch_complex_response(frd_t, [bq_t], gain_db=-1.0, delay_seconds=5e-5, sample_rate=sample_rate)
            _ = calculate_acoustic_complex_summation([hw, ht], freqs)

        repetitions = 500
        timings = []

        for _ in range(repetitions):
            t0 = time.perf_counter()
            hw = calculate_branch_complex_response(frd_w, [bq_w], gain_db=0.0, delay_seconds=0.0, sample_rate=sample_rate)
            ht = calculate_branch_complex_response(frd_t, [bq_t], gain_db=-1.0, delay_seconds=5e-5, sample_rate=sample_rate)
            res = calculate_acoustic_complex_summation([hw, ht], freqs)
            t1 = time.perf_counter()
            timings.append((t1 - t0) * 1000.0)  # ms

        median_ms = float(np.median(timings))
        min_ms = float(np.min(timings))
        max_ms = float(np.max(timings))
        mean_ms = float(np.mean(timings))

        print(f"\n[PERFORMANCE TELEMETRY] Repetitions: {repetitions}")
        print(f"[PERFORMANCE TELEMETRY] Min: {min_ms:.4f} ms")
        print(f"[PERFORMANCE TELEMETRY] Median: {median_ms:.4f} ms")
        print(f"[PERFORMANCE TELEMETRY] Mean: {mean_ms:.4f} ms")
        print(f"[PERFORMANCE TELEMETRY] Max: {max_ms:.4f} ms")

        # Output performance telemetry in test assertion
        assert median_ms < 10.0, f"Forward model median execution time {median_ms:.3f} ms exceeds 10.0 ms target."
