"""Tests for Phase 4B Acoustic Response Analysis & Quantitative Metrics.

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
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import AcousticTargetCurve


class TestAcousticMetrics:
    """Test suite verifying numerical correctness of acoustic response metrics."""

    def test_ideal_flat_response_metrics(self) -> None:
        """Verify that a perfectly flat 85.0 dB response yields exact sensitivity, zero ripple, zero tilt."""
        freqs = np.geomspace(20.0, 20000.0, 100)
        mags = np.full_like(freqs, 85.0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(200.0, 2000.0))

        assert isinstance(res, AcousticMetricsResult)
        assert abs(res.passband_sensitivity_db - 85.0) < 1e-12
        assert abs(res.passband_ripple_db - 0.0) < 1e-12
        assert abs(res.spectral_tilt_db_per_oct - 0.0) < 1e-12
        assert res.f3_low_hz is None
        assert res.f3_high_hz is None
        assert res.rms_target_error_db is None

    def test_target_error_evaluation(self) -> None:
        """Verify RMS, peak positive, and peak negative target error calculation."""
        freqs = np.array([100.0, 200.0, 500.0, 1000.0, 2000.0], dtype=np.float64)
        mags = np.array([80.0, 84.0, 86.0, 88.0, 82.0], dtype=np.float64)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        target = AcousticTargetCurve(
            name="flat_85",
            points=((100.0, 85.0), (2000.0, 85.0)),
        )

        res = calculate_response_metrics(frd, target_curve=target, passband_hz=(200.0, 1000.0))

        # Expected errors relative to 85.0 dB target:
        # diffs = [-5.0, -1.0, +1.0, +3.0, -3.0]
        # RMS = sqrt((-5^2 + -1^2 + 1^2 + 3^2 + -3^2) / 5) = sqrt((25 + 1 + 1 + 9 + 9)/5) = sqrt(45/5) = sqrt(9) = 3.0 dB
        assert res.rms_target_error_db is not None
        assert abs(res.rms_target_error_db - 3.0) < 1e-12
        assert res.peak_positive_error_db is not None
        assert abs(res.peak_positive_error_db - 3.0) < 1e-12
        assert res.peak_negative_error_db is not None
        assert abs(res.peak_negative_error_db - (-5.0)) < 1e-12

    def test_passband_ripple_calculation(self) -> None:
        """Verify passband ripple calculation includes boundary interpolated points."""
        freqs = np.array([100.0, 300.0, 500.0, 1000.0, 3000.0], dtype=np.float64)
        mags = np.array([80.0, 88.0, 82.0, 90.0, 75.0], dtype=np.float64)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(300.0, 1000.0))
        # Inside [300, 1000], mags are 88.0, 82.0, 90.0
        # max = 90.0, min = 82.0 -> ripple = 8.0 dB
        assert abs(res.passband_ripple_db - 8.0) < 1e-12

    def test_spectral_tilt_calculation(self) -> None:
        """Verify linear regression of M(f) against log2(f)."""
        # Exactly +3.0 dB per octave from 100 Hz (80 dB) to 800 Hz (3 octaves -> 89 dB)
        f0 = 100.0
        freqs = f0 * np.power(2.0, np.linspace(0, 3, 31))
        mags = 80.0 + 3.0 * np.log2(freqs / f0)
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        res = calculate_response_metrics(frd, passband_hz=(100.0, 800.0))
        assert abs(res.spectral_tilt_db_per_oct - 3.0) < 1e-6

    def test_fractional_octave_smoothing(self) -> None:
        """Verify log-Gaussian fractional-octave smoothing produces variance reduction without edge dip."""
        freqs = np.geomspace(20.0, 20000.0, 200)
        # 85 dB mean with +/- 5 dB high frequency noise ripple
        raw_mags = 85.0 + 5.0 * np.sin(np.linspace(0, 40 * np.pi, 200))
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=raw_mags)

        smoothed = smooth_frequency_response(frd, mode=SmoothingMode.OCTAVE_1_3)
        assert isinstance(smoothed, FrequencyResponseData)
        assert smoothed.num_points == frd.num_points

        # Variance of smoothed response must be strictly smaller than raw
        raw_var = float(np.var(frd.magnitude_db))
        smooth_var = float(np.var(smoothed.magnitude_db))
        assert smooth_var < raw_var

        # Mean SPL preserved
        assert abs(np.mean(smoothed.magnitude_db) - 85.0) < 0.5

    def test_input_immutability(self) -> None:
        """Verify that calculate_response_metrics and smooth_frequency_response do not mutate input data."""
        freqs = np.geomspace(100.0, 10000.0, 50)
        mags = 85.0 + np.sin(np.linspace(0, 10, 50))
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        orig_mags = frd.magnitude_db.copy()
        _ = calculate_response_metrics(frd, smoothing=SmoothingMode.OCTAVE_1_6)

        np.testing.assert_array_equal(frd.magnitude_db, orig_mags)

    def test_invalid_parameter_rejection(self) -> None:
        """Verify strict parameter checking."""
        freqs = np.array([100.0, 1000.0])
        mags = np.array([85.0, 85.0])
        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        # Inverted passband
        with pytest.raises(InvalidParameterError, match="must be strictly less than f_max"):
            calculate_response_metrics(frd, passband_hz=(1000.0, 100.0))

        # Passband exceeds measurement bounds
        with pytest.raises(InvalidParameterError, match="exceeds measurement range"):
            calculate_response_metrics(frd, passband_hz=(50.0, 1000.0))

        # Invalid object type
        with pytest.raises(InvalidParameterError):
            calculate_response_metrics("not_a_frd")  # type: ignore
