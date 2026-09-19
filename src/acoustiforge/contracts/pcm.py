"""AcoustiForge canonical PCM data structures.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6A)
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Self
import numpy as np

from .validation import (
    validate_metadata,
    validate_pcm_buffer,
    MalformedBufferError,
)


class ChannelLayout(str, Enum):
    """Supported Phase 0 channel ordering semantics."""
    MONO = "mono"      # Channel 0: Mono (M)
    STEREO = "stereo"  # Channel 0: Left (L), Channel 1: Right (R)


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    """Immutable audio metadata container for canonical PCM blocks."""
    sample_rate: int
    channels: int

    def __post_init__(self) -> None:
        validate_metadata(self.sample_rate, self.channels)

    @property
    def layout(self) -> ChannelLayout:
        """Return the channel layout associated with this channel count."""
        return ChannelLayout.MONO if self.channels == 1 else ChannelLayout.STEREO


@dataclass(frozen=True, slots=True)
class PCMBlock:
    """Canonical in-memory PCM audio block.

    Layout: Planar, C-contiguous array of shape (channels, frames), dtype float32.
    """
    samples: np.ndarray
    metadata: AudioMetadata

    def __init__(self, samples: np.ndarray, metadata: AudioMetadata) -> None:
        if not isinstance(metadata, AudioMetadata):
            raise MalformedBufferError(f"metadata must be an AudioMetadata instance, got {type(metadata)!r}.")

        # Convert to C-contiguous float32 if standard Python or list was passed, but validate if ndarray
        if not isinstance(samples, np.ndarray):
            raise MalformedBufferError(f"samples must be a numpy.ndarray, got {type(samples)!r}.")

        validate_pcm_buffer(samples, metadata.channels)

        # Set frozen attributes via object.__setattr__
        object.__setattr__(self, "samples", samples)
        object.__setattr__(self, "metadata", metadata)

    @classmethod
    def from_array(cls, array: np.ndarray, sample_rate: int) -> Self:
        """Create a PCMBlock from a NumPy array and sample rate with automatic validation."""
        if not isinstance(array, np.ndarray):
            raise MalformedBufferError(f"Input array must be a numpy.ndarray, got {type(array)!r}.")
        if array.ndim != 2:
            raise MalformedBufferError(f"Input array must be 2D (channels, frames), got shape {array.shape}.")

        channels = array.shape[0]
        metadata = AudioMetadata(sample_rate=sample_rate, channels=channels)
        return cls(samples=array, metadata=metadata)

    @property
    def channels(self) -> int:
        """Number of audio channels (dimension 0)."""
        return self.metadata.channels

    @property
    def frames(self) -> int:
        """Number of temporal frames in this block (dimension 1)."""
        return int(self.samples.shape[1])

    @property
    def sample_rate(self) -> int:
        """Discrete sampling frequency in Hz."""
        return self.metadata.sample_rate

    @property
    def shape(self) -> tuple[int, int]:
        """Tensor dimensions as (channels, frames)."""
        return (self.channels, self.frames)

    @property
    def dtype(self) -> np.dtype:
        """Numerical sample format."""
        return self.samples.dtype

    def channel(self, index: int) -> np.ndarray:
        """Return a 1D slice of frames for a specific channel index."""
        if index < 0 or index >= self.channels:
            raise IndexError(f"Channel index {index} out of range for {self.channels}-channel block.")
        return self.samples[index, :]

    def copy(self) -> PCMBlock:
        """Return a deep copy of this PCM block."""
        return PCMBlock(
            samples=self.samples.copy(),
            metadata=self.metadata,
        )
