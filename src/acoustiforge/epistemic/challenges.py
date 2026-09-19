"""AcoustiForge Epistemic Challenge Value Objects and Registry.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E5: Challenge Representation
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - CHALLENGE != FALSIFICATION
  - CHALLENGE != TARGET_INVALIDATION
  - CHALLENGE != EVIDENCE
  - CHALLENGE_STATUS != TRUTH
  - PROPOSED_TEST != EXECUTED_TEST
  - EPISTEMIC_ACCEPTED != PRODUCTION_AUTHORITY
  - Provenance != Evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence

from .vocabulary import (
    ChallengeStatus,
)


# ==============================================================================
# 1. Epistemic Challenge Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class EpistemicChallenge:
    """Immutable representation of an epistemic challenge against an assumption, model, or object.

    A challenge records that an epistemic target deserves investigation for stated reasons,
    under a declared scope, motivated by explicit trigger references, with proposed tests.
    It does NOT determine whether the target is disproven, invalidated, or false.
    """
    challenge_id: str
    target_id: str
    target_kind: str
    rationale: str
    provenance: str
    status: ChallengeStatus = ChallengeStatus.CHALLENGE_PROPOSED
    scope: Optional[Mapping[str, Any]] = None
    trigger_refs: tuple[str, ...] = ()
    proposed_tests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # 1. Validate challenge_id
        if not isinstance(self.challenge_id, str) or not self.challenge_id.strip():
            raise ValueError(f"challenge_id must be a non-empty string, got {self.challenge_id!r}.")

        # 2. Validate target_id
        if not isinstance(self.target_id, str) or not self.target_id.strip():
            raise ValueError(f"target_id must be a non-empty string, got {self.target_id!r}.")

        # 3. Validate target_kind
        if not isinstance(self.target_kind, str) or not self.target_kind.strip():
            raise ValueError(f"target_kind must be a non-empty string, got {self.target_kind!r}.")

        # 4. Validate rationale
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError(f"rationale must be a non-empty string, got {self.rationale!r}.")

        # 5. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # 6. Validate status
        if not isinstance(self.status, ChallengeStatus):
            raise ValueError(f"status must be an instance of ChallengeStatus, got {type(self.status)!r}.")

        # 7. Validate scope
        if self.scope is None:
            object.__setattr__(self, "scope", {})
        elif isinstance(self.scope, Mapping):
            object.__setattr__(self, "scope", dict(self.scope))
        else:
            raise ValueError(f"scope must be a Mapping or None, got {type(self.scope)!r}.")

        # 8. Validate trigger_refs
        if isinstance(self.trigger_refs, (str, bytes)):
            raise ValueError("trigger_refs must be a sequence of non-empty strings, not a single string.")
        try:
            triggers = tuple(self.trigger_refs)
        except TypeError as exc:
            raise ValueError(f"trigger_refs must be an iterable of strings, got {type(self.trigger_refs)!r}.") from exc

        for idx, tr in enumerate(triggers):
            if not isinstance(tr, str) or not tr.strip():
                raise ValueError(f"trigger_refs item at index {idx} must be a non-empty string, got {tr!r}.")
        object.__setattr__(self, "trigger_refs", triggers)

        # 9. Validate proposed_tests
        if isinstance(self.proposed_tests, (str, bytes)):
            raise ValueError("proposed_tests must be a sequence of non-empty strings, not a single string.")
        try:
            tests = tuple(self.proposed_tests)
        except TypeError as exc:
            raise ValueError(f"proposed_tests must be an iterable of strings, got {type(self.proposed_tests)!r}.") from exc

        for idx, pt in enumerate(tests):
            if not isinstance(pt, str) or not pt.strip():
                raise ValueError(f"proposed_tests item at index {idx} must be a non-empty string, got {pt!r}.")
        object.__setattr__(self, "proposed_tests", tests)

    def to_dict(self) -> dict[str, Any]:
        """Convert EpistemicChallenge to a serializable dictionary."""
        return {
            "challenge_id": self.challenge_id,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "status": self.status.value,
            "rationale": self.rationale,
            "scope": dict(self.scope),
            "trigger_refs": list(self.trigger_refs),
            "proposed_tests": list(self.proposed_tests),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpistemicChallenge:
        """Create an EpistemicChallenge from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "challenge_id",
            "target_id",
            "target_kind",
            "status",
            "rationale",
            "scope",
            "trigger_refs",
            "proposed_tests",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        raw_status = data["status"]
        if isinstance(raw_status, ChallengeStatus):
            status = raw_status
        elif isinstance(raw_status, str):
            try:
                status = ChallengeStatus(raw_status)
            except ValueError as exc:
                raise ValueError(f"Invalid ChallengeStatus value: {raw_status!r}") from exc
        else:
            raise ValueError(f"status must be a ChallengeStatus or string, got {type(raw_status)!r}.")

        return cls(
            challenge_id=data["challenge_id"],
            target_id=data["target_id"],
            target_kind=data["target_kind"],
            status=status,
            rationale=data["rationale"],
            scope=data["scope"],
            trigger_refs=tuple(data["trigger_refs"]),
            proposed_tests=tuple(data["proposed_tests"]),
            provenance=data["provenance"],
        )


# ==============================================================================
# 2. Challenge Registry
# ==============================================================================

class ChallengeRegistry:
    """Deterministic, auditable in-memory registry for epistemic challenges.

    Maintains duplicate protection, deterministic insertion-order iteration,
    immutable stored objects, and non-inferential querying.
    """

    def __init__(self) -> None:
        self._challenges: dict[str, EpistemicChallenge] = {}

    def register(self, challenge: EpistemicChallenge) -> None:
        """Register an epistemic challenge with duplicate protection."""
        if not isinstance(challenge, EpistemicChallenge):
            raise ValueError(f"challenge must be an instance of EpistemicChallenge, got {type(challenge)!r}.")

        cid = challenge.challenge_id
        if cid in self._challenges:
            raise ValueError(f"Challenge with ID '{cid}' is already registered.")

        self._challenges[cid] = challenge

    def get(self, challenge_id: str) -> EpistemicChallenge:
        """Retrieve a registered challenge by ID or raise KeyError."""
        if challenge_id not in self._challenges:
            raise KeyError(f"Challenge with ID '{challenge_id}' not found in registry.")
        return self._challenges[challenge_id]

    def contains(self, challenge_id: str) -> bool:
        """Check if a challenge ID is registered."""
        return challenge_id in self._challenges

    def all(self) -> tuple[EpistemicChallenge, ...]:
        """Return all registered challenges in deterministic insertion order."""
        return tuple(self._challenges.values())

    def query(
        self,
        *,
        status: Optional[ChallengeStatus] = None,
        target_id: Optional[str] = None,
        target_kind: Optional[str] = None,
    ) -> tuple[EpistemicChallenge, ...]:
        """Filter registered challenges by explicit attributes without semantic inference."""
        results: list[EpistemicChallenge] = []
        for challenge in self._challenges.values():
            if status is not None and challenge.status != status:
                continue
            if target_id is not None and challenge.target_id != target_id:
                continue
            if target_kind is not None and challenge.target_kind != target_kind:
                continue
            results.append(challenge)
        return tuple(results)

    def __len__(self) -> int:
        return len(self._challenges)

    def __iter__(self) -> Iterator[EpistemicChallenge]:
        return iter(self._challenges.values())

    def __contains__(self, challenge_id: str) -> bool:
        return challenge_id in self._challenges
