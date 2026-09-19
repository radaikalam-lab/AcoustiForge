"""Experience collector for assembling runtime episodes across AcoustiForge pipeline stages.

Normative Authority:
    - Phase 5-6 Specification: Section 19 (Experience Collector)
    - Phase 5-6 Extension: Engagement Capture
    - Zero Mutation Invariant: Collector only observes; it must never mutate Core, Graph, or Backends.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Mapping, Optional, Sequence, Union

from .contracts import (
    DayPhase,
    EngagementEvidenceSource,
    EngagementMetrics,
    EventType,
    EvidenceType,
    ExecutionContextSummary,
    ExperienceEvent,
    ExperienceRecord,
    ExperienceValidationError,
    FeedbackStatus,
    GraphSummary,
    HumanFeedback,
    IntentSummary,
    OptimizationSummary,
    OutcomeClassification,
    RuntimeObservations,
    SolarProvenance,
    SpecificationSummary,
    TemporalSolarContext,
)


class ExperienceCollector:
    """Non-intrusive builder for assembling canonical ExperienceRecords from pipeline executions."""

    def __init__(self, session_id: Optional[str] = None) -> None:
        self._session_id = session_id or f"exp-{uuid.uuid4().hex[:12]}"
        self._intent_summary: Optional[IntentSummary] = None
        self._spec_summary: Optional[SpecificationSummary] = None
        self._opt_summary: Optional[OptimizationSummary] = None
        self._graph_summary: Optional[GraphSummary] = None
        self._exec_context: Optional[ExecutionContextSummary] = None
        self._runtime_obs: Optional[RuntimeObservations] = None
        self._temporal_context: Optional[TemporalSolarContext] = None
        self._engagement: Optional[EngagementMetrics] = None
        self._events: list[ExperienceEvent] = []
        self._human_feedback: HumanFeedback = HumanFeedback(status=FeedbackStatus.UNRATED)

    @property
    def session_id(self) -> str:
        return self._session_id

    def record_intent(
        self,
        intent: Any,
        query: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> ExperienceCollector:
        """Capture intent data from a DesignIntent instance."""
        target_preset = getattr(getattr(intent, "target_curve", None), "preset_name", None)
        crossover = getattr(intent, "crossover", None)
        xo_target = getattr(crossover, "target_frequency_hz", None)
        xo_family = getattr(getattr(crossover, "family", None), "value", None)
        xo_order = getattr(crossover, "order", None)
        spatial = getattr(intent, "spatial", None)
        spatial_profile = getattr(spatial, "profile_name", None)

        tonal = getattr(intent, "tonal_balance", None)
        tonal_summary = {}
        if tonal is not None:
            for field_name in ("warmth_db", "brightness_db", "low_shelf_db", "high_shelf_db", "tilt_db_per_octave"):
                val = getattr(tonal, field_name, 0.0)
                if val != 0.0:
                    tonal_summary[field_name] = float(val)

        self._intent_summary = IntentSummary(
            query=query or getattr(intent, "query", None),
            intent_id=getattr(intent, "intent_id", None),
            target_preset=target_preset,
            crossover_frequency_target_hz=xo_target,
            crossover_family=xo_family,
            crossover_order=xo_order,
            spatial_profile=spatial_profile,
            tonal_summary=tonal_summary,
            provider_name=provider_name or getattr(intent, "source_provider", None),
        )
        return self

    def record_specification(self, spec: Any) -> ExperienceCollector:
        """Capture compiled Core or Track C specification details."""
        spec_type = type(spec).__name__
        crossover_spec = getattr(spec, "crossover_specification", None)
        xo_family = getattr(getattr(crossover_spec, "family", None), "value", "LINKWITZ_RILEY")
        xo_order = getattr(crossover_spec, "order", 4)
        search_band = getattr(crossover_spec, "search_band_hz", (500.0, 5000.0))

        positions = getattr(spec, "positions", None)
        spatial_count = len(positions) if positions is not None else 1

        self._spec_summary = SpecificationSummary(
            specification_type=spec_type,
            crossover_family=str(xo_family),
            crossover_order=int(xo_order),
            search_band_hz=(float(search_band[0]), float(search_band[1])),
            spatial_position_count=spatial_count,
            sample_rate=getattr(crossover_spec, "sample_rate", 48000),
        )
        return self

    def record_optimization(self, opt_result: Any) -> ExperienceCollector:
        """Capture deterministic optimization results."""
        converged = bool(getattr(opt_result, "converged", False))
        init_loss = float(getattr(opt_result, "initial_loss_db", getattr(opt_result, "initial_loss", 0.0)))
        final_loss = float(getattr(opt_result, "final_loss_db", getattr(opt_result, "total_loss", 0.0)))

        crossover_res = getattr(opt_result, "crossover_result", None)
        if hasattr(crossover_res, "crossover_frequency_hz"):
            xo_freq = float(crossover_res.crossover_frequency_hz)
        elif isinstance(crossover_res, tuple) and len(crossover_res) > 0:
            xo_freq = float(getattr(crossover_res[0], "crossover_frequency_hz", 0.0))
        else:
            xo_freq = 0.0

        iterations = int(getattr(opt_result, "iterations_completed", 0))

        self._opt_summary = OptimizationSummary(
            converged=converged,
            initial_loss_db=init_loss,
            final_loss_db=final_loss,
            selected_crossover_hz=xo_freq,
            iterations_completed=iterations,
        )
        return self

    def record_graph(self, graph: Any) -> ExperienceCollector:
        """Capture frozen ComputeGraph summary."""
        self._graph_summary = GraphSummary(
            graph_name=getattr(graph, "name", "ComputeGraph"),
            node_count=len(getattr(graph, "nodes", {})),
            sample_rate=int(getattr(graph, "sample_rate", 48000)),
            channels=int(getattr(graph, "channels", 1)),
            is_frozen=bool(getattr(graph, "is_frozen", True)),
        )
        return self

    def record_execution(
        self,
        backend: Any,
        config: Any,
        total_execution_time_s: float,
        blocks_processed: int,
        samples_processed: int,
        xrun_count: int = 0,
        peak_output_dbfs: Optional[float] = None,
        clipping_detected: bool = False,
        hardware_target: Optional[str] = None,
    ) -> ExperienceCollector:
        """Capture execution context and runtime observations."""
        backend_name = type(backend).__name__
        platform_name = "linux" if "alsa" in backend_name.lower() or "linux" in backend_name.lower() else "offline"

        sample_rate = int(getattr(config, "sample_rate", 48000))
        channels = int(getattr(config, "channels", 1))
        block_size = int(getattr(config, "block_size", 512))

        self._exec_context = ExecutionContextSummary(
            backend_type=backend_name,
            platform=platform_name,
            sample_rate=sample_rate,
            channels=channels,
            block_size=block_size,
            hardware_target=hardware_target,
        )

        mean_block_us = (
            (total_execution_time_s / blocks_processed) * 1e6 if blocks_processed > 0 else 0.0
        )

        # Derived calculations
        audio_duration_s = samples_processed / sample_rate if sample_rate > 0 else 0.0
        realtime_margin = (
            audio_duration_s / total_execution_time_s if total_execution_time_s > 0 else None
        )
        throughput = (
            samples_processed / total_execution_time_s if total_execution_time_s > 0 else None
        )

        self._runtime_obs = RuntimeObservations(
            blocks_processed=blocks_processed,
            samples_processed=samples_processed,
            total_execution_time_s=float(total_execution_time_s),
            mean_block_time_us=float(mean_block_us),
            xrun_count=int(xrun_count),
            peak_output_dbfs=peak_output_dbfs,
            clipping_detected=clipping_detected,
            derived_realtime_margin=round(realtime_margin, 2) if realtime_margin is not None else None,
            derived_throughput_samples_per_sec=round(throughput, 1) if throughput is not None else None,
        )
        return self

    def record_temporal_context(
        self,
        context: Union[TemporalSolarContext, datetime.datetime],
        sunrise_dt: Optional[datetime.datetime] = None,
        sunset_dt: Optional[datetime.datetime] = None,
        source: SolarProvenance = SolarProvenance.CALCULATED,
    ) -> ExperienceCollector:
        """Capture temporal and solar environmental context."""
        if isinstance(context, TemporalSolarContext):
            self._temporal_context = context
        elif isinstance(context, datetime.datetime):
            self._temporal_context = TemporalSolarContext.create_computed(
                local_dt=context,
                sunrise_dt=sunrise_dt,
                sunset_dt=sunset_dt,
                source=source,
            )
        else:
            raise ExperienceValidationError(
                f"context must be TemporalSolarContext or datetime, got {type(context)!r}"
            )
        return self

    def record_event(
        self,
        event_type: Union[EventType, str],
        timestamp_iso: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> ExperienceCollector:
        """Append a session trajectory event."""
        ev_enum = EventType(event_type) if isinstance(event_type, str) else event_type
        ts_iso = timestamp_iso or datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._events.append(ExperienceEvent(event_type=ev_enum, timestamp_iso=ts_iso, payload=dict(payload or {})))
        return self

    def record_engagement(
        self,
        session_duration_s: Optional[float] = None,
        listening_duration_s: Optional[float] = None,
        interaction_count: Optional[int] = None,
        configuration_change_count: Optional[int] = None,
        accepted_change_count: Optional[int] = None,
        rejected_change_count: Optional[int] = None,
        reverted_change_count: Optional[int] = None,
        replay_count: Optional[int] = None,
        completion_ratio: Optional[float] = None,
        session_abandoned: Optional[bool] = None,
        session_completed: Optional[bool] = None,
        return_session: Optional[bool] = None,
        explicit_engagement_rating: Optional[float] = None,
        explicit_engagement_feedback: Optional[str] = None,
        derived_engagement_score: Optional[float] = None,
        derived_notes: Optional[str] = None,
        source: EngagementEvidenceSource = EngagementEvidenceSource.SESSION_TELEMETRY,
    ) -> ExperienceCollector:
        """Capture behavioral and user-reported engagement observations."""
        self._engagement = EngagementMetrics(
            session_duration_s=session_duration_s,
            listening_duration_s=listening_duration_s,
            interaction_count=interaction_count,
            configuration_change_count=configuration_change_count,
            accepted_change_count=accepted_change_count,
            rejected_change_count=rejected_change_count,
            reverted_change_count=reverted_change_count,
            replay_count=replay_count,
            completion_ratio=completion_ratio,
            session_abandoned=session_abandoned,
            session_completed=session_completed,
            return_session=return_session,
            explicit_engagement_rating=explicit_engagement_rating,
            explicit_engagement_feedback=explicit_engagement_feedback,
            derived_engagement_score=derived_engagement_score,
            derived_notes=derived_notes,
            events=tuple(self._events),
            source=source,
        )
        return self

    def record_feedback(
        self,
        status: FeedbackStatus,
        rating: Optional[float] = None,
        notes: Optional[str] = None,
        comparison_outcome: Optional[str] = None,
    ) -> ExperienceCollector:
        """Capture user feedback observations."""
        self._human_feedback = HumanFeedback(
            status=status,
            rating=rating,
            qualitative_notes=notes,
            comparison_outcome=comparison_outcome,
        )
        return self

    def build(
        self,
        evidence_type: EvidenceType = EvidenceType.SOFTWARE_OFFLINE,
        outcome: Optional[OutcomeClassification] = None,
        experience_id: Optional[str] = None,
    ) -> ExperienceRecord:
        """Assemble the complete validated ExperienceRecord.

        Args:
            evidence_type: Evidence classification (SOFTWARE_OFFLINE, PHYSICAL_HARDWARE, HYBRID_SIMULATION).
            outcome: Optional explicit outcome; if None, derived from optimization convergence and feedback.
            experience_id: Optional custom ID; defaults to session ID.

        Returns:
            Validated immutable ExperienceRecord instance.
        """
        # Determine outcome if not explicitly provided
        if outcome is None:
            if self._human_feedback.status == FeedbackStatus.REJECTED:
                outcome = OutcomeClassification.REJECTED
            elif self._engagement is not None and self._engagement.session_abandoned is True:
                outcome = OutcomeClassification.REJECTED
            elif self._opt_summary is not None and not self._opt_summary.converged:
                outcome = OutcomeClassification.FAILED
            elif self._opt_summary is not None and self._opt_summary.converged:
                outcome = OutcomeClassification.SUCCESS
            else:
                outcome = OutcomeClassification.UNKNOWN

        # Default temporal context to current timezone-aware timestamp if none was recorded
        temporal = self._temporal_context
        if temporal is None:
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            temporal = TemporalSolarContext(
                local_timestamp_iso=now_dt.isoformat(),
                timezone_name="UTC",
                day_phase=DayPhase.MIDDAY,
                source=SolarProvenance.UNAVAILABLE,
            )

        # If engagement was not explicitly built but events were recorded, create engagement container
        engagement = self._engagement
        if engagement is None and self._events:
            engagement = EngagementMetrics(
                events=tuple(self._events),
                source=EngagementEvidenceSource.SESSION_TELEMETRY,
            )

        timestamp_iso = temporal.local_timestamp_iso

        return ExperienceRecord(
            experience_id=experience_id or self._session_id,
            timestamp_iso=timestamp_iso,
            evidence_type=evidence_type,
            outcome=outcome,
            intent_summary=self._intent_summary,
            specification_summary=self._spec_summary,
            optimization_summary=self._opt_summary,
            graph_summary=self._graph_summary,
            execution_context=self._exec_context,
            runtime_observations=self._runtime_obs,
            temporal_solar_context=temporal,
            engagement=engagement,
            human_feedback=self._human_feedback,
        )
