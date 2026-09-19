"""AcoustiForge Acoustic Response Analysis & Quantitative Metrics.

Pure deterministic mathematical operations for extracting quantitative metrics from
frequency response data, including passband sensitivity, bandwidth cutoffs, target error,
spectral tilt, passband ripple, and fractional-octave smoothing.

Normative Authority:
- docs/contracts/ACOUSTIC_METRICS_CONTRACT.md
- docs/phases/PHASE_4B_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional, Sequence, Tuple
import numpy as np

from ..contracts.validation import InvalidParameterError
from ..domain.measurements import FrequencyResponseData
from ..domain.specifications import AcousticTargetCurve
from .target_curve import evaluate_target_curve


class SmoothingMode(str, Enum):
    """Supported fractional-octave smoothing resolutions."""
    NONE = "none"
    OCTAVE_1_3 = "1/3"
    OCTAVE_1_6 = "1/6"
    OCTAVE_1_12 = "1/12"
    OCTAVE_1_24 = "1/24"


_SMOOTHING_N_MAP = {
    SmoothingMode.OCTAVE_1_3: 3.0,
    SmoothingMode.OCTAVE_1_6: 6.0,
    SmoothingMode.OCTAVE_1_12: 12.0,
    SmoothingMode.OCTAVE_1_24: 24.0,
}


@dataclass(frozen=True, slots=True)
class AcousticMetricsResult:
    """Immutable mathematical analysis result container for acoustic metrics."""
    passband_sensitivity_db: float
    f3_low_hz: Optional[float]
    f3_high_hz: Optional[float]
    f6_low_hz: Optional[float]
    f6_high_hz: Optional[float]
    f10_low_hz: Optional[float]
    f10_high_hz: Optional[float]
    rms_target_error_db: Optional[float]
    peak_positive_error_db: Optional[float]
    peak_negative_error_db: Optional[float]
    spectral_tilt_db_per_oct: float
    passband_ripple_db: float
    passband_range_hz: Tuple[float, float]


def smooth_frequency_response(
    measurement: FrequencyResponseData,
    mode: SmoothingMode | str,
) -> FrequencyResponseData:
    """Apply log-Gaussian fractional-octave smoothing to FrequencyResponseData.

    Args:
        measurement: Immutable FrequencyResponseData instance.
        mode: Fractional-octave smoothing mode (NONE, 1/3, 1/6, 1/12, 1/24).

    Returns:
        New immutable FrequencyResponseData with smoothed magnitude (phase unmodified).

    Raises:
        InvalidParameterError: If measurement or smoothing mode is invalid.
    """
    if not isinstance(measurement, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData, got {type(measurement)!r}.")

    if isinstance(mode, str):
        try:
            mode = SmoothingMode(mode.lower() if mode != "1/3" and mode != "1/6" and mode != "1/12" and mode != "1/24" else mode)
        except ValueError as err:
            raise InvalidParameterError(f"Unsupported smoothing mode: {mode!r}") from err

    if mode == SmoothingMode.NONE:
        return measurement

    n_oct = _SMOOTHING_N_MAP.get(mode)
    if n_oct is None:
        return measurement

    freqs = np.array(measurement.frequencies_hz, dtype=np.float64)
    mags = np.array(measurement.magnitude_db, dtype=np.float64)
    log2_f = np.log2(freqs)

    # Standard deviation in octaves: sigma = 1 / (2.35482 * N)
    sigma = 1.0 / (2.3548200450309493 * n_oct)
    two_sigma_sq = 2.0 * sigma * sigma
    trunc_radius = 3.0 * sigma

    num_pts = len(freqs)
    smoothed_mags = np.empty(num_pts, dtype=np.float64)

    for i in range(num_pts):
        center_x = log2_f[i]
        diffs = log2_f - center_x
        # 3-sigma truncation mask
        mask = np.abs(diffs) <= trunc_radius
        sub_diffs = diffs[mask]
        sub_mags = mags[mask]

        weights = np.exp(-(sub_diffs * sub_diffs) / two_sigma_sq)
        weight_sum = np.sum(weights)
        if weight_sum > 0.0:
            smoothed_mags[i] = np.sum(weights * sub_mags) / weight_sum
        else:
            smoothed_mags[i] = mags[i]

    return FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=smoothed_mags,
        phase_rad=measurement.phase_rad,
    )


def _interpolate_mag_log10(freqs: np.ndarray, mags: np.ndarray, target_freq: float) -> float:
    """Interpolate magnitude in dB at target frequency using log10-frequency interpolation."""
    log_f = np.log10(freqs)
    log_target = math.log10(target_freq)
    return float(np.interp(log_target, log_f, mags, left=mags[0], right=mags[-1]))


def _calculate_passband_sensitivity(
    freqs: np.ndarray,
    mags: np.ndarray,
    f_min: float,
    f_max: float,
) -> float:
    """Calculate energy-weighted mean SPL in dB across [f_min, f_max] in log10(frequency) domain."""
    if f_min >= f_max:
        raise InvalidParameterError(f"f_min ({f_min} Hz) must be strictly less than f_max ({f_max} Hz).")

    # Extract internal points within (f_min, f_max)
    mask = (freqs > f_min) & (freqs < f_max)
    sub_f = list(freqs[mask])
    sub_m = list(mags[mask])

    # Interpolate exact endpoints at f_min and f_max
    m_min = _interpolate_mag_log10(freqs, mags, f_min)
    m_max = _interpolate_mag_log10(freqs, mags, f_max)

    grid_f = np.array([f_min] + sub_f + [f_max], dtype=np.float64)
    grid_m = np.array([m_min] + sub_m + [m_max], dtype=np.float64)

    # Convert magnitude dB to linear intensity/energy: I(f) = 10^(M(f) / 10)
    grid_i = np.power(10.0, grid_m / 10.0)
    grid_log_f = np.log10(grid_f)

    # Integrate intensity over log10(f) using trapezoidal rule
    delta_log_f = math.log10(f_max) - math.log10(f_min)
    if hasattr(np, "trapezoid"):
        integral_i = float(np.trapezoid(grid_i, grid_log_f))
    else:
        integral_i = float(np.trapz(grid_i, grid_log_f))

    mean_i = integral_i / delta_log_f
    # Guard against zero or non-positive intensity
    mean_i = max(mean_i, 1e-12)
    return float(10.0 * math.log10(mean_i))


def _find_cutoff_frequency(
    freqs: np.ndarray,
    mags: np.ndarray,
    threshold_db: float,
    f_anchor: float,
    direction: str,
) -> Optional[float]:
    """Find cutoff frequency where response drops below threshold_db under outermost policy.

    Args:
        freqs: Frequency array in Hz (strictly ascending).
        mags: Magnitude array in dB.
        threshold_db: Target attenuation threshold in dB.
        f_anchor: Passband anchor boundary frequency (f_min for low search, f_max for high search).
        direction: 'low' (searching downwards) or 'high' (searching upwards).

    Returns:
        Interpolated cutoff frequency in Hz, or None if threshold is never crossed.
    """
    if direction == "low":
        # Search points up to f_anchor, ordered from lowest frequency up to anchor
        indices = np.where(freqs <= f_anchor)[0]
        if len(indices) < 2:
            return None

        # Outermost policy for low cutoff: find the outermost boundary crossing
        # scanning from the lowest measured frequency upwards towards f_anchor.
        # The first transition from <= threshold_db to > threshold_db marks the entry into operating band.
        for i in range(len(indices) - 1):
            idx_lo = indices[i]
            idx_hi = indices[i + 1]
            m_lo = mags[idx_lo]
            m_hi = mags[idx_hi]

            # Crossing occurs when m_lo <= threshold_db < m_hi
            if m_lo <= threshold_db < m_hi:
                f_lo, f_hi = freqs[idx_lo], freqs[idx_hi]
                log_f_lo, log_f_hi = math.log10(f_lo), math.log10(f_hi)
                t = (threshold_db - m_lo) / (m_hi - m_lo)
                log_cutoff = log_f_lo + t * (log_f_hi - log_f_lo)
                return float(math.pow(10.0, log_cutoff))

        return None

    elif direction == "high":
        # Search points from f_anchor up to highest frequency
        indices = np.where(freqs >= f_anchor)[0]
        if len(indices) < 2:
            return None

        # Outermost policy for high cutoff: find the outermost boundary crossing
        # scanning from highest measured frequency downwards towards f_anchor.
        # The first transition from <= threshold_db (at higher f) to > threshold_db (at lower f) marks entry into operating band.
        for i in range(len(indices) - 1, 0, -1):
            idx_hi = indices[i]
            idx_lo = indices[i - 1]
            m_hi = mags[idx_hi]
            m_lo = mags[idx_lo]

            # Crossing occurs when m_hi <= threshold_db < m_lo
            if m_hi <= threshold_db < m_lo:
                f_lo, f_hi = freqs[idx_lo], freqs[idx_hi]
                log_f_lo, log_f_hi = math.log10(f_lo), math.log10(f_hi)
                t = (threshold_db - m_lo) / (m_hi - m_lo)
                log_cutoff = log_f_lo + t * (log_f_hi - log_f_lo)
                return float(math.pow(10.0, log_cutoff))

        return None

    return None


def calculate_response_metrics(
    measurement: FrequencyResponseData,
    target_curve: Optional[AcousticTargetCurve] = None,
    passband_hz: Optional[Tuple[float, float]] = None,
    smoothing: SmoothingMode | str = SmoothingMode.NONE,
) -> AcousticMetricsResult:
    """Calculate deterministic quantitative acoustic metrics over a frequency response measurement.

    Args:
        measurement: Immutable FrequencyResponseData instance.
        target_curve: Optional AcousticTargetCurve instance for error tracking.
        passband_hz: Optional (f_min, f_max) tuple in Hz defining the reference passband.
            Defaults to (200.0, 2000.0) Hz, clamped to measurement frequency range.
        smoothing: Optional fractional-octave smoothing mode.

    Returns:
        Immutable AcousticMetricsResult containing all analyzed metric properties.

    Raises:
        InvalidParameterError: If measurement data is invalid or passband bounds are inverted.
    """
    if not isinstance(measurement, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData, got {type(measurement)!r}.")

    if target_curve is not None and not isinstance(target_curve, AcousticTargetCurve):
        raise InvalidParameterError(f"Expected AcousticTargetCurve or None, got {type(target_curve)!r}.")

    # Apply smoothing if requested
    if smoothing != SmoothingMode.NONE:
        data = smooth_frequency_response(measurement, smoothing)
    else:
        data = measurement

    freqs = np.array(data.frequencies_hz, dtype=np.float64)
    mags = np.array(data.magnitude_db, dtype=np.float64)
    f_start_meas, f_end_meas = freqs[0], freqs[-1]

    # Resolve passband bounds
    if passband_hz is None:
        p_min = max(200.0, f_start_meas)
        p_max = min(2000.0, f_end_meas)
        if p_min >= p_max:
            # Narrow bandwidth measurement: use full measured span
            p_min = f_start_meas
            p_max = f_end_meas
    else:
        if not isinstance(passband_hz, (tuple, list)) or len(passband_hz) != 2:
            raise InvalidParameterError(f"passband_hz must be a 2-element tuple (f_min, f_max), got {passband_hz!r}.")
        p_min, p_max = float(passband_hz[0]), float(passband_hz[1])
        if not (math.isfinite(p_min) and math.isfinite(p_max)) or p_min <= 0.0 or p_max <= 0.0:
            raise InvalidParameterError(f"Passband frequencies must be positive finite floats, got ({p_min}, {p_max}).")
        if p_min >= p_max:
            raise InvalidParameterError(f"passband_hz f_min ({p_min} Hz) must be strictly less than f_max ({p_max} Hz).")
        if p_min < f_start_meas or p_max > f_end_meas:
            raise InvalidParameterError(
                f"Declared passband [{p_min:.1f}, {p_max:.1f}] Hz exceeds measurement range [{f_start_meas:.1f}, {f_end_meas:.1f}] Hz."
            )

    # 1. Passband Sensitivity
    s_passband = _calculate_passband_sensitivity(freqs, mags, p_min, p_max)

    # 2. Bandwidth Cutoffs (F3, F6, F10)
    f3_lo = _find_cutoff_frequency(freqs, mags, s_passband - 3.0, p_min, direction="low")
    f3_hi = _find_cutoff_frequency(freqs, mags, s_passband - 3.0, p_max, direction="high")

    f6_lo = _find_cutoff_frequency(freqs, mags, s_passband - 6.0, p_min, direction="low")
    f6_hi = _find_cutoff_frequency(freqs, mags, s_passband - 6.0, p_max, direction="high")

    f10_lo = _find_cutoff_frequency(freqs, mags, s_passband - 10.0, p_min, direction="low")
    f10_hi = _find_cutoff_frequency(freqs, mags, s_passband - 10.0, p_max, direction="high")

    # 3. Target Error
    rms_error: Optional[float] = None
    peak_pos_error: Optional[float] = None
    peak_neg_error: Optional[float] = None

    if target_curve is not None:
        target_pts = target_curve.points
        t_f_min = target_pts[0][0]
        t_f_max = target_pts[-1][0]
        overlap_min = max(f_start_meas, t_f_min)
        overlap_max = min(f_end_meas, t_f_max)

        if overlap_min < overlap_max:
            overlap_mask = (freqs >= overlap_min) & (freqs <= overlap_max)
            if np.any(overlap_mask):
                sub_freqs = freqs[overlap_mask]
                sub_mags = mags[overlap_mask]
                sub_targets = np.array([evaluate_target_curve(target_curve, f) for f in sub_freqs], dtype=np.float64)
                diffs = sub_mags - sub_targets

                rms_error = float(np.sqrt(np.mean(diffs * diffs)))
                peak_pos_error = float(np.max(diffs))
                peak_neg_error = float(np.min(diffs))

    # 4. Spectral Tilt (Unweighted OLS regression of M(f) vs log2(f) across passband or full span)
    log2_f = np.log2(freqs)
    # Fit across the passband region
    pass_mask = (freqs >= p_min) & (freqs <= p_max)
    if np.count_nonzero(pass_mask) >= 2:
        reg_x = log2_f[pass_mask]
        reg_y = mags[pass_mask]
    else:
        reg_x = log2_f
        reg_y = mags

    x_mean = np.mean(reg_x)
    y_mean = np.mean(reg_y)
    denom = np.sum((reg_x - x_mean) ** 2)
    if denom > 0.0:
        tilt = float(np.sum((reg_x - x_mean) * (reg_y - y_mean)) / denom)
    else:
        tilt = 0.0

    # 5. Passband Ripple: max - min within passband (including boundary interpolated points)
    m_pmin = _interpolate_mag_log10(freqs, mags, p_min)
    m_pmax = _interpolate_mag_log10(freqs, mags, p_max)
    pass_mags = list(mags[pass_mask]) + [m_pmin, m_pmax]
    ripple = float(max(pass_mags) - min(pass_mags))

    return AcousticMetricsResult(
        passband_sensitivity_db=s_passband,
        f3_low_hz=f3_lo,
        f3_high_hz=f3_hi,
        f6_low_hz=f6_lo,
        f6_high_hz=f6_hi,
        f10_low_hz=f10_lo,
        f10_high_hz=f10_hi,
        rms_target_error_db=rms_error,
        peak_positive_error_db=peak_pos_error,
        peak_negative_error_db=peak_neg_error,
        spectral_tilt_db_per_oct=tilt,
        passband_ripple_db=ripple,
        passband_range_hz=(p_min, p_max),
    )
