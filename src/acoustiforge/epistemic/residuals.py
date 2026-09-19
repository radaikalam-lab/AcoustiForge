"""AcoustiForge Epistemic Residual and Residual Assessment Value Objects and Registry.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E4: Unknown and Residual Representation
- Governing Invariants:
  - RESIDUAL != MODEL_ERROR
  - RESIDUAL != FALSIFICATION
  - RESIDUAL != PROOF
  - RESIDUAL != TRUTH
  - Candidate Explanations != Declarations of Truth
  - Proposed Tests != Test Execution
  - Assessment != Falsification Event
  - Provenance != Evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence

from .vocabulary import (
    ResidualClassificationType,
)


# ==============================================================================
# 1. Model Residual Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class ModelResidual:
    """Immutable representation of an observed discrepancy between an observation and a model prediction.

    A ModelResidual records what model was evaluated, what observation was involved, what prediction
    was evaluated, what discrepancy was observed, under what declared scope, and from what source.
    It is descriptive data; it does not automatically classify itself or declare model error.
    """
    residual_id: str
    model_id: str
    observation_ref: str
    prediction_ref: str
    residual_summary: str
    scope: Mapping[str, Any]
    provenance: str

    def __post_init__(self) -> None:
        # 1. Validate residual_id
        if not isinstance(self.residual_id, str) or not self.residual_id.strip():
            raise ValueError(f"residual_id must be a non-empty string, got {self.residual_id!r}.")

        # 2. Validate model_id
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError(f"model_id must be a non-empty string, got {self.model_id!r}.")

        # 3. Validate observation_ref
        if not isinstance(self.observation_ref, str) or not self.observation_ref.strip():
            raise ValueError(f"observation_ref must be a non-empty string, got {self.observation_ref!r}.")

        # 4. Validate prediction_ref
        if not isinstance(self.prediction_ref, str) or not self.prediction_ref.strip():
            raise ValueError(f"prediction_ref must be a non-empty string, got {self.prediction_ref!r}.")

        # 5. Validate residual_summary
        if not isinstance(self.residual_summary, str) or not self.residual_summary.strip():
            raise ValueError(f"residual_summary must be a non-empty string, got {self.residual_summary!r}.")

        # 6. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # 7. Validate scope
        if not isinstance(self.scope, Mapping):
            raise ValueError(f"scope must be a Mapping, got {type(self.scope)!r}.")

        # Canonicalize string attributes
        object.__setattr__(self, "residual_id", self.residual_id.strip())
        object.__setattr__(self, "model_id", self.model_id.strip())
        object.__setattr__(self, "observation_ref", self.observation_ref.strip())
        object.__setattr__(self, "prediction_ref", self.prediction_ref.strip())
        object.__setattr__(self, "residual_summary", self.residual_summary.strip())
        object.__setattr__(self, "provenance", self.provenance.strip())
        # Store scope as an immutable dict copy
        object.__setattr__(self, "scope", dict(self.scope))

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic conversion to JSON-serializable dictionary."""
        return {
            "residual_id": self.residual_id,
            "model_id": self.model_id,
            "observation_ref": self.observation_ref,
            "prediction_ref": self.prediction_ref,
            "residual_summary": self.residual_summary,
            "scope": dict(self.scope),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelResidual:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected mapping, got {type(data)!r}.")
        return cls(
            residual_id=data.get("residual_id", ""),
            model_id=data.get("model_id", ""),
            observation_ref=data.get("observation_ref", ""),
            prediction_ref=data.get("prediction_ref", ""),
            residual_summary=data.get("residual_summary", ""),
            scope=data.get("scope", {}),
            provenance=data.get("provenance", ""),
        )


# ==============================================================================
# 2. Residual Assessment Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class ResidualAssessment:
    """Immutable structured assessment of residual characteristics providing candidate hypotheses.

    An assessment records candidate explanatory classes, references to evidence, proposed tests
    that could discriminate between candidates, whether the residual is unresolved, and the diagnostic rationale.
    It is an assessment, not a truth claim or falsification event.
    """
    residual_id: str
    candidate_classes: tuple[ResidualClassificationType, ...]
    evidence_refs: tuple[str, ...]
    proposed_tests: tuple[str, ...]
    unresolved: bool
    rationale: str

    def __post_init__(self) -> None:
        # 1. Validate residual_id
        if not isinstance(self.residual_id, str) or not self.residual_id.strip():
            raise ValueError(f"residual_id must be a non-empty string, got {self.residual_id!r}.")

        # 2. Validate candidate_classes
        if not isinstance(self.candidate_classes, (tuple, list)):
            raise ValueError(f"candidate_classes must be a tuple or list, got {type(self.candidate_classes)!r}.")

        validated_classes: list[ResidualClassificationType] = []
        for idx, cls_item in enumerate(self.candidate_classes):
            if isinstance(cls_item, ResidualClassificationType):
                validated_classes.append(cls_item)
            elif isinstance(cls_item, str):
                try:
                    validated_classes.append(ResidualClassificationType(cls_item))
                except ValueError as err:
                    raise ValueError(f"Unsupported ResidualClassificationType at index {idx}: {cls_item!r}.") from err
            else:
                raise ValueError(f"candidate_classes[{idx}] must be ResidualClassificationType or str, got {type(cls_item)!r}.")

        # 3. Validate evidence_refs
        if not isinstance(self.evidence_refs, (tuple, list)):
            raise ValueError(f"evidence_refs must be a tuple or list of strings, got {type(self.evidence_refs)!r}.")

        validated_ev_refs: list[str] = []
        for idx, ev_ref in enumerate(self.evidence_refs):
            if not isinstance(ev_ref, str) or not ev_ref.strip():
                raise ValueError(f"evidence_refs[{idx}] must be a non-empty string, got {ev_ref!r}.")
            validated_ev_refs.append(ev_ref.strip())

        # 4. Validate proposed_tests
        if not isinstance(self.proposed_tests, (tuple, list)):
            raise ValueError(f"proposed_tests must be a tuple or list of strings, got {type(self.proposed_tests)!r}.")

        validated_tests: list[str] = []
        for idx, t_item in enumerate(self.proposed_tests):
            if not isinstance(t_item, str) or not t_item.strip():
                raise ValueError(f"proposed_tests[{idx}] must be a non-empty string, got {t_item!r}.")
            validated_tests.append(t_item.strip())

        # 5. Validate unresolved
        if not isinstance(self.unresolved, bool):
            raise ValueError(f"unresolved must be a boolean, got {type(self.unresolved)!r}.")

        # 6. Validate rationale
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError(f"rationale must be a non-empty string, got {self.rationale!r}.")

        # Canonicalize string attributes
        object.__setattr__(self, "residual_id", self.residual_id.strip())
        object.__setattr__(self, "candidate_classes", tuple(validated_classes))
        object.__setattr__(self, "evidence_refs", tuple(validated_ev_refs))
        object.__setattr__(self, "proposed_tests", tuple(validated_tests))
        object.__setattr__(self, "unresolved", bool(self.unresolved))
        object.__setattr__(self, "rationale", self.rationale.strip())

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic conversion to JSON-serializable dictionary."""
        return {
            "residual_id": self.residual_id,
            "candidate_classes": [c.value for c in self.candidate_classes],
            "evidence_refs": list(self.evidence_refs),
            "proposed_tests": list(self.proposed_tests),
            "unresolved": self.unresolved,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResidualAssessment:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected mapping, got {type(data)!r}.")

        raw_classes = data.get("candidate_classes", ())
        parsed_classes = tuple(ResidualClassificationType(c) for c in raw_classes)

        return cls(
            residual_id=data.get("residual_id", ""),
            candidate_classes=parsed_classes,
            evidence_refs=tuple(data.get("evidence_refs", ())),
            proposed_tests=tuple(data.get("proposed_tests", ())),
            unresolved=bool(data.get("unresolved", True)),
            rationale=data.get("rationale", ""),
        )


# ==============================================================================
# 3. Residual Registry Container
# ==============================================================================

class ResidualRegistry:
    """Deterministic, auditable in-memory registry for ModelResidual and ResidualAssessment objects.

    Provides strict identity protection (no silent replacement on duplicate IDs),
    deterministic enumeration, and query filtering without global singleton state.
    """

    def __init__(self) -> None:
        self._residuals: dict[str, ModelResidual] = {}
        self._assessments: dict[str, ResidualAssessment] = {}

    def register_residual(self, residual: ModelResidual) -> None:
        """Register a ModelResidual in the registry.

        Args:
            residual: A ModelResidual instance.

        Raises:
            ValueError: If a residual with the same residual_id is already registered,
                or if input is not a ModelResidual.
        """
        if not isinstance(residual, ModelResidual):
            raise ValueError(f"Expected ModelResidual instance, got {type(residual)!r}.")

        if residual.residual_id in self._residuals:
            raise ValueError(
                f"ModelResidual '{residual.residual_id}' is already registered in this registry. "
                "Duplicate registration is rejected to prevent silent overwrite."
            )

        self._residuals[residual.residual_id] = residual

    def get_residual(self, residual_id: str) -> ModelResidual:
        """Retrieve a ModelResidual by its unique identity.

        Args:
            residual_id: Unique string identifier.

        Returns:
            The registered ModelResidual instance.

        Raises:
            KeyError: If residual_id is not found in the registry.
        """
        if not isinstance(residual_id, str):
            raise KeyError(f"residual_id must be a string, got {type(residual_id)!r}.")

        clean_id = residual_id.strip()
        if clean_id not in self._residuals:
            raise KeyError(f"ModelResidual '{clean_id}' not found in registry.")

        return self._residuals[clean_id]

    def contains_residual(self, residual_id: str) -> bool:
        """Check whether a residual ID is registered."""
        if not isinstance(residual_id, str):
            return False
        return residual_id.strip() in self._residuals

    def all_residuals(self) -> tuple[ModelResidual, ...]:
        """Return all registered residuals as an immutable tuple in deterministic registration order."""
        return tuple(self._residuals.values())

    def register_assessment(self, assessment: ResidualAssessment) -> None:
        """Register a ResidualAssessment in the registry.

        Args:
            assessment: A ResidualAssessment instance.

        Raises:
            ValueError: If an assessment with the same residual_id is already registered,
                or if input is not a ResidualAssessment.
        """
        if not isinstance(assessment, ResidualAssessment):
            raise ValueError(f"Expected ResidualAssessment instance, got {type(assessment)!r}.")

        if assessment.residual_id in self._assessments:
            raise ValueError(
                f"ResidualAssessment for residual '{assessment.residual_id}' is already registered. "
                "Duplicate registration is rejected to prevent silent overwrite."
            )

        self._assessments[assessment.residual_id] = assessment

    def get_assessment(self, residual_id: str) -> ResidualAssessment:
        """Retrieve a ResidualAssessment by residual identity.

        Args:
            residual_id: Unique string identifier.

        Returns:
            The registered ResidualAssessment instance.

        Raises:
            KeyError: If residual_id is not found in the assessment registry.
        """
        if not isinstance(residual_id, str):
            raise KeyError(f"residual_id must be a string, got {type(residual_id)!r}.")

        clean_id = residual_id.strip()
        if clean_id not in self._assessments:
            raise KeyError(f"ResidualAssessment for '{clean_id}' not found in registry.")

        return self._assessments[clean_id]

    def contains_assessment(self, residual_id: str) -> bool:
        """Check whether an assessment for a residual ID is registered."""
        if not isinstance(residual_id, str):
            return False
        return residual_id.strip() in self._assessments

    def all_assessments(self) -> tuple[ResidualAssessment, ...]:
        """Return all registered assessments as an immutable tuple in deterministic registration order."""
        return tuple(self._assessments.values())

    def clear(self) -> None:
        """Clear all residuals and assessments from the registry instance."""
        self._residuals.clear()
        self._assessments.clear()

    def __len__(self) -> int:
        return len(self._residuals)

    def __iter__(self) -> Iterator[ModelResidual]:
        return iter(self._residuals.values())
