"""AcoustiForge PCM validation rules and typed exception hierarchy.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6A, 6F)
"""

from __future__ import annotations
from typing import Any
import numpy as np


class AcoustiForgeError(Exception):
    """Base exception for all AcoustiForge contract and runtime errors."""
    pass


class InvalidSampleRateError(AcoustiForgeError, ValueError):
    """Raised when a sample rate is <= 0 or not an integer."""
    pass


class InvalidChannelCountError(AcoustiForgeError, ValueError):
    """Raised when channel count is invalid or unsupported in Phase 0."""
    pass


class InvalidSampleFormatError(AcoustiForgeError, TypeError):
    """Raised when buffer dtype is not float32."""
    pass


class InvalidBlockSizeError(AcoustiForgeError, ValueError):
    """Raised when frame count is less than 1 (empty block)."""
    pass


class MalformedBufferError(AcoustiForgeError, ValueError):
    """Raised when audio buffer tensor is not 2-dimensional."""
    pass


class ChannelMismatchError(AcoustiForgeError, ValueError):
    """Raised when tensor shape[0] does not match metadata channel count."""
    pass


class NonContiguousBufferError(AcoustiForgeError, ValueError):
    """Raised when memory buffer is not C-contiguous."""
    pass


class NonFiniteValueError(AcoustiForgeError, ValueError):
    """Raised when buffer contains NaN, +Inf, or -Inf values."""
    pass


class IncompatibleNodeError(AcoustiForgeError, ValueError):
    """Raised when connected nodes have mismatched sample rates or channel counts."""
    pass


class InvalidParameterError(AcoustiForgeError, ValueError):
    """Raised when an algorithm/filter parameter is mathematically or physically invalid."""
    pass


class UnstableFilterError(AcoustiForgeError, ValueError):
    """Raised when a candidate filter's poles fall on or outside the unit circle."""
    pass


class InvalidGraphError(AcoustiForgeError, ValueError):
    """Base exception for compute graph topological and structural validation errors."""
    pass


class CycleDetectedError(InvalidGraphError):
    """Raised when a directed cycle is detected in a compute graph."""
    pass


class UnconnectedPortError(InvalidGraphError):
    """Raised when a required input port lacks an incoming edge."""
    pass


class DuplicateEdgeError(InvalidGraphError):
    """Raised when multiple producer edges target the same input port or an identical edge is added."""
    pass


class FrozenGraphError(InvalidGraphError, RuntimeError):
    """Raised when mutation is attempted on a frozen graph or execution on an unfrozen graph."""
    pass


def validate_metadata(sample_rate: int, channels: int) -> None:
    """Validate audio metadata parameters.

    Args:
        sample_rate: Discrete clock rate in Hz (must be positive integer).
        channels: Channel count (Phase 0 strictly supports 1=Mono, 2=Stereo).

    Raises:
        InvalidSampleRateError: If sample_rate <= 0 or not an integer.
        InvalidChannelCountError: If channels <= 0 or > 2 (Phase 0 scope).
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(
            f"Invalid sample rate: {sample_rate!r}. Must be a positive integer."
        )

    if not isinstance(channels, int) or isinstance(channels, bool) or channels <= 0:
        raise InvalidChannelCountError(
            f"Invalid channel count: {channels!r}. Must be a positive integer."
        )

    if channels > 2:
        raise InvalidChannelCountError(
            f"Unsupported channel count: {channels}. Phase 0 strictly supports Mono (1) and Stereo (2)."
        )


def validate_pcm_buffer(buffer: Any, expected_channels: int) -> None:
    """Validate a raw audio buffer array.

    Args:
        buffer: Array-like audio tensor.
        expected_channels: Expected channel count from metadata.

    Raises:
        MalformedBufferError: If buffer is not a 2D ndarray.
        InvalidSampleFormatError: If buffer dtype is not float32.
        InvalidBlockSizeError: If frame count is < 1.
        ChannelMismatchError: If buffer.shape[0] != expected_channels.
        NonContiguousBufferError: If buffer is not C-contiguous.
        NonFiniteValueError: If buffer contains NaN or Inf.
    """
    if not isinstance(buffer, np.ndarray):
        raise MalformedBufferError(f"Buffer must be a numpy.ndarray, got {type(buffer)!r}.")

    if buffer.ndim != 2:
        raise MalformedBufferError(
            f"Buffer must be 2-dimensional (channels, frames), got ndim={buffer.ndim} with shape {buffer.shape}."
        )

    if buffer.dtype != np.float32:
        raise InvalidSampleFormatError(
            f"Buffer dtype must be float32, got {buffer.dtype}."
        )

    channels, frames = buffer.shape

    if frames < 1:
        raise InvalidBlockSizeError(
            f"Invalid frame count: {frames}. An audio block must contain at least 1 frame."
        )

    if channels != expected_channels:
        raise ChannelMismatchError(
            f"Buffer channel dimension ({channels}) does not match metadata channels ({expected_channels})."
        )

    if not buffer.flags.c_contiguous:
        raise NonContiguousBufferError(
            "Buffer memory layout must be C-contiguous."
        )

    if not np.isfinite(buffer).all():
        raise NonFiniteValueError(
            "Buffer contains non-finite values (NaN, +Inf, or -Inf)."
        )


def validate_pipeline_link(producer_rate: int, producer_channels: int,
                           consumer_rate: int, consumer_channels: int) -> None:
    """Validate compatibility between connected pipeline stages."""
    if producer_rate != consumer_rate:
        raise IncompatibleNodeError(
            f"Sample rate mismatch between connected nodes: producer={producer_rate} Hz, consumer={consumer_rate} Hz."
        )
    if producer_channels != consumer_channels:
        raise IncompatibleNodeError(
            f"Channel count mismatch between connected nodes: producer={producer_channels}, consumer={consumer_channels}."
        )
