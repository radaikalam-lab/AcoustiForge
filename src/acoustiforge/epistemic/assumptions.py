"""AcoustiForge Epistemic Assumption Value Objects and Registry.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E2: Assumption Registry Implementation
- Governing Invariants:
  - MODEL != LAW
  - APPROXIMATION != LAW
  - HEURISTIC != LAW
  - HYPOTHESIS != EVIDENCE
  - EPISTEMIC_ACCEPTANCE != PRODUCTION_AUTHORITY
  - Assumption != Truth
  - Scope != Proof of Applicability
  - Provenance != Evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

from .vocabulary import (
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# 1. Epistemic Assumption Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class EpistemicAssumption:
    """Immutable first-class representation of an acoustic, mathematical, or engineering assumption.

    An assumption records what a model or component presumes to hold, its declared scope,
    provenance, and epistemic category. Registering an assumption does not assert its physical truth.
    """
    assumption_id: str
    statement: str
    epistemic_class: EpistemicClass
    zone: EpistemicZone
    status: EpistemicStatus
    scope: Mapping[str, Any]
    provenance: str

    def __post_init__(self) -> None:
        # 1. Validate assumption_id
        if not isinstance(self.assumption_id, str) or not self.assumption_id.strip():
            raise ValueError(f"assumption_id must be a non-empty string, got {self.assumption_id!r}.")

        # 2. Validate statement
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError(f"statement must be a non-empty string, got {self.statement!r}.")

        # 3. Validate epistemic_class
        if not isinstance(self.epistemic_class, EpistemicClass):
            if isinstance(self.epistemic_class, str):
                try:
                    object.__setattr__(self, "epistemic_class", EpistemicClass(self.epistemic_class))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicClass: {self.epistemic_class!r}.") from err
            else:
                raise ValueError(f"epistemic_class must be an EpistemicClass enum or str, got {type(self.epistemic_class)!r}.")

        # 4. Validate zone
        if not isinstance(self.zone, EpistemicZone):
            if isinstance(self.zone, str):
                try:
                    object.__setattr__(self, "zone", EpistemicZone(self.zone))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicZone: {self.zone!r}.") from err
            else:
                raise ValueError(f"zone must be an EpistemicZone enum or str, got {type(self.zone)!r}.")

        # 5. Validate status
        if not isinstance(self.status, EpistemicStatus):
            if isinstance(self.status, str):
                try:
                    object.__setattr__(self, "status", EpistemicStatus(self.status))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicStatus: {self.status!r}.") from err
            else:
                raise ValueError(f"status must be an EpistemicStatus enum or str, got {type(self.status)!r}.")

        # 6. Validate scope
        if not isinstance(self.scope, Mapping):
            raise ValueError(f"scope must be a Mapping, got {type(self.scope)!r}.")

        # 7. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # Canonicalize string attributes
        object.__setattr__(self, "assumption_id", self.assumption_id.strip())
        object.__setattr__(self, "statement", self.statement.strip())
        object.__setattr__(self, "provenance", self.provenance.strip())
        # Store scope as an immutable dict copy
        object.__setattr__(self, "scope", dict(self.scope))

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic conversion to JSON-serializable dictionary."""
        return {
            "assumption_id": self.assumption_id,
            "statement": self.statement,
            "epistemic_class": self.epistemic_class.value,
            "zone": self.zone.value,
            "status": self.status.value,
            "scope": dict(self.scope),
            "provenance": self.provenance,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpistemicAssumption:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected mapping, got {type(data)!r}.")
        return cls(
            assumption_id=data.get("assumption_id", ""),
            statement=data.get("statement", ""),
            epistemic_class=EpistemicClass(data.get("epistemic_class", EpistemicClass.HYPOTHESIS.value)),
            zone=EpistemicZone(data.get("zone", EpistemicZone.ZONE_M.value)),
            status=EpistemicStatus(data.get("status", EpistemicStatus.HYPOTHESIS.value)),
            scope=data.get("scope", {}),
            provenance=data.get("provenance", ""),
        )


# ==============================================================================
# 2. Assumption Registry Container
# ==============================================================================

class AssumptionRegistry:
    """Deterministic, auditable in-memory registry for EpistemicAssumption objects.

    Provides strict identity protection (no silent replacement or merge on duplicate IDs),
    deterministic enumeration, and query filtering without global singleton state.
    """

    def __init__(self) -> None:
        self._assumptions: dict[str, EpistemicAssumption] = {}

    def register(self, assumption: EpistemicAssumption) -> None:
        """Register an assumption in the registry.

        Args:
            assumption: An EpistemicAssumption instance.

        Raises:
            ValueError: If an assumption with the same assumption_id is already registered,
                or if input is not an EpistemicAssumption.
        """
        if not isinstance(assumption, EpistemicAssumption):
            raise ValueError(f"Expected EpistemicAssumption instance, got {type(assumption)!r}.")

        if assumption.assumption_id in self._assumptions:
            raise ValueError(
                f"Assumption '{assumption.assumption_id}' is already registered in this registry. "
                "Duplicate registration is rejected to prevent silent overwrite."
            )

        self._assumptions[assumption.assumption_id] = assumption

    def get(self, assumption_id: str) -> EpistemicAssumption:
        """Retrieve an assumption by its unique identity.

        Args:
            assumption_id: Unique string identifier.

        Returns:
            The registered EpistemicAssumption instance.

        Raises:
            KeyError: If assumption_id is not found in the registry.
        """
        if not isinstance(assumption_id, str):
            raise KeyError(f"assumption_id must be a string, got {type(assumption_id)!r}.")

        clean_id = assumption_id.strip()
        if clean_id not in self._assumptions:
            raise KeyError(f"Assumption '{clean_id}' not found in registry.")

        return self._assumptions[clean_id]

    def contains(self, assumption_id: str) -> bool:
        """Check whether an assumption ID is registered."""
        if not isinstance(assumption_id, str):
            return False
        return assumption_id.strip() in self._assumptions

    def all(self) -> tuple[EpistemicAssumption, ...]:
        """Return all registered assumptions as an immutable tuple in deterministic registration order."""
        return tuple(self._assumptions.values())

    def query(
        self,
        *,
        zone: Optional[EpistemicZone] = None,
        epistemic_class: Optional[EpistemicClass] = None,
        status: Optional[EpistemicStatus] = None,
    ) -> tuple[EpistemicAssumption, ...]:
        """Filter registered assumptions by zone, epistemic class, or status."""
        results: list[EpistemicAssumption] = []
        for asm in self._assumptions.values():
            if zone is not None and asm.zone != zone:
                continue
            if epistemic_class is not None and asm.epistemic_class != epistemic_class:
                continue
            if status is not None and asm.status != status:
                continue
            results.append(asm)
        return tuple(results)

    def clear(self) -> None:
        """Clear all assumptions from the registry instance."""
        self._assumptions.clear()

    def __len__(self) -> int:
        return len(self._assumptions)

    def __iter__(self) -> Iterator[EpistemicAssumption]:
        return iter(self._assumptions.values())

    def __contains__(self, assumption_id: object) -> bool:
        if isinstance(assumption_id, str):
            return self.contains(assumption_id)
        if isinstance(assumption_id, EpistemicAssumption):
            return assumption_id.assumption_id in self._assumptions
        return False
