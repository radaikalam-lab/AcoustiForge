"""AcoustiForge Acoustic Intelligence & Domain Models Package.

Normative Authority:
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from .measurements import FrequencyResponseData, ImpulseResponseData
from .profiles import DriverProfile, DriverRole, EnclosureProfile, EnclosureType
from .specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
    OptimizationResult,
    OptimizationSpecification,
    TransducerLimits,
)
from .validation import (
    DomainError,
    InvalidMeasurementError,
    InvalidProfileError,
    InvalidSpecificationError,
)

__all__ = [
    "AcousticTargetCurve",
    "CrossoverFamily",
    "CrossoverSpecification",
    "DomainError",
    "DriverProfile",
    "DriverRole",
    "EnclosureProfile",
    "EnclosureType",
    "EqualizerBudget",
    "FrequencyResponseData",
    "ImpulseResponseData",
    "InvalidMeasurementError",
    "InvalidProfileError",
    "InvalidSpecificationError",
    "OptimizationResult",
    "OptimizationSpecification",
    "TransducerLimits",
]
