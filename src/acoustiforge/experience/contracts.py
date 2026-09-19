"""Immutable data contracts for AcoustiForge runtime experience capture.

Normative Authority:
    - Phase 5-6 Specification: Runtime Experience & Learning Boundary
    - Phase 5-6 Extension: Engagement Capture
    - Governing Principle: "AI proposes. AcoustiForge validates and executes."
    - Runtime Principle: "Runtime teaches the AI layer; runtime does not rewrite the acoustic Core."
    - Evidence Principle: "The Experience Store is authoritative historical evidence, NOT LLM memory."
    - Temporal Principle: "Temporal and solar context are contextual variables, NOT direct measurements of human mood."
    - Engagement Principle: "Engagement is captured as behavioral or explicitly reported evidence; it is not automatically treated as psychological state or mood."
"""

from __future__ import annotations

import datetime
from enum import Enum
import math
from typing import Any, Mapping, Optional, Sequence
from dataclasses import dataclass, field


# ==============================================================================
# 1. Enums
# ==============================================================================

class EvidenceType(str, Enum):
    """Categorization of acoustic and execution evidence."""
    SOFTWARE_OFFLINE = "SOFTWARE_OFFLINE"
    PHYSICAL_HARDWARE = "PHYSICAL_HARDWARE"
    HYBRID_SIMULATION = "HYBRID_SIMULATION"


class OutcomeClassification(str, Enum):
    """Evaluation outcome of the pipeline execution episode."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class FeedbackStatus(str, Enum):
    """User feedback classification status."""
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"
    UNRATED = "UNRATED"


class DayPhase(str, Enum):
    """Astronomical / diurnal temporal phase."""
    PRE_SUNRISE = "PRE_SUNRISE"
    MORNING = "MORNING"
    MIDDAY = "MIDDAY"
    AFTERNOON = "AFTERNOON"
    SUNSET_WINDOW = "SUNSET_WINDOW"
    EVENING = "EVENING"
    NIGHT = "NIGHT"


class SolarProvenance(str, Enum):
    """Provenance/origin of solar timing data."""
    CALCULATED = "calculated"
    EXTERNAL_CONTEXT = "external-context"
    USER_SUPPLIED = "user-supplied"
    UNAVAILABLE = "unavailable"


class EventType(str, Enum):
    """Categorization of session trajectory events."""
    SESSION_STARTED = "SESSION_STARTED"
    INTENT_PROPOSED = "INTENT_PROPOSED"
    INTENT_ACCEPTED = "INTENT_ACCEPTED"
    INTENT_REJECTED = "INTENT_REJECTED"
    CONFIGURATION_APPLIED = "CONFIGURATION_APPLIED"
    CONFIGURATION_MODIFIED = "CONFIGURATION_MODIFIED"
    CONFIGURATION_REVERTED = "CONFIGURATION_REVERTED"
    MEASUREMENT_CAPTURED = "MEASUREMENT_CAPTURED"
    USER_FEEDBACK = "USER_FEEDBACK"
    PLAYBACK_STARTED = "PLAYBACK_STARTED"
    PLAYBACK_STOPPED = "PLAYBACK_STOPPED"
    REPLAY = "REPLAY"
    SESSION_COMPLETED = "SESSION_COMPLETED"
    SESSION_ABANDONED = "SESSION_ABANDONED"


class EngagementEvidenceSource(str, Enum):
    """Source provenance for engagement observations."""
    SESSION_TELEMETRY = "SESSION_TELEMETRY"
    USER_REPORTED = "USER_REPORTED"
    DERIVED = "DERIVED"
    UNAVAILABLE = "UNAVAILABLE"


# ==============================================================================
# 2. Errors
# ==============================================================================

class ExperienceValidationError(ValueError):
    """Raised when an Experience contract violates invariants or bounds."""
    pass


# ==============================================================================
# 3. Sub-Contracts & Summaries
# ==============================================================================

@dataclass(frozen=True)
class IntentSummary:
    """Compact summary of user query and high-level design intent."""
    query: Optional[str] = None
    intent_id: Optional[str] = None
    target_preset: Optional[str] = None
    crossover_frequency_target_hz: Optional[float] = None
    crossover_family: Optional[str] = None
    crossover_order: Optional[int] = None
    spatial_profile: Optional[str] = None
    tonal_summary: Mapping[str, float] = field(default_factory=dict)
    provider_name: Optional[str] = None

    def __post_init__(self) -> None:
        if self.crossover_frequency_target_hz is not None:
            if not math.isfinite(self.crossover_frequency_target_hz) or self.crossover_frequency_target_hz <= 0:
                raise ExperienceValidationError("crossover_frequency_target_hz must be a positive finite float.")


@dataclass(frozen=True)
class SpecificationSummary:
    """Summary of the compiled, validated Core OptimizationSpecification."""
    specification_type: str
    crossover_family: str
    crossover_order: int
    search_band_hz: tuple[float, float]
    spatial_position_count: int = 1
    sample_rate: int = 48000

    def __post_init__(self) -> None:
        if not self.specification_type:
            raise ExperienceValidationError("specification_type cannot be empty.")
        if len(self.search_band_hz) != 2:
            raise ExperienceValidationError("search_band_hz must be a 2-tuple (min_hz, max_hz).")
        f_min, f_max = self.search_band_hz
        if not (math.isfinite(f_min) and math.isfinite(f_max) and 0 < f_min < f_max):
            raise ExperienceValidationError(f"Invalid search_band_hz: {self.search_band_hz}")
        if self.spatial_position_count < 1:
            raise ExperienceValidationError("spatial_position_count must be >= 1.")


@dataclass(frozen=True)
class OptimizationSummary:
    """Summary of deterministic Core optimization output."""
    converged: bool
    initial_loss_db: float
    final_loss_db: float
    selected_crossover_hz: float
    iterations_completed: int
    optimizer_name: str = "DeterministicNelderMead"

    def __post_init__(self) -> None:
        for name, val in [
            ("initial_loss_db", self.initial_loss_db),
            ("final_loss_db", self.final_loss_db),
            ("selected_crossover_hz", self.selected_crossover_hz),
        ]:
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
                raise ExperienceValidationError(f"{name} must be a finite float, got {val!r}.")
        if self.iterations_completed < 0:
            raise ExperienceValidationError("iterations_completed must be non-negative.")


@dataclass(frozen=True)
class GraphSummary:
    """Summary of compiled frozen ComputeGraph."""
    graph_name: str
    node_count: int
    sample_rate: int
    channels: int
    is_frozen: bool = True

    def __post_init__(self) -> None:
        if not self.graph_name:
            raise ExperienceValidationError("graph_name must not be empty.")
        if self.node_count <= 0:
            raise ExperienceValidationError("node_count must be > 0.")
        if self.sample_rate <= 0 or self.channels <= 0:
            raise ExperienceValidationError("sample_rate and channels must be positive integers.")


@dataclass(frozen=True)
class ExecutionContextSummary:
    """Hardware and runtime context of the audio execution backend."""
    backend_type: str
    platform: str
    sample_rate: int
    channels: int
    block_size: int
    hardware_target: Optional[str] = None
    driver_version: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.backend_type:
            raise ExperienceValidationError("backend_type must be specified.")
        if self.sample_rate <= 0 or self.channels <= 0 or self.block_size <= 0:
            raise ExperienceValidationError("Stream parameters must be positive integers.")


@dataclass(frozen=True)
class RuntimeObservations:
    """Runtime telemetry separating observed measurements from derived metrics.

    Invariants:
        1. Observed measurements represent direct execution timings and buffer counts.
        2. Derived metrics are calculated post-hoc and must never masquerade as physical observations.
    """
    # Direct Observations
    blocks_processed: int
    samples_processed: int
    total_execution_time_s: float
    mean_block_time_us: float
    xrun_count: int = 0
    peak_output_dbfs: Optional[float] = None
    clipping_detected: bool = False

    # Derived Metrics (Calculated post-hoc)
    derived_realtime_margin: Optional[float] = None
    derived_throughput_samples_per_sec: Optional[float] = None

    def __post_init__(self) -> None:
        if self.blocks_processed < 0 or self.samples_processed < 0 or self.xrun_count < 0:
            raise ExperienceValidationError("Buffer counts and xruns must be non-negative.")
        for name, val in [
            ("total_execution_time_s", self.total_execution_time_s),
            ("mean_block_time_us", self.mean_block_time_us),
        ]:
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < 0:
                raise ExperienceValidationError(f"{name} must be a non-negative finite float.")
        if self.derived_realtime_margin is not None:
            if not math.isfinite(self.derived_realtime_margin):
                raise ExperienceValidationError("derived_realtime_margin must be a finite float.")
        if self.derived_throughput_samples_per_sec is not None:
            if not math.isfinite(self.derived_throughput_samples_per_sec):
                raise ExperienceValidationError("derived_throughput_samples_per_sec must be a finite float.")


@dataclass(frozen=True)
class TemporalSolarContext:
    """Environmental and diurnal context.

    Normative Invariant:
        Temporal and solar context are contextual explanatory variables for future preference learning.
        They are NOT direct measurements of human mood, emotion, or psychological state.
    """
    local_timestamp_iso: str
    timezone_name: str
    sunrise_timestamp_iso: Optional[str] = None
    sunset_timestamp_iso: Optional[str] = None
    daylight_duration_s: Optional[float] = None
    minutes_since_sunrise: Optional[float] = None
    minutes_until_sunset: Optional[float] = None
    daylight_fraction: Optional[float] = None
    day_phase: DayPhase = DayPhase.MIDDAY
    source: SolarProvenance = SolarProvenance.UNAVAILABLE

    def __post_init__(self) -> None:
        if not self.local_timestamp_iso:
            raise ExperienceValidationError("local_timestamp_iso cannot be empty.")
        if not self.timezone_name:
            raise ExperienceValidationError("timezone_name cannot be empty.")
        for name, val in [
            ("daylight_duration_s", self.daylight_duration_s),
            ("minutes_since_sunrise", self.minutes_since_sunrise),
            ("minutes_until_sunset", self.minutes_until_sunset),
            ("daylight_fraction", self.daylight_fraction),
        ]:
            if val is not None:
                if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
                    raise ExperienceValidationError(f"{name} must be a finite float, got {val!r}.")

    @classmethod
    def create_computed(
        cls,
        local_dt: datetime.datetime,
        sunrise_dt: Optional[datetime.datetime] = None,
        sunset_dt: Optional[datetime.datetime] = None,
        source: SolarProvenance = SolarProvenance.CALCULATED,
    ) -> TemporalSolarContext:
        """Deterministically calculate relative solar features and day-phase from timestamps."""
        if local_dt.tzinfo is None:
            raise ExperienceValidationError("local_dt must be a timezone-aware datetime.")

        local_iso = local_dt.isoformat()
        tz_name = str(local_dt.tzinfo)

        if sunrise_dt is None or sunset_dt is None:
            # Fallback to pure clock-time day phase when solar coordinates are unavailable
            hour = local_dt.hour + local_dt.minute / 60.0
            if 5.0 <= hour < 8.0:
                phase = DayPhase.MORNING
            elif 8.0 <= hour < 12.0:
                phase = DayPhase.MORNING
            elif 12.0 <= hour < 14.0:
                phase = DayPhase.MIDDAY
            elif 14.0 <= hour < 18.0:
                phase = DayPhase.AFTERNOON
            elif 18.0 <= hour < 22.0:
                phase = DayPhase.EVENING
            else:
                phase = DayPhase.NIGHT
            return cls(
                local_timestamp_iso=local_iso,
                timezone_name=tz_name,
                day_phase=phase,
                source=SolarProvenance.UNAVAILABLE,
            )

        if sunrise_dt.tzinfo is None or sunset_dt.tzinfo is None:
            raise ExperienceValidationError("sunrise_dt and sunset_dt must be timezone-aware datetimes.")

        sunrise_iso = sunrise_dt.isoformat()
        sunset_iso = sunset_dt.isoformat()

        daylight_duration_s = max(0.0, (sunset_dt - sunrise_dt).total_seconds())
        minutes_since_sunrise = (local_dt - sunrise_dt).total_seconds() / 60.0
        minutes_until_sunset = (sunset_dt - local_dt).total_seconds() / 60.0

        if daylight_duration_s > 0.0:
            elapsed_daylight = (local_dt - sunrise_dt).total_seconds()
            daylight_fraction = max(0.0, min(1.0, elapsed_daylight / daylight_duration_s))
        else:
            daylight_fraction = 0.0

        # Relative solar day-phase classification
        if local_dt < sunrise_dt - datetime.timedelta(minutes=60):
            phase = DayPhase.NIGHT
        elif local_dt < sunrise_dt:
            phase = DayPhase.PRE_SUNRISE
        elif local_dt < sunrise_dt + datetime.timedelta(minutes=180):
            phase = DayPhase.MORNING
        elif abs(minutes_until_sunset - (daylight_duration_s / 120.0)) < 60.0:
            phase = DayPhase.MIDDAY
        elif local_dt < sunset_dt - datetime.timedelta(minutes=60):
            phase = DayPhase.AFTERNOON
        elif local_dt <= sunset_dt + datetime.timedelta(minutes=45):
            phase = DayPhase.SUNSET_WINDOW
        elif local_dt <= sunset_dt + datetime.timedelta(minutes=240):
            phase = DayPhase.EVENING
        else:
            phase = DayPhase.NIGHT

        return cls(
            local_timestamp_iso=local_iso,
            timezone_name=tz_name,
            sunrise_timestamp_iso=sunrise_iso,
            sunset_timestamp_iso=sunset_iso,
            daylight_duration_s=daylight_duration_s,
            minutes_since_sunrise=round(minutes_since_sunrise, 2),
            minutes_until_sunset=round(minutes_until_sunset, 2),
            daylight_fraction=round(daylight_fraction, 4),
            day_phase=phase,
            source=source,
        )


@dataclass(frozen=True)
class ExperienceEvent:
    """Timestamped event in a session trajectory."""
    event_type: EventType
    timestamp_iso: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType):
            raise ExperienceValidationError(f"Invalid EventType: {self.event_type!r}")
        if not self.timestamp_iso:
            raise ExperienceValidationError("timestamp_iso cannot be empty.")


@dataclass(frozen=True)
class EngagementMetrics:
    """Immutable engagement observations separating behavioral, user-reported, and derived evidence.

    Normative Invariants:
        1. Behavioral telemetry is raw observed durations and counts from playback/session monitoring.
        2. Explicit user-reported feedback represents qualitative or rating input provided by the user.
        3. Derived engagement metrics are calculated post-hoc and must never masquerade as physical observations.
        4. No hardcoded formula: engagement is raw evidence for future learning systems to interpret.
    """
    # Behavioral Evidence (Observed from session monitoring)
    session_duration_s: Optional[float] = None
    listening_duration_s: Optional[float] = None
    interaction_count: Optional[int] = None
    configuration_change_count: Optional[int] = None
    accepted_change_count: Optional[int] = None
    rejected_change_count: Optional[int] = None
    reverted_change_count: Optional[int] = None
    replay_count: Optional[int] = None
    completion_ratio: Optional[float] = None
    session_abandoned: Optional[bool] = None
    session_completed: Optional[bool] = None
    return_session: Optional[bool] = None

    # Explicit User-Reported Evidence
    explicit_engagement_rating: Optional[float] = None
    explicit_engagement_feedback: Optional[str] = None

    # Derived Evidence (Strictly segregated, post-hoc calculations)
    derived_engagement_score: Optional[float] = None
    derived_notes: Optional[str] = None

    # Trajectory Events
    events: tuple[ExperienceEvent, ...] = field(default_factory=tuple)

    # Source Provenance
    source: EngagementEvidenceSource = EngagementEvidenceSource.SESSION_TELEMETRY

    def __post_init__(self) -> None:
        # Validate non-negative numbers
        for name, val in [
            ("session_duration_s", self.session_duration_s),
            ("listening_duration_s", self.listening_duration_s),
        ]:
            if val is not None:
                if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < 0:
                    raise ExperienceValidationError(f"{name} must be a non-negative finite float, got {val!r}.")

        for name, val in [
            ("interaction_count", self.interaction_count),
            ("configuration_change_count", self.configuration_change_count),
            ("accepted_change_count", self.accepted_change_count),
            ("rejected_change_count", self.rejected_change_count),
            ("reverted_change_count", self.reverted_change_count),
            ("replay_count", self.replay_count),
        ]:
            if val is not None:
                if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                    raise ExperienceValidationError(f"{name} must be a non-negative integer, got {val!r}.")

        if self.completion_ratio is not None:
            if not isinstance(self.completion_ratio, (int, float)) or isinstance(self.completion_ratio, bool) or not math.isfinite(self.completion_ratio):
                raise ExperienceValidationError("completion_ratio must be a finite float.")
            if not (0.0 <= float(self.completion_ratio) <= 1.0):
                raise ExperienceValidationError(f"completion_ratio {self.completion_ratio} must be between 0.0 and 1.0.")

        if self.explicit_engagement_rating is not None:
            if not isinstance(self.explicit_engagement_rating, (int, float)) or isinstance(self.explicit_engagement_rating, bool) or not math.isfinite(self.explicit_engagement_rating):
                raise ExperienceValidationError("explicit_engagement_rating must be a finite float.")
            if not (1.0 <= float(self.explicit_engagement_rating) <= 5.0):
                raise ExperienceValidationError(f"explicit_engagement_rating {self.explicit_engagement_rating} must be between 1.0 and 5.0.")

        if self.derived_engagement_score is not None:
            if not isinstance(self.derived_engagement_score, (int, float)) or isinstance(self.derived_engagement_score, bool) or not math.isfinite(self.derived_engagement_score):
                raise ExperienceValidationError("derived_engagement_score must be a finite float.")


@dataclass(frozen=True)
class HumanFeedback:
    """User feedback and subjective preference observations."""
    status: FeedbackStatus = FeedbackStatus.UNRATED
    rating: Optional[float] = None
    qualitative_notes: Optional[str] = None
    comparison_outcome: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, FeedbackStatus):
            raise ExperienceValidationError(f"Invalid FeedbackStatus: {self.status!r}")
        if self.rating is not None:
            if not isinstance(self.rating, (int, float)) or isinstance(self.rating, bool) or not math.isfinite(self.rating):
                raise ExperienceValidationError("rating must be a finite numeric value.")
            if not (1.0 <= float(self.rating) <= 5.0):
                raise ExperienceValidationError(f"Rating {self.rating} must be between 1.0 and 5.0.")


# ==============================================================================
# 4. Top-Level Experience Record
# ==============================================================================

@dataclass(frozen=True)
class ExperienceRecord:
    """Canonical immutable episode record capturing the complete intent-to-execution trajectory."""
    experience_id: str
    timestamp_iso: str
    evidence_type: EvidenceType
    outcome: OutcomeClassification
    schema_version: str = "1.1.0"
    runtime_version: str = "0.5.6"
    intent_summary: Optional[IntentSummary] = None
    specification_summary: Optional[SpecificationSummary] = None
    optimization_summary: Optional[OptimizationSummary] = None
    graph_summary: Optional[GraphSummary] = None
    execution_context: Optional[ExecutionContextSummary] = None
    runtime_observations: Optional[RuntimeObservations] = None
    temporal_solar_context: Optional[TemporalSolarContext] = None
    engagement: Optional[EngagementMetrics] = None
    human_feedback: HumanFeedback = field(default_factory=HumanFeedback)

    def __post_init__(self) -> None:
        if not self.experience_id:
            raise ExperienceValidationError("experience_id cannot be empty.")
        if not self.timestamp_iso:
            raise ExperienceValidationError("timestamp_iso cannot be empty.")
        if not isinstance(self.evidence_type, EvidenceType):
            raise ExperienceValidationError(f"Invalid evidence_type: {self.evidence_type!r}")
        if not isinstance(self.outcome, OutcomeClassification):
            raise ExperienceValidationError(f"Invalid outcome: {self.outcome!r}")

    def to_dict(self) -> dict[str, Any]:
        """Lossless conversion to JSON-serializable dictionary."""
        def _serialize(obj: Any) -> Any:
            if obj is None:
                return None
            if isinstance(obj, Enum):
                return obj.value
            if isinstance(obj, tuple):
                return [_serialize(item) for item in obj]
            if isinstance(obj, list):
                return [_serialize(item) for item in obj]
            if isinstance(obj, dict):
                return {k: _serialize(v) for k, v in obj.items()}
            if hasattr(obj, "__dataclass_fields__"):
                return {k: _serialize(getattr(obj, k)) for k in obj.__dataclass_fields__}
            return obj

        return _serialize(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExperienceRecord:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ExperienceValidationError(f"Expected mapping, got {type(data)!r}")

        # Validate required identity fields
        exp_id = data.get("experience_id")
        ts_iso = data.get("timestamp_iso")
        if not exp_id or not ts_iso:
            raise ExperienceValidationError("experience_id and timestamp_iso are required.")

        evidence_type = EvidenceType(data.get("evidence_type", EvidenceType.SOFTWARE_OFFLINE.value))
        outcome = OutcomeClassification(data.get("outcome", OutcomeClassification.UNKNOWN.value))
        schema_version = str(data.get("schema_version", "1.1.0"))
        runtime_version = str(data.get("runtime_version", "0.5.6"))

        # Deserialize intent summary
        intent_summary = None
        if data.get("intent_summary"):
            i_data = data["intent_summary"]
            intent_summary = IntentSummary(
                query=i_data.get("query"),
                intent_id=i_data.get("intent_id"),
                target_preset=i_data.get("target_preset"),
                crossover_frequency_target_hz=i_data.get("crossover_frequency_target_hz"),
                crossover_family=i_data.get("crossover_family"),
                crossover_order=i_data.get("crossover_order"),
                spatial_profile=i_data.get("spatial_profile"),
                tonal_summary=dict(i_data.get("tonal_summary", {})),
                provider_name=i_data.get("provider_name"),
            )

        # Deserialize specification summary
        spec_summary = None
        if data.get("specification_summary"):
            s_data = data["specification_summary"]
            raw_band = s_data.get("search_band_hz", (500.0, 5000.0))
            spec_summary = SpecificationSummary(
                specification_type=s_data.get("specification_type", "UnknownSpec"),
                crossover_family=s_data.get("crossover_family", "LINKWITZ_RILEY"),
                crossover_order=int(s_data.get("crossover_order", 4)),
                search_band_hz=(float(raw_band[0]), float(raw_band[1])),
                spatial_position_count=int(s_data.get("spatial_position_count", 1)),
                sample_rate=int(s_data.get("sample_rate", 48000)),
            )

        # Deserialize optimization summary
        opt_summary = None
        if data.get("optimization_summary"):
            o_data = data["optimization_summary"]
            opt_summary = OptimizationSummary(
                converged=bool(o_data.get("converged", False)),
                initial_loss_db=float(o_data.get("initial_loss_db", 0.0)),
                final_loss_db=float(o_data.get("final_loss_db", 0.0)),
                selected_crossover_hz=float(o_data.get("selected_crossover_hz", 0.0)),
                iterations_completed=int(o_data.get("iterations_completed", 0)),
                optimizer_name=str(o_data.get("optimizer_name", "DeterministicNelderMead")),
            )

        # Deserialize graph summary
        graph_summary = None
        if data.get("graph_summary"):
            g_data = data["graph_summary"]
            graph_summary = GraphSummary(
                graph_name=str(g_data.get("graph_name", "Graph")),
                node_count=int(g_data.get("node_count", 1)),
                sample_rate=int(g_data.get("sample_rate", 48000)),
                channels=int(g_data.get("channels", 1)),
                is_frozen=bool(g_data.get("is_frozen", True)),
            )

        # Deserialize execution context
        exec_context = None
        if data.get("execution_context"):
            e_data = data["execution_context"]
            exec_context = ExecutionContextSummary(
                backend_type=str(e_data.get("backend_type", "OfflineExecutionBackend")),
                platform=str(e_data.get("platform", "generic")),
                sample_rate=int(e_data.get("sample_rate", 48000)),
                channels=int(e_data.get("channels", 1)),
                block_size=int(e_data.get("block_size", 512)),
                hardware_target=e_data.get("hardware_target"),
                driver_version=e_data.get("driver_version"),
            )

        # Deserialize runtime observations
        runtime_obs = None
        if data.get("runtime_observations"):
            r_data = data["runtime_observations"]
            runtime_obs = RuntimeObservations(
                blocks_processed=int(r_data.get("blocks_processed", 0)),
                samples_processed=int(r_data.get("samples_processed", 0)),
                total_execution_time_s=float(r_data.get("total_execution_time_s", 0.0)),
                mean_block_time_us=float(r_data.get("mean_block_time_us", 0.0)),
                xrun_count=int(r_data.get("xrun_count", 0)),
                peak_output_dbfs=float(r_data["peak_output_dbfs"]) if r_data.get("peak_output_dbfs") is not None else None,
                clipping_detected=bool(r_data.get("clipping_detected", False)),
                derived_realtime_margin=float(r_data["derived_realtime_margin"]) if r_data.get("derived_realtime_margin") is not None else None,
                derived_throughput_samples_per_sec=float(r_data["derived_throughput_samples_per_sec"]) if r_data.get("derived_throughput_samples_per_sec") is not None else None,
            )

        # Deserialize temporal solar context
        temp_context = None
        if data.get("temporal_solar_context"):
            t_data = data["temporal_solar_context"]
            temp_context = TemporalSolarContext(
                local_timestamp_iso=str(t_data.get("local_timestamp_iso", "")),
                timezone_name=str(t_data.get("timezone_name", "UTC")),
                sunrise_timestamp_iso=t_data.get("sunrise_timestamp_iso"),
                sunset_timestamp_iso=t_data.get("sunset_timestamp_iso"),
                daylight_duration_s=float(t_data["daylight_duration_s"]) if t_data.get("daylight_duration_s") is not None else None,
                minutes_since_sunrise=float(t_data["minutes_since_sunrise"]) if t_data.get("minutes_since_sunrise") is not None else None,
                minutes_until_sunset=float(t_data["minutes_until_sunset"]) if t_data.get("minutes_until_sunset") is not None else None,
                daylight_fraction=float(t_data["daylight_fraction"]) if t_data.get("daylight_fraction") is not None else None,
                day_phase=DayPhase(t_data.get("day_phase", DayPhase.MIDDAY.value)),
                source=SolarProvenance(t_data.get("source", SolarProvenance.UNAVAILABLE.value)),
            )

        # Deserialize engagement metrics
        engagement = None
        if data.get("engagement"):
            eng_data = data["engagement"]
            events_list: list[ExperienceEvent] = []
            for ev_item in eng_data.get("events", []):
                events_list.append(
                    ExperienceEvent(
                        event_type=EventType(ev_item["event_type"]),
                        timestamp_iso=str(ev_item["timestamp_iso"]),
                        payload=dict(ev_item.get("payload", {})),
                    )
                )
            engagement = EngagementMetrics(
                session_duration_s=float(eng_data["session_duration_s"]) if eng_data.get("session_duration_s") is not None else None,
                listening_duration_s=float(eng_data["listening_duration_s"]) if eng_data.get("listening_duration_s") is not None else None,
                interaction_count=int(eng_data["interaction_count"]) if eng_data.get("interaction_count") is not None else None,
                configuration_change_count=int(eng_data["configuration_change_count"]) if eng_data.get("configuration_change_count") is not None else None,
                accepted_change_count=int(eng_data["accepted_change_count"]) if eng_data.get("accepted_change_count") is not None else None,
                rejected_change_count=int(eng_data["rejected_change_count"]) if eng_data.get("rejected_change_count") is not None else None,
                reverted_change_count=int(eng_data["reverted_change_count"]) if eng_data.get("reverted_change_count") is not None else None,
                replay_count=int(eng_data["replay_count"]) if eng_data.get("replay_count") is not None else None,
                completion_ratio=float(eng_data["completion_ratio"]) if eng_data.get("completion_ratio") is not None else None,
                session_abandoned=bool(eng_data["session_abandoned"]) if eng_data.get("session_abandoned") is not None else None,
                session_completed=bool(eng_data["session_completed"]) if eng_data.get("session_completed") is not None else None,
                return_session=bool(eng_data["return_session"]) if eng_data.get("return_session") is not None else None,
                explicit_engagement_rating=float(eng_data["explicit_engagement_rating"]) if eng_data.get("explicit_engagement_rating") is not None else None,
                explicit_engagement_feedback=eng_data.get("explicit_engagement_feedback"),
                derived_engagement_score=float(eng_data["derived_engagement_score"]) if eng_data.get("derived_engagement_score") is not None else None,
                derived_notes=eng_data.get("derived_notes"),
                events=tuple(events_list),
                source=EngagementEvidenceSource(eng_data.get("source", EngagementEvidenceSource.SESSION_TELEMETRY.value)),
            )

        # Deserialize human feedback
        feedback = HumanFeedback()
        if data.get("human_feedback"):
            f_data = data["human_feedback"]
            feedback = HumanFeedback(
                status=FeedbackStatus(f_data.get("status", FeedbackStatus.UNRATED.value)),
                rating=float(f_data["rating"]) if f_data.get("rating") is not None else None,
                qualitative_notes=f_data.get("qualitative_notes"),
                comparison_outcome=f_data.get("comparison_outcome"),
            )

        return cls(
            experience_id=str(exp_id),
            timestamp_iso=str(ts_iso),
            evidence_type=evidence_type,
            outcome=outcome,
            schema_version=schema_version,
            runtime_version=runtime_version,
            intent_summary=intent_summary,
            specification_summary=spec_summary,
            optimization_summary=opt_summary,
            graph_summary=graph_summary,
            execution_context=exec_context,
            runtime_observations=runtime_obs,
            temporal_solar_context=temp_context,
            engagement=engagement,
            human_feedback=feedback,
        )
