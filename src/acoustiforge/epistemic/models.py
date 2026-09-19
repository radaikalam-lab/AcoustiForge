"""AcoustiForge Epistemic Model Value Objects and Registry.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E3: Model Registry Implementation
- Governing Invariants:
  - MODEL != LAW
  - APPROXIMATION != LAW
  - HEURISTIC != LAW
  - HYPOTHESIS != EVIDENCE
  - EPISTEMIC_ACCEPTANCE != PRODUCTION_AUTHORITY
  - Model != Truth
  - Assumption Dependencies != Proof of Assumption Validity
  - Provenance != Evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional, Sequence

from .vocabulary import (
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# 1. Epistemic Model Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class EpistemicModel:
    """Immutable first-class representation of an acoustic or mathematical explanatory model.

    An EpistemicModel records what a candidate or existing model claims to represent, its declared
    dependencies on epistemic assumptions, its provenance, and its epistemic status.
    Registering a model records its existence; it does not assert its physical truth or production authority.
    """
    model_id: str
    name: str
    description: str
    epistemic_class: EpistemicClass
    zone: EpistemicZone
    status: EpistemicStatus
    assumption_ids: tuple[str, ...]
    provenance: str

    def __post_init__(self) -> None:
        # 1. Validate model_id
        if not isinstance(self.model_id, str) or not self.model_id.strip():
            raise ValueError(f"model_id must be a non-empty string, got {self.model_id!r}.")

        # 2. Validate name
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError(f"name must be a non-empty string, got {self.name!r}.")

        # 3. Validate description
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(f"description must be a non-empty string, got {self.description!r}.")

        # 4. Validate epistemic_class
        if not isinstance(self.epistemic_class, EpistemicClass):
            if isinstance(self.epistemic_class, str):
                try:
                    object.__setattr__(self, "epistemic_class", EpistemicClass(self.epistemic_class))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicClass: {self.epistemic_class!r}.") from err
            else:
                raise ValueError(f"epistemic_class must be an EpistemicClass enum or str, got {type(self.epistemic_class)!r}.")

        # 5. Validate zone
        if not isinstance(self.zone, EpistemicZone):
            if isinstance(self.zone, str):
                try:
                    object.__setattr__(self, "zone", EpistemicZone(self.zone))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicZone: {self.zone!r}.") from err
            else:
                raise ValueError(f"zone must be an EpistemicZone enum or str, got {type(self.zone)!r}.")

        # 6. Validate status
        if not isinstance(self.status, EpistemicStatus):
            if isinstance(self.status, str):
                try:
                    object.__setattr__(self, "status", EpistemicStatus(self.status))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicStatus: {self.status!r}.") from err
            else:
                raise ValueError(f"status must be an EpistemicStatus enum or str, got {type(self.status)!r}.")

        # 7. Validate assumption_ids
        if not isinstance(self.assumption_ids, (tuple, list)):
            raise ValueError(f"assumption_ids must be a tuple or list of strings, got {type(self.assumption_ids)!r}.")

        validated_asm_ids: list[str] = []
        for idx, asm_id in enumerate(self.assumption_ids):
            if not isinstance(asm_id, str) or not asm_id.strip():
                raise ValueError(f"assumption_ids[{idx}] must be a non-empty string, got {asm_id!r}.")
            validated_asm_ids.append(asm_id.strip())

        # 8. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # Canonicalize string attributes
        object.__setattr__(self, "model_id", self.model_id.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", self.description.strip())
        object.__setattr__(self, "assumption_ids", tuple(validated_asm_ids))
        object.__setattr__(self, "provenance", self.provenance.strip())

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic conversion to JSON-serializable dictionary."""
        return {
            "model_id": self.model_id,
            "name": self.name,
            "description": self.description,
            "epistemic_class": self.epistemic_class.value,
            "zone": self.zone.value,
            "status": self.status.value,
            "assumption_ids": list(self.assumption_ids),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpistemicModel:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected mapping, got {type(data)!r}.")
        return cls(
            model_id=data.get("model_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            epistemic_class=EpistemicClass(data.get("epistemic_class", EpistemicClass.HYPOTHESIS.value)),
            zone=EpistemicZone(data.get("zone", EpistemicZone.ZONE_M.value)),
            status=EpistemicStatus(data.get("status", EpistemicStatus.HYPOTHESIS.value)),
            assumption_ids=tuple(data.get("assumption_ids", ())),
            provenance=data.get("provenance", ""),
        )


# ==============================================================================
# 2. Model Registry Container
# ==============================================================================

class ModelRegistry:
    """Deterministic, auditable in-memory registry for EpistemicModel objects.

    Provides strict identity protection (no silent replacement or merge on duplicate IDs),
    deterministic enumeration, and query filtering without global singleton state.
    """

    def __init__(self) -> None:
        self._models: dict[str, EpistemicModel] = {}

    def register(self, model: EpistemicModel) -> None:
        """Register an explanatory model in the registry.

        Args:
            model: An EpistemicModel instance.

        Raises:
            ValueError: If a model with the same model_id is already registered,
                or if input is not an EpistemicModel.
        """
        if not isinstance(model, EpistemicModel):
            raise ValueError(f"Expected EpistemicModel instance, got {type(model)!r}.")

        if model.model_id in self._models:
            raise ValueError(
                f"Model '{model.model_id}' is already registered in this registry. "
                "Duplicate registration is rejected to prevent silent overwrite."
            )

        self._models[model.model_id] = model

    def get(self, model_id: str) -> EpistemicModel:
        """Retrieve a model by its unique identity.

        Args:
            model_id: Unique string identifier.

        Returns:
            The registered EpistemicModel instance.

        Raises:
            KeyError: If model_id is not found in the registry.
        """
        if not isinstance(model_id, str):
            raise KeyError(f"model_id must be a string, got {type(model_id)!r}.")

        clean_id = model_id.strip()
        if clean_id not in self._models:
            raise KeyError(f"Model '{clean_id}' not found in registry.")

        return self._models[clean_id]

    def contains(self, model_id: str) -> bool:
        """Check whether a model ID is registered."""
        if not isinstance(model_id, str):
            return False
        return model_id.strip() in self._models

    def all(self) -> tuple[EpistemicModel, ...]:
        """Return all registered models as an immutable tuple in deterministic registration order."""
        return tuple(self._models.values())

    def query(
        self,
        *,
        zone: Optional[EpistemicZone] = None,
        epistemic_class: Optional[EpistemicClass] = None,
        status: Optional[EpistemicStatus] = None,
    ) -> tuple[EpistemicModel, ...]:
        """Filter registered models by zone, epistemic class, or status."""
        results: list[EpistemicModel] = []
        for mdl in self._models.values():
            if zone is not None and mdl.zone != zone:
                continue
            if epistemic_class is not None and mdl.epistemic_class != epistemic_class:
                continue
            if status is not None and mdl.status != status:
                continue
            results.append(mdl)
        return tuple(results)

    def clear(self) -> None:
        """Clear all models from the registry instance."""
        self._models.clear()

    def __len__(self) -> int:
        return len(self._models)

    def __iter__(self) -> Iterator[EpistemicModel]:
        return iter(self._models.values())

    def __contains__(self, model_id: object) -> bool:
        if isinstance(model_id, str):
            return self.contains(model_id)
        if isinstance(model_id, EpistemicModel):
            return model_id.model_id in self._models
        return False
