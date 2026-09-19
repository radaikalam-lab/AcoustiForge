"""Unit and integration tests for Phase 5-7A Experience Retrieval & Analytics.

Normative Authority:
    - Phase 5-7A Specification: Experience Retrieval & Analytics
    - Governing Invariants:
        1. AI proposes. AcoustiForge validates and executes.
        2. Runtime teaches the AI layer; runtime does not rewrite the acoustic Core.
        3. The Experience Store is the historical evidence layer.
        4. Historical experience is advisory evidence, never an authoritative source of DSP parameters.
        5. Temporal and solar context are contextual variables, not measurements of mood.
        6. Behavioral engagement evidence must not be silently interpreted as satisfaction or psychological state.
"""

import datetime
from pathlib import Path
import pytest

from acoustiforge.experience.contracts import (
    DayPhase,
    EngagementEvidenceSource,
    EngagementMetrics,
    EventType,
    EvidenceType,
    ExecutionContextSummary,
    ExperienceEvent,
    ExperienceRecord,
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
from acoustiforge.experience.store import ExperienceStore
from acoustiforge.experience.retrieval import ExperienceQuery, ExperienceRetriever
from acoustiforge.experience.analytics import (
    ExperienceAnalytics,
    ExperienceAnalyticsSummary,
    OptimizationAnalyticsSummary,
    EngagementAnalyticsSummary,
    RuntimeAnalyticsSummary,
)


# ==============================================================================
# Fixtures & Synthetic Test Dataset
# ==============================================================================

def _make_record(
    exp_id: str,
    outcome: OutcomeClassification = OutcomeClassification.SUCCESS,
    evidence_type: EvidenceType = EvidenceType.SOFTWARE_OFFLINE,
    crossover_family: str = "LINKWITZ_RILEY",
    crossover_order: int = 4,
    selected_crossover_hz: float = 2000.0,
    target_crossover_hz: float = 2000.0,
    initial_loss_db: float = 5.0,
    final_loss_db: float = 1.0,
    converged: bool = True,
    platform: str = "offline",
    backend_type: str = "OfflineExecutionBackend",
    day_phase: DayPhase = DayPhase.MIDDAY,
    listening_duration_s: float = 1200.0,
    engagement_rating: float = 4.5,
    user_rating: float = 4.5,
    session_completed: bool = True,
    session_abandoned: bool = False,
    reverted_changes: int = 0,
    timestamp_iso: str = "2026-09-19T12:00:00Z",
) -> ExperienceRecord:
    """Helper to synthesize calibrated ExperienceRecords for retrieval/analytics testing."""
    intent_sum = IntentSummary(
        query="Test query",
        intent_id=f"intent-{exp_id}",
        target_preset="flat",
        crossover_frequency_target_hz=target_crossover_hz,
        crossover_family=crossover_family,
        crossover_order=crossover_order,
    )
    spec_sum = SpecificationSummary(
        specification_type="OptimizationSpecification",
        crossover_family=crossover_family,
        crossover_order=crossover_order,
        search_band_hz=(500.0, 5000.0),
    )
    opt_sum = OptimizationSummary(
        converged=converged,
        initial_loss_db=initial_loss_db,
        final_loss_db=final_loss_db,
        selected_crossover_hz=selected_crossover_hz,
        iterations_completed=10,
    )
    exec_ctx = ExecutionContextSummary(
        backend_type=backend_type,
        platform=platform,
        sample_rate=48000,
        channels=1,
        block_size=512,
    )
    runtime_obs = RuntimeObservations(
        blocks_processed=100,
        samples_processed=51200,
        total_execution_time_s=0.050,
        mean_block_time_us=500.0,
        xrun_count=0,
        derived_realtime_margin=21.33,
    )
    temporal = TemporalSolarContext(
        local_timestamp_iso=timestamp_iso,
        timezone_name="UTC",
        day_phase=day_phase,
    )
    eng = EngagementMetrics(
        session_duration_s=listening_duration_s + 50.0,
        listening_duration_s=listening_duration_s,
        interaction_count=3,
        reverted_change_count=reverted_changes,
        session_completed=session_completed,
        session_abandoned=session_abandoned,
        explicit_engagement_rating=engagement_rating,
        events=(ExperienceEvent(EventType.SESSION_STARTED, timestamp_iso),),
    )
    feedback = HumanFeedback(
        status=FeedbackStatus.ACCEPTED if outcome == OutcomeClassification.SUCCESS else FeedbackStatus.REJECTED,
        rating=user_rating,
    )

    return ExperienceRecord(
        experience_id=exp_id,
        timestamp_iso=timestamp_iso,
        evidence_type=evidence_type,
        outcome=outcome,
        intent_summary=intent_sum,
        specification_summary=spec_sum,
        optimization_summary=opt_sum,
        graph_summary=GraphSummary("TestGraph", 8, 48000, 1),
        execution_context=exec_ctx,
        runtime_observations=runtime_obs,
        temporal_solar_context=temporal,
        engagement=eng,
        human_feedback=feedback,
    )


@pytest.fixture
def populated_store(tmp_path: Path) -> ExperienceStore:
    """Create a populated ExperienceStore with varied calibrated records."""
    store_file = tmp_path / "analytics_test_store.jsonl"
    store = ExperienceStore(store_file)

    records = [
        # Record 1: Linkwitz-Riley 4th, 2 kHz, Success, 4.8 rating, Midday, Offline
        _make_record(
            "rec-001",
            outcome=OutcomeClassification.SUCCESS,
            evidence_type=EvidenceType.SOFTWARE_OFFLINE,
            crossover_family="LINKWITZ_RILEY",
            crossover_order=4,
            selected_crossover_hz=2000.0,
            target_crossover_hz=2000.0,
            initial_loss_db=6.0,
            final_loss_db=0.8,
            day_phase=DayPhase.MIDDAY,
            engagement_rating=4.8,
            user_rating=4.8,
            timestamp_iso="2026-09-19T12:00:00Z",
        ),
        # Record 2: Butterworth 2nd, 1.5 kHz, Success, 4.2 rating, Evening, Offline
        _make_record(
            "rec-002",
            outcome=OutcomeClassification.SUCCESS,
            evidence_type=EvidenceType.SOFTWARE_OFFLINE,
            crossover_family="BUTTERWORTH",
            crossover_order=2,
            selected_crossover_hz=1500.0,
            target_crossover_hz=1500.0,
            initial_loss_db=8.0,
            final_loss_db=1.5,
            day_phase=DayPhase.EVENING,
            engagement_rating=4.2,
            user_rating=4.2,
            timestamp_iso="2026-09-19T19:00:00Z",
        ),
        # Record 3: Linkwitz-Riley 4th, 2.5 kHz, Physical Hardware, Linux, Success, 4.9 rating
        _make_record(
            "rec-003",
            outcome=OutcomeClassification.SUCCESS,
            evidence_type=EvidenceType.PHYSICAL_HARDWARE,
            crossover_family="LINKWITZ_RILEY",
            crossover_order=4,
            selected_crossover_hz=2500.0,
            target_crossover_hz=2400.0,
            initial_loss_db=5.5,
            final_loss_db=0.6,
            platform="linux",
            backend_type="AlsaExecutionBackend",
            day_phase=DayPhase.SUNSET_WINDOW,
            engagement_rating=4.9,
            user_rating=4.9,
            timestamp_iso="2026-09-19T18:15:00Z",
        ),
        # Record 4: Rejected episode, unconverged, abandoned session
        _make_record(
            "rec-004",
            outcome=OutcomeClassification.REJECTED,
            evidence_type=EvidenceType.SOFTWARE_OFFLINE,
            crossover_family="LINKWITZ_RILEY",
            crossover_order=4,
            selected_crossover_hz=3000.0,
            target_crossover_hz=3000.0,
            initial_loss_db=10.0,
            final_loss_db=8.5,
            converged=False,
            day_phase=DayPhase.NIGHT,
            engagement_rating=1.5,
            user_rating=1.5,
            session_completed=False,
            session_abandoned=True,
            reverted_changes=2,
            timestamp_iso="2026-09-19T23:00:00Z",
        ),
    ]

    for r in records:
        store.append(r)

    return store


# ==============================================================================
# 1. ExperienceRetriever Tests
# ==============================================================================

def test_retriever_exact_and_range_filtering(populated_store: ExperienceStore) -> None:
    """Verify structured filtering on crossover family, range, and convergence."""
    retriever = ExperienceRetriever(populated_store)

    # 1. Filter by crossover family
    lr_records = retriever.search(crossover_family="LINKWITZ_RILEY")
    assert len(lr_records) == 3
    assert all(r.specification_summary.crossover_family == "LINKWITZ_RILEY" for r in lr_records)

    bw_records = retriever.search(crossover_family="BUTTERWORTH")
    assert len(bw_records) == 1
    assert bw_records[0].experience_id == "rec-002"

    # 2. Filter by selected crossover frequency range
    mid_freq_records = retriever.search(selected_crossover_range_hz=(1800.0, 2600.0))
    assert len(mid_freq_records) == 2
    assert {r.experience_id for r in mid_freq_records} == {"rec-001", "rec-003"}

    # 3. Filter by convergence
    converged_records = retriever.search(converged_only=True)
    assert len(converged_records) == 3
    assert "rec-004" not in [r.experience_id for r in converged_records]


def test_retriever_evidence_type_segregation(populated_store: ExperienceStore) -> None:
    """Verify that physical hardware evidence is strictly segregated from software offline evidence."""
    retriever = ExperienceRetriever(populated_store)

    physical_records = retriever.search(evidence_type=EvidenceType.PHYSICAL_HARDWARE)
    assert len(physical_records) == 1
    assert physical_records[0].experience_id == "rec-003"
    assert physical_records[0].evidence_type == EvidenceType.PHYSICAL_HARDWARE

    offline_records = retriever.search(evidence_type=EvidenceType.SOFTWARE_OFFLINE)
    assert len(offline_records) == 3
    assert all(r.evidence_type == EvidenceType.SOFTWARE_OFFLINE for r in offline_records)


def test_retriever_engagement_and_temporal_filtering(populated_store: ExperienceStore) -> None:
    """Verify filtering on explicit engagement rating, session completion, and day phase."""
    retriever = ExperienceRetriever(populated_store)

    # 1. Minimum explicit engagement rating >= 4.5
    high_engagement = retriever.search(min_engagement_rating=4.5)
    assert len(high_engagement) == 2
    assert {r.experience_id for r in high_engagement} == {"rec-001", "rec-003"}

    # 2. Session completed only
    completed = retriever.search(session_completed_only=True)
    assert len(completed) == 3
    assert "rec-004" not in [r.experience_id for r in completed]

    # 3. Session abandoned only
    abandoned = retriever.search(session_abandoned_only=True)
    assert len(abandoned) == 1
    assert abandoned[0].experience_id == "rec-004"

    # 4. Day phase filtering
    evening_sunset = retriever.search(day_phase=DayPhase.SUNSET_WINDOW)
    assert len(evening_sunset) == 1
    assert evening_sunset[0].experience_id == "rec-003"


def test_retriever_deterministic_ranking_hierarchy(populated_store: ExperienceStore) -> None:
    """Verify hierarchical ranking: Outcome tier -> Rating -> Acoustic distance -> Loss -> Tie breaker."""
    retriever = ExperienceRetriever(populated_store)

    # Search around target crossover 2400 Hz
    ranked = retriever.search(target_crossover_hz=2400.0)
    assert len(ranked) == 4

    # The 3 SUCCESS records must precede the 1 REJECTED record
    assert ranked[3].experience_id == "rec-004"  # REJECTED

    # Among SUCCESS records, rec-003 has rating 4.9, rec-001 has 4.8, rec-002 has 4.2
    assert ranked[0].experience_id == "rec-003"  # Rating 4.9 & closest to 2400 Hz (2500 Hz)
    assert ranked[1].experience_id == "rec-001"  # Rating 4.8
    assert ranked[2].experience_id == "rec-002"  # Rating 4.2


def test_retriever_determinism_repeated_execution(populated_store: ExperienceStore) -> None:
    """Verify that identical queries over the same store produce bit-exact identical sequences."""
    retriever = ExperienceRetriever(populated_store)

    res1 = [r.experience_id for r in retriever.search(crossover_family="LINKWITZ_RILEY")]
    res2 = [r.experience_id for r in retriever.search(crossover_family="LINKWITZ_RILEY")]
    res3 = [r.experience_id for r in retriever.search(crossover_family="LINKWITZ_RILEY")]

    assert res1 == res2 == res3


# ==============================================================================
# 2. ExperienceAnalytics Tests
# ==============================================================================

def test_analytics_empty_dataset_safe_handling() -> None:
    """Verify that an empty record sequence returns a clean summary with None for missing averages."""
    summary = ExperienceAnalytics.summarize([])
    assert summary.total_records == 0
    assert summary.optimization.record_count == 0
    assert summary.optimization.convergence_ratio == 0.0
    assert summary.optimization.mean_final_loss_db is None
    assert summary.engagement.mean_listening_duration_s is None
    assert summary.runtime.mean_block_time_us is None


def test_analytics_summary_calculation(populated_store: ExperienceStore) -> None:
    """Verify accurate calculation of descriptive optimization, engagement, and runtime metrics."""
    records = list(populated_store.iter_records())
    summary = ExperienceAnalytics.summarize(records)

    assert summary.total_records == 4

    # Outcome counts
    assert summary.outcome_counts[OutcomeClassification.SUCCESS.value] == 3
    assert summary.outcome_counts[OutcomeClassification.REJECTED.value] == 1

    # Evidence type counts
    assert summary.evidence_type_counts[EvidenceType.SOFTWARE_OFFLINE.value] == 3
    assert summary.evidence_type_counts[EvidenceType.PHYSICAL_HARDWARE.value] == 1

    # Optimization analytics
    # Initial losses: [6.0, 8.0, 5.5, 10.0] -> sum = 29.5 / 4 = 7.375
    assert summary.optimization.record_count == 4
    assert summary.optimization.converged_count == 3
    assert summary.optimization.convergence_ratio == 0.75
    assert summary.optimization.mean_initial_loss_db == pytest.approx(7.375, abs=1e-3)
    # Final losses: [0.8, 1.5, 0.6, 8.5] -> sum = 11.4 / 4 = 2.85
    assert summary.optimization.mean_final_loss_db == pytest.approx(2.85, abs=1e-3)
    # Reductions: [5.2, 6.5, 4.9, 1.5] -> sum = 18.1 / 4 = 4.525
    assert summary.optimization.mean_loss_reduction_db == pytest.approx(4.525, abs=1e-3)
    assert summary.optimization.min_final_loss_db == 0.6
    assert summary.optimization.max_final_loss_db == 8.5

    # Engagement analytics
    assert summary.engagement.record_count == 4
    assert summary.engagement.completed_sessions_count == 3
    assert summary.engagement.abandoned_sessions_count == 1
    assert summary.engagement.completion_ratio == 0.75

    # Runtime analytics
    assert summary.runtime.record_count == 4
    assert summary.runtime.total_blocks_processed == 400
    assert summary.runtime.total_xruns == 0
    assert summary.runtime.mean_realtime_margin == pytest.approx(21.33, abs=1e-2)


def test_analytics_grouping_methods(populated_store: ExperienceStore) -> None:
    """Verify grouping by crossover family, day phase, evidence type, and platform."""
    records = list(populated_store.iter_records())

    # 1. Group by Crossover Family
    by_family = ExperienceAnalytics.group_by_crossover_family(records)
    assert "LINKWITZ_RILEY" in by_family
    assert "BUTTERWORTH" in by_family
    assert by_family["LINKWITZ_RILEY"].total_records == 3
    assert by_family["BUTTERWORTH"].total_records == 1

    # 2. Group by Day Phase
    by_phase = ExperienceAnalytics.group_by_day_phase(records)
    assert DayPhase.MIDDAY.value in by_phase
    assert DayPhase.EVENING.value in by_phase
    assert DayPhase.SUNSET_WINDOW.value in by_phase
    assert DayPhase.NIGHT.value in by_phase

    # 3. Group by Evidence Type
    by_evidence = ExperienceAnalytics.group_by_evidence_type(records)
    assert EvidenceType.SOFTWARE_OFFLINE.value in by_evidence
    assert EvidenceType.PHYSICAL_HARDWARE.value in by_evidence
    assert by_evidence[EvidenceType.PHYSICAL_HARDWARE.value].total_records == 1

    # 4. Group by Platform
    by_platform = ExperienceAnalytics.group_by_platform(records)
    assert "linux" in by_platform
    assert "offline" in by_platform
    assert by_platform["linux"].total_records == 1
    assert by_platform["offline"].total_records == 3
