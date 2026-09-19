"""AcoustiForge Epistemic Shadow Model Competition and Comparison Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E6: Shadow Model Competition
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Model competition produces comparative evidence, NOT truth
  - Lower BIC / Lower Residual / Better Fit != Model Status Promotion
  - No universal ModelWinner or composite truth/adequacy score
  - Multi-dimensional evidence dimensions remain strictly separated
  - Incomparability is explicitly represented
  - No automatic falsification or challenge resolution
  - No mutation of EpistemicModel, EpistemicAssumption, or Production Core
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence


# ==============================================================================
# 1. Model Evidence Profile Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class ModelEvidenceProfile:
    """Immutable record describing how one model performed against a defined evidence context.

    Captures fit metrics, information criteria, predictive performance, and constraint compliance
    as distinct evidence dimensions without collapsing them into a single scalar score or truth claim.
    """
    model_id: str
    observation_ref: str
    residual_summary: str
    provenance: str
    evidence_refs: tuple[str, ...] = ()
    fit_metrics: Optional[Mapping[str, Any]] = None
    information_criteria: Optional[Mapping[str, Any]] = None
    predictive_metrics: Optional[Mapping[str, Any]] = None
    constraint_results: Optional[Mapping[str, Any]] = None
    applicability_notes: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # 1. Validate model_id
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError(f"model_id must be a non-empty string, got {self.model_id!r}.")

        # 2. Validate observation_ref
        if not isinstance(self.observation_ref, str) or not self.observation_ref.strip():
            raise ValueError(f"observation_ref must be a non-empty string, got {self.observation_ref!r}.")

        # 3. Validate residual_summary
        if not isinstance(self.residual_summary, str) or not self.residual_summary.strip():
            raise ValueError(f"residual_summary must be a non-empty string, got {self.residual_summary!r}.")

        # 4. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # 5. Validate evidence_refs
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

        # 6. Validate mappings (fit_metrics, information_criteria, predictive_metrics, constraint_results)
        for field_name in ("fit_metrics", "information_criteria", "predictive_metrics", "constraint_results"):
            val = getattr(self, field_name)
            if val is None:
                object.__setattr__(self, field_name, {})
            elif isinstance(val, Mapping):
                object.__setattr__(self, field_name, dict(val))
            else:
                raise ValueError(f"{field_name} must be a Mapping or None, got {type(val)!r}.")

        # 7. Validate sequence tuples (applicability_notes, unresolved_items)
        for field_name in ("applicability_notes", "unresolved_items"):
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
        """Convert ModelEvidenceProfile to a serializable dictionary."""
        return {
            "model_id": self.model_id,
            "observation_ref": self.observation_ref,
            "evidence_refs": list(self.evidence_refs),
            "residual_summary": self.residual_summary,
            "fit_metrics": dict(self.fit_metrics),
            "information_criteria": dict(self.information_criteria),
            "predictive_metrics": dict(self.predictive_metrics),
            "constraint_results": dict(self.constraint_results),
            "applicability_notes": list(self.applicability_notes),
            "unresolved_items": list(self.unresolved_items),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelEvidenceProfile:
        """Create a ModelEvidenceProfile from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "model_id",
            "observation_ref",
            "evidence_refs",
            "residual_summary",
            "fit_metrics",
            "information_criteria",
            "predictive_metrics",
            "constraint_results",
            "applicability_notes",
            "unresolved_items",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            model_id=data["model_id"],
            observation_ref=data["observation_ref"],
            evidence_refs=tuple(data["evidence_refs"]),
            residual_summary=data["residual_summary"],
            fit_metrics=data["fit_metrics"],
            information_criteria=data["information_criteria"],
            predictive_metrics=data["predictive_metrics"],
            constraint_results=data["constraint_results"],
            applicability_notes=tuple(data["applicability_notes"]),
            unresolved_items=tuple(data["unresolved_items"]),
            provenance=data["provenance"],
        )


# ==============================================================================
# 2. Model Comparison Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class ModelComparison:
    """Immutable record describing multi-model, dimension-by-dimension epistemic comparison.

    Represents comparative findings across individual dimensions (e.g. RMSE, BIC) and explicitly
    documents incomparable dimensions and scope limitations without declaring a global winner.
    """
    comparison_id: str
    observation_ref: str
    model_ids: tuple[str, ...]
    provenance: str
    profile_refs: tuple[str, ...] = ()
    comparison_dimensions: tuple[str, ...] = ()
    pairwise_results: tuple[Mapping[str, Any], ...] = ()
    incomparable_dimensions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        # 1. Validate comparison_id
        if not isinstance(self.comparison_id, str) or not self.comparison_id.strip():
            raise ValueError(f"comparison_id must be a non-empty string, got {self.comparison_id!r}.")

        # 2. Validate observation_ref
        if not isinstance(self.observation_ref, str) or not self.observation_ref.strip():
            raise ValueError(f"observation_ref must be a non-empty string, got {self.observation_ref!r}.")

        # 3. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # 4. Validate model_ids
        if isinstance(self.model_ids, (str, bytes)):
            raise ValueError("model_ids must be a sequence of model ID strings, not a single string.")
        try:
            m_tuple = tuple(self.model_ids)
        except TypeError as exc:
            raise ValueError(f"model_ids must be iterable, got {type(self.model_ids)!r}.") from exc
        if len(m_tuple) < 2:
            raise ValueError(f"model_ids must contain at least 2 models to compare, got {len(m_tuple)}.")
        for idx, mid in enumerate(m_tuple):
            if not isinstance(mid, str) or not mid.strip():
                raise ValueError(f"model_ids item at index {idx} must be a non-empty string, got {mid!r}.")
        object.__setattr__(self, "model_ids", m_tuple)

        # 5. Validate sequence tuples (profile_refs, comparison_dimensions, incomparable_dimensions, limitations)
        for field_name in ("profile_refs", "comparison_dimensions", "incomparable_dimensions", "limitations"):
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

        # 6. Validate pairwise_results
        if isinstance(self.pairwise_results, (str, bytes)):
            raise ValueError("pairwise_results must be a sequence of mappings.")
        try:
            pw_tuple = tuple(self.pairwise_results)
        except TypeError as exc:
            raise ValueError(f"pairwise_results must be iterable, got {type(self.pairwise_results)!r}.") from exc
        for idx, item in enumerate(pw_tuple):
            if not isinstance(item, Mapping):
                raise ValueError(f"pairwise_results item at index {idx} must be a Mapping, got {type(item)!r}.")
        object.__setattr__(self, "pairwise_results", tuple(dict(m) for m in pw_tuple))

    def to_dict(self) -> dict[str, Any]:
        """Convert ModelComparison to a serializable dictionary."""
        return {
            "comparison_id": self.comparison_id,
            "observation_ref": self.observation_ref,
            "model_ids": list(self.model_ids),
            "profile_refs": list(self.profile_refs),
            "comparison_dimensions": list(self.comparison_dimensions),
            "pairwise_results": [dict(m) for m in self.pairwise_results],
            "incomparable_dimensions": list(self.incomparable_dimensions),
            "limitations": list(self.limitations),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelComparison:
        """Create a ModelComparison from a dictionary."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Input data must be a Mapping, got {type(data)!r}.")

        required_keys = {
            "comparison_id",
            "observation_ref",
            "model_ids",
            "profile_refs",
            "comparison_dimensions",
            "pairwise_results",
            "incomparable_dimensions",
            "limitations",
            "provenance",
        }
        missing_keys = required_keys - set(data.keys())
        if missing_keys:
            raise ValueError(f"Missing required keys in dictionary: {sorted(missing_keys)}")

        return cls(
            comparison_id=data["comparison_id"],
            observation_ref=data["observation_ref"],
            model_ids=tuple(data["model_ids"]),
            profile_refs=tuple(data["profile_refs"]),
            comparison_dimensions=tuple(data["comparison_dimensions"]),
            pairwise_results=tuple(data["pairwise_results"]),
            incomparable_dimensions=tuple(data["incomparable_dimensions"]),
            limitations=tuple(data["limitations"]),
            provenance=data["provenance"],
        )


# ==============================================================================
# 3. Model Competition Registry
# ==============================================================================

class ModelCompetitionRegistry:
    """Deterministic in-memory registry for model evidence profiles and comparisons.

    Stores completed evaluation profiles and comparison records with duplicate protection,
    deterministic insertion ordering, and non-inferential querying.
    """

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], ModelEvidenceProfile] = {}
        self._comparisons: dict[str, ModelComparison] = {}

    def register_profile(self, profile: ModelEvidenceProfile) -> None:
        """Register a model evidence profile with duplicate protection on (model_id, observation_ref)."""
        if not isinstance(profile, ModelEvidenceProfile):
            raise ValueError(f"profile must be an instance of ModelEvidenceProfile, got {type(profile)!r}.")

        key = (profile.model_id, profile.observation_ref)
        if key in self._profiles:
            raise ValueError(f"Profile for model '{profile.model_id}' and observation '{profile.observation_ref}' already registered.")

        self._profiles[key] = profile

    def get_profile(self, model_id: str, observation_ref: str) -> ModelEvidenceProfile:
        """Retrieve a registered profile by model_id and observation_ref or raise KeyError."""
        key = (model_id, observation_ref)
        if key not in self._profiles:
            raise KeyError(f"Profile for model '{model_id}' and observation '{observation_ref}' not found.")
        return self._profiles[key]

    def all_profiles(self) -> tuple[ModelEvidenceProfile, ...]:
        """Return all registered profiles in deterministic insertion order."""
        return tuple(self._profiles.values())

    def register(self, comparison: ModelComparison) -> None:
        """Register a model comparison record with duplicate protection on comparison_id."""
        if not isinstance(comparison, ModelComparison):
            raise ValueError(f"comparison must be an instance of ModelComparison, got {type(comparison)!r}.")

        cid = comparison.comparison_id
        if cid in self._comparisons:
            raise ValueError(f"Comparison with ID '{cid}' is already registered.")

        self._comparisons[cid] = comparison

    def get(self, comparison_id: str) -> ModelComparison:
        """Retrieve a registered comparison by ID or raise KeyError."""
        if comparison_id not in self._comparisons:
            raise KeyError(f"Comparison with ID '{comparison_id}' not found.")
        return self._comparisons[comparison_id]

    def contains(self, comparison_id: str) -> bool:
        """Check if a comparison ID is registered."""
        return comparison_id in self._comparisons

    def all(self) -> tuple[ModelComparison, ...]:
        """Return all registered comparisons in deterministic insertion order."""
        return tuple(self._comparisons.values())

    def query(
        self,
        *,
        observation_ref: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> tuple[ModelComparison, ...]:
        """Filter registered comparisons by exact matching without semantic inference."""
        results: list[ModelComparison] = []
        for comp in self._comparisons.values():
            if observation_ref is not None and comp.observation_ref != observation_ref:
                continue
            if model_id is not None and model_id not in comp.model_ids:
                continue
            results.append(comp)
        return tuple(results)

    def __len__(self) -> int:
        return len(self._comparisons)

    def __iter__(self) -> Iterator[ModelComparison]:
        return iter(self._comparisons.values())

    def __contains__(self, comparison_id: str) -> bool:
        return comparison_id in self._comparisons
