"""AcoustiForge Acoustic Target Curve Evaluation Mathematics.

Pure deterministic interpolation and evaluation of acoustic target curves.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3B_ACOUSTIC_DOMAIN_VALUE_TYPES_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import math
from typing import Sequence, Union
import numpy as np

from ..contracts.validation import InvalidParameterError
from ..domain.specifications import AcousticTargetCurve


def _evaluate_scalar_target(curve: AcousticTargetCurve, freq: float) -> float:
    """Evaluate target curve magnitude at a single scalar frequency."""
    if not isinstance(freq, (int, float)) or isinstance(freq, bool) or not math.isfinite(freq) or freq <= 0.0:
        raise InvalidParameterError(f"Target curve evaluation frequency must be a positive finite float, got {freq!r}.")

    f = float(freq)
    pts = curve.points
    f_min, m_first = pts[0]
    f_max, m_last = pts[-1]

    # Boundary clamping
    if f <= f_min:
        return float(m_first)
    if f >= f_max:
        return float(m_last)

    # Log10-domain linear interpolation
    log_f = math.log10(f)
    for i in range(len(pts) - 1):
        f0, m0 = pts[i]
        f1, m1 = pts[i + 1]
        if f0 <= f <= f1:
            log_f0 = math.log10(f0)
            log_f1 = math.log10(f1)
            t = (log_f - log_f0) / (log_f1 - log_f0)
            return float(m0 + t * (m1 - m0))

    return float(m_last)


def evaluate_target_curve(
    curve: AcousticTargetCurve,
    frequency_hz: Union[float, int, Sequence[float], np.ndarray],
) -> Union[float, np.ndarray]:
    """Evaluate target curve magnitude in dB at specified frequency or frequencies.

    Interpolation Contract:
    - Domain: log10(frequency)
    - Method: Piecewise linear interpolation in log-frequency
    - Below minimum frequency: clamped to first target point magnitude
    - Above maximum frequency: clamped to last target point magnitude

    Args:
        curve: AcousticTargetCurve value object.
        frequency_hz: Scalar frequency or array/sequence of frequencies in Hz.

    Returns:
        Interpolated magnitude in dB as a float (if input was scalar) or 1D np.ndarray.

    Raises:
        InvalidParameterError: If curve is invalid or frequencies are non-positive / non-finite.
    """
    if not isinstance(curve, AcousticTargetCurve):
        raise InvalidParameterError(f"Expected AcousticTargetCurve instance, got {type(curve)!r}.")

    if isinstance(frequency_hz, (int, float)) and not isinstance(frequency_hz, bool):
        return _evaluate_scalar_target(curve, float(frequency_hz))

    # Array / sequence evaluation
    if isinstance(frequency_hz, (list, tuple, np.ndarray)):
        arr = np.asarray(frequency_hz, dtype=np.float64)
        if arr.ndim == 0:
            return _evaluate_scalar_target(curve, float(arr.item()))
        if arr.ndim != 1:
            raise InvalidParameterError(f"Frequencies array must be 1-dimensional, got shape {arr.shape}.")

        if not np.all(np.isfinite(arr)) or not np.all(arr > 0.0):
            raise InvalidParameterError("All frequencies must be positive finite numbers.")

        pts = curve.points
        src_f = np.array([p[0] for p in pts], dtype=np.float64)
        src_m = np.array([p[1] for p in pts], dtype=np.float64)
        log_src_f = np.log10(src_f)
        log_target_f = np.log10(arr)

        # np.interp performs linear interpolation and clamps out-of-range values to left/right bounds
        interpolated = np.interp(log_target_f, log_src_f, src_m, left=src_m[0], right=src_m[-1])
        return interpolated

    raise InvalidParameterError(
        f"frequency_hz must be a float, int, Sequence[float], or ndarray, got {type(frequency_hz)!r}."
    )
