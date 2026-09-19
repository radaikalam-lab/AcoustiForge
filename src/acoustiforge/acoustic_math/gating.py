"""AcoustiForge Reflection Gating & Spectral Fourier Transformation.

Normative Authority:
- docs/contracts/REFLECTION_GATING_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Optional, Union
import numpy as np

from ..contracts.validation import InvalidParameterError
from ..domain.measurements import FrequencyResponseData, ImpulseResponseData


class WindowType(str, Enum):
    """Supported window and taper functions."""
    RECTANGULAR = "RECTANGULAR"
    HANN = "HANN"
    TUKEY = "TUKEY"
    HALF_HANN = "HALF_HANN"
    HALF_TUKEY = "HALF_TUKEY"


def generate_window(
    window_type: WindowType | str,
    length: int,
    alpha: float = 0.5,
) -> np.ndarray:
    """Generate a discrete window weighting vector.

    Args:
        window_type: WindowType enum or string identifier.
        length: Number of discrete samples (M >= 1).
        alpha: Taper fraction for Tukey windows in [0.0, 1.0] (default 0.5).

    Returns:
        1D float64 NumPy array of window coefficients.

    Raises:
        InvalidParameterError: If length < 1, alpha out of range, or window_type unknown.
    """
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        raise InvalidParameterError(f"Window length must be an integer >= 1, got {length!r}.")

    if not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not (0.0 <= alpha <= 1.0):
        raise InvalidParameterError(f"Tukey alpha must be in [0.0, 1.0], got {alpha!r}.")

    if isinstance(window_type, str):
        try:
            w_enum = WindowType(window_type.upper())
        except ValueError:
            raise InvalidParameterError(f"Unsupported window type: {window_type!r}.")
    else:
        w_enum = window_type

    if length == 1:
        return np.ones(1, dtype=np.float64)

    n = np.arange(length, dtype=np.float64)
    m_minus_1 = float(length - 1)

    if w_enum == WindowType.RECTANGULAR:
        return np.ones(length, dtype=np.float64)

    elif w_enum == WindowType.HANN:
        return 0.5 * (1.0 - np.cos(2.0 * math.pi * n / m_minus_1))

    elif w_enum == WindowType.TUKEY:
        if alpha <= 0.0:
            return np.ones(length, dtype=np.float64)
        if alpha >= 1.0:
            return 0.5 * (1.0 - np.cos(2.0 * math.pi * n / m_minus_1))

        # Transition length L
        l_trans = int(math.floor(alpha * m_minus_1 / 2.0))
        if l_trans < 1:
            return np.ones(length, dtype=np.float64)

        w = np.ones(length, dtype=np.float64)
        # Left rising taper
        idx_left = np.arange(l_trans, dtype=np.float64)
        w[:l_trans] = 0.5 * (1.0 - np.cos(math.pi * idx_left / float(l_trans)))
        # Right falling taper
        idx_right = np.arange(l_trans, dtype=np.float64)
        w[length - l_trans:] = 0.5 * (1.0 - np.cos(math.pi * (float(l_trans) - 1.0 - idx_right) / float(l_trans)))
        return w

    elif w_enum == WindowType.HALF_HANN:
        # Rising half-Hann from 0.0 to 1.0
        return 0.5 * (1.0 - np.cos(math.pi * n / m_minus_1))

    elif w_enum == WindowType.HALF_TUKEY:
        # Half-Tukey: flat with right falling taper
        l_trans = int(math.floor(alpha * m_minus_1))
        if l_trans < 1:
            return np.ones(length, dtype=np.float64)
        w = np.ones(length, dtype=np.float64)
        idx_right = np.arange(l_trans, dtype=np.float64)
        w[length - l_trans:] = 0.5 * (1.0 + np.cos(math.pi * idx_right / float(l_trans)))
        return w

    raise InvalidParameterError(f"Unhandled window type {w_enum}.")


@dataclass(frozen=True, slots=True)
class GateSpecification:
    """Immutable specification for reflection gating parameters.

    Attributes:
        left_time_ms: Pre-peak window duration in ms. Defaults to 1.0 ms.
        right_time_ms: Post-peak window duration in ms (truncating reflections). Defaults to 5.0 ms.
        left_samples: Explicit pre-peak window sample count (overrides left_time_ms).
        right_samples: Explicit post-peak window sample count (overrides right_time_ms).
        left_window: Window taper type for left edge.
        right_window: Window taper type for right edge.
        taper_alpha: Taper fraction for Tukey taper functions in [0.0, 1.0].
    """
    left_time_ms: Optional[float] = 1.0
    right_time_ms: Optional[float] = 5.0
    left_samples: Optional[int] = None
    right_samples: Optional[int] = None
    left_window: WindowType = WindowType.HALF_HANN
    right_window: WindowType = WindowType.HALF_HANN
    taper_alpha: float = 0.5


@dataclass(frozen=True, slots=True)
class GatedImpulseResult:
    """Immutable container for reflection-gated impulse response results."""
    gated_impulse: ImpulseResponseData
    gate_start_index: int
    gate_end_index: int
    gate_duration_seconds: float
    f_min_valid_hz: float
    window_weights: np.ndarray


def apply_reflection_gate(
    impulse: ImpulseResponseData,
    gate_spec: Optional[GateSpecification] = None,
) -> GatedImpulseResult:
    """Apply pseudo-anechoic reflection gating to an acoustic impulse response.

    Preserves the original buffer length, sample rate, time reference, and peak index.

    Args:
        impulse: Input ImpulseResponseData instance.
        gate_spec: Optional GateSpecification. If None, defaults to 1.0 ms left / 5.0 ms right half-Hann gate.

    Returns:
        Immutable GatedImpulseResult containing the gated impulse and gating metadata.

    Raises:
        InvalidParameterError: If impulse is invalid or gate parameters are non-positive.
    """
    if not isinstance(impulse, ImpulseResponseData):
        raise InvalidParameterError(f"Expected ImpulseResponseData, got {type(impulse)!r}.")

    spec = gate_spec if gate_spec is not None else GateSpecification()
    fs = impulse.sample_rate
    n_samples = impulse.num_samples
    n_peak = impulse.peak_index

    # Resolve left span
    if spec.left_samples is not None:
        if spec.left_samples < 0:
            raise InvalidParameterError(f"left_samples must be non-negative, got {spec.left_samples}.")
        n_left = spec.left_samples
    elif spec.left_time_ms is not None:
        if spec.left_time_ms < 0.0:
            raise InvalidParameterError(f"left_time_ms must be non-negative, got {spec.left_time_ms}.")
        n_left = int(round(spec.left_time_ms * 1e-3 * fs))
    else:
        n_left = int(round(1.0 * 1e-3 * fs))

    # Resolve right span
    if spec.right_samples is not None:
        if spec.right_samples < 0:
            raise InvalidParameterError(f"right_samples must be non-negative, got {spec.right_samples}.")
        n_right = spec.right_samples
    elif spec.right_time_ms is not None:
        if spec.right_time_ms < 0.0:
            raise InvalidParameterError(f"right_time_ms must be non-negative, got {spec.right_time_ms}.")
        n_right = int(round(spec.right_time_ms * 1e-3 * fs))
    else:
        n_right = int(round(5.0 * 1e-3 * fs))

    n_start = max(0, n_peak - n_left)
    n_end = min(n_samples - 1, n_peak + n_right)

    if n_start >= n_end:
        raise InvalidParameterError(f"Gate start index {n_start} must be strictly less than gate end index {n_end}.")

    # Build composite window weight vector W[n] of length n_samples
    weights = np.zeros(n_samples, dtype=np.float64)

    # 1. Left taper from n_start to n_peak (inclusive)
    len_left = (n_peak - n_start) + 1
    if len_left > 1:
        if spec.left_window == WindowType.RECTANGULAR:
            weights[n_start : n_peak + 1] = 1.0
        else:
            # Half-Hann / rising taper
            t_idx = np.arange(len_left, dtype=np.float64)
            weights[n_start : n_peak + 1] = 0.5 * (1.0 - np.cos(math.pi * t_idx / float(len_left - 1)))
    else:
        weights[n_peak] = 1.0

    # 2. Right taper from n_peak to n_end (inclusive)
    len_right = (n_end - n_peak) + 1
    if len_right > 1:
        if spec.right_window == WindowType.RECTANGULAR:
            weights[n_peak : n_end + 1] = 1.0
        else:
            # Half-Hann / falling taper
            t_idx = np.arange(len_right, dtype=np.float64)
            weights[n_peak : n_end + 1] = 0.5 * (1.0 + np.cos(math.pi * t_idx / float(len_right - 1)))
    else:
        weights[n_peak] = 1.0

    # Apply gating to samples
    raw_samples = impulse.samples
    gated_samples = raw_samples * weights

    gate_duration = float((n_end - n_start) / fs)
    f_min_valid = float(1.0 / gate_duration) if gate_duration > 0.0 else float("inf")

    gated_ir = ImpulseResponseData(
        samples=gated_samples,
        sample_rate=fs,
        peak_index=n_peak,
    )

    return GatedImpulseResult(
        gated_impulse=gated_ir,
        gate_start_index=n_start,
        gate_end_index=n_end,
        gate_duration_seconds=gate_duration,
        f_min_valid_hz=f_min_valid,
        window_weights=weights,
    )


def transform_impulse_to_frequency_response(
    impulse: Union[ImpulseResponseData, GatedImpulseResult],
    n_fft: Optional[int] = None,
    phase_reference: str = "raw",
) -> FrequencyResponseData:
    """Transform a time-domain impulse response to frequency-response representation via discrete FFT.

    Conforms to FrequencyResponseData invariants by excluding the DC bin (k=0) to guarantee strictly positive frequencies.

    Args:
        impulse: ImpulseResponseData or GatedImpulseResult instance.
        n_fft: Optional FFT length. Defaults to the next power of 2 >= sample length (minimum 16).
        phase_reference: 'raw' (preserves time-of-flight phase) or 'peak_aligned' (removes linear peak phase delay).

    Returns:
        Immutable FrequencyResponseData instance with magnitude in dB and phase in radians.

    Raises:
        InvalidParameterError: If impulse is invalid, n_fft is smaller than buffer, or phase_reference is unknown.
    """
    if isinstance(impulse, GatedImpulseResult):
        target_ir = impulse.gated_impulse
    elif isinstance(impulse, ImpulseResponseData):
        target_ir = impulse
    else:
        raise InvalidParameterError(f"Expected ImpulseResponseData or GatedImpulseResult, got {type(impulse)!r}.")

    if phase_reference not in ("raw", "peak_aligned"):
        raise InvalidParameterError(f"phase_reference must be 'raw' or 'peak_aligned', got {phase_reference!r}.")

    samples = np.asarray(target_ir.samples, dtype=np.float64)
    n_samples = target_ir.num_samples
    fs = target_ir.sample_rate
    n_peak = target_ir.peak_index

    # Resolve n_fft
    if n_fft is None:
        target_n_fft = int(2 ** math.ceil(math.log2(max(16, n_samples))))
    else:
        if not isinstance(n_fft, int) or isinstance(n_fft, bool) or n_fft < n_samples:
            raise InvalidParameterError(f"n_fft must be an integer >= sample length ({n_samples}), got {n_fft!r}.")
        target_n_fft = n_fft

    # Compute Real FFT
    spectrum = np.fft.rfft(samples, n=target_n_fft)
    num_bins = spectrum.shape[0]  # target_n_fft // 2 + 1

    # Exclude DC bin (k=0) to ensure strictly positive frequencies f_k > 0
    k_indices = np.arange(1, num_bins, dtype=np.float64)
    freqs = k_indices * (float(fs) / float(target_n_fft))
    spec_ac = spectrum[1:]

    # Compute magnitude in dB with 1e-12 (-240 dB) floor clamping
    mag_linear = np.abs(spec_ac)
    mag_db = 20.0 * np.log10(np.maximum(mag_linear, 1e-12))

    # Compute phase
    if phase_reference == "raw":
        phase_rad = np.angle(spec_ac)
    else:
        # Peak-aligned phase: multiply by e^(+j 2pi k n_peak / N_fft)
        correction = np.exp(1j * 2.0 * math.pi * k_indices * float(n_peak) / float(target_n_fft))
        aligned_spec = spec_ac * correction
        phase_rad = np.angle(aligned_spec)

    return FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=mag_db,
        phase_rad=phase_rad,
    )
