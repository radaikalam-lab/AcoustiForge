"""Unit and Invariant Tests for Time-Domain Impulse Response Ingestion.

Normative Authority:
- docs/contracts/IMPULSE_RESPONSE_INGESTION_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import io
from pathlib import Path
import struct
import numpy as np
import pytest

from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain.measurements import ImpulseResponseData
from acoustiforge.io.exceptions import (
    InvalidMeasurementDataError,
    MalformedMeasurementDataError,
    UnsupportedMeasurementFormatError,
)
from acoustiforge.io.impulse_parser import (
    _WAVE_FORMAT_EXTENSIBLE,
    _WAVE_FORMAT_IEEE_FLOAT,
    _WAVE_FORMAT_PCM,
    _parse_wav_bytes,
    parse_impulse_file,
    parse_impulse_text,
)


def _create_wav_bytes(
    samples: np.ndarray,
    sample_rate: int = 48000,
    bits_per_sample: int = 16,
    format_code: int = _WAVE_FORMAT_PCM,
    num_channels: int = 1,
) -> bytes:
    """Helper function to synthesize well-formed binary WAV byte streams."""
    bio = io.BytesIO()
    total_frames = len(samples) // num_channels
    bytes_per_sample = bits_per_sample // 8
    data_size = total_frames * num_channels * bytes_per_sample

    # 1. RIFF Header
    bio.write(b"RIFF")
    bio.write(struct.pack("<I", 36 + data_size))
    bio.write(b"WAVE")

    # 2. fmt Chunk
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    bio.write(b"fmt ")
    bio.write(struct.pack("<IHHIIHH", 16, format_code, num_channels, sample_rate, byte_rate, block_align, bits_per_sample))

    # 3. data Chunk
    bio.write(b"data")
    bio.write(struct.pack("<I", data_size))

    if format_code == _WAVE_FORMAT_PCM:
        if bits_per_sample == 16:
            int_samples = np.clip(np.round(samples * 32768.0), -32768, 32767).astype(np.int16)
            bio.write(int_samples.tobytes())
        elif bits_per_sample == 24:
            int_samples = np.clip(np.round(samples * 8388608.0), -8388608, 8388607).astype(np.int32)
            raw_bytes = bytearray()
            for val in int_samples:
                b0 = val & 0xFF
                b1 = (val >> 8) & 0xFF
                b2 = (val >> 16) & 0xFF
                raw_bytes.extend([b0, b1, b2])
            bio.write(bytes(raw_bytes))
        elif bits_per_sample == 32:
            int_samples = np.clip(np.round(samples * 2147483648.0), -2147483648, 2147483647).astype(np.int32)
            bio.write(int_samples.tobytes())
    elif format_code == _WAVE_FORMAT_IEEE_FLOAT:
        float_samples = samples.astype(np.float32)
        bio.write(float_samples.tobytes())

    return bio.getvalue()


class TestImpulseParser:
    """Test suite for WAV and ASCII impulse response file parsers."""

    def test_parse_wav_16bit_pcm(self) -> None:
        """Verify 16-bit integer PCM WAV parsing."""
        raw_samples = np.zeros(64, dtype=np.float64)
        raw_samples[10] = 1.0  # Unit impulse peak
        raw_samples[11] = -0.5
        wav_data = _create_wav_bytes(raw_samples, sample_rate=48000, bits_per_sample=16)

        ir = _parse_wav_bytes(wav_data)
        assert isinstance(ir, ImpulseResponseData)
        assert ir.sample_rate == 48000
        assert ir.num_samples == 64
        assert ir.peak_index == 10
        assert abs(ir.samples[10] - 1.0) < 1e-4
        assert abs(ir.samples[11] - (-0.5)) < 1e-4

    def test_parse_wav_24bit_pcm(self) -> None:
        """Verify 24-bit integer PCM WAV parsing with sign extension."""
        raw_samples = np.zeros(32, dtype=np.float64)
        raw_samples[5] = 0.75
        raw_samples[6] = -0.75
        wav_data = _create_wav_bytes(raw_samples, sample_rate=96000, bits_per_sample=24)

        ir = _parse_wav_bytes(wav_data)
        assert ir.sample_rate == 96000
        assert ir.num_samples == 32
        assert ir.peak_index == 5
        assert abs(ir.samples[5] - 0.75) < 1e-6
        assert abs(ir.samples[6] - (-0.75)) < 1e-6

    def test_parse_wav_32bit_pcm(self) -> None:
        """Verify 32-bit signed integer PCM WAV parsing."""
        raw_samples = np.zeros(32, dtype=np.float64)
        raw_samples[4] = 0.9
        wav_data = _create_wav_bytes(raw_samples, sample_rate=44100, bits_per_sample=32)

        ir = _parse_wav_bytes(wav_data)
        assert ir.sample_rate == 44100
        assert ir.num_samples == 32
        assert abs(ir.samples[4] - 0.9) < 1e-6

    def test_parse_wav_32bit_float(self) -> None:
        """Verify 32-bit IEEE float WAV parsing without SciPy."""
        raw_samples = np.zeros(48, dtype=np.float64)
        raw_samples[12] = 1.0
        raw_samples[13] = -0.25
        wav_data = _create_wav_bytes(
            raw_samples, sample_rate=48000, bits_per_sample=32, format_code=_WAVE_FORMAT_IEEE_FLOAT
        )

        ir = _parse_wav_bytes(wav_data)
        assert ir.sample_rate == 48000
        assert ir.num_samples == 48
        assert ir.peak_index == 12
        assert abs(ir.samples[12] - 1.0) < 1e-6
        assert abs(ir.samples[13] - (-0.25)) < 1e-6

    def test_parse_wav_stereo_channel_extraction(self) -> None:
        """Verify channel selection on multi-channel stereo WAV files."""
        # 32 stereo frames: Left peak at index 5, Right peak at index 15
        left = np.zeros(32, dtype=np.float64)
        left[5] = 0.8
        right = np.zeros(32, dtype=np.float64)
        right[15] = 0.9

        interleaved = np.empty(64, dtype=np.float64)
        interleaved[0::2] = left
        interleaved[1::2] = right

        wav_data = _create_wav_bytes(interleaved, sample_rate=48000, bits_per_sample=16, num_channels=2)

        # Channel 0 (Left)
        ir_left = _parse_wav_bytes(wav_data, channel_index=0)
        assert ir_left.num_samples == 32
        assert ir_left.peak_index == 5
        assert abs(ir_left.samples[5] - 0.8) < 1e-4

        # Channel 1 (Right)
        ir_right = _parse_wav_bytes(wav_data, channel_index=1)
        assert ir_right.num_samples == 32
        assert ir_right.peak_index == 15
        assert abs(ir_right.samples[15] - 0.9) < 1e-4

        # Invalid channel index rejection
        with pytest.raises(InvalidParameterError):
            _parse_wav_bytes(wav_data, channel_index=2)

    def test_parse_ascii_two_column_time_amplitude(self) -> None:
        """Verify 2-column ASCII impulse parsing with uniform sampling rate derivation."""
        # 48 kHz -> dt = 1 / 48000 = 0.000020833333 s
        dt = 1.0 / 48000.0
        lines = ["# REW ASCII Impulse Export", "Time(s)    Amplitude"]
        for i in range(32):
            val = 1.0 if i == 8 else 0.0
            lines.append(f"{i * dt:.8f}    {val:.6f}")

        text = "\n".join(lines)
        ir = parse_impulse_text(text)

        assert ir.sample_rate == 48000
        assert ir.num_samples == 32
        assert ir.peak_index == 8
        assert abs(ir.samples[8] - 1.0) < 1e-6

    def test_parse_ascii_single_column_with_explicit_sample_rate(self) -> None:
        """Verify 1-column amplitude ASCII impulse parsing with explicit sample rate."""
        lines = ["; Single column raw samples", "; Comment line"]
        for i in range(20):
            lines.append(f"{0.5 if i == 5 else 0.0}")

        text = "\n".join(lines)
        ir = parse_impulse_text(text, sample_rate=44100)

        assert ir.sample_rate == 44100
        assert ir.num_samples == 20
        assert ir.peak_index == 5

    def test_parse_ascii_missing_sample_rate_on_single_column_rejected(self) -> None:
        """Verify single column without sample rate raises InvalidParameterError."""
        lines = [f"{i * 0.1}" for i in range(20)]
        text = "\n".join(lines)
        with pytest.raises(InvalidParameterError):
            parse_impulse_text(text)

    def test_parse_wav_rejections(self) -> None:
        """Verify corrupt WAV files are rejected cleanly."""
        # Not a RIFF file
        with pytest.raises(UnsupportedMeasurementFormatError):
            _parse_wav_bytes(b"NOT_A_RIFF_FILE_HEADER")

        # Too short
        with pytest.raises(MalformedMeasurementDataError):
            _parse_wav_bytes(b"RIFF")
