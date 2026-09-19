"""Independent Analytical Golden Vectors for Acoustic Response Metrics.

Normative Authority:
- docs/contracts/ACOUSTIC_METRICS_CONTRACT.md
- docs/phases/PHASE_4B_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.metrics import (
    AcousticMetricsResult,
    SmoothingMode,
    calculate_response_metrics,
    smooth_frequency_response,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import AcousticTargetCurve


class TestAcousticMetricsGolden:
    """Independent analytical verification of acoustic metrics without self-referential production code."""

    def test_golden_flat_response_analytical(self) -> None:
        """Verify analytical flat response: exact sensitivity, 0 ripple, 0 tilt, None cutoffs."""
        freqs = np.geomspace(20.0, 20000.0, 500)
        mags = np.full_like(freqs, 86.5)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(200.0, 2000.0))

        # Sensitivity must match 86.5 dB within 1e-12 dB
        assert abs(res.passband_sensitivity_db - 86.5) < 1e-12
        # Ripple must be 0.0 dB
        assert abs(res.passband_ripple_db - 0.0) < 1e-12
        # Tilt must be 0.0 dB/oct
        assert abs(res.spectral_tilt_db_per_oct - 0.0) < 1e-12
        # No cutoffs
        assert res.f3_low_hz is None
        assert res.f3_high_hz is None
        assert res.f6_low_hz is None
        assert res.f6_high_hz is None
        assert res.f10_low_hz is None
        assert res.f10_high_hz is None

    def test_golden_constant_spectral_tilt_analytical(self) -> None:
        """Verify exact unweighted OLS tilt derivation for a known linear-log2 slope."""
        # Slope = -3.0 dB/octave, offset = 90.0 dB at 1000 Hz
        # M(f) = 90.0 - 3.0 * log2(f / 1000.0)
        freqs = np.geomspace(100.0, 10000.0, 200)
        mags = 90.0 - 3.0 * np.log2(freqs / 1000.0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(200.0, 4000.0))

        # Tilt must match -3.0 dB/oct within 1e-6 dB/oct
        assert abs(res.spectral_tilt_db_per_oct - (-3.0)) < 1e-6

    def test_golden_target_offset_error_analytical(self) -> None:
        """Verify analytical target error calculation against an AcousticTargetCurve."""
        # Flat measurement at 88.0 dB
        freqs = np.geomspace(100.0, 10000.0, 100)
        mags = np.full_like(freqs, 88.0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        # Target curve at 85.0 dB -> constant offset of +3.0 dB
        target = AcousticTargetCurve(
            name="Golden Flat Target",
            points=((100.0, 85.0), (10000.0, 85.0)),
        )

        res = calculate_response_metrics(frd, target_curve=target)

        assert res.rms_target_error_db is not None
        assert abs(res.rms_target_error_db - 3.0) < 1e-12
        assert res.peak_positive_error_db is not None
        assert abs(res.peak_positive_error_db - 3.0) < 1e-12
        assert res.peak_negative_error_db is not None
        assert abs(res.peak_negative_error_db - 3.0) < 1e-12

    def test_golden_passband_ripple_analytical(self) -> None:
        """Verify analytical passband ripple max(M) - min(M)."""
        freqs = np.array([100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0], dtype=np.float64)
        # Passband [200, 2000]: points are 200 (83 dB), 500 (87.5 dB), 1000 (81.0 dB), 2000 (84.0 dB)
        # Max = 87.5 dB, Min = 81.0 dB -> Ripple = 6.5 dB
        mags = np.array([75.0, 83.0, 87.5, 81.0, 84.0, 70.0], dtype=np.float64)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(200.0, 2000.0))

        assert abs(res.passband_ripple_db - 6.5) < 1e-12

    def test_golden_analytical_butterworth_4th_order_lowpass(self) -> None:
        """Verify exact analytical F3, F6, F10 and asymptotic rolloff for 4th-order Butterworth low-pass."""
        fc = 1000.0
        n_order = 4
        # Analytical formula: M(f) = 85.0 - 10 * log10(1 + (f / 1000.0)^8)
        freqs = np.geomspace(100.0, 10000.0, 1000)
        mags = 85.0 - 10.0 * np.log10(1.0 + np.power(freqs / fc, 2 * n_order))
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(100.0, 300.0))

        # 1. Exact Passband Sensitivity
        assert abs(res.passband_sensitivity_db - 85.0) < 0.01

        # 2. Exact Analytical F3, F6, F10 cutoffs:
        expected_f3 = fc * math.pow(math.pow(10.0, 0.3) - 1.0, 1.0 / (2.0 * n_order))
        expected_f6 = fc * math.pow(math.pow(10.0, 0.6) - 1.0, 1.0 / (2.0 * n_order))
        expected_f10 = fc * math.pow(math.pow(10.0, 1.0) - 1.0, 1.0 / (2.0 * n_order))

        assert res.f3_high_hz is not None
        assert abs(res.f3_high_hz - expected_f3) < 0.5

        assert res.f6_high_hz is not None
        assert abs(res.f6_high_hz - expected_f6) < 0.5

        assert res.f10_high_hz is not None
        assert abs(res.f10_high_hz - expected_f10) < 0.5

    def test_golden_outermost_crossing_policy_disambiguation(self) -> None:
        """Verify outermost crossing policy correctly disambiguates rolloff from internal notch dips."""
        # Low frequency rolloff drops below 82 dB at exactly 60 Hz.
        # Internal narrow notch dips to 78 dB at 150 Hz but recovers to 85 dB by 200 Hz.
        freq_list = [20.0, 40.0, 60.0, 80.0, 100.0, 130.0, 150.0, 170.0, 200.0, 500.0, 1000.0, 2000.0]
        mag_list =  [70.0, 80.0, 82.0, 85.0,  85.0,  85.0,  78.0,  85.0,  85.0,  85.0,   85.0,   85.0]

        frd = FrequencyResponseData(
            frequencies_hz=np.array(freq_list, dtype=np.float64),
            magnitude_db=np.array(mag_list, dtype=np.float64),
        )

        res = calculate_response_metrics(frd, passband_hz=(500.0, 1500.0))

        assert abs(res.passband_sensitivity_db - 85.0) < 1e-12
        assert res.f3_low_hz is not None
        assert abs(res.f3_low_hz - 60.0) < 1e-4

    def test_golden_boundary_interpolation(self) -> None:
        """Verify exact boundary interpolation when passband limits fall strictly between discrete bins."""
        # Grid at 100 Hz (80 dB) and 200 Hz (90 dB).
        # Midpoint on log10 scale: f = 10^( (log10(100) + log10(200))/2 ) = sqrt(20000) = 141.421356 Hz
        # Interpolated magnitude at sqrt(20000) must be exactly 85.0 dB
        f_mid = math.sqrt(100.0 * 200.0)
        freqs = np.array([50.0, 100.0, 200.0, 400.0], dtype=np.float64)
        mags = np.array([70.0, 80.0, 90.0, 100.0], dtype=np.float64)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(100.0, f_mid))
        # Passband is [100, f_mid]. At 100 Hz, mag = 80 dB. At f_mid, mag = 85 dB.
        # Max is 85 dB, min is 80 dB -> Ripple is 5.0 dB
        assert abs(res.passband_ripple_db - 5.0) < 1e-12

    def test_golden_fractional_octave_smoothing_invariance_on_flat(self) -> None:
        """Verify fractional-octave smoothing leaves an analytical flat response perfectly invariant."""
        freqs = np.geomspace(20.0, 20000.0, 300)
        mags = np.full_like(freqs, 84.0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        smoothed = smooth_frequency_response(frd, mode=SmoothingMode.OCTAVE_1_3)
        np.testing.assert_allclose(smoothed.magnitude_db, 84.0, atol=1e-12)

    def test_golden_no_crossing_returns_none(self) -> None:
        """Verify that when the response never attenuates by 3/6/10 dB, None is returned."""
        freqs = np.geomspace(100.0, 5000.0, 50)
        mags = np.full_like(freqs, 85.0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(500.0, 2000.0))

        assert res.f3_low_hz is None
        assert res.f3_high_hz is None
        assert res.f6_low_hz is None
        assert res.f6_high_hz is None
        assert res.f10_low_hz is None
        assert res.f10_high_hz is None

    def test_golden_deterministic_repeated_evaluation(self) -> None:
        """Verify repeated evaluation produces identical results."""
        freqs = np.geomspace(20.0, 20000.0, 100)
        mags = 85.0 + 3.0 * np.sin(np.linspace(0, 10, 100))
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res1 = calculate_response_metrics(frd)
        res2 = calculate_response_metrics(frd)

        assert res1.passband_sensitivity_db == res2.passband_sensitivity_db
        assert res1.spectral_tilt_db_per_oct == res2.spectral_tilt_db_per_oct
        assert res1.passband_ripple_db == res2.passband_ripple_db
