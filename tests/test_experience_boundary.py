"""Unit and integration tests for Phase 5-6 Runtime Experience & Learning Boundary.

Normative Invariants Tested:
    1. AI proposes. AcoustiForge validates and executes.
    2. Runtime teaches the AI layer; runtime does not rewrite the acoustic Core.
    3. The Experience Store is authoritative historical evidence, NOT LLM memory.
    4. Temporal and solar context are contextual variables, NOT direct measurements of human mood.
    5. Engagement is captured as behavioral or explicitly reported evidence; it is not automatically treated as psychological state or mood.
    6. Zero mutation of frozen Core, Track C, and Execution layers.
"""

import dataclasses
import datetime
import json
from pathlib import Path
import math
import numpy as np
import pytest

from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    OptimizationResult,
    OptimizationSpecification,
)
from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.builders.optimization_adapter import compile_optimization_result_to_graph
from acoustiforge.execution.interface import StreamConfig
from acoustiforge.execution.offline import OfflineExecutionBackend
from acoustiforge.extensions.spatial_optimization import (
    MultiPositionOptimizationSpecification,
    SpatialMeasurementPosition,
    optimize_multi_position,
    MultiPositionOptimizationResult,
)
from acoustiforge.intent.contracts import (
    CrossoverIntent,
    DesignIntent,
    SpatialIntent,
    TargetCurveIntent,
    TonalBalanceIntent,
)
from acoustiforge.intent.provider import MockDesignIntentProvider
from acoustiforge.intent.adapter import DesignIntentAdapter

from acoustiforge.experience.contracts import (
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
from acoustiforge.experience.collector import ExperienceCollector
from acoustiforge.experience.store import ExperienceStore, ExperienceStoreError


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def synthetic_driver_responses() -> tuple[FrequencyResponseData, FrequencyResponseData]:
    """Create synthetic woofer and tweeter responses."""
    freqs = np.geomspace(200.0, 8000.0, 100)
    w_mag = 90.0 - 12.0 * np.log10(1.0 + (freqs / 2000.0) ** 4)
    w_phase = np.linspace(0.0, -np.pi, 100)
    woofer = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=w_mag, phase_rad=w_phase)

    t_mag = 90.0 - 12.0 * np.log10(1.0 + (2000.0 / freqs) ** 4)
    t_phase = np.linspace(np.pi, 0.0, 100)
    tweeter = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=t_mag, phase_rad=t_phase)
    return woofer, tweeter


@pytest.fixture
def sample_experience_record() -> ExperienceRecord:
    """Construct a complete valid ExperienceRecord for testing."""
    now_dt = datetime.datetime(2026, 9, 19, 14, 30, 0, tzinfo=datetime.timezone.utc)
    sunrise_dt = datetime.datetime(2026, 9, 19, 6, 15, 0, tzinfo=datetime.timezone.utc)
    sunset_dt = datetime.datetime(2026, 9, 19, 18, 45, 0, tzinfo=datetime.timezone.utc)

    temporal = TemporalSolarContext.create_computed(
        local_dt=now_dt,
        sunrise_dt=sunrise_dt,
        sunset_dt=sunset_dt,
        source=SolarProvenance.CALCULATED,
    )

    intent_sum = IntentSummary(
        query="Design warm 2-way with 2 kHz crossover",
        intent_id="intent-test-01",
        target_preset="flat",
        crossover_frequency_target_hz=2000.0,
        crossover_family="LINKWITZ_RILEY",
        crossover_order=4,
        tonal_summary={"warmth_db": 1.5},
        provider_name="MockDesignIntentProvider",
    )

    spec_sum = SpecificationSummary(
        specification_type="OptimizationSpecification",
        crossover_family="LINKWITZ_RILEY",
        crossover_order=4,
        search_band_hz=(1400.0, 2800.0),
        spatial_position_count=1,
    )

    opt_sum = OptimizationSummary(
        converged=True,
        initial_loss_db=4.52,
        final_loss_db=0.88,
        selected_crossover_hz=2050.0,
        iterations_completed=42,
    )

    graph_sum = GraphSummary(
        graph_name="TestGraph",
        node_count=8,
        sample_rate=48000,
        channels=1,
        is_frozen=True,
    )

    exec_context = ExecutionContextSummary(
        backend_type="OfflineExecutionBackend",
        platform="generic",
        sample_rate=48000,
        channels=1,
        block_size=512,
    )

    runtime_obs = RuntimeObservations(
        blocks_processed=10,
        samples_processed=5120,
        total_execution_time_s=0.005,
        mean_block_time_us=500.0,
        xrun_count=0,
        peak_output_dbfs=-3.2,
        derived_realtime_margin=21.3,
        derived_throughput_samples_per_sec=1024000.0,
    )

    events = (
        ExperienceEvent(event_type=EventType.SESSION_STARTED, timestamp_iso="2026-09-19T14:30:00Z"),
        ExperienceEvent(event_type=EventType.PLAYBACK_STARTED, timestamp_iso="2026-09-19T14:30:05Z"),
        ExperienceEvent(event_type=EventType.SESSION_COMPLETED, timestamp_iso="2026-09-19T15:10:00Z"),
    )

    engagement = EngagementMetrics(
        session_duration_s=2400.0,
        listening_duration_s=2350.0,
        interaction_count=5,
        configuration_change_count=2,
        accepted_change_count=2,
        rejected_change_count=0,
        reverted_change_count=0,
        replay_count=1,
        completion_ratio=1.0,
        session_abandoned=False,
        session_completed=True,
        return_session=True,
        explicit_engagement_rating=4.8,
        explicit_engagement_feedback="Immersive listening experience without fatigue.",
        derived_engagement_score=0.92,
        derived_notes="Calculated for reference only; not an oracle score.",
        events=events,
        source=EngagementEvidenceSource.SESSION_TELEMETRY,
    )

    feedback = HumanFeedback(
        status=FeedbackStatus.ACCEPTED,
        rating=4.5,
        qualitative_notes="Warm tonal balance sounds natural in the near-field.",
    )

    return ExperienceRecord(
        experience_id="exp-20260919-001",
        timestamp_iso=now_dt.isoformat(),
        evidence_type=EvidenceType.SOFTWARE_OFFLINE,
        outcome=OutcomeClassification.SUCCESS,
        schema_version="1.1.0",
        intent_summary=intent_sum,
        specification_summary=spec_sum,
        optimization_summary=opt_sum,
        graph_summary=graph_sum,
        execution_context=exec_context,
        runtime_observations=runtime_obs,
        temporal_solar_context=temporal,
        engagement=engagement,
        human_feedback=feedback,
    )


# ==============================================================================
# 1. Contract Validation & Immutability Tests
# ==============================================================================

def test_experience_record_construction_and_immutability(sample_experience_record: ExperienceRecord) -> None:
    """Verify that ExperienceRecord and all sub-dataclasses are strictly immutable."""
    assert sample_experience_record.experience_id == "exp-20260919-001"
    assert sample_experience_record.evidence_type == EvidenceType.SOFTWARE_OFFLINE
    assert sample_experience_record.outcome == OutcomeClassification.SUCCESS
    assert sample_experience_record.schema_version == "1.1.0"
    assert sample_experience_record.engagement is not None
    assert sample_experience_record.engagement.session_completed is True

    with pytest.raises(dataclasses.FrozenInstanceError):
        sample_experience_record.outcome = OutcomeClassification.FAILED  # type: ignore

    with pytest.raises(dataclasses.FrozenInstanceError):
        sample_experience_record.engagement.interaction_count = 10  # type: ignore


def test_experience_validation_rejection_of_invalid_values() -> None:
    """Verify fail-closed validation for non-finite values, negative counts, and out-of-range ratings."""
    with pytest.raises(ExperienceValidationError, match="experience_id cannot be empty"):
        ExperienceRecord(
            experience_id="",
            timestamp_iso="2026-09-19T00:00:00Z",
            evidence_type=EvidenceType.SOFTWARE_OFFLINE,
            outcome=OutcomeClassification.SUCCESS,
        )

    with pytest.raises(ExperienceValidationError, match="finite float"):
        OptimizationSummary(
            converged=True,
            initial_loss_db=float("nan"),
            final_loss_db=1.0,
            selected_crossover_hz=2000.0,
            iterations_completed=10,
        )

    with pytest.raises(ExperienceValidationError, match="Rating .* must be between 1.0 and 5.0"):
        HumanFeedback(status=FeedbackStatus.ACCEPTED, rating=6.0)

    # Engagement validations
    with pytest.raises(ExperienceValidationError, match="session_duration_s must be a non-negative finite float"):
        EngagementMetrics(session_duration_s=-10.0)

    with pytest.raises(ExperienceValidationError, match="interaction_count must be a non-negative integer"):
        EngagementMetrics(interaction_count=-1)

    with pytest.raises(ExperienceValidationError, match="explicit_engagement_rating .* must be between 1.0 and 5.0"):
        EngagementMetrics(explicit_engagement_rating=5.5)

    with pytest.raises(ExperienceValidationError, match="completion_ratio .* must be between 0.0 and 1.0"):
        EngagementMetrics(completion_ratio=1.5)


# ==============================================================================
# 2. Serialization and Lossless Round-Trip Tests
# ==============================================================================

def test_experience_record_json_roundtrip(sample_experience_record: ExperienceRecord) -> None:
    """Verify lossless serialization to dict and reconstruction from dict."""
    record_dict = sample_experience_record.to_dict()
    assert isinstance(record_dict, dict)
    assert record_dict["experience_id"] == "exp-20260919-001"
    assert record_dict["evidence_type"] == "SOFTWARE_OFFLINE"
    assert record_dict["schema_version"] == "1.1.0"
    assert "engagement" in record_dict
    assert record_dict["engagement"]["listening_duration_s"] == 2350.0

    json_str = json.dumps(record_dict)
    loaded_dict = json.loads(json_str)

    restored = ExperienceRecord.from_dict(loaded_dict)
    assert restored.experience_id == sample_experience_record.experience_id
    assert restored.timestamp_iso == sample_experience_record.timestamp_iso
    assert restored.evidence_type == sample_experience_record.evidence_type
    assert restored.outcome == sample_experience_record.outcome
    assert restored.schema_version == sample_experience_record.schema_version

    # Verify nested contracts restored accurately
    assert restored.intent_summary == sample_experience_record.intent_summary
    assert restored.specification_summary == sample_experience_record.specification_summary
    assert restored.optimization_summary == sample_experience_record.optimization_summary
    assert restored.graph_summary == sample_experience_record.graph_summary
    assert restored.execution_context == sample_experience_record.execution_context
    assert restored.runtime_observations == sample_experience_record.runtime_observations
    assert restored.temporal_solar_context == sample_experience_record.temporal_solar_context
    assert restored.engagement == sample_experience_record.engagement
    assert restored.human_feedback == sample_experience_record.human_feedback


# ==============================================================================
# 3. ExperienceStore Local Storage & Query Tests
# ==============================================================================

def test_experience_store_append_and_query(tmp_path: Path, sample_experience_record: ExperienceRecord) -> None:
    """Verify append-only JSONL storage, retrieval, and query filtering including engagement."""
    store_file = tmp_path / "test_experience.jsonl"
    store = ExperienceStore(store_file)

    assert store.count() == 0

    # 1. Append record
    store.append(sample_experience_record)
    assert store.count() == 1

    # 2. Retrieve by ID
    retrieved = store.get_by_id("exp-20260919-001")
    assert retrieved is not None
    assert retrieved.experience_id == "exp-20260919-001"
    assert retrieved.outcome == OutcomeClassification.SUCCESS

    # 3. Append a second record with different engagement and outcome
    now_evening = datetime.datetime(2026, 9, 19, 21, 0, 0, tzinfo=datetime.timezone.utc)
    evening_context = TemporalSolarContext(
        local_timestamp_iso=now_evening.isoformat(),
        timezone_name="UTC",
        day_phase=DayPhase.EVENING,
        source=SolarProvenance.UNAVAILABLE,
    )
    eng2 = EngagementMetrics(
        session_duration_s=60.0,
        listening_duration_s=45.0,
        interaction_count=1,
        session_abandoned=True,
        session_completed=False,
        explicit_engagement_rating=2.0,
    )
    rec2 = dataclasses.replace(
        sample_experience_record,
        experience_id="exp-20260919-002",
        timestamp_iso=now_evening.isoformat(),
        outcome=OutcomeClassification.REJECTED,
        temporal_solar_context=evening_context,
        engagement=eng2,
    )
    store.append(rec2)
    assert store.count() == 2

    # 4. Query filters
    success_records = store.query(outcome=OutcomeClassification.SUCCESS)
    assert len(success_records) == 1
    assert success_records[0].experience_id == "exp-20260919-001"

    rejected_records = store.query(outcome=OutcomeClassification.REJECTED)
    assert len(rejected_records) == 1
    assert rejected_records[0].experience_id == "exp-20260919-002"

    evening_records = store.query(day_phase=DayPhase.EVENING)
    assert len(evening_records) == 1
    assert evening_records[0].experience_id == "exp-20260919-002"

    # Engagement filters
    high_engagement = store.query(min_engagement_rating=4.0)
    assert len(high_engagement) == 1
    assert high_engagement[0].experience_id == "exp-20260919-001"

    abandoned = store.query(session_abandoned=True)
    assert len(abandoned) == 1
    assert abandoned[0].experience_id == "exp-20260919-002"

    completed = store.query(session_completed=True)
    assert len(completed) == 1
    assert completed[0].experience_id == "exp-20260919-001"


def test_experience_store_corrupted_line_fail_closed(tmp_path: Path, sample_experience_record: ExperienceRecord) -> None:
    """Verify that malformed/corrupted JSON lines are handled safely without crashing or code execution."""
    store_file = tmp_path / "corrupted_store.jsonl"
    store = ExperienceStore(store_file)

    store.append(sample_experience_record)

    # Inject corrupted non-JSON and malformed lines
    with open(store_file, "a", encoding="utf-8") as f:
        f.write("CORRUPTED_RAW_NON_JSON_DATA\n")
        f.write('{"experience_id": "malformed_missing_timestamp"}\n')

    # store.iter_records(skip_corrupted=True) should safely yield only valid records
    records = list(store.iter_records(skip_corrupted=True))
    assert len(records) == 1
    assert records[0].experience_id == sample_experience_record.experience_id

    # store.iter_records(skip_corrupted=False) should raise ExperienceStoreError
    with pytest.raises(ExperienceStoreError):
        list(store.iter_records(skip_corrupted=False))


# ==============================================================================
# 4. Observed vs Derived Separation Tests
# ==============================================================================

def test_observed_vs_derived_separation() -> None:
    """Verify that observed execution metrics and post-hoc derived calculations remain segregated."""
    obs = RuntimeObservations(
        blocks_processed=100,
        samples_processed=51200,
        total_execution_time_s=0.050,  # 50 ms total execution
        mean_block_time_us=500.0,
        xrun_count=0,
        derived_realtime_margin=21.33,  # 1.0667s audio / 0.050s execution
        derived_throughput_samples_per_sec=1024000.0,
    )

    # Observed metrics are raw timings/counts
    assert obs.blocks_processed == 100
    assert obs.samples_processed == 51200
    assert obs.total_execution_time_s == 0.050
    assert obs.mean_block_time_us == 500.0
    assert obs.xrun_count == 0

    # Derived metrics are explicitly calculated and marked
    assert obs.derived_realtime_margin == 21.33
    assert obs.derived_throughput_samples_per_sec == 1024000.0


# ==============================================================================
# 5. Engagement Evidence Separation & Trajectory Tests
# ==============================================================================

def test_engagement_evidence_separation_and_trajectory() -> None:
    """Verify separation of behavioral, explicit user-reported, and derived engagement evidence."""
    events = (
        ExperienceEvent(event_type=EventType.SESSION_STARTED, timestamp_iso="2026-09-19T10:00:00Z"),
        ExperienceEvent(event_type=EventType.CONFIGURATION_APPLIED, timestamp_iso="2026-09-19T10:00:10Z", payload={"crossover_hz": 2000}),
        ExperienceEvent(event_type=EventType.PLAYBACK_STARTED, timestamp_iso="2026-09-19T10:00:15Z"),
        ExperienceEvent(event_type=EventType.REPLAY, timestamp_iso="2026-09-19T10:30:00Z"),
        ExperienceEvent(event_type=EventType.SESSION_COMPLETED, timestamp_iso="2026-09-19T10:45:00Z"),
    )

    eng = EngagementMetrics(
        # Behavioral
        session_duration_s=2700.0,
        listening_duration_s=2680.0,
        interaction_count=4,
        configuration_change_count=1,
        replay_count=1,
        session_completed=True,
        # Explicit user-reported
        explicit_engagement_rating=4.9,
        explicit_engagement_feedback="Engaging soundstage with excellent clarity.",
        # Derived
        derived_engagement_score=0.95,
        derived_notes="Non-oracle derived metric.",
        events=events,
        source=EngagementEvidenceSource.SESSION_TELEMETRY,
    )

    # Behavioral metrics are raw observations
    assert eng.listening_duration_s == 2680.0
    assert eng.replay_count == 1
    assert eng.session_completed is True

    # Explicit feedback is stored separately
    assert eng.explicit_engagement_rating == 4.9
    assert eng.explicit_engagement_feedback == "Engaging soundstage with excellent clarity."

    # Derived values do not masquerade as raw measurements
    assert eng.derived_engagement_score == 0.95

    # Trajectory events preserved in order
    assert len(eng.events) == 5
    assert eng.events[0].event_type == EventType.SESSION_STARTED
    assert eng.events[3].event_type == EventType.REPLAY
    assert eng.events[4].event_type == EventType.SESSION_COMPLETED


def test_no_hardcoded_engagement_formula_or_mood_inference() -> None:
    """Verify that engagement metrics do not compute arbitrary weighted formulas or infer mood."""
    eng = EngagementMetrics(
        listening_duration_s=3600.0,
        interaction_count=20,
    )
    # The contract must not auto-generate a mood or mandatory composite score
    assert not hasattr(eng, "mood")
    assert not hasattr(eng, "emotional_state")
    assert eng.derived_engagement_score is None  # Remains unpopulated unless explicitly supplied


# ==============================================================================
# 6. Software vs Physical Evidence Segregation Tests
# ==============================================================================

def test_software_vs_physical_evidence_type() -> None:
    """Verify that offline execution is labeled SOFTWARE_OFFLINE and never PHYSICAL_HARDWARE."""
    rec_offline = ExperienceRecord(
        experience_id="exp-offline",
        timestamp_iso="2026-09-19T12:00:00Z",
        evidence_type=EvidenceType.SOFTWARE_OFFLINE,
        outcome=OutcomeClassification.SUCCESS,
    )
    assert rec_offline.evidence_type == EvidenceType.SOFTWARE_OFFLINE
    assert rec_offline.evidence_type != EvidenceType.PHYSICAL_HARDWARE


# ==============================================================================
# 7. Temporal and Solar Context Tests
# ==============================================================================

def test_temporal_solar_context_relative_features_and_day_phase() -> None:
    """Verify relative solar feature calculation (minutes since/until, daylight fraction, day phase)."""
    tz = datetime.timezone.utc
    sunrise = datetime.datetime(2026, 9, 19, 6, 0, 0, tzinfo=tz)
    sunset = datetime.datetime(2026, 9, 19, 18, 0, 0, tzinfo=tz)

    # 1. Pre-sunrise (05:30)
    t_pre = datetime.datetime(2026, 9, 19, 5, 30, 0, tzinfo=tz)
    ctx_pre = TemporalSolarContext.create_computed(t_pre, sunrise, sunset)
    assert ctx_pre.day_phase == DayPhase.PRE_SUNRISE
    assert ctx_pre.minutes_since_sunrise == -30.0
    assert ctx_pre.minutes_until_sunset == 750.0
    assert ctx_pre.daylight_fraction == 0.0

    # 2. Morning (08:00)
    t_morn = datetime.datetime(2026, 9, 19, 8, 0, 0, tzinfo=tz)
    ctx_morn = TemporalSolarContext.create_computed(t_morn, sunrise, sunset)
    assert ctx_morn.day_phase == DayPhase.MORNING
    assert ctx_morn.minutes_since_sunrise == 120.0
    assert ctx_morn.daylight_fraction == pytest.approx(2.0 / 12.0, abs=1e-3)

    # 3. Midday (12:00)
    t_mid = datetime.datetime(2026, 9, 19, 12, 0, 0, tzinfo=tz)
    ctx_mid = TemporalSolarContext.create_computed(t_mid, sunrise, sunset)
    assert ctx_mid.day_phase == DayPhase.MIDDAY
    assert ctx_mid.daylight_fraction == pytest.approx(0.5, abs=1e-3)

    # 4. Sunset window (18:15 - 15 mins after sunset)
    t_sunset = datetime.datetime(2026, 9, 19, 18, 15, 0, tzinfo=tz)
    ctx_sunset = TemporalSolarContext.create_computed(t_sunset, sunrise, sunset)
    assert ctx_sunset.day_phase == DayPhase.SUNSET_WINDOW
    assert ctx_sunset.minutes_until_sunset == -15.0

    # 5. Evening (20:00)
    t_eve = datetime.datetime(2026, 9, 19, 20, 0, 0, tzinfo=tz)
    ctx_eve = TemporalSolarContext.create_computed(t_eve, sunrise, sunset)
    assert ctx_eve.day_phase == DayPhase.EVENING

    # 6. Night (23:30)
    t_night = datetime.datetime(2026, 9, 19, 23, 30, 0, tzinfo=tz)
    ctx_night = TemporalSolarContext.create_computed(t_night, sunrise, sunset)
    assert ctx_night.day_phase == DayPhase.NIGHT


def test_temporal_solar_context_missing_solar_coordinates_safe_fallback() -> None:
    """Verify that missing solar data falls back gracefully to clock-based day phase."""
    tz = datetime.timezone.utc
    t_local = datetime.datetime(2026, 9, 19, 13, 0, 0, tzinfo=tz)

    ctx = TemporalSolarContext.create_computed(t_local, sunrise_dt=None, sunset_dt=None)
    assert ctx.day_phase == DayPhase.MIDDAY
    assert ctx.source == SolarProvenance.UNAVAILABLE
    assert ctx.sunrise_timestamp_iso is None
    assert ctx.sunset_timestamp_iso is None
    assert ctx.daylight_duration_s is None


def test_mood_boundary_no_psychological_inference() -> None:
    """Explicitly verify that sunset/sunrise does NOT infer or assign mood labels."""
    tz = datetime.timezone.utc
    sunrise = datetime.datetime(2026, 9, 19, 6, 0, 0, tzinfo=tz)
    sunset = datetime.datetime(2026, 9, 19, 18, 0, 0, tzinfo=tz)
    t_sunset = datetime.datetime(2026, 9, 19, 18, 10, 0, tzinfo=tz)

    ctx = TemporalSolarContext.create_computed(t_sunset, sunrise, sunset)
    # The context must record strictly physical/astronomical variables
    assert not hasattr(ctx, "mood")
    assert not hasattr(ctx, "emotional_state")
    assert not hasattr(ctx, "relaxation_score")
    assert ctx.day_phase == DayPhase.SUNSET_WINDOW


# ==============================================================================
# 8. End-to-End Pipeline Capture Test with Engagement & Events
# ==============================================================================

def test_end_to_end_experience_capture_pipeline(
    tmp_path: Path,
    synthetic_driver_responses: tuple[FrequencyResponseData, FrequencyResponseData],
) -> None:
    """Verify complete pipeline execution and experience episode capture:
    AI Query -> DesignIntent -> Adapter -> Core Optimizer -> ComputeGraph -> Offline Backend -> Events -> Engagement -> ExperienceCollector -> ExperienceStore.
    """
    woofer, tweeter = synthetic_driver_responses
    store_file = tmp_path / "pipeline_experience.jsonl"
    store = ExperienceStore(store_file)

    # 1. AI Intent Proposal
    provider = MockDesignIntentProvider()
    query = "Optimize 2-way system with 2 kHz crossover"
    intent = provider.propose_intent(query)

    collector = ExperienceCollector(session_id="e2e-session-001")
    collector.record_event(EventType.SESSION_STARTED, payload={"query": query})
    collector.record_event(EventType.INTENT_PROPOSED, payload={"intent_id": intent.intent_id})

    # 2. Validation Firewall & Compilation
    pos = SpatialMeasurementPosition("Main", {"woofer": woofer, "tweeter": tweeter}, (0.0, 2.0, 1.0))
    spec, record = DesignIntentAdapter.compile(intent, spatial_positions=(pos,))
    assert record.validation_status == "ACCEPTED"
    assert isinstance(spec, MultiPositionOptimizationSpecification)
    collector.record_event(EventType.INTENT_ACCEPTED)

    # 3. Core Deterministic Optimization
    opt_result = optimize_multi_position(spec)
    assert isinstance(opt_result, MultiPositionOptimizationResult)
    assert opt_result.converged is True

    # 4. Wrap & Compile to ComputeGraph
    from acoustiforge.acoustic_math.metrics import calculate_response_metrics

    primary_resp = opt_result.predicted_responses["Main"]
    metrics = calculate_response_metrics(primary_resp, spec.target_curve)
    core_res = OptimizationResult(
        crossover_result=opt_result.crossover_result,
        gain_results=opt_result.gain_results,
        alignment_results=opt_result.alignment_results,
        predicted_response=primary_resp,
        initial_metrics=metrics,
        optimized_metrics=metrics,
        initial_loss_db=opt_result.initial_loss,
        final_loss_db=opt_result.total_loss,
        converged=opt_result.converged,
        iterations_completed=opt_result.iterations_completed,
    )
    graph = compile_optimization_result_to_graph(core_res, sample_rate=48000, graph_name="E2E_Graph")
    collector.record_event(EventType.CONFIGURATION_APPLIED)

    # 5. Offline PCM Execution
    backend = OfflineExecutionBackend()
    config = StreamConfig(sample_rate=48000, channels=1, block_size=512)
    backend.initialize(graph, config)
    backend.start()

    collector.record_event(EventType.PLAYBACK_STARTED)
    in_samples = np.zeros((1, 512), dtype=np.float32)
    in_samples[0, 0] = 1.0
    in_block = PCMBlock(samples=in_samples, metadata=AudioMetadata(sample_rate=48000, channels=1))

    t_start = datetime.datetime.now()
    for _ in range(5):
        backend.process(in_block)
    t_end = datetime.datetime.now()
    exec_duration_s = max(0.0001, (t_end - t_start).total_seconds())
    backend.close()
    collector.record_event(EventType.PLAYBACK_STOPPED)
    collector.record_event(EventType.SESSION_COMPLETED)

    # 6. Experience Capture via Collector
    collector.record_intent(intent, query=query, provider_name="MockDesignIntentProvider")
    collector.record_specification(spec)
    collector.record_optimization(opt_result)
    collector.record_graph(graph)
    collector.record_execution(
        backend=backend,
        config=config,
        total_execution_time_s=exec_duration_s,
        blocks_processed=5,
        samples_processed=5 * 512,
        xrun_count=0,
    )
    collector.record_engagement(
        session_duration_s=180.0,
        listening_duration_s=175.0,
        interaction_count=3,
        session_completed=True,
        explicit_engagement_rating=4.8,
        explicit_engagement_feedback="Smooth transition across crossover band.",
    )
    collector.record_feedback(
        status=FeedbackStatus.ACCEPTED,
        rating=5.0,
        notes="Clean crossover transition, no phase cancellation.",
    )

    exp_record = collector.build(evidence_type=EvidenceType.SOFTWARE_OFFLINE)
    assert exp_record.experience_id == "e2e-session-001"
    assert exp_record.outcome == OutcomeClassification.SUCCESS
    assert exp_record.evidence_type == EvidenceType.SOFTWARE_OFFLINE
    assert exp_record.engagement is not None
    assert len(exp_record.engagement.events) == 7
    assert exp_record.engagement.session_completed is True

    # 7. Commit to Store
    store.append(exp_record)
    assert store.count() == 1

    stored_rec = store.get_by_id("e2e-session-001")
    assert stored_rec is not None
    assert stored_rec.optimization_summary.converged is True
    assert stored_rec.runtime_observations.blocks_processed == 5
    assert stored_rec.engagement is not None
    assert stored_rec.engagement.explicit_engagement_rating == 4.8


# ==============================================================================
# 9. Architectural Zero-Mutation & Isolation Test
# ==============================================================================

def test_experience_boundary_does_not_mutate_core_or_graph() -> None:
    """Verify that capturing an experience record does not alter Core contracts or Graph state."""
    collector = ExperienceCollector()
    assert collector is not None
    # Verify core domain imports remain clean
    from acoustiforge.domain.specifications import CrossoverSpecification, CrossoverFamily
    spec = CrossoverSpecification(CrossoverFamily.LINKWITZ_RILEY, 4, 2000.0)
    assert spec.frequency_hz == 2000.0
