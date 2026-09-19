"""Negative validation tests covering the complete AcoustiForge rejection matrix.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6F)
"""

import pytest
import numpy as np

from acoustiforge.contracts.pcm import PCMBlock, AudioMetadata
from acoustiforge.contracts.validation import (
    InvalidSampleRateError,
    InvalidChannelCountError,
    InvalidSampleFormatError,
    InvalidBlockSizeError,
    MalformedBufferError,
    ChannelMismatchError,
    NonContiguousBufferError,
    NonFiniteValueError,
    IncompatibleNodeError,
    validate_pipeline_link,
)


class TestValidationMatrix:
    """Test suite for deterministic rejection of invalid configurations and buffers."""

    # VAL-01: Invalid sample rate
    @pytest.mark.parametrize("rate", [0, -1, -48000, 48000.5, "48000", None, True, False])
    def test_val_01_invalid_sample_rate(self, rate: object) -> None:
        with pytest.raises(InvalidSampleRateError):
            AudioMetadata(sample_rate=rate, channels=2)  # type: ignore

    # VAL-02: Invalid channel count
    @pytest.mark.parametrize("channels", [0, -1, 3, 4, 8, 1.5, "2", None, True, False])
    def test_val_02_invalid_channel_count(self, channels: object) -> None:
        with pytest.raises(InvalidChannelCountError):
            AudioMetadata(sample_rate=48000, channels=channels)  # type: ignore

    # VAL-03: Invalid sample format (non-float32)
    @pytest.mark.parametrize("dtype", [np.float64, np.int16, np.int32, np.uint8, np.complex64])
    def test_val_03_invalid_sample_format(self, dtype: np.dtype) -> None:
        data = np.zeros((2, 128), dtype=dtype)
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(InvalidSampleFormatError):
            PCMBlock(samples=data, metadata=meta)

    # VAL-04: Invalid block size (frames < 1)
    def test_val_04_invalid_block_size_zero_frames(self) -> None:
        data = np.zeros((2, 0), dtype=np.float32)
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(InvalidBlockSizeError):
            PCMBlock(samples=data, metadata=meta)

    # VAL-05: Malformed buffer (non-2D)
    @pytest.mark.parametrize("shape", [(128,), (2, 64, 2), (1, 1, 128)])
    def test_val_05_malformed_buffer_dimensions(self, shape: tuple[int, ...]) -> None:
        data = np.zeros(shape, dtype=np.float32)
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(MalformedBufferError):
            PCMBlock(samples=data, metadata=meta)

    def test_val_05_malformed_buffer_non_ndarray(self) -> None:
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(MalformedBufferError):
            PCMBlock(samples=[[0.0, 0.0]], metadata=meta)  # type: ignore

    def test_val_05_malformed_buffer_invalid_metadata_type(self) -> None:
        data = np.zeros((2, 128), dtype=np.float32)
        with pytest.raises(MalformedBufferError):
            PCMBlock(samples=data, metadata={"sample_rate": 48000, "channels": 2})  # type: ignore

    # VAL-06: Channel / Buffer mismatch
    def test_val_06_channel_buffer_mismatch(self) -> None:
        # Buffer has 2 channels, but metadata declared 1 channel
        data = np.zeros((2, 128), dtype=np.float32)
        meta = AudioMetadata(sample_rate=48000, channels=1)
        with pytest.raises(ChannelMismatchError):
            PCMBlock(samples=data, metadata=meta)

    # VAL-07: Non-contiguous memory buffer
    def test_val_07_non_contiguous_buffer(self) -> None:
        # Create a Fortran-ordered (column-major) array
        data_f = np.zeros((2, 128), dtype=np.float32, order="F")
        assert not data_f.flags.c_contiguous
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(NonContiguousBufferError):
            PCMBlock(samples=data_f, metadata=meta)

        # Create a strided slice that is not contiguous
        data_orig = np.zeros((4, 128), dtype=np.float32)
        sliced = data_orig[::2, :]
        if not sliced.flags.c_contiguous:
            with pytest.raises(NonContiguousBufferError):
                PCMBlock(samples=sliced, metadata=meta)

    # VAL-08 & VAL-09: Non-finite values (NaN, +Inf, -Inf)
    @pytest.mark.parametrize("invalid_val", [np.nan, np.inf, -np.inf])
    def test_val_08_09_non_finite_values(self, invalid_val: float) -> None:
        data = np.zeros((2, 128), dtype=np.float32)
        data[0, 50] = invalid_val
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(NonFiniteValueError):
            PCMBlock(samples=data, metadata=meta)

    # VAL-10: Incompatible node linkage
    def test_val_10_incompatible_sample_rates(self) -> None:
        with pytest.raises(IncompatibleNodeError):
            validate_pipeline_link(
                producer_rate=44100, producer_channels=2,
                consumer_rate=48000, consumer_channels=2,
            )

    def test_val_10_incompatible_channels(self) -> None:
        with pytest.raises(IncompatibleNodeError):
            validate_pipeline_link(
                producer_rate=48000, producer_channels=1,
                consumer_rate=48000, consumer_channels=2,
            )
