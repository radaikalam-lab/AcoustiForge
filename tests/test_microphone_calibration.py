"""Tests for Microphone Calibration Mathematics.

Normative Authority:
- docs/contracts/MICROPHONE_CALIBRATION_CONTRACT.md
- docs/phases/PHASE_4A_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.calibration import (
    CalibrationBoundaryPolicy,
    CalibrationOutOfRangeError,
    apply_microphone_calibration,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.io.parser import parse_measurement_file


class TestMicrophoneCalibration:
    """Test suite verifying mathematical correctness of microphone calibration."""

    def test_exact_grid_magnitude_and_phase_subtraction(self) -> None:
        """Verify M_corrected = M_raw - M_cal and phi_corrected = phi_raw - phi_cal on exact grid."""
        freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
        raw_mags = np.array([85.0, 90.0, 88.0], dtype=np.float64)
        raw_phase = np.array([0.1, 0.2, 0.3], dtype=np.float64)

        cal_mags = np.array([0.5, -1.0, 2.0], dtype=np.float64)
        cal_phase = np.array([0.05, -0.05, 0.1], dtype=np.float64)

        raw_frd = FrequencyResponseData(
            frequencies_hz=freqs,
            magnitude_db=raw_mags,
            phase_rad=raw_phase,
        )
        cal_frd = FrequencyResponseData(
            frequencies_hz=freqs,
            magnitude_db=cal_mags,
            phase_rad=cal_phase,
        )

        # Apply calibration with phase enabled
        result = apply_microphone_calibration(
            raw_measurement=raw_frd,
            calibration_data=cal_frd,
            apply_phase_correction=True,
        )

        # Independent golden values
        expected_mags = np.array([85.0 - 0.5, 90.0 - (-1.0), 88.0 - 2.0])  # [84.5, 91.0, 86.0]
        expected_phase = np.array([0.1 - 0.05, 0.2 - (-0.05), 0.3 - 0.1])  # [0.05, 0.25, 0.2]

        np.testing.assert_allclose(result.frequencies_hz, freqs)
        np.testing.assert_allclose(result.magnitude_db, expected_mags, atol=1e-12)
        assert result.phase_rad is not None
        np.testing.assert_allclose(result.phase_rad, expected_phase, atol=1e-12)

    def test_magnitude_only_calibration_ignores_phase_by_default(self) -> None:
        """Verify magnitude-only calibration retains raw phase when apply_phase_correction=False."""
        freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
        raw_mags = np.array([85.0, 90.0, 88.0], dtype=np.float64)
        raw_phase = np.array([0.1, 0.2, 0.3], dtype=np.float64)

        cal_mags = np.array([1.0, 2.0, 3.0], dtype=np.float64)
        cal_phase = np.array([0.5, 0.5, 0.5], dtype=np.float64)

        raw_frd = FrequencyResponseData(
            frequencies_hz=freqs,
            magnitude_db=raw_mags,
            phase_rad=raw_phase,
        )
        cal_frd = FrequencyResponseData(
            frequencies_hz=freqs,
            magnitude_db=cal_mags,
            phase_rad=cal_phase,
        )

        result = apply_microphone_calibration(
            raw_measurement=raw_frd,
            calibration_data=cal_frd,
            apply_phase_correction=False,
        )

        expected_mags = np.array([84.0, 88.0, 85.0])
        np.testing.assert_allclose(result.magnitude_db, expected_mags, atol=1e-12)
        assert result.phase_rad is not None
        # Raw phase preserved unchanged
        np.testing.assert_allclose(result.phase_rad, raw_phase, atol=1e-12)

    def test_log_frequency_interpolation(self) -> None:
        """Verify log-frequency interpolation between calibration anchor points."""
        cal_freqs = np.array([100.0, 1000.0], dtype=np.float64)
        cal_mags = np.array([0.0, 10.0], dtype=np.float64)
        cal_frd = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        # Geometric midpoint between 100 and 1000 is sqrt(100*1000) = sqrt(100000) = 316.22776601683796
        # At geometric midpoint, log-linear interpolation must yield exactly (0 + 10) / 2 = 5.0 dB
        geom_mid = math.sqrt(100.0 * 1000.0)
        raw_freqs = np.array([100.0, geom_mid, 1000.0], dtype=np.float64)
        raw_mags = np.array([90.0, 90.0, 90.0], dtype=np.float64)
        raw_frd = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

        result = apply_microphone_calibration(
            raw_measurement=raw_frd,
            calibration_data=cal_frd,
        )

        # Golden expectation:
        # at 100 Hz: 90.0 - 0.0 = 90.0 dB
        # at geom_mid: 90.0 - 5.0 = 85.0 dB
        # at 1000 Hz: 90.0 - 10.0 = 80.0 dB
        expected_mags = np.array([90.0, 85.0, 80.0])
        np.testing.assert_allclose(result.magnitude_db, expected_mags, atol=1e-12)

    def test_boundary_policy_clamp(self) -> None:
        """Verify CLAMP boundary policy holds edge calibration values outside calibration span."""
        cal_freqs = np.array([100.0, 1000.0], dtype=np.float64)
        cal_mags = np.array([1.5, 3.5], dtype=np.float64)
        cal_frd = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        raw_freqs = np.array([20.0, 50.0, 100.0, 1000.0, 5000.0, 20000.0], dtype=np.float64)
        raw_mags = np.array([80.0, 82.0, 85.0, 90.0, 88.0, 84.0], dtype=np.float64)
        raw_frd = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

        result = apply_microphone_calibration(
            raw_measurement=raw_frd,
            calibration_data=cal_frd,
            boundary_policy=CalibrationBoundaryPolicy.CLAMP,
        )

        # Expected calibration offsets:
        # for f <= 100 Hz: cal = 1.5 dB
        # for f >= 1000 Hz: cal = 3.5 dB
        expected_mags = np.array([
            80.0 - 1.5,  # 78.5
            82.0 - 1.5,  # 80.5
            85.0 - 1.5,  # 83.5
            90.0 - 3.5,  # 86.5
            88.0 - 3.5,  # 84.5
            84.0 - 3.5,  # 80.5
        ])
        np.testing.assert_allclose(result.magnitude_db, expected_mags, atol=1e-12)

    def test_boundary_policy_zero_pad(self) -> None:
        """Verify ZERO_PAD boundary policy applies 0.0 dB correction outside calibration span."""
        cal_freqs = np.array([100.0, 1000.0], dtype=np.float64)
        cal_mags = np.array([2.0, 4.0], dtype=np.float64)
        cal_frd = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        raw_freqs = np.array([20.0, 100.0, 1000.0, 20000.0], dtype=np.float64)
        raw_mags = np.array([80.0, 85.0, 90.0, 84.0], dtype=np.float64)
        raw_frd = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

        result = apply_microphone_calibration(
            raw_measurement=raw_frd,
            calibration_data=cal_frd,
            boundary_policy=CalibrationBoundaryPolicy.ZERO_PAD,
        )

        # Expected:
        # at 20 Hz: cal = 0.0 -> 80.0 - 0 = 80.0
        # at 100 Hz: cal = 2.0 -> 85.0 - 2.0 = 83.0
        # at 1000 Hz: cal = 4.0 -> 90.0 - 4.0 = 86.0
        # at 20000 Hz: cal = 0.0 -> 84.0 - 0 = 84.0
        expected_mags = np.array([80.0, 83.0, 86.0, 84.0])
        np.testing.assert_allclose(result.magnitude_db, expected_mags, atol=1e-12)

    def test_boundary_policy_strict_raises_out_of_range(self) -> None:
        """Verify STRICT boundary policy raises CalibrationOutOfRangeError on out-of-range raw points."""
        cal_freqs = np.array([100.0, 1000.0], dtype=np.float64)
        cal_mags = np.array([2.0, 4.0], dtype=np.float64)
        cal_frd = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        raw_freqs = np.array([50.0, 100.0, 500.0, 1000.0], dtype=np.float64)
        raw_mags = np.array([80.0, 85.0, 88.0, 90.0], dtype=np.float64)
        raw_frd = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

        with pytest.raises(CalibrationOutOfRangeError, match="exceeds calibration bounds"):
            apply_microphone_calibration(
                raw_measurement=raw_frd,
                calibration_data=cal_frd,
                boundary_policy=CalibrationBoundaryPolicy.STRICT,
            )

    def test_input_immutability(self) -> None:
        """Verify that input measurement and calibration objects are not mutated."""
        raw_freqs = np.array([100.0, 1000.0], dtype=np.float64)
        raw_mags = np.array([85.0, 90.0], dtype=np.float64)
        raw_frd = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

        cal_freqs = np.array([100.0, 1000.0], dtype=np.float64)
        cal_mags = np.array([1.0, 2.0], dtype=np.float64)
        cal_frd = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        orig_raw_mags = raw_frd.magnitude_db.copy()
        orig_cal_mags = cal_frd.magnitude_db.copy()

        _ = apply_microphone_calibration(raw_frd, cal_frd)

        np.testing.assert_array_equal(raw_frd.magnitude_db, orig_raw_mags)
        np.testing.assert_array_equal(cal_frd.magnitude_db, orig_cal_mags)

    def test_deterministic_repeated_execution(self) -> None:
        """Verify repeated execution produces byte-identical float arrays."""
        raw_freqs = np.geomspace(20.0, 20000.0, 50)
        raw_mags = 85.0 + 5.0 * np.sin(np.linspace(0, 10, 50))
        raw_frd = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

        cal_freqs = np.array([20.0, 100.0, 1000.0, 10000.0, 20000.0])
        cal_mags = np.array([0.5, 0.2, 0.0, 0.8, 1.5])
        cal_frd = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        res1 = apply_microphone_calibration(raw_frd, cal_frd)
        res2 = apply_microphone_calibration(raw_frd, cal_frd)

        np.testing.assert_array_equal(res1.frequencies_hz, res2.frequencies_hz)
        np.testing.assert_array_equal(res1.magnitude_db, res2.magnitude_db)
