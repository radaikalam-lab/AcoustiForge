"""AcoustiForge Deterministic Measurement File Parser.

Normative Authority:
- docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md
- docs/phases/PHASE_4A_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import os
from pathlib import Path
import re
from typing import List, Optional, Tuple, Union
import numpy as np

from ..domain.measurements import FrequencyResponseData
from .exceptions import (
    InvalidMeasurementDataError,
    MalformedMeasurementDataError,
    UnsupportedMeasurementFormatError,
)
from .result import MeasurementImportResult

SUPPORTED_EXTENSIONS = {".frd", ".csv", ".txt", ".cal"}


def _is_unambiguous_comment(line: str) -> bool:
    """Check if line starts with unambiguous comment character (#, *, //)."""
    stripped = line.strip()
    return (
        stripped.startswith("#")
        or stripped.startswith("*")
        or stripped.startswith("//")
    )


def _try_parse_semicolon_numeric_row(line: str) -> Optional[List[float]]:
    """Attempt to parse line as a semicolon-separated numerical data row.

    Returns list of floats if valid, or None if line is a textual comment.
    """
    stripped = line.strip()
    if not stripped:
        return None
    # If line starts with ;, it might be comment or leading separator
    parts = [p.strip() for p in stripped.split(";") if p.strip()]
    if len(parts) in (2, 3):
        try:
            return [float(p) for p in parts]
        except ValueError:
            return None
    return None


def _detect_separator(lines: List[str]) -> str:
    """Detect primary separator (comma, semicolon, or whitespace) from candidate data lines."""
    for line in lines:
        stripped = line.strip()
        if not stripped or _is_unambiguous_comment(stripped):
            continue
        if _try_parse_semicolon_numeric_row(stripped) is not None:
            return ";"
        if "," in stripped:
            return ","
        if ";" in stripped:
            return ";"
    return r"\s+"


def parse_measurement_text(
    text: str,
    source_format: str = "txt",
    source_path: Optional[str] = None,
) -> MeasurementImportResult:
    """Parse raw measurement ASCII text into FrequencyResponseData and metadata container.

    Args:
        text: Raw file string content.
        source_format: Format identifier ('frd', 'csv', 'txt', 'cal').
        source_path: Optional source filesystem path string.

    Returns:
        MeasurementImportResult containing immutable FrequencyResponseData and provenance.

    Raises:
        MalformedMeasurementDataError: If text is jagged, unparseable, or contains corrupt rows.
        InvalidMeasurementDataError: If frequencies are non-positive, non-ascending, or non-finite.
    """
    if not isinstance(text, str):
        raise MalformedMeasurementDataError(f"Expected string input, got {type(text)!r}.")

    lines = text.splitlines()
    if not lines or not any(line.strip() for line in lines):
        raise InvalidMeasurementDataError("Measurement file is empty.")

    header_comments: List[str] = []
    data_rows: List[List[float]] = []
    expected_cols: Optional[int] = None

    separator = _detect_separator(lines)

    for line_idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        # 1. Unambiguous comment lines
        if _is_unambiguous_comment(line):
            header_comments.append(line)
            continue

        # 2. Semicolon line handling under normative precedence rule
        if line.startswith(";"):
            semicolon_row = _try_parse_semicolon_numeric_row(line)
            if semicolon_row is not None:
                row_floats = semicolon_row
            else:
                header_comments.append(line)
                continue
        else:
            # 3. Tokenize data row
            if separator == r"\s+":
                tokens = line.split()
            elif separator == ",":
                tokens = [t.strip() for t in line.split(",") if t.strip()]
            elif separator == ";":
                tokens = [t.strip() for t in line.split(";") if t.strip()]
            else:
                tokens = line.split()

            try:
                row_floats = [float(t) for t in tokens]
            except ValueError as err:
                if any(re.search(r"[a-zA-Z]", t) for t in tokens):
                    header_comments.append(line)
                    continue
                raise MalformedMeasurementDataError(
                    f"Line {line_idx}: Failed to parse numeric value from {line!r}."
                ) from err

        # Validate column consistency
        num_tokens = len(row_floats)
        if num_tokens not in (2, 3):
            raise MalformedMeasurementDataError(
                f"Line {line_idx}: Expected 2 or 3 columns [Freq, Mag, (Phase)], got {num_tokens}."
            )

        if expected_cols is None:
            expected_cols = num_tokens
        elif expected_cols != num_tokens:
            raise MalformedMeasurementDataError(
                f"Line {line_idx}: Column count mismatch. Expected {expected_cols} columns, got {num_tokens}."
            )

        data_rows.append(row_floats)

    if len(data_rows) < 2:
        raise InvalidMeasurementDataError(
            f"Measurement dataset must contain at least 2 coordinate rows, found {len(data_rows)}."
        )

    # Convert to NumPy arrays for validation and storage
    data_matrix = np.array(data_rows, dtype=np.float64)
    freqs = data_matrix[:, 0]
    mags = data_matrix[:, 1]

    # Validate frequencies
    if not np.all(np.isfinite(freqs)):
        raise InvalidMeasurementDataError("Frequencies contain non-finite values (NaN or Inf).")
    if not np.all(freqs > 0.0):
        raise InvalidMeasurementDataError("Frequencies must be strictly positive (> 0 Hz).")
    
    # Strict ascending monotonicity check (no duplicates or reversals)
    diffs = np.diff(freqs)
    if np.any(diffs <= 0.0):
        raise InvalidMeasurementDataError("Frequencies must be strictly monotonically ascending with no duplicates.")

    # Validate magnitudes
    if not np.all(np.isfinite(mags)):
        raise InvalidMeasurementDataError("Magnitudes contain non-finite values (NaN or Inf).")

    # Optional phase
    phase_rad: Optional[np.ndarray] = None
    if expected_cols == 3:
        phase_deg = data_matrix[:, 2]
        if not np.all(np.isfinite(phase_deg)):
            raise InvalidMeasurementDataError("Phase contains non-finite values (NaN or Inf).")
        phase_rad = np.deg2rad(phase_deg)

    frd_data = FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=mags,
        phase_rad=phase_rad,
    )

    return MeasurementImportResult(
        data=frd_data,
        source_format=source_format.lower().lstrip("."),
        source_path=source_path,
        header_comments=tuple(header_comments),
    )


def parse_measurement_file(file_path: Union[str, Path]) -> MeasurementImportResult:
    """Parse a measurement file (.frd, .csv, .txt, .cal) from filesystem into FrequencyResponseData.

    Args:
        file_path: Absolute or relative path to measurement file.

    Returns:
        MeasurementImportResult containing immutable FrequencyResponseData and provenance.

    Raises:
        FileNotFoundError: If file does not exist.
        UnsupportedMeasurementFormatError: If file format extension is unsupported.
        MalformedMeasurementDataError: If file cannot be decoded or parsed.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Measurement file not found: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedMeasurementFormatError(
            f"Unsupported measurement file extension {ext!r}. Supported extensions: {sorted(SUPPORTED_EXTENSIONS)}."
        )

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="latin-1")
        except Exception as err:
            raise MalformedMeasurementDataError(f"Failed to decode measurement file {path}: {err}") from err

    return parse_measurement_text(
        text=text,
        source_format=ext,
        source_path=str(path),
    )
