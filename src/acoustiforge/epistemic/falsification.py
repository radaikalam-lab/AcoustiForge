"""AcoustiForge Epistemic Falsification Evidence & Model Review Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E7: Falsification Evidence & Model Review
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Contradictory Evidence != Falsification Evidence != Model Falsified
  - Large Residual / Comparison Defeat / Worse BIC != Automatic Falsification
  - FALSIFICATION_EVIDENCE_DETECTED is distinct from FALSIFIED
  - Model status transition to FALSIFIED requires explicit, auditable review
  - Permitted Review Outcomes: DOMAIN_LIMITED, CHALLENGED, FALSIFIED
  - Production Core remains completely untouched
  - AI-generated content cannot become empirical evidence through E7
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Mapping, Optional, Sequence

from .vocabulary import (
    EpistemicStatus,
)


# ==============================================================================
# 1. Applicability Status Enum
# ==============================================================================

class ApplicabilityStatus(str, Enum):
    """Scope applicability evaluation for contradictory / falsification evidence."""
    WITHIN_SCOPE = "WITHIN_SCOPE"
    OUTSIDE_SCOPE = "OUTSIDE_SCOPE"
    PARTIALLY_WITHIN_SCOPE = "PARTIALLY_WITHIN_SCOPE"
    SCOPE_UNCERTAIN = "SCOPE_UNCERTAIN"


# ==============================================================================
# 2. Falsification Evidence Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class FalsificationEvidence:
    """Immutable representation of evidence relevant to a model's declared falsification criterion.

    Records what was observed, what was expected, under what scope, and why it is relevant
    to a stated criterion. Does NOT declare that the model is false or disproven.
    """
    evidence_id: str
    model_id: str
    observation_ref: str
    criterion_id: str
    criterion_description: str
    observed_behavior: str
    expected_behavior: str
    discrepancy_summary: str
    provenance: str
    evidence_refs: tuple[str, ...] = ()
    scope: Optional[Mapping[str, Any]] = None
    applicability_status: str = ApplicabilityStatus.WITHIN_SCOPE.value

    def __post_init__(self) -> None:
        # 1. Validate required string fields
        for field_name in (
            "evidence_id",
            "model_id",
            "observation_ref",
            "criterion_id",
            "criterion_description",
            "observed_behavior",
            "expected_behavior",
            "discrepancy_summary",
            "provenance",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        # 2. Validate applicability_status
        if isinstance(self.applicability_status, ApplicabilityStatus):
            object.__setattr__(self, "applicability_status", self.applicability_status.value)
        elif isinstance(self.applicability_status, str):
            if not self.applicability_status.strip():
                raise ValueError("applicability_status must be a non-empty string.")
        else:
            raise ValueError(f"applicability_status must be a str or ApplicabilityStatus, got {type(self.applicability_status)!r}.")

        # 3. Validate scope
        if self.scope is None:
            object.__setattr__(self, "scope", {})
        elif isinstance(self.scope, Mapping):
            object.__setattr__(self, "scope", dict(self.scope))
        else:
            raise ValueError(f"scope must be a Mapping or None, got {type(self.scope)!r}.")

        # 4. Validate evidence_refs
        if isinstance(self.evidence_refs, (str, bytes)):
            raise ValueError("evidence_refs must be a sequence of strings, not a single string.")
        try:
            ev_tuple = tuple(self.evidence_refs)
        except TypeError as exc:
            raise ValueError(f"evidence_refs must be iterable, got {type(self.evidence_refs)!r}.") from exc
        for idx, item in enumerate(ev_tuple):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"evidence_refs at index {idx} must be a non-empty string, got {item!r}.")
        object.__setattr__(self, "evidence_refs", ev_tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert FalsificationEvidence to a serializable dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "model_id": self.model_id,
            "observation_ref": self.observation_ref,
            "evidence_refs": list(self.evidence_refs),
            "criterion_id": self.criterion_id,
            "criterion_description": self.criterion_description,
            "observed_behavior": self.observed_behavior,
            "expected_behavior": self.expected_behavior,
            "discrepancy_summary": self.discrepancy_summary,
            "scope": dict(self.scope),
            "applicability_status": self.applicability_status,
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FalsificationEvidence:
        """Create FalsificationEvidence from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "evidence_id",
            "model_id",
            "observation_ref",
            "evidence_refs",
            "criterion_id",
            "criterion_description",
            "observed_behavior",
            "expected_behavior",
            "discrepancy_summary",
            "scope",
            "applicability_status",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            evidence_id=data["evidence_id"],
            model_id=data["model_id"],
            observation_ref=data["observation_ref"],
            evidence_refs=tuple(data["evidence_refs"]),
            criterion_id=data["criterion_id"],
            criterion_description=data["criterion_description"],
            observed_behavior=data["observed_behavior"],
            expected_behavior=data["expected_behavior"],
            discrepancy_summary=data["discrepancy_summary"],
            scope=data["scope"],
            applicability_status=data["applicability_status"],
            provenance=data["provenance"],
        )


# ==============================================================================
# 3. Falsification Assessment Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class FalsificationAssessment:
    """Immutable record of deterministic evaluation of evidence against a falsification criterion.

    `criterion_violated=True` indicates that FALSIFICATION_EVIDENCE_DETECTED applies,
    which enters the model into UNDER_REVIEW. It does NOT automatically set status to FALSIFIED.
    """
    assessment_id: str
    model_id: str
    criterion_id: str
    evidence_id: str
    criterion_tested: bool
    criterion_violated: bool
    applicability: str
    evidence_strength_description: str
    rationale: str
    provenance: str
    unresolved_items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "assessment_id",
            "model_id",
            "criterion_id",
            "evidence_id",
            "applicability",
            "evidence_strength_description",
            "rationale",
            "provenance",
        ):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        if not isinstance(self.criterion_tested, bool):
            raise ValueError(f"criterion_tested must be a boolean, got {type(self.criterion_tested)!r}.")
        if not isinstance(self.criterion_violated, bool):
            raise ValueError(f"criterion_violated must be a boolean, got {type(self.criterion_violated)!r}.")

        if isinstance(self.unresolved_items, (str, bytes)):
            raise ValueError("unresolved_items must be a sequence of strings, not a single string.")
        try:
            unres_tuple = tuple(self.unresolved_items)
        except TypeError as exc:
            raise ValueError(f"unresolved_items must be iterable, got {type(self.unresolved_items)!r}.") from exc
        for idx, item in enumerate(unres_tuple):
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"unresolved_items at index {idx} must be a non-empty string, got {item!r}.")
        object.__setattr__(self, "unresolved_items", unres_tuple)

    def to_dict(self) -> dict[str, Any]:
        """Convert FalsificationAssessment to a serializable dictionary."""
        return {
            "assessment_id": self.assessment_id,
            "model_id": self.model_id,
            "criterion_id": self.criterion_id,
            "evidence_id": self.evidence_id,
            "criterion_tested": self.criterion_tested,
            "criterion_violated": self.criterion_violated,
            "applicability": self.applicability,
            "evidence_strength_description": self.evidence_strength_description,
            "rationale": self.rationale,
            "unresolved_items": list(self.unresolved_items),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FalsificationAssessment:
        """Create FalsificationAssessment from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "assessment_id",
            "model_id",
            "criterion_id",
            "evidence_id",
            "criterion_tested",
            "criterion_violated",
            "applicability",
            "evidence_strength_description",
            "rationale",
            "unresolved_items",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            assessment_id=data["assessment_id"],
            model_id=data["model_id"],
            criterion_id=data["criterion_id"],
            evidence_id=data["evidence_id"],
            criterion_tested=bool(data["criterion_tested"]),
            criterion_violated=bool(data["criterion_violated"]),
            applicability=data["applicability"],
            evidence_strength_description=data["evidence_strength_description"],
            rationale=data["rationale"],
            unresolved_items=tuple(data["unresolved_items"]),
            provenance=data["provenance"],
        )


# ==============================================================================
# 4. Falsification Review Record
# ==============================================================================

ALLOWED_REVIEW_DECISIONS: frozenset[EpistemicStatus] = frozenset({
    EpistemicStatus.DOMAIN_LIMITED,
    EpistemicStatus.CHALLENGED,
    EpistemicStatus.FALSIFIED,
})


@dataclass(frozen=True, slots=True)
class FalsificationReview:
    """Immutable audit record representing an explicit review decision on a model under review.

    Only permitted final decisions are: DOMAIN_LIMITED, CHALLENGED, or FALSIFIED.
    E7 reviews cannot confer PRODUCTION_AUTHORITY or promote models.
    """
    review_id: str
    model_id: str
    evidence_id: str
    initial_status: EpistemicStatus
    decision: EpistemicStatus
    rationale: str
    provenance: str
    supporting_evidence_refs: tuple[str, ...] = ()
    contradictory_evidence_refs: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()
    scope: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        # 1. Validate required strings
        for field_name in ("review_id", "model_id", "evidence_id", "rationale", "provenance"):
            val = getattr(self, field_name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string, got {val!r}.")

        # 2. Validate initial_status
        if not isinstance(self.initial_status, EpistemicStatus):
            raise ValueError(f"initial_status must be an EpistemicStatus instance, got {type(self.initial_status)!r}.")

        # 3. Validate decision
        if not isinstance(self.decision, EpistemicStatus):
            raise ValueError(f"decision must be an EpistemicStatus instance, got {type(self.decision)!r}.")
        if self.decision not in ALLOWED_REVIEW_DECISIONS:
            raise ValueError(
                f"Invalid review decision: {self.decision.value}. "
                f"Permitted review decisions are limited to: {[s.value for s in ALLOWED_REVIEW_DECISIONS]}."
            )

        # 4. Validate scope
        if self.scope is None:
            object.__setattr__(self, "scope", {})
        elif isinstance(self.scope, Mapping):
            object.__setattr__(self, "scope", dict(self.scope))
        else:
            raise ValueError(f"scope must be a Mapping or None, got {type(self.scope)!r}.")

        # 5. Validate sequence tuples
        for field_name in ("supporting_evidence_refs", "contradictory_evidence_refs", "unresolved_items"):
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
        """Convert FalsificationReview to a serializable dictionary."""
        return {
            "review_id": self.review_id,
            "model_id": self.model_id,
            "evidence_id": self.evidence_id,
            "initial_status": self.initial_status.value,
            "decision": self.decision.value,
            "rationale": self.rationale,
            "supporting_evidence_refs": list(self.supporting_evidence_refs),
            "contradictory_evidence_refs": list(self.contradictory_evidence_refs),
            "unresolved_items": list(self.unresolved_items),
            "scope": dict(self.scope),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FalsificationReview:
        """Create FalsificationReview from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "review_id",
            "model_id",
            "evidence_id",
            "initial_status",
            "decision",
            "rationale",
            "supporting_evidence_refs",
            "contradictory_evidence_refs",
            "unresolved_items",
            "scope",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        raw_init = data["initial_status"]
        initial_status = EpistemicStatus(raw_init) if isinstance(raw_init, str) else raw_init

        raw_dec = data["decision"]
        decision = EpistemicStatus(raw_dec) if isinstance(raw_dec, str) else raw_dec

        return cls(
            review_id=data["review_id"],
            model_id=data["model_id"],
            evidence_id=data["evidence_id"],
            initial_status=initial_status,
            decision=decision,
            rationale=data["rationale"],
            supporting_evidence_refs=tuple(data["supporting_evidence_refs"]),
            contradictory_evidence_refs=tuple(data["contradictory_evidence_refs"]),
            unresolved_items=tuple(data["unresolved_items"]),
            scope=data["scope"],
            provenance=data["provenance"],
        )


# ==============================================================================
# 5. Falsification Registry
# ==============================================================================

class FalsificationRegistry:
    """Deterministic in-memory registry for falsification evidence, assessments, and review records.

    Stores audit records with duplicate protection, deterministic insertion ordering,
    and non-inferential querying.
    """

    def __init__(self) -> None:
        self._evidence: dict[str, FalsificationEvidence] = {}
        self._assessments: dict[str, FalsificationAssessment] = {}
        self._reviews: dict[str, FalsificationReview] = {}

    def register_evidence(self, evidence: FalsificationEvidence) -> None:
        """Register a FalsificationEvidence record with duplicate protection."""
        if not isinstance(evidence, FalsificationEvidence):
            raise ValueError(f"evidence must be a FalsificationEvidence instance, got {type(evidence)!r}.")
        eid = evidence.evidence_id
        if eid in self._evidence:
            raise ValueError(f"FalsificationEvidence with ID '{eid}' already registered.")
        self._evidence[eid] = evidence

    def get_evidence(self, evidence_id: str) -> FalsificationEvidence:
        """Retrieve FalsificationEvidence by ID or raise KeyError."""
        if evidence_id not in self._evidence:
            raise KeyError(f"FalsificationEvidence with ID '{evidence_id}' not found.")
        return self._evidence[evidence_id]

    def all_evidence(self) -> tuple[FalsificationEvidence, ...]:
        """Return all registered evidence records in deterministic insertion order."""
        return tuple(self._evidence.values())

    def register_assessment(self, assessment: FalsificationAssessment) -> None:
        """Register a FalsificationAssessment record with duplicate protection."""
        if not isinstance(assessment, FalsificationAssessment):
            raise ValueError(f"assessment must be a FalsificationAssessment instance, got {type(assessment)!r}.")
        aid = assessment.assessment_id
        if aid in self._assessments:
            raise ValueError(f"FalsificationAssessment with ID '{aid}' already registered.")
        self._assessments[aid] = assessment

    def get_assessment(self, assessment_id: str) -> FalsificationAssessment:
        """Retrieve FalsificationAssessment by ID or raise KeyError."""
        if assessment_id not in self._assessments:
            raise KeyError(f"FalsificationAssessment with ID '{assessment_id}' not found.")
        return self._assessments[assessment_id]

    def all_assessments(self) -> tuple[FalsificationAssessment, ...]:
        """Return all registered assessment records in deterministic insertion order."""
        return tuple(self._assessments.values())

    def register_review(self, review: FalsificationReview) -> None:
        """Register a FalsificationReview record with duplicate protection."""
        if not isinstance(review, FalsificationReview):
            raise ValueError(f"review must be a FalsificationReview instance, got {type(review)!r}.")
        rid = review.review_id
        if rid in self._reviews:
            raise ValueError(f"FalsificationReview with ID '{rid}' already registered.")
        self._reviews[rid] = review

    def register(self, review: FalsificationReview) -> None:
        """Convenience alias for register_review."""
        self.register_review(review)

    def get_review(self, review_id: str) -> FalsificationReview:
        """Retrieve FalsificationReview by ID or raise KeyError."""
        if review_id not in self._reviews:
            raise KeyError(f"FalsificationReview with ID '{review_id}' not found.")
        return self._reviews[review_id]

    def get(self, review_id: str) -> FalsificationReview:
        """Convenience alias for get_review."""
        return self.get_review(review_id)

    def contains(self, review_id: str) -> bool:
        """Check if a review ID is registered."""
        return review_id in self._reviews

    def all_reviews(self) -> tuple[FalsificationReview, ...]:
        """Return all registered reviews in deterministic insertion order."""
        return tuple(self._reviews.values())

    def all(self) -> tuple[FalsificationReview, ...]:
        """Convenience alias for all_reviews."""
        return self.all_reviews()

    def query(
        self,
        *,
        model_id: Optional[str] = None,
        decision: Optional[EpistemicStatus] = None,
    ) -> tuple[FalsificationReview, ...]:
        """Filter registered reviews by exact matching without semantic inference."""
        results: list[FalsificationReview] = []
        for rev in self._reviews.values():
            if model_id is not None and rev.model_id != model_id:
                continue
            if decision is not None and rev.decision != decision:
                continue
            results.append(rev)
        return tuple(results)

    def __len__(self) -> int:
        return len(self._reviews)

    def __iter__(self) -> Iterator[FalsificationReview]:
        return iter(self._reviews.values())

    def __contains__(self, review_id: str) -> bool:
        return review_id in self._reviews
