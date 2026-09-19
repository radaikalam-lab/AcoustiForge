"""AcoustiForge Epistemic Vocabulary and Value Objects.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Governing Invariant: Epistemic Novelty != Production Authority
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Mapping, Optional


# ==============================================================================
# 1. Epistemic Zones
# ==============================================================================

class EpistemicZone(str, Enum):
    """The four distinct epistemic zones of knowledge and uncertainty."""
    ZONE_H = "ZONE_H"  # Invariants & bounded hard constraints
    ZONE_M = "ZONE_M"  # Explanatory models & approximations
    ZONE_P = "ZONE_P"  # Problem framing, objectives, ontology, representation
    ZONE_U = "ZONE_U"  # Unknowns, anomalies, unexplained phenomena


# ==============================================================================
# 2. Epistemic Classification
# ==============================================================================

class EpistemicClass(str, Enum):
    """Rigorous epistemic categorization of constraints, rules, and claims."""
    MATHEMATICAL_THEOREM = "MATHEMATICAL_THEOREM"
    PHYSICAL_INVARIANT = "PHYSICAL_INVARIANT"
    CONSTITUTIVE_MODEL = "CONSTITUTIVE_MODEL"
    APPROXIMATION = "APPROXIMATION"
    EMPIRICAL_REGULARITY = "EMPIRICAL_REGULARITY"
    ENGINEERING_HEURISTIC = "ENGINEERING_HEURISTIC"
    OBJECTIVE_ASSUMPTION = "OBJECTIVE_ASSUMPTION"
    ONTOLOGICAL_ASSUMPTION = "ONTOLOGICAL_ASSUMPTION"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


# ==============================================================================
# 3. Epistemic Status (Scientific Lifecycle)
# ==============================================================================

class EpistemicStatus(str, Enum):
    """Lifecycle status of a model or scientific hypothesis."""
    CONJECTURE = "CONJECTURE"
    HYPOTHESIS = "HYPOTHESIS"
    TESTED_CANDIDATE = "TESTED_CANDIDATE"
    VALIDATED_MODEL = "VALIDATED_MODEL"
    EPISTEMIC_ACCEPTED = "EPISTEMIC_ACCEPTED"
    PRODUCTION_CANDIDATE = "PRODUCTION_CANDIDATE"
    PRODUCTION_AUTHORITY = "PRODUCTION_AUTHORITY"
    FALSIFICATION_EVIDENCE_DETECTED = "FALSIFICATION_EVIDENCE_DETECTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    DOMAIN_LIMITED = "DOMAIN_LIMITED"
    CHALLENGED = "CHALLENGED"
    FALSIFIED = "FALSIFIED"
    DEPRECATED = "DEPRECATED"


# ==============================================================================
# 4. Challenge Status (Investigation Lifecycle)
# ==============================================================================

class ChallengeStatus(str, Enum):
    """Investigation status of a scientific challenge."""
    UNCHALLENGED = "UNCHALLENGED"
    CHALLENGE_PROPOSED = "CHALLENGE_PROPOSED"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    EVIDENCE_SUPPORTED = "EVIDENCE_SUPPORTED"
    CHALLENGE_REJECTED = "CHALLENGE_REJECTED"
    EPISTEMIC_ACCEPTED = "EPISTEMIC_ACCEPTED"


# ==============================================================================
# 5. Zone H Challenge Taxonomy
# ==============================================================================

class ZoneHChallengeType(str, Enum):
    """Categorization of challenges directed at Zone H invariants."""
    H_APPLICABILITY_CHALLENGE = "H_APPLICABILITY_CHALLENGE"
    H_CLASSIFICATION_CHALLENGE = "H_CLASSIFICATION_CHALLENGE"
    H_FUNDAMENTAL_CHALLENGE = "H_FUNDAMENTAL_CHALLENGE"


# ==============================================================================
# 6. Residual Candidate Explanatory Classes
# ==============================================================================

class ResidualClassificationType(str, Enum):
    """Candidate explanatory categories for acoustic residuals (not truth claims)."""
    MEASUREMENT_ERROR = "MEASUREMENT_ERROR"
    PARAMETER_ERROR = "PARAMETER_ERROR"
    BOUNDARY_ERROR = "BOUNDARY_ERROR"
    MODEL_ERROR = "MODEL_ERROR"
    MISSING_VARIABLE = "MISSING_VARIABLE"
    UNKNOWN = "UNKNOWN"


# ==============================================================================
# 7. Evidence Taxonomy & Relationships
# ==============================================================================

class EpistemicEvidenceType(str, Enum):
    """Provenance-distinct categorization of evidence."""
    MATHEMATICAL_PROOF = "MATHEMATICAL_PROOF"
    PHYSICAL_MEASUREMENT = "PHYSICAL_MEASUREMENT"
    EXPERIMENTAL_RESULT = "EXPERIMENTAL_RESULT"
    SIMULATION = "SIMULATION"
    OBSERVATIONAL_DATA = "OBSERVATIONAL_DATA"
    ENGINEERING_TEST = "ENGINEERING_TEST"
    HUMAN_FEEDBACK = "HUMAN_FEEDBACK"
    AI_GENERATED_HYPOTHESIS = "AI_GENERATED_HYPOTHESIS"


class EvidenceRelation(str, Enum):
    """Directional relationship between an evidence observation and a target entity."""
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CHALLENGES = "CHALLENGES"
    LOCALIZES = "LOCALIZES"
    DISCRIMINATES = "DISCRIMINATES"
    DOES_NOT_TEST = "DOES_NOT_TEST"


# ==============================================================================
# 8. Epistemic Evidence Link Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class EpistemicEvidenceLink:
    """Immutable value object linking an evidence item to a model, assumption, or unknown."""
    evidence_id: str
    target_id: str
    relation: EvidenceRelation
    confidence: float
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError(f"evidence_id must be a non-empty string, got {self.evidence_id!r}.")

        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError(f"target_id must be a non-empty string, got {self.target_id!r}.")

        if not isinstance(self.relation, EvidenceRelation):
            if isinstance(self.relation, str):
                try:
                    object.__setattr__(self, "relation", EvidenceRelation(self.relation))
                except ValueError as err:
                    raise ValueError(f"Unsupported EvidenceRelation: {self.relation!r}.") from err
            else:
                raise ValueError(f"relation must be an EvidenceRelation enum or str, got {type(self.relation)!r}.")

        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool) or not math.isfinite(self.confidence):
            raise ValueError(f"confidence must be a finite float, got {self.confidence!r}.")

        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be bounded in [0.0, 1.0], got {self.confidence!r}.")

        object.__setattr__(self, "evidence_id", self.evidence_id.strip())
        object.__setattr__(self, "target_id", self.target_id.strip())
        object.__setattr__(self, "confidence", float(self.confidence))
        if self.notes is not None:
            if not isinstance(self.notes, str):
                raise ValueError(f"notes must be a string or None, got {type(self.notes)!r}.")
            object.__setattr__(self, "notes", self.notes.strip())

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic conversion to JSON-serializable dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "confidence": self.confidence,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpistemicEvidenceLink:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected mapping, got {type(data)!r}.")
        return cls(
            evidence_id=data.get("evidence_id", ""),
            target_id=data.get("target_id", ""),
            relation=data.get("relation", EvidenceRelation.SUPPORTS),
            confidence=float(data.get("confidence", 1.0)),
            notes=data.get("notes"),
        )
