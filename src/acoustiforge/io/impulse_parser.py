"""AcoustiForge Time-Domain Impulse Response Ingestion and Parsers.

Normative Authority:
- docs/contracts/IMPULSE_RESPONSE_INGESTION_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import io
import math
from pathlib import Path
import struct
from typing import Optional, Sequence, Tuple, Union
import numpy as np

from ..contracts.validation import InvalidParameterError
from ..domain.measurements import ImpulseResponseData
from .exceptions import (
    InvalidMeasurementDataError,
    MalformedMeasurementDataError,
    MeasurementIngestionError,
    UnsupportedMeasurementFormatError,
)

# Standard WAVE Format Codes
_WAVE_FORMAT_PCM = 0x0001
_WAVE_FORMAT_IEEE_FLOAT = 0x0003
_WAVE_FORMAT_EXTENSIBLE = 0xFFFE

# Standard GUID Subformat prefixes for EXTENSIBLE
_KSDATAFORMAT_SUBTYPE_PCM_PREFIX = b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
_KSDATAFORMAT_SUBTYPE_IEEE_FLOAT_PREFIX = b"\x03\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"


def _parse_wav_bytes(data: bytes, channel_index: int = 0) -> ImpulseResponseData:
    """Decode an uncompressed RIFF/WAVE byte stream into ImpulseResponseData using pure Python."""
    if len(data) < 12:
        raise MalformedMeasurementDataError(f"WAV stream too short ({len(data)} bytes).")

    bio = io.BytesIO(data)
    riff_tag = bio.read(4)
    if riff_tag != b"RIFF":
        raise UnsupportedMeasurementFormatError(f"Expected RIFF header, got {riff_tag!r}.")

    riff_size = struct.unpack("<I", bio.read(4))[0]
    wave_tag = bio.read(4)
    if wave_tag != b"WAVE":
        raise UnsupportedMeasurementFormatError(f"Expected WAVE format, got {wave_tag!r}.")

    fmt_parsed = False
    format_code = 0
    num_channels = 0
    sample_rate = 0
    bits_per_sample = 0
    raw_audio_data: Optional[bytes] = None

    file_size = len(data)

    while bio.tell() < file_size:
        chunk_header = bio.read(8)
        if len(chunk_header) < 8:
            break
        chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)

        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise MalformedMeasurementDataError(f"Invalid fmt chunk size: {chunk_size}.")
            fmt_bytes = bio.read(chunk_size)
            if len(fmt_bytes) < chunk_size:
                raise MalformedMeasurementDataError("Truncated fmt chunk in WAV file.")

            format_code, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = struct.unpack(
                "<HHIIHH", fmt_bytes[:16]
            )

            if format_code == _WAVE_FORMAT_EXTENSIBLE:
                if chunk_size < 40:
                    raise MalformedMeasurementDataError("Malformed WAVE_FORMAT_EXTENSIBLE fmt chunk.")
                sub_format_guid = fmt_bytes[24:40]
                if sub_format_guid == _KSDATAFORMAT_SUBTYPE_PCM_PREFIX:
                    format_code = _WAVE_FORMAT_PCM
                elif sub_format_guid == _KSDATAFORMAT_SUBTYPE_IEEE_FLOAT_PREFIX:
                    format_code = _WAVE_FORMAT_IEEE_FLOAT
                else:
                    raise UnsupportedMeasurementFormatError(f"Unsupported extensible subformat GUID: {sub_format_guid!r}.")

            fmt_parsed = True
            # Word-align
            if chunk_size % 2 == 1:
                bio.read(1)

        elif chunk_id == b"data":
            if not fmt_parsed:
                raise MalformedMeasurementDataError("WAV data chunk encountered before fmt chunk.")
            raw_audio_data = bio.read(chunk_size)
            if len(raw_audio_data) < chunk_size:
                raise MalformedMeasurementDataError(
                    f"Truncated WAV data chunk (expected {chunk_size} bytes, got {len(raw_audio_data)})."
                )
            # Word-align
            if chunk_size % 2 == 1:
                bio.read(1)
        else:
            # Skip unknown chunk (e.g. LIST, JUNK, bext, etc.)
            bio.seek(chunk_size, io.SEEK_CUR)
            if chunk_size % 2 == 1:
                bio.read(1)

    if not fmt_parsed or raw_audio_data is None:
        raise MalformedMeasurementDataError("Incomplete WAV file: missing fmt or data chunk.")

    if num_channels < 1:
        raise InvalidMeasurementDataError(f"Invalid channel count: {num_channels}.")

    if not (8000 <= sample_rate <= 384000):
        raise InvalidMeasurementDataError(f"Sample rate {sample_rate} Hz outside valid range [8000, 384000] Hz.")

    if not isinstance(channel_index, int) or isinstance(channel_index, bool):
        raise InvalidParameterError(f"channel_index must be an integer, got {channel_index!r}.")

    if channel_index < 0 or channel_index >= num_channels:
        raise InvalidParameterError(
            f"Requested channel_index {channel_index} out of bounds for {num_channels}-channel WAV."
        )

    bytes_per_sample = bits_per_sample // 8
    frame_size = bytes_per_sample * num_channels
    if frame_size <= 0:
        raise MalformedMeasurementDataError(f"Invalid frame size calculated from bits_per_sample {bits_per_sample}.")

    total_frames = len(raw_audio_data) // frame_size
    if total_frames < 16:
        raise InvalidMeasurementDataError(
            f"Impulse response too short ({total_frames} samples; minimum required is 16)."
        )

    # Decode audio frames to float64 1D array
    if format_code == _WAVE_FORMAT_PCM:
        if bits_per_sample == 16:
            count = total_frames * num_channels
            raw_unpacked = struct.unpack(f"<{count}h", raw_audio_data[: count * 2])
            interleaved = np.array(raw_unpacked, dtype=np.float64) / 32768.0
        elif bits_per_sample == 24:
            # 24-bit PCM: 3 bytes per sample, signed little-endian with sign extension
            raw_bytes = raw_audio_data[: total_frames * frame_size]
            byte_arr = np.frombuffer(raw_bytes, dtype=np.uint8).reshape((total_frames * num_channels, 3))
            b0 = byte_arr[:, 0].astype(np.int32)
            b1 = byte_arr[:, 1].astype(np.int32)
            b2 = byte_arr[:, 2].astype(np.int32)
            # Sign extension on 24th bit (MSB of b2)
            sign_ext = np.where(b2 >= 128, -1 << 24, 0).astype(np.int32)
            int24 = b0 | (b1 << 8) | (b2 << 16) | sign_ext
            interleaved = int24.astype(np.float64) / 8388608.0
        elif bits_per_sample == 32:
            count = total_frames * num_channels
            raw_unpacked = struct.unpack(f"<{count}i", raw_audio_data[: count * 4])
            interleaved = np.array(raw_unpacked, dtype=np.float64) / 2147483648.0
        else:
            raise UnsupportedMeasurementFormatError(f"Unsupported PCM bits per sample: {bits_per_sample}.")

    elif format_code == _WAVE_FORMAT_IEEE_FLOAT:
        if bits_per_sample == 32:
            count = total_frames * num_channels
            raw_unpacked = struct.unpack(f"<{count}f", raw_audio_data[: count * 4])
            interleaved = np.array(raw_unpacked, dtype=np.float64)
        else:
            raise UnsupportedMeasurementFormatError(f"Unsupported IEEE Float bits per sample: {bits_per_sample}.")
    else:
        raise UnsupportedMeasurementFormatError(f"Unsupported WAV format tag: {format_code:#06x}.")

    if not np.all(np.isfinite(interleaved)):
        raise InvalidMeasurementDataError("WAV stream contains NaN or infinite sample values.")

    # De-interleave and select channel
    if num_channels == 1:
        channel_samples = interleaved
    else:
        channel_samples = interleaved[channel_index::num_channels]

    return ImpulseResponseData(samples=channel_samples, sample_rate=sample_rate)


def parse_impulse_text(text: str, sample_rate: Optional[int] = None) -> ImpulseResponseData:
    """Parse ASCII time-domain impulse response text data.

    Supported Layouts:
    1. Two-column: [Time (seconds or ms), Amplitude] -> strictly monotonic time, derived sample_rate = round(1 / dt)
    2. Single-column: [Amplitude] -> requires explicit sample_rate: int

    Args:
        text: Raw ASCII text content.
        sample_rate: Optional explicit sample rate in Hz (required for 1-column data).

    Returns:
        Immutable ImpulseResponseData instance.

    Raises:
        MalformedMeasurementDataError: For syntax or column inconsistencies.
        InvalidMeasurementDataError: For non-monotonic time, negative sample rates, or NaN/Inf values.
        InvalidParameterError: For missing sample rate on single-column data.
    """
    if not isinstance(text, str):
        raise InvalidParameterError(f"Expected str input, got {type(text)!r}.")

    lines = text.splitlines()
    rows: list[list[float]] = []

    for line_idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        # Comment detection
        if line.startswith(("#", "*", "//")):
            continue

        # Semicolon comment vs separator handling
        if line.startswith(";"):
            # Check if it parses as valid numeric row under semicolon separator
            tokens = [t.strip() for t in line[1:].split(";") if t.strip()]
            if not tokens:
                continue
            try:
                numeric_tokens = [float(t) for t in tokens]
                rows.append(numeric_tokens)
                continue
            except ValueError:
                # Semicolon comment line
                continue

        # Separator tokenization
        if "," in line:
            tokens = [t.strip() for t in line.split(",") if t.strip()]
        elif ";" in line:
            tokens = [t.strip() for t in line.split(";") if t.strip()]
        else:
            tokens = line.split()

        if not tokens:
            continue

        try:
            numeric_row = [float(t) for t in tokens]
            rows.append(numeric_row)
        except ValueError:
            # Header or comment line containing non-numeric strings
            if len(rows) == 0:
                continue
            raise MalformedMeasurementDataError(f"Line {line_idx} contains invalid non-numeric tokens: {line!r}.")

    if len(rows) < 16:
        raise InvalidMeasurementDataError(
            f"Impulse response contains too few data rows ({len(rows)}; minimum 16 required)."
        )

    col_count = len(rows[0])
    if col_count not in (1, 2):
        raise MalformedMeasurementDataError(f"Expected 1 or 2 columns, got {col_count}.")

    for r_idx, row in enumerate(rows, start=1):
        if len(row) != col_count:
            raise MalformedMeasurementDataError(
                f"Inconsistent column count at row {r_idx} (expected {col_count}, got {len(row)})."
            )

    row_array = np.array(rows, dtype=np.float64)
    if not np.all(np.isfinite(row_array)):
        raise InvalidMeasurementDataError("Impulse response data contains NaN or infinite values.")

    if col_count == 2:
        # Two-column: [Time, Amplitude]
        times = row_array[:, 0]
        amplitudes = row_array[:, 1]

        # Check strictly monotonic ascending time
        diffs = np.diff(times)
        if np.any(diffs <= 0.0):
            raise InvalidMeasurementDataError("Time coordinates must be strictly monotonically ascending.")

        # Derive sample rate from dt
        dt_mean = float(np.mean(diffs))
        if dt_mean <= 0.0:
            raise InvalidMeasurementDataError(f"Invalid non-positive delta time: {dt_mean}.")

        # Check time unit (seconds vs milliseconds)
        # If mean dt is between 0.001 and 1.0 and total duration > 1000, time might be in ms
        # Otherwise standard is seconds
        derived_fs = round(1.0 / dt_mean)
        if not (8000 <= derived_fs <= 384000):
            # Check if time was in milliseconds
            dt_sec = dt_mean / 1000.0
            derived_fs_ms = round(1.0 / dt_sec)
            if 8000 <= derived_fs_ms <= 384000:
                derived_fs = derived_fs_ms
            else:
                raise InvalidMeasurementDataError(
                    f"Derived sample rate {derived_fs} Hz outside valid range [8000, 384000] Hz."
                )

        final_fs = sample_rate if sample_rate is not None else derived_fs
        if not (8000 <= final_fs <= 384000):
            raise InvalidMeasurementDataError(f"Sample rate {final_fs} Hz outside valid range [8000, 384000] Hz.")

        return ImpulseResponseData(samples=amplitudes, sample_rate=int(final_fs))

    else:
        # Single-column: [Amplitude]
        if sample_rate is None:
            raise InvalidParameterError("sample_rate must be explicitly provided for single-column impulse response text data.")
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or not (8000 <= sample_rate <= 384000):
            raise InvalidMeasurementDataError(f"Invalid sample_rate: {sample_rate!r}.")

        amplitudes = row_array[:, 0]
        return ImpulseResponseData(samples=amplitudes, sample_rate=int(sample_rate))


def parse_impulse_file(
    file_path: Union[str, Path],
    channel_index: int = 0,
    sample_rate: Optional[int] = None,
) -> ImpulseResponseData:
    """Ingest a time-domain impulse response file (.wav, .txt, .csv, .ir, .tim).

    Args:
        file_path: Absolute or relative Path or str to the measurement file.
        channel_index: Zero-indexed audio channel to extract for multi-channel WAV files (default 0).
        sample_rate: Explicit sample rate in Hz (required for single-column text files).

    Returns:
        Immutable ImpulseResponseData domain object.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnsupportedMeasurementFormatError: If the file format or extension is not supported.
        MalformedMeasurementDataError: If file structure or headers are corrupt.
        InvalidMeasurementDataError: If sample rate or values violate invariants.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Impulse measurement file not found: {path.resolve()}")

    raw_bytes = path.read_bytes()
    suffix = path.suffix.lower()

    if suffix == ".wav":
        return _parse_wav_bytes(raw_bytes, channel_index=channel_index)
    elif suffix in (".txt", ".csv", ".ir", ".tim", ".dat"):
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except UnicodeDecodeError as err:
                raise MalformedMeasurementDataError(f"Unable to decode text file {path.name}: {err}") from err
        return parse_impulse_text(text, sample_rate=sample_rate)
    else:
        # Check if byte content starts with RIFF (WAV without standard extension)
        if raw_bytes.startswith(b"RIFF"):
            return _parse_wav_bytes(raw_bytes, channel_index=channel_index)
        raise UnsupportedMeasurementFormatError(
            f"Unsupported impulse response file extension '{suffix}'. Supported formats: .wav, .txt, .csv, .ir, .tim."
        )
