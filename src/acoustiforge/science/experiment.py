"""AcoustiForge Scientific Experiment Session Protocol.

Represents empirical experiment sessions grouping manipulated variables, controlled conditions,
model predictions, acquired observations, and residual references without asserting epistemic
winners, modifying Core optimization, or conferring production authority.

Normative Authority:
- docs/architecture/POST_FREEZE_INTEGRATION.md (Phase P1)
- docs/phases/PHASE_P1_SCIENTIFIC_OBSERVATION_EXPERIMENT.md (Phase P1.1 Hardening)
- Governing Law: Epistemic Novelty != Production Authority
- Semantic Law: CONTROLLED_VARIABLES != MANIPULATED_VARIABLES, PREDICTION != OBSERVATION
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from ..domain.validation import InvalidSpecificationError


def _freeze_value(val: Any) -> Any:
    """Recursively freeze mappings into MappingProxyType and sequences into tuples."""
    if isinstance(val, Mapping):
        return MappingProxyType({str(k): _freeze_value(v) for k, v in val.items()})
    elif isinstance(val, (list, tuple)):
        return tuple(_freeze_value(v) for v in val)
    elif isinstance(val, (set, frozenset)):
        return frozenset(_freeze_value(v) for v in val)
    return val


def _unfreeze_value(val: Any) -> Any:
    """Recursively unfreeze MappingProxyType to dict and tuples/sets to lists for JSON serialization."""
    if isinstance(val, Mapping):
        return {str(k): _unfreeze_value(v) for k, v in val.items()}
    elif isinstance(val, (list, tuple)):
        return [_unfreeze_value(v) for v in val]
    elif isinstance(val, (set, frozenset)):
        return [_unfreeze_value(v) for v in val]
    return val


class ExperimentLifecycleState(str, Enum):
    """Execution lifecycle state for a scientific measurement experiment."""
    DEFINED = "DEFINED"
    ACQUIRING = "ACQUIRING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


@dataclass(frozen=True, slots=True)
class ExperimentSession:
    """Immutable scientific experiment session container.

    Groups controlled environmental variables, manipulated test parameters,
    candidate model predictions, acquired observation IDs, and resulting residual IDs.
    Guarantees deep immutability across all nested variable mappings and collections.
    """
    experiment_id: str
    name: str
    description: str
    lifecycle_state: ExperimentLifecycleState = ExperimentLifecycleState.DEFINED
    target_model_ids: tuple[str, ...] = ()
    representation_id: Optional[str] = None
    controlled_variables: Mapping[str, Any] = field(default_factory=dict)
    manipulated_variables: Mapping[str, Any] = field(default_factory=dict)
    observation_ids: tuple[str, ...] = ()
    prediction_references: Mapping[str, str] = field(default_factory=dict)
    residual_references: tuple[str, ...] = ()
    provenance: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise InvalidSpecificationError(f"experiment_id must be a non-empty string, got {self.experiment_id!r}.")
        object.__setattr__(self, "experiment_id", self.experiment_id.strip())

        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidSpecificationError(f"name must be a non-empty string, got {self.name!r}.")
        object.__setattr__(self, "name", self.name.strip())

        if not isinstance(self.description, str):
            raise InvalidSpecificationError(f"description must be a string, got {type(self.description)!r}.")
        object.__setattr__(self, "description", self.description.strip())

        if not isinstance(self.lifecycle_state, ExperimentLifecycleState):
            if isinstance(self.lifecycle_state, str):
                try:
                    object.__setattr__(self, "lifecycle_state", ExperimentLifecycleState(self.lifecycle_state))
                except ValueError as err:
                    raise InvalidSpecificationError(f"Invalid lifecycle_state: {self.lifecycle_state!r}") from err
            else:
                raise InvalidSpecificationError(f"lifecycle_state must be ExperimentLifecycleState, got {type(self.lifecycle_state)!r}.")

        if not isinstance(self.target_model_ids, tuple):
            object.__setattr__(self, "target_model_ids", tuple(str(m).strip() for m in self.target_model_ids))

        if self.representation_id is not None:
            object.__setattr__(self, "representation_id", str(self.representation_id).strip())

        object.__setattr__(self, "controlled_variables", _freeze_value(self.controlled_variables))
        object.__setattr__(self, "manipulated_variables", _freeze_value(self.manipulated_variables))

        if not isinstance(self.observation_ids, tuple):
            object.__setattr__(self, "observation_ids", tuple(str(o).strip() for o in self.observation_ids))

        object.__setattr__(self, "prediction_references", _freeze_value(self.prediction_references))

        if not isinstance(self.residual_references, tuple):
            object.__setattr__(self, "residual_references", tuple(str(r).strip() for r in self.residual_references))

        object.__setattr__(self, "provenance", str(self.provenance).strip())
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "description": self.description,
            "lifecycle_state": self.lifecycle_state.value,
            "target_model_ids": list(self.target_model_ids),
            "representation_id": self.representation_id,
            "controlled_variables": _unfreeze_value(self.controlled_variables),
            "manipulated_variables": _unfreeze_value(self.manipulated_variables),
            "observation_ids": list(self.observation_ids),
            "prediction_references": _unfreeze_value(self.prediction_references),
            "residual_references": list(self.residual_references),
            "provenance": self.provenance,
            "metadata": _unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ExperimentSession:
        return cls(
            experiment_id=data["experiment_id"],
            name=data["name"],
            description=data.get("description", ""),
            lifecycle_state=ExperimentLifecycleState(data.get("lifecycle_state", ExperimentLifecycleState.DEFINED.value)),
            target_model_ids=tuple(data.get("target_model_ids", ())),
            representation_id=data.get("representation_id"),
            controlled_variables=dict(data.get("controlled_variables", {})),
            manipulated_variables=dict(data.get("manipulated_variables", {})),
            observation_ids=tuple(data.get("observation_ids", ())),
            prediction_references=dict(data.get("prediction_references", {})),
            residual_references=tuple(data.get("residual_references", ())),
            provenance=data.get("provenance", ""),
            metadata=dict(data.get("metadata", {})),
        )


class ExperimentSessionRegistry:
    """Deterministic, auditable in-memory registry for scientific ExperimentSessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ExperimentSession] = {}

    def register(self, session: ExperimentSession) -> ExperimentSession:
        if not isinstance(session, ExperimentSession):
            raise InvalidSpecificationError(f"Expected ExperimentSession, got {type(session)!r}.")
        if session.experiment_id in self._sessions:
            raise InvalidSpecificationError(f"ExperimentSession with id '{session.experiment_id}' is already registered.")
        self._sessions[session.experiment_id] = session
        return session

    def get(self, experiment_id: str) -> Optional[ExperimentSession]:
        return self._sessions.get(experiment_id)

    def list_all(self) -> tuple[ExperimentSession, ...]:
        return tuple(self._sessions.values())

    def find_by_model(self, model_id: str) -> tuple[ExperimentSession, ...]:
        return tuple(sess for sess in self._sessions.values() if model_id in sess.target_model_ids)

    def find_by_observation(self, observation_id: str) -> tuple[ExperimentSession, ...]:
        return tuple(sess for sess in self._sessions.values() if observation_id in sess.observation_ids)

    def clear(self) -> None:
        self._sessions.clear()
