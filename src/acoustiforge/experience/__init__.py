"""AcoustiForge Experience and Learning Boundary Package.

Normative Authority:
    - Phase 5-6 Specification: Runtime Experience & Learning Boundary
    - Phase 5-6 Extension: Engagement Capture
    - Phase 5-7A Specification: Experience Retrieval & Analytics
    - Governing Principle: "AI proposes. AcoustiForge validates and executes."
    - Runtime Principle: "Runtime teaches the AI layer; runtime does not rewrite the acoustic Core."
    - Storage Principle: "The Experience Store is authoritative historical evidence, NOT LLM memory."
    - Context Principle: "Temporal and solar context are contextual variables, NOT direct measurements of human mood."
    - Engagement Principle: "Engagement is captured as behavioral or explicitly reported evidence; it is not automatically treated as psychological state or mood."
"""

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
from .collector import ExperienceCollector
from .store import ExperienceStore, ExperienceStoreError
from .retrieval import ExperienceQuery, ExperienceRetriever
from .analytics import (
    EngagementAnalyticsSummary,
    ExperienceAnalytics,
    ExperienceAnalyticsSummary,
    OptimizationAnalyticsSummary,
    RuntimeAnalyticsSummary,
)

__all__ = [
    "DayPhase",
    "EngagementAnalyticsSummary",
    "EngagementEvidenceSource",
    "EngagementMetrics",
    "EventType",
    "EvidenceType",
    "ExecutionContextSummary",
    "ExperienceAnalytics",
    "ExperienceAnalyticsSummary",
    "ExperienceCollector",
    "ExperienceEvent",
    "ExperienceQuery",
    "ExperienceRecord",
    "ExperienceRetriever",
    "ExperienceStore",
    "ExperienceStoreError",
    "ExperienceValidationError",
    "FeedbackStatus",
    "GraphSummary",
    "HumanFeedback",
    "IntentSummary",
    "OptimizationAnalyticsSummary",
    "OptimizationSummary",
    "OutcomeClassification",
    "RuntimeAnalyticsSummary",
    "RuntimeObservations",
    "SolarProvenance",
    "SpecificationSummary",
    "TemporalSolarContext",
]
