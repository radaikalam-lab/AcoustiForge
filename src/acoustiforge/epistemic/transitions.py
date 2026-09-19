"""AcoustiForge Epistemic Theory Transition and Integration Audit Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E10: Theory Transition & Integration
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Epistemic reasoning may discover, challenge, compare, and recommend.
  - Deterministic production Core remains authoritative.
  - Theory transition is an auditable record of reasoning, NOT an automatic model promotion engine.
  - PRODUCTION_CANDIDATE != PRODUCTION_AUTHORITY
  - EPISTEMIC_ACCEPTED != PRODUCTION_AUTHORITY
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence


# ==============================================================================
# 1. Theory Transition Record Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class TheoryTransitionRecord:
    """Immutable audit record representing a structured theory/model transition proposal.

    Preserves the full provenance chain from observation, representation gaps, residuals,
    challenges, candidate model evaluations, falsification reviews, and objective challenges.
    Does NOT confer production DSP authority or mutate the deterministic Core.
    """
    transition_id: str
    conclusion: str
    provenance: str
    source_model_id: Optional[str] = None
    candidate_model_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    challenge_refs: tuple[str, ...] = ()
    review_refs: tuple[str, ...] = ()
    objective_refs: tuple[str, ...] = ()
    representation_refs: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()
    scope: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        # 1. Validate required non-empty string fields
        for field_name in ("transition_id", "conclusion", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        # 2. Validate source_model_id
        if self.source_model_id is not None:
            if not isinstance(self.source_model_id, str) or not self.source_model_id.strip():
                raise ValueError(f"source_model_id must be a non-empty string or None, got {self.source_model_id!r}.")

        # 3. Validate scope
        if self.scope is None:
            object.__setattr__(self, "scope", {})
        elif isinstance(self.scope, Mapping):
            object.__setattr__(self, "scope", dict(self.scope))
        else:
            raise ValueError(f"scope must be a Mapping or None, got {type(self.scope)!r}.")

        # 4. Validate sequence tuples
        for field_name in (
            "candidate_model_ids",
            "evidence_refs",
            "challenge_refs",
            "review_refs",
            "objective_refs",
            "representation_refs",
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
        """Convert TheoryTransitionRecord to a serializable dictionary."""
        return {
            "transition_id": self.transition_id,
            "source_model_id": self.source_model_id,
            "candidate_model_ids": list(self.candidate_model_ids),
            "conclusion": self.conclusion,
            "provenance": self.provenance,
            "evidence_refs": list(self.evidence_refs),
            "challenge_refs": list(self.challenge_refs),
            "review_refs": list(self.review_refs),
            "objective_refs": list(self.objective_refs),
            "representation_refs": list(self.representation_refs),
            "unresolved_items": list(self.unresolved_items),
            "scope": dict(self.scope),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TheoryTransitionRecord:
        """Create a TheoryTransitionRecord from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "transition_id",
            "source_model_id",
            "candidate_model_ids",
            "conclusion",
            "provenance",
            "evidence_refs",
            "challenge_refs",
            "review_refs",
            "objective_refs",
            "representation_refs",
            "unresolved_items",
            "scope",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            transition_id=data["transition_id"],
            source_model_id=data["source_model_id"],
            candidate_model_ids=tuple(data["candidate_model_ids"]),
            conclusion=data["conclusion"],
            provenance=data["provenance"],
            evidence_refs=tuple(data["evidence_refs"]),
            challenge_refs=tuple(data["challenge_refs"]),
            review_refs=tuple(data["review_refs"]),
            objective_refs=tuple(data["objective_refs"]),
            representation_refs=tuple(data["representation_refs"]),
            unresolved_items=tuple(data["unresolved_items"]),
            scope=data["scope"],
        )


# ==============================================================================
# 2. Theory Transition Registry
# ==============================================================================

class TheoryTransitionRegistry:
    """Deterministic in-memory registry for theory transition audit records."""

    def __init__(self) -> None:
        self._transitions: dict[str, TheoryTransitionRecord] = {}

    def register(self, record: TheoryTransitionRecord) -> None:
        """Register a TheoryTransitionRecord with duplicate protection."""
        if not isinstance(record, TheoryTransitionRecord):
            raise ValueError(f"record must be a TheoryTransitionRecord instance, got {type(record)!r}.")
        tid = record.transition_id
        if tid in self._transitions:
            raise ValueError(f"TheoryTransitionRecord with ID '{tid}' already registered.")
        self._transitions[tid] = record

    def get(self, transition_id: str) -> TheoryTransitionRecord:
        """Retrieve a TheoryTransitionRecord by ID or raise KeyError."""
        if transition_id not in self._transitions:
            raise KeyError(f"TheoryTransitionRecord with ID '{transition_id}' not found.")
        return self._transitions[transition_id]

    def contains(self, transition_id: str) -> bool:
        """Check if a transition ID is registered."""
        return transition_id in self._transitions

    def all(self) -> tuple[TheoryTransitionRecord, ...]:
        """Return all registered theory transitions in deterministic insertion order."""
        return tuple(self._transitions.values())

    def query(
        self,
        *,
        source_model_id: Optional[str] = None,
        candidate_model_id: Optional[str] = None,
    ) -> tuple[TheoryTransitionRecord, ...]:
        """Filter registered theory transitions by exact matching without semantic inference."""
        results: list[TheoryTransitionRecord] = []
        for t in self._transitions.values():
            if source_model_id is not None and t.source_model_id != source_model_id:
                continue
            if candidate_model_id is not None and candidate_model_id not in t.candidate_model_ids:
                continue
            results.append(t)
        return tuple(results)

    def __len__(self) -> int:
        return len(self._transitions)

    def __iter__(self) -> Iterator[TheoryTransitionRecord]:
        return iter(self._transitions.values())

    def __contains__(self, transition_id: str) -> bool:
        return transition_id in self._transitions
