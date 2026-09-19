"""AcoustiForge Epistemic Representation Definition and Challenge Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E9: Representation Challenge
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Failure of representation is NOT evidence of physical impossibility (NOT_REPRESENTABLE != PHYSICALLY_IMPOSSIBLE)
  - Representation Gap != UNKNOWN != MODEL_ERROR != PHYSICALLY_IMPOSSIBLE != FALSIFIED
  - Representation != Model != Objective != Measurement != Optimization
  - Represented variables and omitted variables remain explicitly inspectable
  - No universal RepresentationWinner, representation adequacy score, or truth score
  - Multi-representation comparison preserves dimension separation without declaring a winner
  - Production Core and domain models remain completely untouched
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence

from .vocabulary import (
    EpistemicStatus,
)


# ==============================================================================
# 1. Representation Definition Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class RepresentationDefinition:
    """Immutable first-class epistemic representation of a conceptual or mathematical abstraction.

    Records what phenomenon the representation describes, what variables are explicitly represented,
    what variables are omitted, internal relationships, underlying assumptions, scope, and provenance.
    """
    representation_id: str
    name: str
    description: str
    represented_phenomenon: str
    provenance: str
    represented_variables: tuple[str, ...] = ()
    omitted_variables: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    scope: Optional[Mapping[str, Any]] = None
    status: EpistemicStatus = EpistemicStatus.VALIDATED_MODEL

    def __post_init__(self) -> None:
        # 1. Validate required non-empty string fields
        for field_name in ("representation_id", "name", "description", "represented_phenomenon", "provenance"):
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

        # 4. Validate sequence tuples
        for field_name in ("represented_variables", "omitted_variables", "relationships", "assumptions"):
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
        """Convert RepresentationDefinition to a serializable dictionary."""
        return {
            "representation_id": self.representation_id,
            "name": self.name,
            "description": self.description,
            "represented_phenomenon": self.represented_phenomenon,
            "represented_variables": list(self.represented_variables),
            "omitted_variables": list(self.omitted_variables),
            "relationships": list(self.relationships),
            "assumptions": list(self.assumptions),
            "scope": dict(self.scope),
            "provenance": self.provenance,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepresentationDefinition:
        """Create a RepresentationDefinition from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "representation_id",
            "name",
            "description",
            "represented_phenomenon",
            "represented_variables",
            "omitted_variables",
            "relationships",
            "assumptions",
            "scope",
            "provenance",
            "status",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        raw_status = data["status"]
        status = EpistemicStatus(raw_status) if isinstance(raw_status, str) else raw_status

        return cls(
            representation_id=data["representation_id"],
            name=data["name"],
            description=data["description"],
            represented_phenomenon=data["represented_phenomenon"],
            represented_variables=tuple(data["represented_variables"]),
            omitted_variables=tuple(data["omitted_variables"]),
            relationships=tuple(data["relationships"]),
            assumptions=tuple(data["assumptions"]),
            scope=data["scope"],
            provenance=data["provenance"],
            status=status,
        )


# ==============================================================================
# 2. Representation Gap Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class RepresentationGap:
    """Immutable record representing a gap where an observed phenomenon cannot be expressed by the current representation.

    Declaring a representation gap explicitly documents an expressive limitation of the abstraction;
    it does NOT declare the phenomenon physically impossible or fictitious.
    """
    gap_id: str
    representation_id: str
    observation_ref: str
    phenomenon_description: str
    missing_capability: str
    provenance: str
    affected_variables: tuple[str, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    scope: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        for field_name in (
            "gap_id",
            "representation_id",
            "observation_ref",
            "phenomenon_description",
            "missing_capability",
            "provenance",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        if self.scope is None:
            object.__setattr__(self, "scope", {})
        elif isinstance(self.scope, Mapping):
            object.__setattr__(self, "scope", dict(self.scope))
        else:
            raise ValueError(f"scope must be a Mapping or None, got {type(self.scope)!r}.")

        for field_name in ("affected_variables", "alternative_explanations", "evidence_refs"):
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
        """Convert RepresentationGap to a serializable dictionary."""
        return {
            "gap_id": self.gap_id,
            "representation_id": self.representation_id,
            "observation_ref": self.observation_ref,
            "phenomenon_description": self.phenomenon_description,
            "missing_capability": self.missing_capability,
            "affected_variables": list(self.affected_variables),
            "alternative_explanations": list(self.alternative_explanations),
            "evidence_refs": list(self.evidence_refs),
            "scope": dict(self.scope),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepresentationGap:
        """Create a RepresentationGap from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "gap_id",
            "representation_id",
            "observation_ref",
            "phenomenon_description",
            "missing_capability",
            "affected_variables",
            "alternative_explanations",
            "evidence_refs",
            "scope",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            gap_id=data["gap_id"],
            representation_id=data["representation_id"],
            observation_ref=data["observation_ref"],
            phenomenon_description=data["phenomenon_description"],
            missing_capability=data["missing_capability"],
            affected_variables=tuple(data["affected_variables"]),
            alternative_explanations=tuple(data["alternative_explanations"]),
            evidence_refs=tuple(data["evidence_refs"]),
            scope=data["scope"],
            provenance=data["provenance"],
        )


# ==============================================================================
# 3. Representation Challenge Assessment Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class RepresentationChallengeAssessment:
    """Immutable audit record representing a structured assessment of a representation challenge.

    Records why a chosen representation is challenged, what variables/gaps are affected,
    and what alternative explanations and discriminating tests are proposed.
    """
    assessment_id: str
    challenge_id: str
    representation_id: str
    rationale: str
    provenance: str
    evidence_refs: tuple[str, ...] = ()
    affected_variables: tuple[str, ...] = ()
    representation_gap_refs: tuple[str, ...] = ()
    alternative_explanations: tuple[str, ...] = ()
    proposed_tests: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("assessment_id", "challenge_id", "representation_id", "rationale", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        for field_name in (
            "evidence_refs",
            "affected_variables",
            "representation_gap_refs",
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
        """Convert RepresentationChallengeAssessment to a serializable dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "challenge_id": self.challenge_id,
            "representation_id": self.representation_id,
            "evidence_refs": list(self.evidence_refs),
            "affected_variables": list(self.affected_variables),
            "representation_gap_refs": list(self.representation_gap_refs),
            "alternative_explanations": list(self.alternative_explanations),
            "proposed_tests": list(self.proposed_tests),
            "unresolved_items": list(self.unresolved_items),
            "rationale": self.rationale,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepresentationChallengeAssessment:
        """Create a RepresentationChallengeAssessment from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "assessment_id",
            "challenge_id",
            "representation_id",
            "evidence_refs",
            "affected_variables",
            "representation_gap_refs",
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
            representation_id=data["representation_id"],
            evidence_refs=tuple(data["evidence_refs"]),
            affected_variables=tuple(data["affected_variables"]),
            representation_gap_refs=tuple(data["representation_gap_refs"]),
            alternative_explanations=tuple(data["alternative_explanations"]),
            proposed_tests=tuple(data["proposed_tests"]),
            unresolved_items=tuple(data["unresolved_items"]),
            rationale=data["rationale"],
            provenance=data["provenance"],
        )


# ==============================================================================
# 4. Representation Comparison Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class RepresentationComparison:
    """Immutable record comparing multiple representations across explicit dimensions without declaring a winner."""
    comparison_id: str
    representation_ids: tuple[str, ...]
    observation_refs: tuple[str, ...]
    dimensions: tuple[str, ...]
    findings: tuple[Mapping[str, Any], ...]
    provenance: str
    incomparable_dimensions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("comparison_id", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        for seq_name, min_len in (("representation_ids", 2), ("observation_refs", 0), ("dimensions", 1)):
            val = getattr(self, seq_name)
            if isinstance(val, (str, bytes)):
                raise ValueError(f"{seq_name} must be a sequence of strings, not a single string.")
            try:
                seq_tuple = tuple(val)
            except TypeError as exc:
                raise ValueError(f"{seq_name} must be iterable, got {type(val)!r}.") from exc
            if len(seq_tuple) < min_len:
                raise ValueError(f"{seq_name} must contain at least {min_len} items, got {len(seq_tuple)}.")
            for idx, item in enumerate(seq_tuple):
                if not isinstance(item, str) or not item.strip():
                    raise ValueError(f"{seq_name} at index {idx} must be a non-empty string, got {item!r}.")
            object.__setattr__(self, seq_name, seq_tuple)

        for field_name in ("incomparable_dimensions", "limitations"):
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

        if isinstance(self.findings, (str, bytes)):
            raise ValueError("findings must be a sequence of mappings.")
        try:
            f_tuple = tuple(self.findings)
        except TypeError as exc:
            raise ValueError(f"findings must be iterable, got {type(self.findings)!r}.") from exc
        for idx, item in enumerate(f_tuple):
            if not isinstance(item, Mapping):
                raise ValueError(f"findings item at index {idx} must be a Mapping, got {type(item)!r}.")
        object.__setattr__(self, "findings", tuple(dict(m) for m in f_tuple))

    def to_dict(self) -> dict[str, Any]:
        """Convert RepresentationComparison to a serializable dictionary."""
        return {
            "comparison_id": self.comparison_id,
            "representation_ids": list(self.representation_ids),
            "observation_refs": list(self.observation_refs),
            "dimensions": list(self.dimensions),
            "findings": [dict(m) for m in self.findings],
            "incomparable_dimensions": list(self.incomparable_dimensions),
            "limitations": list(self.limitations),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepresentationComparison:
        """Create a RepresentationComparison from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "comparison_id",
            "representation_ids",
            "observation_refs",
            "dimensions",
            "findings",
            "incomparable_dimensions",
            "limitations",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            comparison_id=data["comparison_id"],
            representation_ids=tuple(data["representation_ids"]),
            observation_refs=tuple(data["observation_refs"]),
            dimensions=tuple(data["dimensions"]),
            findings=tuple(data["findings"]),
            incomparable_dimensions=tuple(data["incomparable_dimensions"]),
            limitations=tuple(data["limitations"]),
            provenance=data["provenance"],
        )


# ==============================================================================
# 5. Representation Registry
# ==============================================================================

class RepresentationRegistry:
    """Deterministic in-memory registry for representation definitions, gaps, assessments, and comparisons."""

    def __init__(self) -> None:
        self._definitions: dict[str, RepresentationDefinition] = {}
        self._gaps: dict[str, RepresentationGap] = {}
        self._assessments: dict[str, RepresentationChallengeAssessment] = {}
        self._comparisons: dict[str, RepresentationComparison] = {}

    def register(self, definition: RepresentationDefinition) -> None:
        """Register a RepresentationDefinition with duplicate protection."""
        if not isinstance(definition, RepresentationDefinition):
            raise ValueError(f"definition must be a RepresentationDefinition instance, got {type(definition)!r}.")
        rid = definition.representation_id
        if rid in self._definitions:
            raise ValueError(f"RepresentationDefinition with ID '{rid}' already registered.")
        self._definitions[rid] = definition

    def get(self, representation_id: str) -> RepresentationDefinition:
        """Retrieve a RepresentationDefinition by ID or raise KeyError."""
        if representation_id not in self._definitions:
            raise KeyError(f"RepresentationDefinition with ID '{representation_id}' not found.")
        return self._definitions[representation_id]

    def contains(self, representation_id: str) -> bool:
        """Check if a representation ID is registered."""
        return representation_id in self._definitions

    def all(self) -> tuple[RepresentationDefinition, ...]:
        """Return all registered representation definitions in deterministic insertion order."""
        return tuple(self._definitions.values())

    def all_definitions(self) -> tuple[RepresentationDefinition, ...]:
        """Alias for all()."""
        return self.all()

    def register_gap(self, gap: RepresentationGap) -> None:
        """Register a RepresentationGap with duplicate protection."""
        if not isinstance(gap, RepresentationGap):
            raise ValueError(f"gap must be a RepresentationGap instance, got {type(gap)!r}.")
        gid = gap.gap_id
        if gid in self._gaps:
            raise ValueError(f"RepresentationGap with ID '{gid}' already registered.")
        self._gaps[gid] = gap

    def get_gap(self, gap_id: str) -> RepresentationGap:
        """Retrieve a RepresentationGap by ID or raise KeyError."""
        if gap_id not in self._gaps:
            raise KeyError(f"RepresentationGap with ID '{gap_id}' not found.")
        return self._gaps[gap_id]

    def all_gaps(self) -> tuple[RepresentationGap, ...]:
        """Return all registered representation gaps in deterministic insertion order."""
        return tuple(self._gaps.values())

    def register_assessment(self, assessment: RepresentationChallengeAssessment) -> None:
        """Register a RepresentationChallengeAssessment with duplicate protection."""
        if not isinstance(assessment, RepresentationChallengeAssessment):
            raise ValueError(f"assessment must be a RepresentationChallengeAssessment instance, got {type(assessment)!r}.")
        aid = assessment.assessment_id
        if aid in self._assessments:
            raise ValueError(f"RepresentationChallengeAssessment with ID '{aid}' already registered.")
        self._assessments[aid] = assessment

    def get_assessment(self, assessment_id: str) -> RepresentationChallengeAssessment:
        """Retrieve a RepresentationChallengeAssessment by ID or raise KeyError."""
        if assessment_id not in self._assessments:
            raise KeyError(f"RepresentationChallengeAssessment with ID '{assessment_id}' not found.")
        return self._assessments[assessment_id]

    def all_assessments(self) -> tuple[RepresentationChallengeAssessment, ...]:
        """Return all registered challenge assessments in deterministic insertion order."""
        return tuple(self._assessments.values())

    def register_comparison(self, comparison: RepresentationComparison) -> None:
        """Register a RepresentationComparison with duplicate protection."""
        if not isinstance(comparison, RepresentationComparison):
            raise ValueError(f"comparison must be a RepresentationComparison instance, got {type(comparison)!r}.")
        cid = comparison.comparison_id
        if cid in self._comparisons:
            raise ValueError(f"RepresentationComparison with ID '{cid}' already registered.")
        self._comparisons[cid] = comparison

    def get_comparison(self, comparison_id: str) -> RepresentationComparison:
        """Retrieve a RepresentationComparison by ID or raise KeyError."""
        if comparison_id not in self._comparisons:
            raise KeyError(f"RepresentationComparison with ID '{comparison_id}' not found.")
        return self._comparisons[comparison_id]

    def all_comparisons(self) -> tuple[RepresentationComparison, ...]:
        """Return all registered representation comparisons in deterministic insertion order."""
        return tuple(self._comparisons.values())

    def query(self, *, status: Optional[EpistemicStatus] = None) -> tuple[RepresentationDefinition, ...]:
        """Filter registered representations by exact matching without semantic inference."""
        results: list[RepresentationDefinition] = []
        for defn in self._definitions.values():
            if status is not None and defn.status != status:
                continue
            results.append(defn)
        return tuple(results)

    def __len__(self) -> int:
        return len(self._definitions)

    def __iter__(self) -> Iterator[RepresentationDefinition]:
        return iter(self._definitions.values())

    def __contains__(self, representation_id: str) -> bool:
        return representation_id in self._definitions
