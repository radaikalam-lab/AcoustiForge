"""Unit Tests for Acoustic Measurement Quality Diagnostics.

Normative Authority:
- docs/contracts/MEASUREMENT_DIAGNOSTICS_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.diagnostics import (
    DiagnosticFlag,
    MeasurementDiagnosticReport,
    evaluate_measurement_quality,
)
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain.measurements import FrequencyResponseData, ImpulseResponseData


class TestMeasurementDiagnostics:
    """Test suite for objective measurement quality diagnostics."""

    def test_diagnostic_clean_impulse(self) -> None:
        """Verify clean synthetic impulse returns CLEAN flag and high SNR."""
        samples = np.zeros(200, dtype=np.float64)
        samples[50] = 1.0  # Clean direct impulse
        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=50)

        report = evaluate_measurement_quality(impulse=ir)
        assert isinstance(report, MeasurementDiagnosticReport)
        assert report.is_valid is True
        assert report.snr_db > 40.0
        assert DiagnosticFlag.CLEAN in report.flags
        assert report.estimated_reflection_ms is None

    def test_diagnostic_poor_snr_warning(self) -> None:
        """Verify injected pre-onset noise triggers POOR_SNR_WARNING."""
        samples = np.zeros(200, dtype=np.float64)
        # Pre-onset noise with RMS ~ 0.15 relative to peak 1.0 -> SNR ~ 16.5 dB (< 20 dB)
        np.random.seed(42)
        samples[:50] = np.random.normal(0.0, 0.15, size=50)
        samples[50] = 1.0  # Peak

        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=50)
        report = evaluate_measurement_quality(impulse=ir)

        assert report.is_valid is True
        assert report.snr_db < 20.0
        assert DiagnosticFlag.POOR_SNR_WARNING in report.flags

    def test_diagnostic_critical_noise_floor_error(self) -> None:
        """Verify overwhelming noise floor triggers CRITICAL_NOISE_FLOOR_ERROR and invalidates measurement."""
        samples = np.zeros(200, dtype=np.float64)
        # Pre-onset noise with RMS ~ 0.6 relative to peak 1.0 -> SNR ~ 4.4 dB (< 6 dB)
        samples[:50] = 0.6
        samples[50] = 1.0

        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=50)
        report = evaluate_measurement_quality(impulse=ir)

        assert report.is_valid is False
        assert report.snr_db < 6.0
        assert DiagnosticFlag.CRITICAL_NOISE_FLOOR_ERROR in report.flags

    def test_diagnostic_reflection_comb_filtering_detection(self) -> None:
        """Verify periodic reflection notches trigger REFLECTION_CONTAMINATION_WARNING."""
        # Synthesize frequency response with periodic reflection notches at spacing 500 Hz (tau = 2.0 ms)
        freqs = np.linspace(100.0, 10000.0, 2000)
        # Direct sound + echo delayed by 2.0 ms (0.002 s)
        # H(f) = 1 + 0.8 * e^(-j 2pi f * 0.002)
        # |H(f)|^2 = 1 + 0.64 + 1.6 cos(2pi f * 0.002) = 1.64 + 1.6 cos(2pi f * 0.002)
        # Minima occur when 2pi f * 0.002 = pi, 3pi, 5pi -> f = 250, 750, 1250, 1750, 2250 Hz (spacing 500 Hz)
        # Maxima = 1.8 (5.1 dB), Minima = 0.2 (-14.0 dB) -> Notch depth = 19.1 dB (> 6 dB)
        h_complex = 1.0 + 0.8 * np.exp(-1j * 2.0 * np.pi * freqs * 0.002)
        mags_db = 20.0 * np.log10(np.abs(h_complex))

        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags_db)
        report = evaluate_measurement_quality(frequency_response=frd)

        assert DiagnosticFlag.REFLECTION_CONTAMINATION_WARNING in report.flags
        assert report.estimated_reflection_ms is not None
        # Estimated delay should be ~2.0 ms (within +/- 0.3 ms)
        assert abs(report.estimated_reflection_ms - 2.0) < 0.3

    def test_diagnostic_invalid_parameter_rejection(self) -> None:
        """Verify rejection when no inputs are provided."""
        with pytest.raises(InvalidParameterError):
            evaluate_measurement_quality()
