"""AcoustiForge Scientific Observation Envelope.

Provides immutable containers associating raw acoustic measurements with environmental
context, instrument calibration, acquisition provenance, and explicit transform lineage
without collapsing uncertainty or asserting epistemic authority.

Normative Authority:
- docs/architecture/POST_FREEZE_INTEGRATION.md (Phase P1)
- docs/phases/PHASE_P1_SCIENTIFIC_OBSERVATION_EXPERIMENT.md (Phase P1.1 Hardening)
- Governing Law: Epistemic Novelty != Production Authority
- Semantic Law: DATA != EVIDENCE INTERPRETATION
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from ..domain.measurements import FrequencyResponseData
from ..domain.validation import InvalidMeasurementError


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


@dataclass(frozen=True, slots=True)
class EnvironmentalConditions:
    """Immutable environmental ambient parameters recorded during measurement acquisition."""
    temperature_c: Optional[float] = None
    relative_humidity_pct: Optional[float] = None
    ambient_pressure_kpa: Optional[float] = None
    ambient_noise_floor_db: Optional[float] = None

    def __post_init__(self) -> None:
        for attr, val in (
            ("temperature_c", self.temperature_c),
            ("relative_humidity_pct", self.relative_humidity_pct),
            ("ambient_pressure_kpa", self.ambient_pressure_kpa),
            ("ambient_noise_floor_db", self.ambient_noise_floor_db),
        ):
            if val is not None:
                if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
                    raise InvalidMeasurementError(f"{attr} must be a finite float, got {val!r}.")
                object.__setattr__(self, attr, float(val))

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "relative_humidity_pct": self.relative_humidity_pct,
            "ambient_pressure_kpa": self.ambient_pressure_kpa,
            "ambient_noise_floor_db": self.ambient_noise_floor_db,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EnvironmentalConditions:
        return cls(
            temperature_c=data.get("temperature_c"),
            relative_humidity_pct=data.get("relative_humidity_pct"),
            ambient_pressure_kpa=data.get("ambient_pressure_kpa"),
            ambient_noise_floor_db=data.get("ambient_noise_floor_db"),
        )


@dataclass(frozen=True, slots=True)
class MeasurementUncertainty:
    """Dimension-separated measurement uncertainty metrics (no scalar quality/truth collapse)."""
    snr_db: Optional[float] = None
    repeatability_variance_db: Optional[float] = None
    calibration_uncertainty_db: Optional[float] = None
    frequency_range_hz: Optional[tuple[float, float]] = None

    def __post_init__(self) -> None:
        for attr, val in (
            ("snr_db", self.snr_db),
            ("repeatability_variance_db", self.repeatability_variance_db),
            ("calibration_uncertainty_db", self.calibration_uncertainty_db),
        ):
            if val is not None:
                if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
                    raise InvalidMeasurementError(f"{attr} must be a finite float, got {val!r}.")
                object.__setattr__(self, attr, float(val))

        if self.frequency_range_hz is not None:
            if not isinstance(self.frequency_range_hz, (tuple, list)) or len(self.frequency_range_hz) != 2:
                raise InvalidMeasurementError(f"frequency_range_hz must be a 2-tuple, got {self.frequency_range_hz!r}.")
            f_low, f_high = self.frequency_range_hz
            if not isinstance(f_low, (int, float)) or not isinstance(f_high, (int, float)) or f_low < 0 or f_low >= f_high:
                raise InvalidMeasurementError(f"Invalid frequency_range_hz: {self.frequency_range_hz!r}.")
            object.__setattr__(self, "frequency_range_hz", (float(f_low), float(f_high)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "snr_db": self.snr_db,
            "repeatability_variance_db": self.repeatability_variance_db,
            "calibration_uncertainty_db": self.calibration_uncertainty_db,
            "frequency_range_hz": list(self.frequency_range_hz) if self.frequency_range_hz else None,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MeasurementUncertainty:
        fr = data.get("frequency_range_hz")
        return cls(
            snr_db=data.get("snr_db"),
            repeatability_variance_db=data.get("repeatability_variance_db"),
            calibration_uncertainty_db=data.get("calibration_uncertainty_db"),
            frequency_range_hz=tuple(fr) if fr is not None else None,
        )


@dataclass(frozen=True, slots=True)
class MeasurementTransform:
    """Explicit record of a mathematical transform applied to raw measurement data.

    Enforces deep immutability of transform parameters to prevent post-hoc tampering.
    """
    transform_type: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.transform_type, str) or not self.transform_type.strip():
            raise InvalidMeasurementError(f"transform_type must be a non-empty string, got {self.transform_type!r}.")
        object.__setattr__(self, "transform_type", self.transform_type.strip())
        object.__setattr__(self, "parameters", _freeze_value(self.parameters))
        object.__setattr__(self, "rationale", str(self.rationale).strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "transform_type": self.transform_type,
            "parameters": _unfreeze_value(self.parameters),
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> MeasurementTransform:
        return cls(
            transform_type=data.get("transform_type", ""),
            parameters=dict(data.get("parameters", {})),
            rationale=data.get("rationale", ""),
        )


@dataclass(frozen=True, slots=True)
class ObservationEnvelope:
    """Scientific observation container wrapping raw FrequencyResponseData with acquisition context.

    Preserves raw data immutability, instrument identity, environment, uncertainty dimensions,
    and explicit transform history without asserting epistemic conclusions or production authority.
    Guarantees deep immutability across all nested dictionaries and sequence collections.
    """
    observation_id: str
    data: FrequencyResponseData
    source_reference: str
    source_format: str
    sensor_id: Optional[str] = None
    calibration_id: Optional[str] = None
    operator: Optional[str] = None
    microphone_distance_m: Optional[float] = None
    spl_calibration_offset_db: Optional[float] = None
    environmental_conditions: EnvironmentalConditions = field(default_factory=EnvironmentalConditions)
    uncertainty: MeasurementUncertainty = field(default_factory=MeasurementUncertainty)
    transforms: tuple[MeasurementTransform, ...] = ()
    provenance: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.observation_id, str) or not self.observation_id.strip():
            raise InvalidMeasurementError(f"observation_id must be a non-empty string, got {self.observation_id!r}.")
        object.__setattr__(self, "observation_id", self.observation_id.strip())

        if not isinstance(self.data, FrequencyResponseData):
            raise InvalidMeasurementError(f"data must be a FrequencyResponseData instance, got {type(self.data)!r}.")

        if not isinstance(self.source_reference, str) or not self.source_reference.strip():
            raise InvalidMeasurementError(f"source_reference must be a non-empty string, got {self.source_reference!r}.")
        object.__setattr__(self, "source_reference", self.source_reference.strip())

        if not isinstance(self.source_format, str) or not self.source_format.strip():
            raise InvalidMeasurementError(f"source_format must be a non-empty string, got {self.source_format!r}.")
        object.__setattr__(self, "source_format", self.source_format.strip())

        if self.sensor_id is not None:
            object.__setattr__(self, "sensor_id", str(self.sensor_id).strip())

        if self.calibration_id is not None:
            object.__setattr__(self, "calibration_id", str(self.calibration_id).strip())

        if self.operator is not None:
            object.__setattr__(self, "operator", str(self.operator).strip())

        if self.microphone_distance_m is not None:
            if not isinstance(self.microphone_distance_m, (int, float)) or isinstance(self.microphone_distance_m, bool) or not math.isfinite(self.microphone_distance_m) or self.microphone_distance_m <= 0:
                raise InvalidMeasurementError(f"microphone_distance_m must be a positive finite float, got {self.microphone_distance_m!r}.")
            object.__setattr__(self, "microphone_distance_m", float(self.microphone_distance_m))

        if self.spl_calibration_offset_db is not None:
            if not isinstance(self.spl_calibration_offset_db, (int, float)) or isinstance(self.spl_calibration_offset_db, bool) or not math.isfinite(self.spl_calibration_offset_db):
                raise InvalidMeasurementError(f"spl_calibration_offset_db must be a finite float, got {self.spl_calibration_offset_db!r}.")
            object.__setattr__(self, "spl_calibration_offset_db", float(self.spl_calibration_offset_db))

        if not isinstance(self.environmental_conditions, EnvironmentalConditions):
            raise InvalidMeasurementError(f"environmental_conditions must be EnvironmentalConditions, got {type(self.environmental_conditions)!r}.")

        if not isinstance(self.uncertainty, MeasurementUncertainty):
            raise InvalidMeasurementError(f"uncertainty must be MeasurementUncertainty, got {type(self.uncertainty)!r}.")

        if not isinstance(self.transforms, tuple):
            object.__setattr__(self, "transforms", tuple(self.transforms))

        object.__setattr__(self, "provenance", str(self.provenance).strip())
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "data": {
                "frequencies_hz": self.data.frequencies_hz.tolist(),
                "magnitude_db": self.data.magnitude_db.tolist(),
                "phase_rad": self.data.phase_rad.tolist() if self.data.phase_rad is not None else None,
            },
            "source_reference": self.source_reference,
            "source_format": self.source_format,
            "sensor_id": self.sensor_id,
            "calibration_id": self.calibration_id,
            "operator": self.operator,
            "microphone_distance_m": self.microphone_distance_m,
            "spl_calibration_offset_db": self.spl_calibration_offset_db,
            "environmental_conditions": self.environmental_conditions.to_dict(),
            "uncertainty": self.uncertainty.to_dict(),
            "transforms": [t.to_dict() for t in self.transforms],
            "provenance": self.provenance,
            "metadata": _unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ObservationEnvelope:
        raw_data = data["data"]
        freq_resp = FrequencyResponseData(
            frequencies_hz=raw_data["frequencies_hz"],
            magnitude_db=raw_data["magnitude_db"],
            phase_rad=raw_data.get("phase_rad"),
        )
        env = EnvironmentalConditions.from_dict(data.get("environmental_conditions", {}))
        unc = MeasurementUncertainty.from_dict(data.get("uncertainty", {}))
        transforms = tuple(MeasurementTransform.from_dict(t) for t in data.get("transforms", []))

        return cls(
            observation_id=data["observation_id"],
            data=freq_resp,
            source_reference=data["source_reference"],
            source_format=data["source_format"],
            sensor_id=data.get("sensor_id"),
            calibration_id=data.get("calibration_id"),
            operator=data.get("operator"),
            microphone_distance_m=data.get("microphone_distance_m"),
            spl_calibration_offset_db=data.get("spl_calibration_offset_db"),
            environmental_conditions=env,
            uncertainty=unc,
            transforms=transforms,
            provenance=data.get("provenance", ""),
            metadata=dict(data.get("metadata", {})),
        )


class ObservationRegistry:
    """Deterministic, auditable in-memory registry for scientific ObservationEnvelopes."""

    def __init__(self) -> None:
        self._observations: dict[str, ObservationEnvelope] = {}

    def register(self, observation: ObservationEnvelope) -> ObservationEnvelope:
        if not isinstance(observation, ObservationEnvelope):
            raise InvalidMeasurementError(f"Expected ObservationEnvelope, got {type(observation)!r}.")
        if observation.observation_id in self._observations:
            raise InvalidMeasurementError(f"Observation with id '{observation.observation_id}' is already registered.")
        self._observations[observation.observation_id] = observation
        return observation

    def get(self, observation_id: str) -> Optional[ObservationEnvelope]:
        return self._observations.get(observation_id)

    def list_all(self) -> tuple[ObservationEnvelope, ...]:
        return tuple(self._observations.values())

    def find_by_source(self, source_reference: str) -> tuple[ObservationEnvelope, ...]:
        return tuple(obs for obs in self._observations.values() if obs.source_reference == source_reference)

    def find_by_sensor(self, sensor_id: str) -> tuple[ObservationEnvelope, ...]:
        return tuple(obs for obs in self._observations.values() if obs.sensor_id == sensor_id)

    def clear(self) -> None:
        self._observations.clear()
