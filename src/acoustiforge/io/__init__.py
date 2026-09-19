"""AcoustiForge Measurement I/O and Ingestion Package.

Offline parsers and data import routines for acoustic measurement files.

Normative Authority:
- docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md
- docs/phases/PHASE_4A_CONTRACT_RECONCILIATION.md
"""

from .exceptions import (
    InvalidMeasurementDataError,
    MalformedMeasurementDataError,
    MeasurementIngestionError,
    UnsupportedMeasurementFormatError,
)
from .parser import parse_measurement_file, parse_measurement_text
from .result import MeasurementImportResult

__all__ = [
    "InvalidMeasurementDataError",
    "MalformedMeasurementDataError",
    "MeasurementImportResult",
    "MeasurementIngestionError",
    "UnsupportedMeasurementFormatError",
    "parse_measurement_file",
    "parse_measurement_text",
]
