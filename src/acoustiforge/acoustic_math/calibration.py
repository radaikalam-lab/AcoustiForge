"""AcoustiForge Microphone Calibration Mathematics.

Pure deterministic application of microphone calibration curves to acoustic measurements.

Normative Authority:
- docs/contracts/MICROPHONE_CALIBRATION_CONTRACT.md
- docs/phases/PHASE_4A_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from enum import Enum
from typing import Optional
import numpy as np

from ..contracts.validation import AcoustiForgeError, InvalidParameterError
from ..domain.measurements import FrequencyResponseData


class CalibrationBoundaryPolicy(str, Enum):
    """Policy for handling measurement frequencies outside calibration curve frequency bounds."""
    CLAMP = "clamp"
    ZERO_PAD = "zero_pad"
    STRICT = "strict"


class CalibrationOutOfRangeError(AcoustiForgeError):
    """Raised when measurement frequencies exceed calibration bounds under STRICT boundary policy."""
    pass


def apply_microphone_calibration(
    raw_measurement: FrequencyResponseData,
    calibration_data: FrequencyResponseData,
    boundary_policy: CalibrationBoundaryPolicy = CalibrationBoundaryPolicy.CLAMP,
    apply_phase_correction: bool = False,
) -> FrequencyResponseData:
    """Apply microphone calibration correction to a raw frequency response measurement.

    Mathematical definition:
        M_corrected(f) = M_raw(f) - M_cal(f)  [dB]
        phi_corrected(f) = phi_raw(f) - phi_cal(f)  [rad, when apply_phase_correction is True and valid phase exists]

    Args:
        raw_measurement: Raw measured FrequencyResponseData.
        calibration_data: Microphone calibration FrequencyResponseData.
        boundary_policy: Policy for frequencies outside calibration bounds (CLAMP, ZERO_PAD, STRICT).
        apply_phase_correction: If True and calibration_data contains phase, subtracts calibration phase.
            Defaults to False (magnitude-only calibration is the normal Phase 4A case).

    Returns:
        New immutable FrequencyResponseData with calibrated magnitude and phase.

    Raises:
        InvalidParameterError: If inputs are not FrequencyResponseData instances or policy is invalid.
        CalibrationOutOfRangeError: If boundary_policy is STRICT and raw measurement exceeds calibration bounds.
    """
    if not isinstance(raw_measurement, FrequencyResponseData):
        raise InvalidParameterError(f"Expected raw_measurement as FrequencyResponseData, got {type(raw_measurement)!r}.")

    if not isinstance(calibration_data, FrequencyResponseData):
        raise InvalidParameterError(f"Expected calibration_data as FrequencyResponseData, got {type(calibration_data)!r}.")

    if isinstance(boundary_policy, str):
        try:
            boundary_policy = CalibrationBoundaryPolicy(boundary_policy.lower())
        except ValueError as err:
            raise InvalidParameterError(f"Unsupported boundary policy: {boundary_policy!r}") from err

    f_raw = np.array(raw_measurement.frequencies_hz, dtype=np.float64)
    m_raw = np.array(raw_measurement.magnitude_db, dtype=np.float64)
    phi_raw = raw_measurement.phase_rad

    f_cal = np.array(calibration_data.frequencies_hz, dtype=np.float64)
    m_cal = np.array(calibration_data.magnitude_db, dtype=np.float64)
    phi_cal = calibration_data.phase_rad

    f_cal_min, f_cal_max = f_cal[0], f_cal[-1]

    # Handle STRICT boundary policy
    if boundary_policy == CalibrationBoundaryPolicy.STRICT:
        raw_min, raw_max = f_raw[0], f_raw[-1]
        if raw_min < f_cal_min or raw_max > f_cal_max:
            raise CalibrationOutOfRangeError(
                f"Measurement frequency span [{raw_min:.1f}, {raw_max:.1f}] Hz exceeds "
                f"calibration bounds [{f_cal_min:.1f}, {f_cal_max:.1f}] Hz under STRICT policy."
            )

    # Log10-domain linear interpolation
    log_f_raw = np.log10(f_raw)
    log_f_cal = np.log10(f_cal)

    if boundary_policy in (CalibrationBoundaryPolicy.CLAMP, CalibrationBoundaryPolicy.STRICT):
        interp_cal_mag = np.interp(log_f_raw, log_f_cal, m_cal, left=m_cal[0], right=m_cal[-1])
    elif boundary_policy == CalibrationBoundaryPolicy.ZERO_PAD:
        interp_cal_mag = np.interp(log_f_raw, log_f_cal, m_cal, left=0.0, right=0.0)
    else:
        raise InvalidParameterError(f"Unhandled boundary policy: {boundary_policy!r}")

    # Magnitude subtraction: M_corrected = M_raw - M_cal
    corrected_mag = m_raw - interp_cal_mag

    # Phase correction (only when explicitly declared and compatible calibration phase exists)
    corrected_phase: Optional[np.ndarray] = None
    if phi_raw is not None:
        if apply_phase_correction and phi_cal is not None:
            phi_cal_arr = np.array(phi_cal, dtype=np.float64)
            if boundary_policy in (CalibrationBoundaryPolicy.CLAMP, CalibrationBoundaryPolicy.STRICT):
                interp_cal_phase = np.interp(log_f_raw, log_f_cal, phi_cal_arr, left=phi_cal_arr[0], right=phi_cal_arr[-1])
            else:
                interp_cal_phase = np.interp(log_f_raw, log_f_cal, phi_cal_arr, left=0.0, right=0.0)
            corrected_phase = np.array(phi_raw, dtype=np.float64) - interp_cal_phase
        else:
            # Preserve raw phase unmodified when magnitude-only calibration
            corrected_phase = np.copy(phi_raw)

    return FrequencyResponseData(
        frequencies_hz=f_raw,
        magnitude_db=corrected_mag,
        phase_rad=corrected_phase,
    )
