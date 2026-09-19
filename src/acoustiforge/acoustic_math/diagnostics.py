"""AcoustiForge Acoustic Measurement Quality Diagnostics.

Normative Authority:
- docs/contracts/MEASUREMENT_DIAGNOSTICS_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional, Sequence, Tuple, Union
import numpy as np

from ..contracts.validation import InvalidParameterError
from ..domain.measurements import FrequencyResponseData, ImpulseResponseData
from .gating import GatedImpulseResult, transform_impulse_to_frequency_response


class DiagnosticFlag(str, Enum):
    """Quality diagnostic classification flags."""
    CLEAN = "CLEAN"
    LOW_FREQUENCY_RESOLUTION_LIMIT = "LOW_FREQUENCY_RESOLUTION_LIMIT"
    POOR_SNR_WARNING = "POOR_SNR_WARNING"
    CRITICAL_NOISE_FLOOR_ERROR = "CRITICAL_NOISE_FLOOR_ERROR"
    REFLECTION_CONTAMINATION_WARNING = "REFLECTION_CONTAMINATION_WARNING"
    PHASE_DISCONTINUITY_WARNING = "PHASE_DISCONTINUITY_WARNING"


@dataclass(frozen=True, slots=True)
class MeasurementDiagnosticReport:
    """Immutable diagnostic evaluation report for acoustic measurements."""
    is_valid: bool
    snr_db: float
    f_valid_min_hz: float
    flags: Tuple[DiagnosticFlag, ...]
    estimated_reflection_ms: Optional[float] = None


def _detect_reflection_comb_notches(
    freqs: np.ndarray,
    mags: np.ndarray,
    f_min_valid: float,
) -> Tuple[bool, Optional[float]]:
    """Scan magnitude spectrum for periodic reflection comb notches.

    Criteria:
    - Minimum depth >= 6.0 dB relative to adjacent peaks
    - Narrow bandwidth Q >= 10.0
    - >= 3 consecutive periodic notches with spacing tolerance <= 15%
    """
    valid_mask = freqs >= f_min_valid
    if np.count_nonzero(valid_mask) < 10:
        return False, None

    f_sub = freqs[valid_mask]
    m_sub = mags[valid_mask]
    n_pts = len(f_sub)

    # Identify local minima
    notch_freqs: list[float] = []

    for i in range(1, n_pts - 1):
        if m_sub[i] < m_sub[i - 1] and m_sub[i] < m_sub[i + 1]:
            f0 = f_sub[i]
            m0 = m_sub[i]

            # Find left peak
            j_left = i - 1
            while j_left > 0 and m_sub[j_left - 1] > m_sub[j_left]:
                j_left -= 1
            left_peak_mag = m_sub[j_left]

            # Find right peak
            j_right = i + 1
            while j_right < n_pts - 1 and m_sub[j_right + 1] > m_sub[j_right]:
                j_right += 1
            right_peak_mag = m_sub[j_right]

            depth = min(left_peak_mag, right_peak_mag) - m0
            if depth >= 6.0:
                # Estimate -3dB bandwidth relative to notch floor
                m_3db = m0 + 3.0
                # Scan left flank for crossing
                k_l = i
                while k_l > j_left and m_sub[k_l] < m_3db:
                    k_l -= 1
                f_l = f_sub[k_l]

                # Scan right flank for crossing
                k_r = i
                while k_r < j_right and m_sub[k_r] < m_3db:
                    k_r += 1
                f_r = f_sub[k_r]

                bw = max(f_r - f_l, 1e-3)
                q_val = f0 / bw
                if q_val >= 10.0:
                    notch_freqs.append(f0)

    if len(notch_freqs) < 3:
        return False, None

    # Check periodic spacing across consecutive triples
    for start_idx in range(len(notch_freqs) - 2):
        triplet = notch_freqs[start_idx : start_idx + 3]
        d1 = triplet[1] - triplet[0]
        d2 = triplet[2] - triplet[1]
        mean_d = (d1 + d2) / 2.0
        if mean_d > 10.0:  # Minimum 10 Hz notch spacing
            if abs(d1 - mean_d) / mean_d <= 0.15 and abs(d2 - mean_d) / mean_d <= 0.15:
                est_delay_sec = 1.0 / mean_d
                return True, float(est_delay_sec * 1000.0)

    return False, None


def evaluate_measurement_quality(
    impulse: Optional[ImpulseResponseData] = None,
    frequency_response: Optional[FrequencyResponseData] = None,
    gated_result: Optional[GatedImpulseResult] = None,
) -> MeasurementDiagnosticReport:
    """Evaluate objective quality metrics and diagnostics over an acoustic measurement.

    Args:
        impulse: Optional raw ImpulseResponseData.
        frequency_response: Optional FrequencyResponseData.
        gated_result: Optional GatedImpulseResult.

    Returns:
        Immutable MeasurementDiagnosticReport containing validation status, SNR, flags, and reflection estimates.

    Raises:
        InvalidParameterError: If no valid input object is provided.
    """
    if impulse is None and frequency_response is None and gated_result is None:
        raise InvalidParameterError("At least one of impulse, frequency_response, or gated_result must be provided.")

    target_ir = gated_result.gated_impulse if gated_result is not None else impulse
    flags: list[DiagnosticFlag] = []
    is_valid = True
    snr_db = 100.0
    f_valid_min = 20.0

    # 1. Low-Frequency Validity Boundary
    if gated_result is not None:
        f_valid_min = gated_result.f_min_valid_hz
    elif target_ir is not None:
        f_valid_min = float(1.0 / target_ir.duration_seconds)
    elif frequency_response is not None:
        f_valid_min = float(frequency_response.frequencies_hz[0])

    # 2. SNR Evaluation from Time-Domain Impulse
    if target_ir is not None:
        samples = target_ir.samples
        n_peak = target_ir.peak_index
        n_samples = target_ir.num_samples

        if gated_result is not None:
            n_noise_end = max(1, gated_result.gate_start_index)
        else:
            n_noise_end = max(1, n_peak // 2)

        # Minimum 8 samples for noise estimation; fallback to first 5% if peak is very early
        if n_noise_end < 8:
            n_noise_end = max(2, int(n_samples * 0.05))

        noise_region = samples[:n_noise_end]
        rms_noise = float(np.sqrt(np.mean(noise_region ** 2)))
        peak_amp = float(abs(samples[n_peak]))

        if rms_noise > 0.0:
            snr_db = float(20.0 * math.log10(max(peak_amp, 1e-12) / max(rms_noise, 1e-12)))
        else:
            snr_db = 120.0

        if snr_db < 6.0:
            flags.append(DiagnosticFlag.CRITICAL_NOISE_FLOOR_ERROR)
            is_valid = False
        elif snr_db < 20.0:
            flags.append(DiagnosticFlag.POOR_SNR_WARNING)

    # 3. Frequency Response & Reflection Notch Detection
    target_frd = frequency_response
    if target_frd is None and target_ir is not None:
        target_frd = transform_impulse_to_frequency_response(target_ir)

    est_refl_ms: Optional[float] = None
    if target_frd is not None:
        freqs = target_frd.frequencies_hz
        mags = target_frd.magnitude_db
        has_refl, est_refl_ms = _detect_reflection_comb_notches(freqs, mags, f_valid_min)
        if has_refl:
            flags.append(DiagnosticFlag.REFLECTION_CONTAMINATION_WARNING)

        # Phase discontinuity check if phase is present
        if target_frd.phase_rad is not None:
            phase_diffs = np.abs(np.diff(target_frd.phase_rad))
            # Phase wrap jump is expected, but check if there are rapid oscillations (> 3 rad consecutive)
            if np.count_nonzero(phase_diffs > math.pi * 0.95) > (len(phase_diffs) * 0.2):
                flags.append(DiagnosticFlag.PHASE_DISCONTINUITY_WARNING)

    if not flags:
        flags.append(DiagnosticFlag.CLEAN)

    return MeasurementDiagnosticReport(
        is_valid=is_valid,
        snr_db=snr_db,
        f_valid_min_hz=f_valid_min,
        flags=tuple(flags),
        estimated_reflection_ms=est_refl_ms,
    )
