"""Deterministic, local-first Experience Retrieval service for AcoustiForge.

Normative Authority:
    - Phase 5-7A Specification: Experience Retrieval & Analytics
    - Governing Principle: "AI proposes. AcoustiForge validates and executes."
    - Storage Principle: "The Experience Store is authoritative historical evidence, NOT LLM memory."
    - Evidence Principle: "Historical experience is advisory evidence, never an authoritative source of DSP parameters."
    - Temporal Principle: "Temporal and solar context are contextual variables, not measurements of mood."
    - Engagement Principle: "Behavioral engagement evidence must not be silently interpreted as satisfaction or psychological state."
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence
from dataclasses import dataclass, field

from .contracts import (
    DayPhase,
    EvidenceType,
    ExperienceRecord,
    ExperienceValidationError,
    FeedbackStatus,
    OutcomeClassification,
)
from .store import ExperienceStore


# ==============================================================================
# 1. Structured Retrieval Query Contract
# ==============================================================================

@dataclass(frozen=True)
class ExperienceQuery:
    """Multi-criteria structured filter query for ExperienceRecords.

    All criteria are evaluated strictly using conjunctive (AND) semantics.
    """
    # Identity & Evidence Type
    outcome: Optional[OutcomeClassification] = None
    evidence_type: Optional[EvidenceType] = None
    schema_version: Optional[str] = None

    # Acoustic Intent & Specification
    crossover_family: Optional[str] = None
    crossover_order: Optional[int] = None
    target_frequency_range_hz: Optional[tuple[float, float]] = None
    spatial_profile: Optional[str] = None
    min_spatial_positions: Optional[int] = None
    target_preset: Optional[str] = None

    # Optimization Result
    converged_only: Optional[bool] = None
    selected_crossover_range_hz: Optional[tuple[float, float]] = None
    max_loss_db: Optional[float] = None
    optimizer_name: Optional[str] = None

    # Execution Context
    backend_type: Optional[str] = None
    platform: Optional[str] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    hardware_target: Optional[str] = None

    # Engagement & User Feedback
    min_engagement_rating: Optional[float] = None
    feedback_status: Optional[FeedbackStatus] = None
    min_user_rating: Optional[float] = None
    session_completed_only: Optional[bool] = None
    session_abandoned_only: Optional[bool] = None
    min_listening_duration_s: Optional[float] = None
    max_reverted_changes: Optional[int] = None

    # Temporal & Diurnal Context
    day_phase: Optional[DayPhase] = None
    start_time_iso: Optional[str] = None
    end_time_iso: Optional[str] = None

    # Query Control
    limit: Optional[int] = None

    def __post_init__(self) -> None:
        if self.target_frequency_range_hz is not None:
            if len(self.target_frequency_range_hz) != 2:
                raise ExperienceValidationError("target_frequency_range_hz must be (f_min, f_max).")
            f_min, f_max = self.target_frequency_range_hz
            if not (math.isfinite(f_min) and math.isfinite(f_max) and 0 < f_min <= f_max):
                raise ExperienceValidationError(f"Invalid target_frequency_range_hz: {self.target_frequency_range_hz}")

        if self.selected_crossover_range_hz is not None:
            if len(self.selected_crossover_range_hz) != 2:
                raise ExperienceValidationError("selected_crossover_range_hz must be (f_min, f_max).")
            f_min, f_max = self.selected_crossover_range_hz
            if not (math.isfinite(f_min) and math.isfinite(f_max) and 0 < f_min <= f_max):
                raise ExperienceValidationError(f"Invalid selected_crossover_range_hz: {self.selected_crossover_range_hz}")

        if self.limit is not None and self.limit <= 0:
            raise ExperienceValidationError("limit must be a positive integer.")


# ==============================================================================
# 2. ExperienceRetriever Engine
# ==============================================================================

class ExperienceRetriever:
    """Deterministic, local query and ranking engine over an ExperienceStore."""

    def __init__(self, store: ExperienceStore) -> None:
        if not isinstance(store, ExperienceStore):
            raise ExperienceValidationError(f"Expected ExperienceStore instance, got {type(store)!r}")
        self._store = store

    @property
    def store(self) -> ExperienceStore:
        return self._store

    def search(
        self,
        query: Optional[ExperienceQuery] = None,
        target_crossover_hz: Optional[float] = None,
        **kwargs: Any,
    ) -> list[ExperienceRecord]:
        """Execute a multi-criteria search and return deterministically ranked matching records.

        Args:
            query: Optional ExperienceQuery instance. If omitted, constructed from kwargs.
            target_crossover_hz: Optional reference crossover frequency for acoustic proximity ranking.
            **kwargs: Inline filter criteria matching ExperienceQuery attributes.

        Returns:
            List of matching ExperienceRecords in deterministic ranking order.
        """
        if query is None:
            query = ExperienceQuery(**kwargs)

        matching_records: list[ExperienceRecord] = []

        for record in self._store.iter_records(skip_corrupted=True):
            if self._matches(record, query):
                matching_records.append(record)

        ranked_records = self.deterministic_rank(
            matching_records,
            target_crossover_hz=target_crossover_hz,
        )

        if query.limit is not None:
            return ranked_records[: query.limit]
        return ranked_records

    def _matches(self, record: ExperienceRecord, q: ExperienceQuery) -> bool:
        """Check if an ExperienceRecord satisfies all query criteria (AND semantics)."""
        # Identity & Evidence
        if q.outcome is not None and record.outcome != q.outcome:
            return False
        if q.evidence_type is not None and record.evidence_type != q.evidence_type:
            return False
        if q.schema_version is not None and record.schema_version != q.schema_version:
            return False

        # Acoustic Intent & Specification
        intent = record.intent_summary
        spec = record.specification_summary

        if q.crossover_family is not None:
            fam = spec.crossover_family if spec else (intent.crossover_family if intent else None)
            if fam is None or fam.upper() != q.crossover_family.upper():
                return False

        if q.crossover_order is not None:
            order = spec.crossover_order if spec else (intent.crossover_order if intent else None)
            if order is None or order != q.crossover_order:
                return False

        if q.target_frequency_range_hz is not None:
            f_min, f_max = q.target_frequency_range_hz
            target_f = intent.crossover_frequency_target_hz if intent else None
            if target_f is None or not (f_min <= target_f <= f_max):
                return False

        if q.spatial_profile is not None:
            profile = intent.spatial_profile if intent else None
            if profile is None or profile != q.spatial_profile:
                return False

        if q.min_spatial_positions is not None:
            pos_count = spec.spatial_position_count if spec else 1
            if pos_count < q.min_spatial_positions:
                return False

        if q.target_preset is not None:
            preset = intent.target_preset if intent else None
            if preset is None or preset != q.target_preset:
                return False

        # Optimization
        opt = record.optimization_summary
        if q.converged_only is not None and q.converged_only:
            if opt is None or not opt.converged:
                return False

        if q.selected_crossover_range_hz is not None:
            if opt is None:
                return False
            f_min, f_max = q.selected_crossover_range_hz
            if not (f_min <= opt.selected_crossover_hz <= f_max):
                return False

        if q.max_loss_db is not None:
            if opt is None or opt.final_loss_db > q.max_loss_db:
                return False

        if q.optimizer_name is not None:
            if opt is None or opt.optimizer_name != q.optimizer_name:
                return False

        # Execution Context
        exec_ctx = record.execution_context
        if q.backend_type is not None:
            if exec_ctx is None or exec_ctx.backend_type != q.backend_type:
                return False
        if q.platform is not None:
            if exec_ctx is None or exec_ctx.platform != q.platform:
                return False
        if q.sample_rate is not None:
            if exec_ctx is None or exec_ctx.sample_rate != q.sample_rate:
                return False
        if q.channels is not None:
            if exec_ctx is None or exec_ctx.channels != q.channels:
                return False
        if q.hardware_target is not None:
            if exec_ctx is None or exec_ctx.hardware_target != q.hardware_target:
                return False

        # Engagement & Feedback
        eng = record.engagement
        fb = record.human_feedback

        if q.min_engagement_rating is not None:
            if eng is None or eng.explicit_engagement_rating is None or eng.explicit_engagement_rating < q.min_engagement_rating:
                return False

        if q.feedback_status is not None:
            if fb is None or fb.status != q.feedback_status:
                return False

        if q.min_user_rating is not None:
            if fb is None or fb.rating is None or fb.rating < q.min_user_rating:
                return False

        if q.session_completed_only is not None and q.session_completed_only:
            if eng is None or eng.session_completed is not True:
                return False

        if q.session_abandoned_only is not None and q.session_abandoned_only:
            if eng is None or eng.session_abandoned is not True:
                return False

        if q.min_listening_duration_s is not None:
            if eng is None or eng.listening_duration_s is None or eng.listening_duration_s < q.min_listening_duration_s:
                return False

        if q.max_reverted_changes is not None:
            if eng is None or eng.reverted_change_count is None or eng.reverted_change_count > q.max_reverted_changes:
                return False

        # Temporal Context
        temporal = record.temporal_solar_context
        if q.day_phase is not None:
            if temporal is None or temporal.day_phase != q.day_phase:
                return False

        if q.start_time_iso is not None and record.timestamp_iso < q.start_time_iso:
            return False
        if q.end_time_iso is not None and record.timestamp_iso > q.end_time_iso:
            return False

        return True

    def deterministic_rank(
        self,
        records: Sequence[ExperienceRecord],
        target_crossover_hz: Optional[float] = None,
    ) -> list[ExperienceRecord]:
        """Deterministically sort records using a strict hierarchical ranking policy.

        Hierarchy:
            1. Outcome Tier (SUCCESS > PARTIAL > UNKNOWN > REJECTED > FAILED)
            2. Explicit Human Rating (Highest rating first; unrated last)
            3. Acoustic Proximity (|selected_crossover_hz - target_crossover_hz| ascending, if target provided)
            4. Final Optimization Loss (Lowest final_loss_db first)
            5. Stable Immutable Tie-Breaker (experience_id ascending)
        """
        outcome_rank = {
            OutcomeClassification.SUCCESS: 0,
            OutcomeClassification.PARTIAL: 1,
            OutcomeClassification.UNKNOWN: 2,
            OutcomeClassification.REJECTED: 3,
            OutcomeClassification.FAILED: 4,
        }

        def _sort_key(rec: ExperienceRecord) -> tuple[int, float, float, float, str]:
            # 1. Outcome
            out_score = outcome_rank.get(rec.outcome, 99)

            # 2. Rating (Inverted for descending sort; None placed after lowest rating)
            user_rating = rec.human_feedback.rating if rec.human_feedback and rec.human_feedback.rating is not None else None
            eng_rating = rec.engagement.explicit_engagement_rating if rec.engagement and rec.engagement.explicit_engagement_rating is not None else None
            effective_rating = user_rating if user_rating is not None else eng_rating
            rating_score = -float(effective_rating) if effective_rating is not None else 0.0

            # 3. Acoustic Distance
            if target_crossover_hz is not None and rec.optimization_summary is not None:
                acoustic_dist = abs(rec.optimization_summary.selected_crossover_hz - target_crossover_hz)
            else:
                acoustic_dist = 0.0

            # 4. Final Loss
            loss_score = rec.optimization_summary.final_loss_db if rec.optimization_summary is not None else 999.0

            # 5. Stable Tie-Breaker
            tie_breaker = rec.experience_id

            return (out_score, rating_score, acoustic_dist, loss_score, tie_breaker)

        return sorted(records, key=_sort_key)
