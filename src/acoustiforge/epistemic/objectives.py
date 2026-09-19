"""AcoustiForge Epistemic Objective Representation and Challenge Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E8: Objective Challenge
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - An objective can be challenged without silently redefining production intent or optimizer behavior
  - Poor optimization result != Bad objective != Bad model != Bad measurement
  - Objective terms, assumptions, scope, and constraints remain explicitly separated and inspectable
  - No universal ObjectiveWinner, objective truth score, or composite adequacy score
  - Multi-objective comparison preserves dimension separation without declaring a winner
  - Production Core and optimizer remain completely untouched
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence

from .vocabulary import (
    ChallengeStatus,
    EpistemicStatus,
)


# ==============================================================================
# 1. Epistemic Objective Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class EpistemicObjective:
    """Immutable first-class epistemic representation of an optimization objective.

    Distinguishes the mathematical expression, individual terms, underlying assumptions,
    applicable scope, hard constraints, provenance, and epistemic status.
    """
    objective_id: str
    name: str
    description: str
    expression: str
    provenance: str
    terms: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    scope: Optional[Mapping[str, Any]] = None
    constraints: tuple[str, ...] = ()
    status: EpistemicStatus = EpistemicStatus.VALIDATED_MODEL

    def __post_init__(self) -> None:
        # 1. Validate required non-empty string fields
        for field_name in ("objective_id", "name", "description", "expression", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        # 2. Validate status
        if not isinstance(self.status, EpistemicStatus):
            raise ValueError(f"status must be an instance of EpistemicStatus, got {type(self.status)!r}.")

        # 3. Validate scope
        if self.scope is None:
            object.__setattr__(self, "scope", {})
        elif isinstance(self.scope, Mapping):
            object.__setattr__(self, "scope", dict(self.scope))
        else:
            raise ValueError(f"scope must be a Mapping or None, got {type(self.scope)!r}.")

        # 4. Validate sequence tuples (terms, assumptions, constraints)
        for field_name in ("terms", "assumptions", "constraints"):
            val = getattr(self, field_name)
            if isinstance(val, (str, bytes)):
                raise ValueError(f"{field_name} must be a sequence of strings, not a single string.")
            try:
                seq_tuple = tuple(val)
            except TypeError as exc:
                raise ValueError(f"{field_name} must be iterable, got {type(val)!r}.") from exc
            for idx, item in enumerate(seq_tuple):
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"{field_name} at index {idx} must be a non-empty string, got {item!r}.")
            object.__setattr__(self, field_name, seq_tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert EpistemicObjective to a serializable dictionary."""
        return {
            "objective_id": self.objective_id,
            "name": self.name,
            "description": self.description,
            "expression": self.expression,
            "terms": list(self.terms),
            "assumptions": list(self.assumptions),
            "scope": dict(self.scope),
            "constraints": list(self.constraints),
            "provenance": self.provenance,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpistemicObjective:
        """Create an EpistemicObjective from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "objective_id",
            "name",
            "description",
            "expression",
            "terms",
            "assumptions",
            "scope",
            "constraints",
            "provenance",
            "status",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        raw_status = data["status"]
        status = EpistemicStatus(raw_status) if isinstance(raw_status, str) else raw_status

        return cls(
            objective_id=data["objective_id"],
            name=data["name"],
            description=data["description"],
            expression=data["expression"],
            terms=tuple(data["terms"]),
            assumptions=tuple(data["assumptions"]),
            scope=data["scope"],
            constraints=tuple(data["constraints"]),
            provenance=data["provenance"],
            status=status,
        )


# ==============================================================================
# 2. Objective Challenge Assessment Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class ObjectiveChallengeAssessment:
    """Immutable audit record representing a structured assessment of an objective challenge.

    Records why an objective formulation may fail to represent the intended scientific or engineering goal,
    which terms/scope are affected, and what alternative explanations or tests exist.
    """
    assessment_id: str
    challenge_id: str
    objective_id: str
    rationale: str
    provenance: str
    evidence_refs: tuple[str, ...] = ()
    affected_terms: tuple[str, ...] = ()
    affected_scope: Optional[Mapping[str, Any]] = None
    observations: tuple[str, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    proposed_tests: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("assessment_id", "challenge_id", "objective_id", "rationale", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        if self.affected_scope is None:
            object.__setattr__(self, "affected_scope", {})
        elif isinstance(self.affected_scope, Mapping):
            object.__setattr__(self, "affected_scope", dict(self.affected_scope))
        else:
            raise ValueError(f"affected_scope must be a Mapping or None, got {type(self.affected_scope)!r}.")

        for field_name in (
            "evidence_refs",
            "affected_terms",
            "observations",
            "alternative_explanations",
            "proposed_tests",
            "unresolved_items",
        ):
            val = getattr(self, field_name)
            if isinstance(val, (str, bytes)):
                raise ValueError(f"{field_name} must be a sequence of strings, not a single string.")
            try:
                seq_tuple = tuple(val)
            except TypeError as exc:
                raise ValueError(f"{field_name} must be iterable, got {type(val)!r}.") from exc
            for idx, item in enumerate(seq_tuple):
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"{field_name} at index {idx} must be a non-empty string, got {item!r}.")
            object.__setattr__(self, field_name, seq_tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert ObjectiveChallengeAssessment to a serializable dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "challenge_id": self.challenge_id,
            "objective_id": self.objective_id,
            "evidence_refs": list(self.evidence_refs),
            "affected_terms": list(self.affected_terms),
            "affected_scope": dict(self.affected_scope),
            "observations": list(self.observations),
            "alternative_explanations": list(self.alternative_explanations),
            "proposed_tests": list(self.proposed_tests),
            "unresolved_items": list(self.unresolved_items),
            "rationale": self.rationale,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ObjectiveChallengeAssessment:
        """Create an ObjectiveChallengeAssessment from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "assessment_id",
            "challenge_id",
            "objective_id",
            "evidence_refs",
            "affected_terms",
            "affected_scope",
            "observations",
            "alternative_explanations",
            "proposed_tests",
            "unresolved_items",
            "rationale",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            assessment_id=data["assessment_id"],
            challenge_id=data["challenge_id"],
            objective_id=data["objective_id"],
            evidence_refs=tuple(data["evidence_refs"]),
            affected_terms=tuple(data["affected_terms"]),
            affected_scope=data["affected_scope"],
            observations=tuple(data["observations"]),
            alternative_explanations=tuple(data["alternative_explanations"]),
            proposed_tests=tuple(data["proposed_tests"]),
            unresolved_items=tuple(data["unresolved_items"]),
            rationale=data["rationale"],
            provenance=data["provenance"],
        )


# ==============================================================================
# 3. Objective Comparison Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class ObjectiveComparison:
    """Immutable record comparing multiple objective formulations across explicit dimensions.

    Maintains dimension separation (coverage, measurability, robustness, tradeoffs) without declaring a winner.
    """
    comparison_id: str
    objective_ids: tuple[str, ...]
    comparison_dimensions: tuple[str, ...]
    dimension_findings: tuple[Mapping[str, Any], ...]
    provenance: str
    incomparable_dimensions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("comparison_id", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        if isinstance(self.objective_ids, (str, bytes)):
            raise ValueError("objective_ids must be a sequence of objective IDs, not a single string.")
        try:
            o_tuple = tuple(self.objective_ids)
        except TypeError as exc:
            raise ValueError(f"objective_ids must be iterable, got {type(self.objective_ids)!r}.") from exc
        if len(o_tuple) < 2:
            raise ValueError(f"objective_ids must contain at least 2 objectives to compare, got {len(o_tuple)}.")
        for idx, item in enumerate(o_tuple):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"objective_ids at index {idx} must be a non-empty string, got {item!r}.")
        object.__setattr__(self, "objective_ids", o_tuple)

        for field_name in ("comparison_dimensions", "incomparable_dimensions", "limitations"):
            val = getattr(self, field_name)
            if isinstance(val, (str, bytes)):
                raise ValueError(f"{field_name} must be a sequence of strings, not a single string.")
            try:
                seq_tuple = tuple(val)
            except TypeError as exc:
                raise ValueError(f"{field_name} must be iterable, got {type(val)!r}.") from exc
            for idx, item in enumerate(seq_tuple):
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"{field_name} at index {idx} must be a non-empty string, got {item!r}.")
            object.__setattr__(self, field_name, seq_tuple)

        if isinstance(self.dimension_findings, (str, bytes)):
            raise ValueError("dimension_findings must be a sequence of mappings.")
        try:
            df_tuple = tuple(self.dimension_findings)
        except TypeError as exc:
            raise ValueError(f"dimension_findings must be iterable, got {type(self.dimension_findings)!r}.") from exc
        for idx, item in enumerate(df_tuple):
            if not isinstance(item, Mapping):
                raise ValueError(f"dimension_findings item at index {idx} must be a Mapping, got {type(item)!r}.")
        object.__setattr__(self, "dimension_findings", tuple(dict(m) for m in df_tuple))

    def to_dict(self) -> dict[str, Any]:
        """Convert ObjectiveComparison to a serializable dictionary."""
        return {
            "comparison_id": self.comparison_id,
            "objective_ids": list(self.objective_ids),
            "comparison_dimensions": list(self.comparison_dimensions),
            "dimension_findings": [dict(m) for m in self.dimension_findings],
            "incomparable_dimensions": list(self.incomparable_dimensions),
            "limitations": list(self.limitations),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ObjectiveComparison:
        """Create an ObjectiveComparison from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "comparison_id",
            "objective_ids",
            "comparison_dimensions",
            "dimension_findings",
            "incomparable_dimensions",
            "limitations",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            comparison_id=data["comparison_id"],
            objective_ids=tuple(data["objective_ids"]),
            comparison_dimensions=tuple(data["comparison_dimensions"]),
            dimension_findings=tuple(data["dimension_findings"]),
            incomparable_dimensions=tuple(data["incomparable_dimensions"]),
            limitations=tuple(data["limitations"]),
            provenance=data["provenance"],
        )


# ==============================================================================
# 4. Objective Registry
# ==============================================================================

class ObjectiveRegistry:
    """Deterministic in-memory registry for epistemic objectives, challenge assessments, and comparisons."""

    def __init__(self) -> None:
        self._objectives: dict[str, EpistemicObjective] = {}
        self._assessments: dict[str, ObjectiveChallengeAssessment] = {}
        self._comparisons: dict[str, ObjectiveComparison] = {}

    def register(self, objective: EpistemicObjective) -> None:
        """Register an EpistemicObjective with duplicate protection."""
        if not isinstance(objective, EpistemicObjective):
            raise ValueError(f"objective must be an EpistemicObjective instance, got {type(objective)!r}.")
        oid = objective.objective_id
        if oid in self._objectives:
            raise ValueError(f"Objective with ID '{oid}' already registered.")
        self._objectives[oid] = objective

    def get(self, objective_id: str) -> EpistemicObjective:
        """Retrieve an EpistemicObjective by ID or raise KeyError."""
        if objective_id not in self._objectives:
            raise KeyError(f"Objective with ID '{objective_id}' not found.")
        return self._objectives[objective_id]

    def contains(self, objective_id: str) -> bool:
        """Check if an objective ID is registered."""
        return objective_id in self._objectives

    def all(self) -> tuple[EpistemicObjective, ...]:
        """Return all registered objectives in deterministic insertion order."""
        return tuple(self._objectives.values())

    def all_objectives(self) -> tuple[EpistemicObjective, ...]:
        """Alias for all()."""
        return self.all()

    def register_assessment(self, assessment: ObjectiveChallengeAssessment) -> None:
        """Register an ObjectiveChallengeAssessment with duplicate protection."""
        if not isinstance(assessment, ObjectiveChallengeAssessment):
            raise ValueError(f"assessment must be an ObjectiveChallengeAssessment instance, got {type(assessment)!r}.")
        aid = assessment.assessment_id
        if aid in self._assessments:
            raise ValueError(f"ObjectiveChallengeAssessment with ID '{aid}' already registered.")
        self._assessments[aid] = assessment

    def get_assessment(self, assessment_id: str) -> ObjectiveChallengeAssessment:
        """Retrieve an ObjectiveChallengeAssessment by ID or raise KeyError."""
        if assessment_id not in self._assessments:
            raise KeyError(f"ObjectiveChallengeAssessment with ID '{assessment_id}' not found.")
        return self._assessments[assessment_id]

    def all_assessments(self) -> tuple[ObjectiveChallengeAssessment, ...]:
        """Return all registered challenge assessments in deterministic insertion order."""
        return tuple(self._assessments.values())

    def register_comparison(self, comparison: ObjectiveComparison) -> None:
        """Register an ObjectiveComparison with duplicate protection."""
        if not isinstance(comparison, ObjectiveComparison):
            raise ValueError(f"comparison must be an ObjectiveComparison instance, got {type(comparison)!r}.")
        cid = comparison.comparison_id
        if cid in self._comparisons:
            raise ValueError(f"ObjectiveComparison with ID '{cid}' already registered.")
        self._comparisons[cid] = comparison

    def get_comparison(self, comparison_id: str) -> ObjectiveComparison:
        """Retrieve an ObjectiveComparison by ID or raise KeyError."""
        if comparison_id not in self._comparisons:
            raise KeyError(f"ObjectiveComparison with ID '{comparison_id}' not found.")
        return self._comparisons[comparison_id]

    def all_comparisons(self) -> tuple[ObjectiveComparison, ...]:
        """Return all registered objective comparisons in deterministic insertion order."""
        return tuple(self._comparisons.values())

    def query(self, *, status: Optional[EpistemicStatus] = None) -> tuple[EpistemicObjective, ...]:
        """Filter registered objectives by exact matching without semantic inference."""
        results: list[EpistemicObjective] = []
        for obj in self._objectives.values():
            if status is not None and obj.status != status:
                continue
            results.append(obj)
        return tuple(results)

    def __len__(self) -> int:
        return len(self._objectives)

    def __iter__(self) -> Iterator[EpistemicObjective]:
        return iter(self._objectives.values())

    def __contains__(self, objective_id: str) -> bool:
        return objective_id in self._objectives
