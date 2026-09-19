"""Tests for Phase 4A Measurement File Ingestion.

Normative Authority:
- docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md
- docs/phases/PHASE_4A_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.io.exceptions import (
    InvalidMeasurementDataError,
    MalformedMeasurementDataError,
    UnsupportedMeasurementFormatError,
)
from acoustiforge.io.parser import parse_measurement_file, parse_measurement_text
from acoustiforge.io.result import MeasurementImportResult

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class TestMeasurementIngestion:
    """Verification of measurement text parsers and invariant enforcement."""

    def test_parse_valid_2col_frd_file(self) -> None:
        """Verify parsing standard 2-column whitespace-delimited FRD file."""
        file_path = FIXTURES_DIR / "valid_2col.frd"
        result = parse_measurement_file(file_path)

        assert isinstance(result, MeasurementImportResult)
        assert result.source_format == "frd"
        assert result.source_path == str(file_path)
        assert len(result.header_comments) >= 1

        data = result.data
        assert isinstance(data, FrequencyResponseData)
        assert data.num_points == 5
        assert data.phase_rad is None

        # Exact analytical values
        expected_freqs = np.array([20.0, 100.0, 1000.0, 10000.0, 20000.0])
        expected_mags = np.array([82.5, 85.0, 88.0, 87.5, 84.0])
        np.testing.assert_allclose(data.frequencies_hz, expected_freqs)
        np.testing.assert_allclose(data.magnitude_db, expected_mags)

        # Immutability
        assert not data.frequencies_hz.flags.writeable
        assert not data.magnitude_db.flags.writeable

    def test_parse_valid_3col_csv_file(self) -> None:
        """Verify parsing 3-column CSV with headers and phase."""
        file_path = FIXTURES_DIR / "valid_3col.csv"
        result = parse_measurement_file(file_path)

        assert result.source_format == "csv"
        data = result.data
        assert data.num_points == 5
        assert data.phase_rad is not None

        expected_freqs = np.array([20.0, 100.0, 1000.0, 10000.0, 20000.0])
        expected_mags = np.array([82.5, 85.0, 88.0, 87.5, 84.0])
        expected_phase_deg = np.array([0.0, -15.0, -45.0, -90.0, -135.0])
        expected_phase_rad = np.deg2rad(expected_phase_deg)

        np.testing.assert_allclose(data.frequencies_hz, expected_freqs)
        np.testing.assert_allclose(data.magnitude_db, expected_mags)
        np.testing.assert_allclose(data.phase_rad, expected_phase_rad)

    def test_parse_valid_semicolon_csv_precedence_rule(self) -> None:
        """Verify semicolon-delimited CSV rows are parsed as data and comments are preserved."""
        file_path = FIXTURES_DIR / "valid_semicolon.csv"
        result = parse_measurement_file(file_path)

        data = result.data
        assert data.num_points == 4
        assert len(result.header_comments) >= 1
        assert "Semicolon delimited" in result.header_comments[0]

        expected_freqs = np.array([20.0, 100.0, 1000.0, 20000.0])
        np.testing.assert_allclose(data.frequencies_hz, expected_freqs)

    def test_parse_rew_text_export(self) -> None:
        """Verify parsing REW plain text export with * comments and 3 columns."""
        file_path = FIXTURES_DIR / "rew_export.txt"
        result = parse_measurement_file(file_path)

        assert result.source_format == "txt"
        assert len(result.header_comments) == 3
        assert result.data.num_points == 7
        assert result.data.frequency_range == (20.0, 20000.0)

    def test_reject_unsupported_format(self, tmp_path: Path) -> None:
        """Verify error on unsupported binary or non-text extensions."""
        bin_file = tmp_path / "measurement.bin"
        bin_file.write_bytes(b"\x00\x01\x02\x03")

        with pytest.raises(UnsupportedMeasurementFormatError, match="Unsupported measurement file extension"):
            parse_measurement_file(bin_file)

    def test_reject_empty_or_single_point(self) -> None:
        """Verify rejection of empty data or fewer than 2 points."""
        with pytest.raises(InvalidMeasurementDataError, match="empty"):
            parse_measurement_text("")

        with pytest.raises(InvalidMeasurementDataError, match="at least 2 coordinate rows"):
            parse_measurement_text("100.0 85.0\n")

    def test_reject_non_monotonic_frequencies(self) -> None:
        """Verify rejection of non-ascending frequency sequences."""
        file_path = FIXTURES_DIR / "invalid_frequency_order.frd"
        with pytest.raises(InvalidMeasurementDataError, match="strictly monotonically ascending"):
            parse_measurement_file(file_path)

    def test_reject_duplicate_frequencies(self) -> None:
        """Verify rejection of duplicate frequency points."""
        text = "20.0 80.0\n100.0 85.0\n100.0 86.0\n1000.0 88.0"
        with pytest.raises(InvalidMeasurementDataError, match="strictly monotonically ascending"):
            parse_measurement_text(text)

    def test_reject_non_positive_and_non_finite(self) -> None:
        """Verify rejection of zero, negative, NaN, and Inf values."""
        with pytest.raises(InvalidMeasurementDataError, match="strictly positive"):
            parse_measurement_text("0.0 80.0\n100.0 85.0")

        with pytest.raises(InvalidMeasurementDataError, match="strictly positive"):
            parse_measurement_text("-20.0 80.0\n100.0 85.0")

        with pytest.raises(InvalidMeasurementDataError, match="non-finite"):
            parse_measurement_text("20.0 nan\n100.0 85.0")

        with pytest.raises(InvalidMeasurementDataError, match="non-finite"):
            parse_measurement_text("20.0 80.0\n100.0 inf")

    def test_reject_malformed_and_jagged_rows(self) -> None:
        """Verify rejection of inconsistent row lengths."""
        file_path = FIXTURES_DIR / "malformed_jagged.txt"
        with pytest.raises(MalformedMeasurementDataError):
            parse_measurement_file(file_path)
