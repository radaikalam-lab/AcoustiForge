"""AcoustiForge Acoustic Measurement Data Models.

Normative Authority:
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
import numpy as np

from .validation import (
    InvalidMeasurementError,
    validate_frequency_vector,
    validate_impulse_response,
    validate_magnitude_vector,
    validate_phase_vector,
)


@dataclass(frozen=True, slots=True)
class FrequencyResponseData:
    """Immutable acoustic frequency response measurement data container.

    Enforces owned, contiguous, read-only numpy array storage to guarantee data immutability.
    """
    frequencies_hz: np.ndarray
    magnitude_db: np.ndarray
    phase_rad: Optional[np.ndarray] = None

    def __init__(
        self,
        frequencies_hz: Any,
        magnitude_db: Any,
        phase_rad: Optional[Any] = None,
    ) -> None:
        freq_arr = validate_frequency_vector(frequencies_hz)
        mag_arr = validate_magnitude_vector(magnitude_db, expected_len=freq_arr.shape[0])

        phase_arr: Optional[np.ndarray] = None
        if phase_rad is not None:
            phase_arr = validate_phase_vector(phase_rad, expected_len=freq_arr.shape[0])

        object.__setattr__(self, "frequencies_hz", freq_arr)
        object.__setattr__(self, "magnitude_db", mag_arr)
        object.__setattr__(self, "phase_rad", phase_arr)

    @property
    def num_points(self) -> int:
        """Number of discrete frequency points in this measurement."""
        return int(self.frequencies_hz.shape[0])

    @property
    def frequency_range(self) -> tuple[float, float]:
        """Measurement frequency span as (min_freq_hz, max_freq_hz)."""
        return (float(self.frequencies_hz[0]), float(self.frequencies_hz[-1]))

    def __repr__(self) -> str:
        has_phase = self.phase_rad is not None
        return (
            f"FrequencyResponseData(num_points={self.num_points}, "
            f"range={self.frequency_range[0]:.1f}Hz-{self.frequency_range[1]:.1f}Hz, "
            f"has_phase={has_phase})"
        )


@dataclass(frozen=True, slots=True)
class ImpulseResponseData:
    """Immutable acoustic impulse response data container.

    Enforces owned, contiguous, read-only numpy array storage to guarantee data immutability.
    """
    samples: np.ndarray
    sample_rate: int
    peak_index: int

    def __init__(
        self,
        samples: Any,
        sample_rate: int,
        peak_index: Optional[int] = None,
    ) -> None:
        samp_arr = validate_impulse_response(samples, sample_rate)

        if peak_index is None:
            derived_peak = int(np.argmax(np.abs(samp_arr)))
        else:
            if not isinstance(peak_index, int) or isinstance(peak_index, bool) or peak_index < 0 or peak_index >= samp_arr.shape[0]:
                raise InvalidMeasurementError(
                    f"peak_index {peak_index!r} out of bounds for impulse response with {samp_arr.shape[0]} samples."
                )
            derived_peak = peak_index

        object.__setattr__(self, "samples", samp_arr)
        object.__setattr__(self, "sample_rate", sample_rate)
        object.__setattr__(self, "peak_index", derived_peak)

    @property
    def num_samples(self) -> int:
        """Total number of samples in the impulse response."""
        return int(self.samples.shape[0])

    @property
    def duration_seconds(self) -> float:
        """Temporal duration in seconds."""
        return float(self.num_samples / self.sample_rate)

    @property
    def time_to_peak_seconds(self) -> float:
        """Time elapsed from onset to peak arrival in seconds."""
        return float(self.peak_index / self.sample_rate)

    def __repr__(self) -> str:
        return (
            f"ImpulseResponseData(samples={self.num_samples}, "
            f"sample_rate={self.sample_rate}Hz, duration={self.duration_seconds*1000:.1f}ms, "
            f"peak_idx={self.peak_index})"
        )
