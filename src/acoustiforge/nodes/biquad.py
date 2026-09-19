"""AcoustiForge Biquad Filter Node and Coefficient Generation.

Normative Authority:
- docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md
- docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Union
import numpy as np

from ..contracts.pcm import AudioMetadata, PCMBlock
from ..contracts.validation import (
    AcoustiForgeError,
    IncompatibleNodeError,
    InvalidParameterError,
    InvalidSampleRateError,
    NonFiniteValueError,
    UnstableFilterError,
    validate_metadata,
)
from .base import BaseProcessingNode


class FilterType(str, Enum):
    """Canonical Biquad Filter Family Types defined in Phase 1B Section 5."""
    LOW_PASS = "low_pass"
    HIGH_PASS = "high_pass"
    BAND_PASS = "band_pass"
    NOTCH = "notch"
    PEAKING = "peaking"
    LOW_SHELF = "low_shelf"
    HIGH_SHELF = "high_shelf"


@dataclass(frozen=True)
class BiquadCoefficients:
    """Immutable normalized Biquad coefficient vector [b0, b1, b2, a1, a2] with implicit a0 = 1.0.

    Canonical ACE difference equation:
        y[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y[n-1] - a2*y[n-2]
    """
    b0: float
    b1: float
    b2: float
    a1: float
    a2: float

    @property
    def a0(self) -> float:
        """Implicit normalized denominator reference coefficient."""
        return 1.0

    def as_tuple(self) -> Tuple[float, float, float, float, float]:
        """Return the normalized coefficient tuple (b0, b1, b2, a1, a2)."""
        return (self.b0, self.b1, self.b2, self.a1, self.a2)

    def to_numpy(self, dtype: np.dtype = np.float32) -> np.ndarray:
        """Return coefficients as a 1D NumPy array with specified precision."""
        return np.array([self.b0, self.b1, self.b2, self.a1, self.a2], dtype=dtype)

    def is_stable(self, epsilon: float = 0.0) -> bool:
        """Check stability via strict Schur/Jury criterion with optional numerical guard.

        Mathematical criteria (Section 11.2):
            1 - a2 > 0  (|a2| < 1.0)
            1 + a1 + a2 > 0
            1 - a1 + a2 > 0
        """
        return (
            abs(self.a2) < (1.0 - epsilon)
            and (1.0 + self.a1 + self.a2) > epsilon
            and (1.0 - self.a1 + self.a2) > epsilon
        )


def _validate_finite(name: str, val: float) -> None:
    """Ensure value is finite (not NaN, +Inf, -Inf)."""
    if not math.isfinite(val):
        raise NonFiniteValueError(f"Parameter '{name}' must be finite, got {val!r}.")


def calculate_biquad_coefficients(
    filter_type: Union[FilterType, str],
    sample_rate: int,
    frequency: float,
    q: Optional[float] = None,
    bandwidth: Optional[float] = None,
    shelf_slope: Optional[float] = None,
    gain_db: float = 0.0,
) -> BiquadCoefficients:
    """Calculate normalized Biquad filter coefficients in reference float64 precision.

    Follows Robert Bristow-Johnson (RBJ) Audio EQ Cookbook equations as frozen in Phase 1B.

    Args:
        filter_type: Canonical filter family (FilterType or case-insensitive string).
        sample_rate: Sampling frequency fs in Hz (must be positive integer).
        frequency: Center/corner frequency f0 in Hz (must be 0 < f0 < fs/2).
        q: Quality factor Q (must be > 0).
        bandwidth: Bandwidth in octaves BW (must be > 0).
        shelf_slope: Shelf slope parameter S (must be > 0, shelf filters only).
        gain_db: Gain in decibels (peaking and shelf filters only).

    Returns:
        Immutable normalized BiquadCoefficients instance.

    Raises:
        InvalidSampleRateError: If sample_rate <= 0.
        InvalidParameterError: If frequency, Q, BW, or S violate physical/mathematical bounds.
        NonFiniteValueError: If any parameter is NaN or Inf.
        UnstableFilterError: If calculated filter is unstable.
    """
    # 1. Parse and validate filter type
    if isinstance(filter_type, str):
        try:
            filter_type = FilterType(filter_type.lower())
        except ValueError:
            raise InvalidParameterError(f"Unsupported filter type: {filter_type!r}.")

    # 2. Validate sample rate
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"Sample rate must be a positive integer, got {sample_rate!r}.")

    # 3. Validate frequency
    _validate_finite("frequency", frequency)
    fs = float(sample_rate)
    f0 = float(frequency)
    if f0 <= 0.0:
        raise InvalidParameterError(f"Frequency f0 must be > 0 Hz (DC boundary violation), got {frequency}.")
    nyquist = fs / 2.0
    if f0 >= nyquist:
        raise InvalidParameterError(
            f"Frequency f0 ({frequency} Hz) must be strictly below Nyquist ({nyquist} Hz)."
        )

    _validate_finite("gain_db", gain_db)
    gain_db = float(gain_db)

    # 4. Normalized angular frequency w0
    w0 = 2.0 * math.pi * (f0 / fs)
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)

    # 5. Determine alpha
    # Priority: Q -> BW -> S
    if shelf_slope is not None and filter_type in (FilterType.LOW_SHELF, FilterType.HIGH_SHELF):
        _validate_finite("shelf_slope", shelf_slope)
        s_val = float(shelf_slope)
        if s_val <= 0.0:
            raise InvalidParameterError(f"Shelf slope S must be > 0, got {shelf_slope}.")
        A = math.pow(10.0, gain_db / 40.0)
        # alpha = (sin(w0)/2) * sqrt((A + 1/A)*(1/S - 1) + 2)
        inner = (A + 1.0 / A) * (1.0 / s_val - 1.0) + 2.0
        if inner < 0.0:
            # Clamp to 0.0 if numerical precision creates slight negative for extreme S
            inner = 0.0
        alpha = (sin_w0 / 2.0) * math.sqrt(inner)
    elif bandwidth is not None:
        _validate_finite("bandwidth", bandwidth)
        bw_val = float(bandwidth)
        if bw_val <= 0.0:
            raise InvalidParameterError(f"Bandwidth BW must be > 0 octaves, got {bandwidth}.")
        # alpha = sin(w0) * sinh( (ln(2)/2) * BW * (w0 / sin(w0)) )
        ratio = w0 / sin_w0 if sin_w0 != 0.0 else 1.0
        arg = (math.log(2.0) / 2.0) * bw_val * ratio
        alpha = sin_w0 * math.sinh(arg)
    elif q is not None:
        _validate_finite("q", q)
        q_val = float(q)
        if q_val <= 0.0:
            raise InvalidParameterError(f"Quality factor Q must be > 0, got {q}.")
        alpha = sin_w0 / (2.0 * q_val)
    else:
        # Default Q = 1/sqrt(2) ~ 0.7071067811865476 (Butterworth)
        q_val = 1.0 / math.sqrt(2.0)
        alpha = sin_w0 / (2.0 * q_val)

    # 6. Amplitude A for peaking and shelf filters
    A = math.pow(10.0, gain_db / 40.0)

    # 7. Compute raw coefficients [b0, b1, b2, a0, a1, a2] in float64
    if filter_type == FilterType.LOW_PASS:
        b0 = (1.0 - cos_w0) / 2.0
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

    elif filter_type == FilterType.HIGH_PASS:
        b0 = (1.0 + cos_w0) / 2.0
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

    elif filter_type == FilterType.BAND_PASS:
        # Constant skirt gain, peak gain = Q
        b0 = sin_w0 / 2.0
        b1 = 0.0
        b2 = -sin_w0 / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

    elif filter_type == FilterType.NOTCH:
        b0 = 1.0
        b1 = -2.0 * cos_w0
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

    elif filter_type == FilterType.PEAKING:
        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / A

    elif filter_type == FilterType.LOW_SHELF:
        sqrt_A = math.sqrt(A)
        b0 = A * ((A + 1.0) - (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha)
        b1 = 2.0 * A * ((A - 1.0) - (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) - (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha)
        a0 = (A + 1.0) + (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha
        a1 = -2.0 * ((A - 1.0) + (A + 1.0) * cos_w0)
        a2 = (A + 1.0) + (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha

    elif filter_type == FilterType.HIGH_SHELF:
        sqrt_A = math.sqrt(A)
        b0 = A * ((A + 1.0) + (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha)
        b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) + (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha)
        a0 = (A + 1.0) - (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha
        a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cos_w0)
        a2 = (A + 1.0) - (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha

    else:
        raise InvalidParameterError(f"Unhandled filter type: {filter_type}")

    # 8. Normalization (a0 != 0 check)
    if a0 == 0.0:
        raise InvalidParameterError("Degenerate filter: normalization coefficient a0 == 0.")

    b0_norm = b0 / a0
    b1_norm = b1 / a0
    b2_norm = b2 / a0
    a1_norm = a1 / a0
    a2_norm = a2 / a0

    # 9. Stability Validation (Schur / Jury criterion)
    coeffs = BiquadCoefficients(
        b0=b0_norm,
        b1=b1_norm,
        b2=b2_norm,
        a1=a1_norm,
        a2=a2_norm,
    )

    if not coeffs.is_stable():
        raise UnstableFilterError(
            f"Calculated filter coefficients are unstable (poles on or outside unit circle): "
            f"a1={a1_norm:.6f}, a2={a2_norm:.6f}"
        )

    return coeffs


class BiquadNode(BaseProcessingNode):
    """Direct Form II Transposed (DF-II-T) second-order IIR Biquad filter node.

    Conforms to Phase 1A Node Contract & Phase 1B Biquad Mathematical Contract.
    """

    def __init__(
        self,
        filter_type: Union[FilterType, str],
        frequency: float,
        q: Optional[float] = None,
        bandwidth: Optional[float] = None,
        shelf_slope: Optional[float] = None,
        gain_db: float = 0.0,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize BiquadNode with filter parameters and optional configuration."""
        super().__init__(name=name)

        if isinstance(filter_type, str):
            filter_type = FilterType(filter_type.lower())

        self._filter_type: FilterType = filter_type
        self._frequency: float = float(frequency)
        self._q: Optional[float] = float(q) if q is not None else None
        self._bandwidth: Optional[float] = float(bandwidth) if bandwidth is not None else None
        self._shelf_slope: Optional[float] = float(shelf_slope) if shelf_slope is not None else None
        self._gain_db: float = float(gain_db)

        self._coefficients: Optional[BiquadCoefficients] = None
        self._state: Optional[np.ndarray] = None
        self._custom_coefficients: bool = False

        if sample_rate is not None and channels is not None:
            self.configure(sample_rate, channels)

    @classmethod
    def from_coefficients(
        cls,
        coefficients: BiquadCoefficients,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        name: Optional[str] = None,
    ) -> BiquadNode:
        """Instantiate a BiquadNode directly with pre-synthesized BiquadCoefficients.

        Args:
            coefficients: Immutable BiquadCoefficients instance.
            sample_rate: Optional audio sampling rate in Hz.
            channels: Optional channel count.
            name: Optional node name.

        Returns:
            Configured BiquadNode executing the explicit coefficients.
        """
        if not isinstance(coefficients, BiquadCoefficients):
            raise TypeError(f"Expected BiquadCoefficients, got {type(coefficients)!r}.")

        node = cls.__new__(cls)
        super(BiquadNode, node).__init__(name=name)
        node._filter_type = FilterType.LOW_PASS
        node._frequency = 0.0
        node._q = None
        node._bandwidth = None
        node._shelf_slope = None
        node._gain_db = 0.0
        node._coefficients = coefficients
        node._state = None
        node._custom_coefficients = True

        if sample_rate is not None and channels is not None:
            node.configure(sample_rate, channels)

        return node

    @property
    def latency_frames(self) -> int:
        """Algorithmic latency in frames (Biquad recursive filter has zero algorithmic latency)."""
        return 0

    @property
    def filter_type(self) -> FilterType:
        """Active filter family."""
        return self._filter_type

    @property
    def frequency(self) -> float:
        """Active center/corner frequency in Hz."""
        return self._frequency

    @property
    def q(self) -> Optional[float]:
        """Active quality factor Q."""
        return self._q

    @property
    def bandwidth(self) -> Optional[float]:
        """Active bandwidth BW in octaves."""
        return self._bandwidth

    @property
    def shelf_slope(self) -> Optional[float]:
        """Active shelf slope S."""
        return self._shelf_slope

    @property
    def gain_db(self) -> float:
        """Active gain in dB."""
        return self._gain_db

    @property
    def coefficients(self) -> Optional[BiquadCoefficients]:
        """Active normalized Biquad coefficients."""
        return self._coefficients

    def configure(self, sample_rate: int, channels: int) -> None:
        """Configure node sample rate, channel count, and calculate coefficients."""
        validate_metadata(sample_rate, channels)

        if not getattr(self, "_custom_coefficients", False):
            # Calculate coefficients for configured sample rate
            coeffs = calculate_biquad_coefficients(
                filter_type=self._filter_type,
                sample_rate=sample_rate,
                frequency=self._frequency,
                q=self._q,
                bandwidth=self._bandwidth,
                shelf_slope=self._shelf_slope,
                gain_db=self._gain_db,
            )
            self._coefficients = coeffs

        super().configure(sample_rate, channels)

        # Initialize DF-II-T state registers: shape (channels, 2)
        if self._state is None or self._state.shape[0] != channels:
            self._state = np.zeros((channels, 2), dtype=np.float32)
        else:
            self._state.fill(0.0)

    def set_parameters(
        self,
        filter_type: Optional[Union[FilterType, str]] = None,
        frequency: Optional[float] = None,
        q: Optional[float] = None,
        bandwidth: Optional[float] = None,
        shelf_slope: Optional[float] = None,
        gain_db: Optional[float] = None,
    ) -> None:
        """Atomically update filter parameters without resetting state registers.

        If validation or stability fails, active parameters and state are preserved unmodified.
        """
        cand_type = self._filter_type if filter_type is None else (
            FilterType(filter_type.lower()) if isinstance(filter_type, str) else filter_type
        )
        cand_freq = self._frequency if frequency is None else float(frequency)
        cand_q = self._q if q is None else float(q)
        cand_bw = self._bandwidth if bandwidth is None else float(bandwidth)
        cand_slope = self._shelf_slope if shelf_slope is None else float(shelf_slope)
        cand_gain = self._gain_db if gain_db is None else float(gain_db)

        # If already configured with a sample rate, compute candidate coefficients
        if self._sample_rate is not None:
            cand_coeffs = calculate_biquad_coefficients(
                filter_type=cand_type,
                sample_rate=self._sample_rate,
                frequency=cand_freq,
                q=cand_q,
                bandwidth=cand_bw,
                shelf_slope=cand_slope,
                gain_db=cand_gain,
            )
            # Atomic commit
            self._coefficients = cand_coeffs

        self._filter_type = cand_type
        self._frequency = cand_freq
        self._q = cand_q
        self._bandwidth = cand_bw
        self._shelf_slope = cand_slope
        self._gain_db = cand_gain

    def reset(self) -> None:
        """Reset internal filter state registers (s1, s2) to zero while preserving configuration."""
        if self._state is not None:
            self._state.fill(0.0)

    def process(self, block: PCMBlock) -> PCMBlock:
        """Process an input PCM block through the DF-II-T Biquad filter.

        Args:
            block: Valid canonical input PCMBlock.

        Returns:
            Valid canonical output PCMBlock.
        """
        # 1. Check auto-configuration or compatibility
        if self._sample_rate is None or self._channels is None:
            self.configure(block.sample_rate, block.channels)
        else:
            if block.sample_rate != self._sample_rate:
                raise IncompatibleNodeError(
                    f"Sample rate mismatch: Node configured for {self._sample_rate} Hz, "
                    f"block has {block.sample_rate} Hz."
                )
            if block.channels != self._channels:
                raise IncompatibleNodeError(
                    f"Channel count mismatch: Node configured for {self._channels} channels, "
                    f"block has {block.channels} channels."
                )

        # 2. Bypass / Inactive pass-through
        if not self._is_active:
            return block.copy()

        if self._coefficients is None:
            self._coefficients = calculate_biquad_coefficients(
                filter_type=self._filter_type,
                sample_rate=self._sample_rate,
                frequency=self._frequency,
                q=self._q,
                bandwidth=self._bandwidth,
                shelf_slope=self._shelf_slope,
                gain_db=self._gain_db,
            )

        # 3. Direct Form II Transposed filtering
        # Extract coefficients as float32 for runtime execution
        b0 = np.float32(self._coefficients.b0)
        b1 = np.float32(self._coefficients.b1)
        b2 = np.float32(self._coefficients.b2)
        a1 = np.float32(self._coefficients.a1)
        a2 = np.float32(self._coefficients.a2)

        x = block.samples
        channels, frames = x.shape
        y = np.empty((channels, frames), dtype=np.float32)

        if self._state is None or self._state.shape[0] != channels:
            self._state = np.zeros((channels, 2), dtype=np.float32)

        state = self._state

        # Per-channel DF-II-T execution loop
        for c in range(channels):
            s1 = state[c, 0]
            s2 = state[c, 1]
            x_c = x[c]
            y_c = y[c]

            for n in range(frames):
                x_n = x_c[n]
                # y[n] = b0 * x[n] + s1[n-1]
                y_n = b0 * x_n + s1
                # s1[n] = b1 * x[n] - a1 * y[n] + s2[n-1]
                s1 = b1 * x_n - a1 * y_n + s2
                # s2[n] = b2 * x[n] - a2 * y[n]
                s2 = b2 * x_n - a2 * y_n
                y_c[n] = y_n

            state[c, 0] = s1
            state[c, 1] = s2

        return PCMBlock(
            samples=y,
            metadata=block.metadata,
        )
