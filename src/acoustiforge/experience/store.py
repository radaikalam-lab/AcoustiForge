"""Local-first append-only Experience Store for AcoustiForge runtime episodes.

Normative Authority:
    - Phase 5-6 Specification: Section 18 (Experience Store)
    - Governing Principle: "The Experience Store is authoritative historical evidence, NOT LLM memory."
    - Security Invariant: "Store must never execute contents of an experience record."
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence

from .contracts import (
    DayPhase,
    EvidenceType,
    ExperienceRecord,
    ExperienceValidationError,
    OutcomeClassification,
)


class ExperienceStoreError(Exception):
    """Raised when an ExperienceStore operation fails."""
    pass


class ExperienceStore:
    """Append-only, local-first JSONL store for historical ExperienceRecords.

    Guarantees:
        1. Local-First: Data remains strictly on local filesystem; no telemetry or remote transmission.
        2. Append-Only: Existing records are immutable and never overwritten.
        3. Schema Validation Firewall: Every record is validated against canonical dataclass contracts before commit.
        4. Non-Executable Safety: Storage data is parsed strictly as passive JSON; no dynamic execution or eval.
    """

    def __init__(self, storage_path: str | Path) -> None:
        self._path = Path(storage_path).resolve()
        # Ensure parent directory exists
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        """Absolute file path to the backing JSONL store."""
        return self._path

    def append(self, record: ExperienceRecord) -> None:
        """Append a validated ExperienceRecord to the store.

        Args:
            record: Validated ExperienceRecord instance.

        Raises:
            ExperienceValidationError: If record is invalid or not an ExperienceRecord.
            ExperienceStoreError: If writing to disk fails.
        """
        if not isinstance(record, ExperienceRecord):
            raise ExperienceValidationError(
                f"Expected ExperienceRecord instance, got {type(record)!r}"
            )

        # Validate by round-tripping to dict
        record_dict = record.to_dict()
        line = json.dumps(record_dict, ensure_ascii=False, sort_keys=True)

        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            raise ExperienceStoreError(f"Failed to append record to {self._path}: {e}") from e

    def append_many(self, records: Sequence[ExperienceRecord]) -> int:
        """Append multiple validated records atomically or sequentially.

        Returns:
            Count of records successfully appended.
        """
        count = 0
        for rec in records:
            self.append(rec)
            count += 1
        return count

    def get_by_id(self, experience_id: str) -> Optional[ExperienceRecord]:
        """Retrieve an ExperienceRecord by its unique ID.

        Returns:
            ExperienceRecord if found, None otherwise.
        """
        if not experience_id:
            return None

        for record in self.iter_records():
            if record.experience_id == experience_id:
                return record
        return None

    def query(
        self,
        outcome: Optional[OutcomeClassification] = None,
        evidence_type: Optional[EvidenceType] = None,
        day_phase: Optional[DayPhase] = None,
        schema_version: Optional[str] = None,
        min_engagement_rating: Optional[float] = None,
        session_completed: Optional[bool] = None,
        session_abandoned: Optional[bool] = None,
        start_time_iso: Optional[str] = None,
        end_time_iso: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[ExperienceRecord]:
        """Query and filter experience records from local storage.

        Args:
            outcome: Optional filter by outcome status.
            evidence_type: Optional filter by evidence type.
            day_phase: Optional filter by diurnal solar/temporal phase.
            schema_version: Optional filter by schema version.
            min_engagement_rating: Optional lower bound on explicit engagement rating.
            session_completed: Optional filter for completed sessions.
            session_abandoned: Optional filter for abandoned sessions.
            start_time_iso: Optional lower timestamp bound (inclusive).
            end_time_iso: Optional upper timestamp bound (inclusive).
            limit: Maximum count of records to return.

        Returns:
            List of matching validated ExperienceRecords in chronological order.
        """
        results: list[ExperienceRecord] = []

        for record in self.iter_records():
            if outcome is not None and record.outcome != outcome:
                continue
            if evidence_type is not None and record.evidence_type != evidence_type:
                continue
            if schema_version is not None and record.schema_version != schema_version:
                continue
            if day_phase is not None:
                if (
                    record.temporal_solar_context is None
                    or record.temporal_solar_context.day_phase != day_phase
                ):
                    continue
            if min_engagement_rating is not None:
                if (
                    record.engagement is None
                    or record.engagement.explicit_engagement_rating is None
                    or record.engagement.explicit_engagement_rating < min_engagement_rating
                ):
                    continue
            if session_completed is not None:
                if (
                    record.engagement is None
                    or record.engagement.session_completed != session_completed
                ):
                    continue
            if session_abandoned is not None:
                if (
                    record.engagement is None
                    or record.engagement.session_abandoned != session_abandoned
                ):
                    continue
            if start_time_iso is not None and record.timestamp_iso < start_time_iso:
                continue
            if end_time_iso is not None and record.timestamp_iso > end_time_iso:
                continue

            results.append(record)
            if limit is not None and len(results) >= limit:
                break

        return results

    def iter_records(self, skip_corrupted: bool = True) -> Iterator[ExperienceRecord]:
        """Iterate lazily over all records in the store with fail-closed validation.

        Args:
            skip_corrupted: If True, log/skip malformed JSON lines; if False, raise on error.

        Yields:
            Validated ExperienceRecord instances.
        """
        if not self._path.exists():
            return

        with open(self._path, "r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    record = ExperienceRecord.from_dict(data)
                    yield record
                except Exception as e:
                    if not skip_corrupted:
                        raise ExperienceStoreError(
                            f"Corrupted record at line {line_no} in {self._path}: {e}"
                        ) from e
                    # Otherwise safely ignore corrupted lines (fail-closed)

    def count(self) -> int:
        """Return the total number of valid records in the store."""
        return sum(1 for _ in self.iter_records())
