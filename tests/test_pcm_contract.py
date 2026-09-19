"""Unit tests for AcoustiForge canonical PCM contracts.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6A, 6E)
"""

import pytest
import numpy as np
from dataclasses import FrozenInstanceError

from acoustiforge.contracts.pcm import PCMBlock, AudioMetadata, ChannelLayout


class TestAudioMetadata:
    """Test suite for AudioMetadata."""

    def test_valid_mono_metadata(self) -> None:
        meta = AudioMetadata(sample_rate=48000, channels=1)
        assert meta.sample_rate == 48000
        assert meta.channels == 1
        assert meta.layout == ChannelLayout.MONO

    def test_valid_stereo_metadata(self) -> None:
        meta = AudioMetadata(sample_rate=44100, channels=2)
        assert meta.sample_rate == 44100
        assert meta.channels == 2
        assert meta.layout == ChannelLayout.STEREO

    def test_metadata_immutability(self) -> None:
        meta = AudioMetadata(sample_rate=48000, channels=2)
        with pytest.raises(FrozenInstanceError):
            meta.sample_rate = 96000  # type: ignore


class TestPCMBlockContract:
    """Test suite for PCMBlock structure and invariants."""

    def test_create_mono_block(self) -> None:
        frames = 256
        data = np.zeros((1, frames), dtype=np.float32)
        meta = AudioMetadata(sample_rate=48000, channels=1)
        block = PCMBlock(samples=data, metadata=meta)

        assert block.channels == 1
        assert block.frames == frames
        assert block.sample_rate == 48000
        assert block.shape == (1, frames)
        assert block.dtype == np.float32
        assert block.samples.flags.c_contiguous

    def test_create_stereo_block(self) -> None:
        frames = 512
        data = np.ones((2, frames), dtype=np.float32)
        meta = AudioMetadata(sample_rate=96000, channels=2)
        block = PCMBlock(samples=data, metadata=meta)

        assert block.channels == 2
        assert block.frames == frames
        assert block.sample_rate == 96000
        assert block.shape == (2, frames)
        assert block.dtype == np.float32

    def test_from_array_factory(self) -> None:
        data = np.zeros((2, 128), dtype=np.float32)
        block = PCMBlock.from_array(data, sample_rate=44100)

        assert block.channels == 2
        assert block.frames == 128
        assert block.sample_rate == 44100
        assert block.metadata.layout == ChannelLayout.STEREO

    def test_channel_slicing(self) -> None:
        frames = 64
        left = np.linspace(-0.5, 0.5, frames, dtype=np.float32)
        right = np.linspace(-1.0, 1.0, frames, dtype=np.float32)
        data = np.vstack([left, right])
        block = PCMBlock.from_array(data, sample_rate=48000)

        assert np.array_equal(block.channel(0), left)
        assert np.array_equal(block.channel(1), right)

        with pytest.raises(IndexError):
            block.channel(2)

        with pytest.raises(IndexError):
            block.channel(-1)

    def test_block_copy(self) -> None:
        data = np.ones((2, 32), dtype=np.float32)
        block = PCMBlock.from_array(data, sample_rate=48000)
        copied = block.copy()

        assert copied is not block
        assert copied.samples is not block.samples
        assert np.array_equal(copied.samples, block.samples)
        assert copied.metadata == block.metadata

    def test_block_immutability(self) -> None:
        data = np.zeros((1, 32), dtype=np.float32)
        block = PCMBlock.from_array(data, sample_rate=48000)
        with pytest.raises(FrozenInstanceError):
            block.samples = np.ones((1, 32), dtype=np.float32)  # type: ignore
