"""AcoustiForge Epistemic Unknown Value Objects and Registry.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E4: Unknown and Residual Representation
- Governing Invariants:
  - UNKNOWN != INVALID
  - UNKNOWN != MODEL_ERROR
  - UNKNOWN != FALSIFIED
  - UNKNOWN != FALSE
  - NOT_REPRESENTABLE != PHYSICALLY_IMPOSSIBLE
  - Scope != Proof of Applicability
  - Provenance != Evidence
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

from .vocabulary import (
    EpistemicStatus,
)


# ==============================================================================
# 1. Epistemic Unknown Value Object
# ==============================================================================

@dataclass(frozen=True, slots=True)
class EpistemicUnknown:
    """Immutable first-class representation of a declared epistemic unknown or anomaly.

    An EpistemicUnknown records an unexplained phenomenon, unmeasured variable, or unrepresented
    behavior. Registering an unknown declares an epistemic gap; it does not imply that the observation
    is invalid, false, or physically impossible.
    """
    unknown_id: str
    statement: str
    scope: Mapping[str, Any]
    provenance: str
    status: EpistemicStatus = EpistemicStatus.HYPOTHESIS

    def __post_init__(self) -> None:
        # 1. Validate unknown_id
        if not isinstance(self.unknown_id, str) or not self.unknown_id.strip():
            raise ValueError(f"unknown_id must be a non-empty string, got {self.unknown_id!r}.")

        # 2. Validate statement
        if not isinstance(self.statement, str) or not self.statement.strip():
            raise ValueError(f"statement must be a non-empty string, got {self.statement!r}.")

        # 3. Validate provenance
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(f"provenance must be a non-empty string, got {self.provenance!r}.")

        # 4. Validate status
        if not isinstance(self.status, EpistemicStatus):
            if isinstance(self.status, str):
                try:
                    object.__setattr__(self, "status", EpistemicStatus(self.status))
                except ValueError as err:
                    raise ValueError(f"Unsupported EpistemicStatus: {self.status!r}.") from err
            else:
                raise ValueError(f"status must be an EpistemicStatus enum or str, got {type(self.status)!r}.")

        # 5. Validate scope
        if not isinstance(self.scope, Mapping):
            raise ValueError(f"scope must be a Mapping, got {type(self.scope)!r}.")

        # Canonicalize string attributes
        object.__setattr__(self, "unknown_id", self.unknown_id.strip())
        object.__setattr__(self, "statement", self.statement.strip())
        object.__setattr__(self, "provenance", self.provenance.strip())
        # Store scope as an immutable dict copy
        object.__setattr__(self, "scope", dict(self.scope))

    def to_dict(self) -> dict[str, Any]:
        """Lossless deterministic conversion to JSON-serializable dictionary."""
        return {
            "unknown_id": self.unknown_id,
            "statement": self.statement,
            "scope": dict(self.scope),
            "provenance": self.provenance,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EpistemicUnknown:
        """Deterministic reconstruction from dictionary representation."""
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected mapping, got {type(data)!r}.")
        return cls(
            unknown_id=data.get("unknown_id", ""),
            statement=data.get("statement", ""),
            scope=data.get("scope", {}),
            provenance=data.get("provenance", ""),
            status=EpistemicStatus(data.get("status", EpistemicStatus.HYPOTHESIS.value)),
        )


# ==============================================================================
# 2. Unknown Registry Container
# ==============================================================================

class UnknownRegistry:
    """Deterministic, auditable in-memory registry for EpistemicUnknown objects.

    Provides strict identity protection (no silent replacement on duplicate IDs),
    deterministic enumeration, and query filtering without global singleton state.
    """

    def __init__(self) -> None:
        self._unknowns: dict[str, EpistemicUnknown] = {}

    def register(self, unknown: EpistemicUnknown) -> None:
        """Register an unknown in the registry.

        Args:
            unknown: An EpistemicUnknown instance.

        Raises:
            ValueError: If an unknown with the same unknown_id is already registered,
                or if input is not an EpistemicUnknown.
        """
        if not isinstance(unknown, EpistemicUnknown):
            raise ValueError(f"Expected EpistemicUnknown instance, got {type(unknown)!r}.")

        if unknown.unknown_id in self._unknowns:
            raise ValueError(
                f"Unknown '{unknown.unknown_id}' is already registered in this registry. "
                "Duplicate registration is rejected to prevent silent overwrite."
            )

        self._unknowns[unknown.unknown_id] = unknown

    def get(self, unknown_id: str) -> EpistemicUnknown:
        """Retrieve an unknown by its unique identity.

        Args:
            unknown_id: Unique string identifier.

        Returns:
            The registered EpistemicUnknown instance.

        Raises:
            KeyError: If unknown_id is not found in the registry.
        """
        if not isinstance(unknown_id, str):
            raise KeyError(f"unknown_id must be a string, got {type(unknown_id)!r}.")

        clean_id = unknown_id.strip()
        if clean_id not in self._unknowns:
            raise KeyError(f"Unknown '{clean_id}' not found in registry.")

        return self._unknowns[clean_id]

    def contains(self, unknown_id: str) -> bool:
        """Check whether an unknown ID is registered."""
        if not isinstance(unknown_id, str):
            return False
        return unknown_id.strip() in self._unknowns

    def all(self) -> tuple[EpistemicUnknown, ...]:
        """Return all registered unknowns as an immutable tuple in deterministic registration order."""
        return tuple(self._unknowns.values())

    def query(
        self,
        *,
        status: Optional[EpistemicStatus] = None,
    ) -> tuple[EpistemicUnknown, ...]:
        """Filter registered unknowns by status."""
        results: list[EpistemicUnknown] = []
        for unk in self._unknowns.values():
            if status is not None and unk.status != status:
                continue
            results.append(unk)
        return tuple(results)

    def clear(self) -> None:
        """Clear all unknowns from the registry instance."""
        self._unknowns.clear()

    def __len__(self) -> int:
        return len(self._unknowns)

    def __iter__(self) -> Iterator[EpistemicUnknown]:
        return iter(self._unknowns.values())

    def __contains__(self, unknown_id: object) -> bool:
        if isinstance(unknown_id, str):
            return self.contains(unknown_id)
        if isinstance(unknown_id, EpistemicUnknown):
            return unknown_id.unknown_id in self._unknowns
        return False
