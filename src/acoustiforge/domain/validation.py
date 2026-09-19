"""AcoustiForge Acoustic Domain Validation and Exceptions.

Normative Authority:
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

import math
from typing import Any, Sequence
import numpy as np

from ..contracts.validation import AcoustiForgeError


class DomainError(AcoustiForgeError):
    """Base exception for all acoustic domain model and control plane errors."""
    pass


class InvalidSpecificationError(DomainError, ValueError):
    """Raised when an acoustic specification or budget is mathematically invalid."""
    pass


class InvalidProfileError(DomainError, ValueError):
    """Raised when a driver or enclosure profile parameter is physically invalid."""
    pass


class InvalidMeasurementError(DomainError, ValueError):
    """Raised when measurement vectors or impulse response arrays are malformed."""
    pass


def validate_frequency_vector(frequencies: Any) -> np.ndarray:
    """Validate and normalize a 1D discrete frequency vector.

    Requirements:
    - 1D numpy array or convertible sequence
    - At least 2 frequency points
    - Strictly positive frequencies (> 0 Hz)
    - Strictly monotonically increasing frequencies
    - All finite values (no NaN, Inf)

    Returns:
        Owned, contiguous, read-only 1D float64 numpy array.
    """
    if not isinstance(frequencies, np.ndarray):
        try:
            frequencies = np.asarray(frequencies, dtype=np.float64)
        except Exception as err:
            raise InvalidMeasurementError(f"Frequencies could not be converted to numpy array: {err}") from err

    if frequencies.ndim != 1:
        raise InvalidMeasurementError(
            f"Frequency vector must be 1-dimensional, got ndim={frequencies.ndim} with shape {frequencies.shape}."
        )

    if frequencies.shape[0] < 2:
        raise InvalidMeasurementError(
            f"Frequency vector must contain at least 2 points, got {frequencies.shape[0]}."
        )

    if not np.all(np.isfinite(frequencies)):
        raise InvalidMeasurementError("Frequency vector contains non-finite values (NaN or Inf).")

    if not np.all(frequencies > 0.0):
        raise InvalidMeasurementError("All frequencies in vector must be strictly positive (> 0 Hz).")

    # Strict monotonicity check: f[k+1] > f[k]
    diffs = np.diff(frequencies)
    if not np.all(diffs > 0.0):
        raise InvalidMeasurementError("Frequency vector must be strictly monotonically increasing.")

    arr = np.array(frequencies, dtype=np.float64, copy=True)
    arr.flags.writeable = False
    return arr


def validate_magnitude_vector(magnitudes: Any, expected_len: int) -> np.ndarray:
    """Validate and normalize a 1D magnitude (dB) response vector.

    Returns:
        Owned, contiguous, read-only 1D float64 numpy array.
    """
    if not isinstance(magnitudes, np.ndarray):
        try:
            magnitudes = np.asarray(magnitudes, dtype=np.float64)
        except Exception as err:
            raise InvalidMeasurementError(f"Magnitudes could not be converted to numpy array: {err}") from err

    if magnitudes.ndim != 1:
        raise InvalidMeasurementError(
            f"Magnitude vector must be 1-dimensional, got ndim={magnitudes.ndim} with shape {magnitudes.shape}."
        )

    if magnitudes.shape[0] != expected_len:
        raise InvalidMeasurementError(
            f"Magnitude vector length ({magnitudes.shape[0]}) does not match frequency vector length ({expected_len})."
        )

    if not np.all(np.isfinite(magnitudes)):
        raise InvalidMeasurementError("Magnitude vector contains non-finite values (NaN or Inf).")

    arr = np.array(magnitudes, dtype=np.float64, copy=True)
    arr.flags.writeable = False
    return arr


def validate_phase_vector(phases: Any, expected_len: int) -> np.ndarray:
    """Validate and normalize a 1D phase (radians) vector.

    Returns:
        Owned, contiguous, read-only 1D float64 numpy array.
    """
    if not isinstance(phases, np.ndarray):
        try:
            phases = np.asarray(phases, dtype=np.float64)
        except Exception as err:
            raise InvalidMeasurementError(f"Phase vector could not be converted to numpy array: {err}") from err

    if phases.ndim != 1:
        raise InvalidMeasurementError(
            f"Phase vector must be 1-dimensional, got ndim={phases.ndim} with shape {phases.shape}."
        )

    if phases.shape[0] != expected_len:
        raise InvalidMeasurementError(
            f"Phase vector length ({phases.shape[0]}) does not match frequency vector length ({expected_len})."
        )

    if not np.all(np.isfinite(phases)):
        raise InvalidMeasurementError("Phase vector contains non-finite values (NaN or Inf).")

    arr = np.array(phases, dtype=np.float64, copy=True)
    arr.flags.writeable = False
    return arr


def validate_impulse_response(samples: Any, sample_rate: int) -> np.ndarray:
    """Validate and normalize a 1D time-domain impulse response array.

    Returns:
        Owned, contiguous, read-only 1D float32 numpy array.
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidMeasurementError(f"Sample rate must be a positive integer, got {sample_rate!r}.")

    if not isinstance(samples, np.ndarray):
        try:
            samples = np.asarray(samples, dtype=np.float32)
        except Exception as err:
            raise InvalidMeasurementError(f"Impulse response could not be converted to numpy array: {err}") from err

    if samples.ndim != 1:
        raise InvalidMeasurementError(
            f"Impulse response must be 1-dimensional (samples,), got ndim={samples.ndim} with shape {samples.shape}."
        )

    if samples.shape[0] < 1:
        raise InvalidMeasurementError("Impulse response array must contain at least 1 sample.")

    if not np.all(np.isfinite(samples)):
        raise InvalidMeasurementError("Impulse response contains non-finite values (NaN or Inf).")

    arr = np.array(samples, dtype=np.float32, copy=True)
    arr.flags.writeable = False
    return arr


def validate_target_points(points: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Validate acoustic target curve frequency-magnitude coordinate pairs."""
    if not isinstance(points, (list, tuple)) or len(points) < 2:
        raise InvalidSpecificationError("Target curve must contain at least 2 coordinate pairs.")

    parsed: list[tuple[float, float]] = []
    last_freq = -1.0

    for idx, pt in enumerate(points):
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise InvalidSpecificationError(f"Point at index {idx} must be a (frequency, dB) tuple, got {pt!r}.")

        f, db = pt
        if not isinstance(f, (int, float)) or isinstance(f, bool) or not math.isfinite(f) or f <= 0.0:
            raise InvalidSpecificationError(f"Frequency at index {idx} must be a positive finite float, got {f!r}.")

        if not isinstance(db, (int, float)) or isinstance(db, bool) or not math.isfinite(db):
            raise InvalidSpecificationError(f"Magnitude dB at index {idx} must be a finite float, got {db!r}.")

        f_float = float(f)
        db_float = float(db)

        if f_float <= last_freq:
            raise InvalidSpecificationError(
                f"Target curve frequencies must be strictly monotonically increasing: "
                f"{f_float} <= prior frequency {last_freq} at index {idx}."
            )

        last_freq = f_float
        parsed.append((f_float, db_float))

    return tuple(parsed)
