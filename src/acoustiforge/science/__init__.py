"""AcoustiForge Scientific Observation and Experiment Envelope Module (Phase P1).

Provides external integration envelopes associating physical/imported measurements
with environmental context, acquisition provenance, and experiment protocols
without modifying the frozen Epistemic Subsystem (E0.5-E10) or Production Core.

Normative Authority:
- docs/architecture/POST_FREEZE_INTEGRATION.md
- docs/phases/PHASE_P1_SCIENTIFIC_OBSERVATION_EXPERIMENT.md
- Governing Law: Epistemic Novelty != Production Authority
"""

from .experiment import (
    ExperimentLifecycleState,
    ExperimentSession,
    ExperimentSessionRegistry,
)
from .observation import (
    EnvironmentalConditions,
    MeasurementTransform,
    MeasurementUncertainty,
    ObservationEnvelope,
    ObservationRegistry,
)

__all__ = [
    "EnvironmentalConditions",
    "ExperimentLifecycleState",
    "ExperimentSession",
    "ExperimentSessionRegistry",
    "MeasurementTransform",
    "MeasurementUncertainty",
    "ObservationEnvelope",
    "ObservationRegistry",
]
