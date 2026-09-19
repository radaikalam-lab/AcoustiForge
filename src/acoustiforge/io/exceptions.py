"""AcoustiForge Measurement Ingestion Exceptions.

Normative Authority:
- docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

from ..contracts.validation import AcoustiForgeError


class MeasurementIngestionError(AcoustiForgeError):
    """Base exception for all measurement parsing and file ingestion errors."""
    pass


class UnsupportedMeasurementFormatError(MeasurementIngestionError):
    """Raised when an unsupported file format or binary measurement file is provided."""
    pass


class MalformedMeasurementDataError(MeasurementIngestionError):
    """Raised when file content contains non-decodable text, jagged rows, or syntax errors."""
    pass


class InvalidMeasurementDataError(MeasurementIngestionError):
    """Raised when measurement data violates acoustic invariants (non-positive/non-monotonic frequencies, NaN/Inf)."""
    pass
