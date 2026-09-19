"""Transparent descriptive analytics service over AcoustiForge ExperienceRecord collections.

Normative Authority:
    - Phase 5-7A Specification: Experience Retrieval & Analytics
    - Governing Principle: "Runtime teaches the AI layer; runtime does not rewrite the acoustic Core."
    - Evidence Principle: "The Experience Store is the historical evidence layer."
    - Statistical Discipline: "Analytics must explicitly handle empty datasets and missing optional fields without silent conversion to zero."
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence
from dataclasses import dataclass, field

from .contracts import (
    DayPhase,
    EvidenceType,
    ExperienceRecord,
    FeedbackStatus,
    OutcomeClassification,
)


# ==============================================================================
# 1. Analytics Summary Data Contracts
# ==============================================================================

@dataclass(frozen=True)
class OptimizationAnalyticsSummary:
    """Descriptive statistics for deterministic Core optimization episodes."""
    record_count: int = 0
    converged_count: int = 0
    convergence_ratio: float = 0.0
    mean_initial_loss_db: Optional[float] = None
    mean_final_loss_db: Optional[float] = None
    mean_loss_reduction_db: Optional[float] = None
    min_final_loss_db: Optional[float] = None
    max_final_loss_db: Optional[float] = None
    mean_iterations: Optional[float] = None


@dataclass(frozen=True)
class EngagementAnalyticsSummary:
    """Descriptive statistics for user interaction and behavioral engagement."""
    record_count: int = 0
    mean_listening_duration_s: Optional[float] = None
    total_listening_duration_s: Optional[float] = None
    mean_session_duration_s: Optional[float] = None
    mean_interaction_count: Optional[float] = None
    mean_replay_count: Optional[float] = None
    completed_sessions_count: int = 0
    abandoned_sessions_count: int = 0
    completion_ratio: Optional[float] = None
    rated_sessions_count: int = 0
    mean_explicit_engagement_rating: Optional[float] = None


@dataclass(frozen=True)
class RuntimeAnalyticsSummary:
    """Descriptive statistics for audio backend execution and hardware observations."""
    record_count: int = 0
    mean_block_time_us: Optional[float] = None
    total_blocks_processed: int = 0
    total_samples_processed: int = 0
    total_xruns: int = 0
    clipping_events_count: int = 0
    mean_realtime_margin: Optional[float] = None  # Clearly marked as derived


@dataclass(frozen=True)
class ExperienceAnalyticsSummary:
    """Top-level descriptive analytical aggregation over an ExperienceRecord collection."""
    total_records: int
    evidence_type_counts: Mapping[str, int]
    outcome_counts: Mapping[str, int]
    feedback_status_counts: Mapping[str, int]
    optimization: OptimizationAnalyticsSummary
    engagement: EngagementAnalyticsSummary
    runtime: RuntimeAnalyticsSummary


# ==============================================================================
# 2. ExperienceAnalytics Service
# ==============================================================================

class ExperienceAnalytics:
    """Stateless descriptive analytics engine over collections of ExperienceRecords."""

    @classmethod
    def summarize(cls, records: Sequence[ExperienceRecord]) -> ExperienceAnalyticsSummary:
        """Compute complete descriptive statistics over a collection of records.

        Args:
            records: Sequence of validated ExperienceRecord instances.

        Returns:
            ExperienceAnalyticsSummary containing transparent descriptive metrics.
        """
        total_records = len(records)

        # 1. Distribution Counts
        evidence_counts: dict[str, int] = {et.value: 0 for et in EvidenceType}
        outcome_counts: dict[str, int] = {oc.value: 0 for oc in OutcomeClassification}
        feedback_counts: dict[str, int] = {fs.value: 0 for fs in FeedbackStatus}

        for rec in records:
            evidence_counts[rec.evidence_type.value] = evidence_counts.get(rec.evidence_type.value, 0) + 1
            outcome_counts[rec.outcome.value] = outcome_counts.get(rec.outcome.value, 0) + 1
            if rec.human_feedback:
                feedback_counts[rec.human_feedback.status.value] = feedback_counts.get(rec.human_feedback.status.value, 0) + 1

        # 2. Optimization Summary
        opt_summary = cls._summarize_optimization(records)

        # 3. Engagement Summary
        eng_summary = cls._summarize_engagement(records)

        # 4. Runtime Summary
        run_summary = cls._summarize_runtime(records)

        return ExperienceAnalyticsSummary(
            total_records=total_records,
            evidence_type_counts=evidence_counts,
            outcome_counts=outcome_counts,
            feedback_status_counts=feedback_counts,
            optimization=opt_summary,
            engagement=eng_summary,
            runtime=run_summary,
        )

    @classmethod
    def _summarize_optimization(cls, records: Sequence[ExperienceRecord]) -> OptimizationAnalyticsSummary:
        opt_records = [r.optimization_summary for r in records if r.optimization_summary is not None]
        count = len(opt_records)
        if count == 0:
            return OptimizationAnalyticsSummary()

        converged = sum(1 for o in opt_records if o.converged)
        conv_ratio = round(converged / count, 4)

        init_losses = [o.initial_loss_db for o in opt_records if math.isfinite(o.initial_loss_db)]
        final_losses = [o.final_loss_db for o in opt_records if math.isfinite(o.final_loss_db)]
        reductions = [
            o.initial_loss_db - o.final_loss_db
            for o in opt_records
            if math.isfinite(o.initial_loss_db) and math.isfinite(o.final_loss_db)
        ]
        iterations = [o.iterations_completed for o in opt_records if o.iterations_completed >= 0]

        mean_init = round(sum(init_losses) / len(init_losses), 4) if init_losses else None
        mean_final = round(sum(final_losses) / len(final_losses), 4) if final_losses else None
        mean_reduc = round(sum(reductions) / len(reductions), 4) if reductions else None
        min_final = round(min(final_losses), 4) if final_losses else None
        max_final = round(max(final_losses), 4) if final_losses else None
        mean_iter = round(sum(iterations) / len(iterations), 2) if iterations else None

        return OptimizationAnalyticsSummary(
            record_count=count,
            converged_count=converged,
            convergence_ratio=conv_ratio,
            mean_initial_loss_db=mean_init,
            mean_final_loss_db=mean_final,
            mean_loss_reduction_db=mean_reduc,
            min_final_loss_db=min_final,
            max_final_loss_db=max_final,
            mean_iterations=mean_iter,
        )

    @classmethod
    def _summarize_engagement(cls, records: Sequence[ExperienceRecord]) -> EngagementAnalyticsSummary:
        eng_records = [r.engagement for r in records if r.engagement is not None]
        count = len(eng_records)
        if count == 0:
            return EngagementAnalyticsSummary()

        listen_durations = [e.listening_duration_s for e in eng_records if e.listening_duration_s is not None]
        session_durations = [e.session_duration_s for e in eng_records if e.session_duration_s is not None]
        interactions = [e.interaction_count for e in eng_records if e.interaction_count is not None]
        replays = [e.replay_count for e in eng_records if e.replay_count is not None]
        ratings = [e.explicit_engagement_rating for e in eng_records if e.explicit_engagement_rating is not None]

        completed = sum(1 for e in eng_records if e.session_completed is True)
        abandoned = sum(1 for e in eng_records if e.session_abandoned is True)
        evaluated_sessions = completed + abandoned
        completion_ratio = round(completed / evaluated_sessions, 4) if evaluated_sessions > 0 else None

        total_listen = round(sum(listen_durations), 2) if listen_durations else None
        mean_listen = round(sum(listen_durations) / len(listen_durations), 2) if listen_durations else None
        mean_sess = round(sum(session_durations) / len(session_durations), 2) if session_durations else None
        mean_interact = round(sum(interactions) / len(interactions), 2) if interactions else None
        mean_replay = round(sum(replays) / len(replays), 2) if replays else None
        mean_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

        return EngagementAnalyticsSummary(
            record_count=count,
            mean_listening_duration_s=mean_listen,
            total_listening_duration_s=total_listen,
            mean_session_duration_s=mean_sess,
            mean_interaction_count=mean_interact,
            mean_replay_count=mean_replay,
            completed_sessions_count=completed,
            abandoned_sessions_count=abandoned,
            completion_ratio=completion_ratio,
            rated_sessions_count=len(ratings),
            mean_explicit_engagement_rating=mean_rating,
        )

    @classmethod
    def _summarize_runtime(cls, records: Sequence[ExperienceRecord]) -> RuntimeAnalyticsSummary:
        run_records = [r.runtime_observations for r in records if r.runtime_observations is not None]
        count = len(run_records)
        if count == 0:
            return RuntimeAnalyticsSummary()

        block_times = [r.mean_block_time_us for r in run_records if math.isfinite(r.mean_block_time_us)]
        total_blocks = sum(r.blocks_processed for r in run_records)
        total_samples = sum(r.samples_processed for r in run_records)
        total_xruns = sum(r.xrun_count for r in run_records)
        clipping_count = sum(1 for r in run_records if r.clipping_detected)
        margins = [r.derived_realtime_margin for r in run_records if r.derived_realtime_margin is not None]

        mean_block_us = round(sum(block_times) / len(block_times), 2) if block_times else None
        mean_margin = round(sum(margins) / len(margins), 2) if margins else None

        return RuntimeAnalyticsSummary(
            record_count=count,
            mean_block_time_us=mean_block_us,
            total_blocks_processed=total_blocks,
            total_samples_processed=total_samples,
            total_xruns=total_xruns,
            clipping_events_count=clipping_count,
            mean_realtime_margin=mean_margin,
        )

    @classmethod
    def group_by_crossover_family(
        cls,
        records: Sequence[ExperienceRecord],
    ) -> dict[str, ExperienceAnalyticsSummary]:
        """Group records by crossover family (e.g. LINKWITZ_RILEY, BUTTERWORTH) and summarize each group."""
        groups: dict[str, list[ExperienceRecord]] = {}
        for r in records:
            fam = "UNKNOWN"
            if r.specification_summary and r.specification_summary.crossover_family:
                fam = r.specification_summary.crossover_family.upper()
            elif r.intent_summary and r.intent_summary.crossover_family:
                fam = r.intent_summary.crossover_family.upper()
            groups.setdefault(fam, []).append(r)

        return {k: cls.summarize(v) for k, v in sorted(groups.items())}

    @classmethod
    def group_by_day_phase(
        cls,
        records: Sequence[ExperienceRecord],
    ) -> dict[str, ExperienceAnalyticsSummary]:
        """Group records by diurnal solar day phase (e.g. MORNING, MIDDAY, SUNSET_WINDOW) and summarize each group."""
        groups: dict[str, list[ExperienceRecord]] = {}
        for r in records:
            phase = "UNKNOWN"
            if r.temporal_solar_context and r.temporal_solar_context.day_phase:
                phase = r.temporal_solar_context.day_phase.value
            groups.setdefault(phase, []).append(r)

        return {k: cls.summarize(v) for k, v in sorted(groups.items())}

    @classmethod
    def group_by_evidence_type(
        cls,
        records: Sequence[ExperienceRecord],
    ) -> dict[str, ExperienceAnalyticsSummary]:
        """Group records by evidence type (SOFTWARE_OFFLINE, PHYSICAL_HARDWARE, HYBRID_SIMULATION)."""
        groups: dict[str, list[ExperienceRecord]] = {}
        for r in records:
            et = r.evidence_type.value
            groups.setdefault(et, []).append(r)

        return {k: cls.summarize(v) for k, v in sorted(groups.items())}

    @classmethod
    def group_by_platform(
        cls,
        records: Sequence[ExperienceRecord],
    ) -> dict[str, ExperienceAnalyticsSummary]:
        """Group records by execution platform (e.g. linux, offline)."""
        groups: dict[str, list[ExperienceRecord]] = {}
        for r in records:
            plat = "generic"
            if r.execution_context and r.execution_context.platform:
                plat = r.execution_context.platform.lower()
            groups.setdefault(plat, []).append(r)

        return {k: cls.summarize(v) for k, v in sorted(groups.items())}
