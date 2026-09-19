"""AcoustiForge Measurement Import Result Container.

Normative Authority:
- docs/contracts/MEASUREMENT_INGESTION_CONTRACT.md
- docs/phases/PHASE_4A_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ..domain.measurements import FrequencyResponseData


@dataclass(frozen=True, slots=True)
class MeasurementImportResult:
    """Immutable container holding parsed acoustic measurement data and file provenance."""
    data: FrequencyResponseData
    source_format: str
    source_path: Optional[str] = None
    header_comments: Tuple[str, ...] = ()
