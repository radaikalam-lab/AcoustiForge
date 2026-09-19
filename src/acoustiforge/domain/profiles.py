"""AcoustiForge Acoustic Driver and Enclosure Profile Models.

Normative Authority:
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .specifications import TransducerLimits
from .validation import InvalidProfileError


class DriverRole(str, Enum):
    """Functional acoustic transducer passband role."""
    WOOFER = "woofer"
    MIDRANGE = "midrange"
    TWEETER = "tweeter"
    SUBWOOFER = "subwoofer"
    FULL_RANGE = "full_range"


@dataclass(frozen=True, slots=True)
class DriverProfile:
    """Immutable physical and acoustic profile of a loudspeaker driver."""
    name: str
    role: DriverRole
    sensitivity_db: float
    depth_offset_mm: float = 0.0
    polarity_inverted: bool = False
    nominal_impedance_ohms: Optional[float] = None
    limits: Optional[TransducerLimits] = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidProfileError(f"Driver profile name must be a non-empty string, got {self.name!r}.")
        object.__setattr__(self, "name", self.name.strip())

        if not isinstance(self.role, DriverRole):
            if isinstance(self.role, str):
                try:
                    object.__setattr__(self, "role", DriverRole(self.role.lower()))
                except ValueError as err:
                    raise InvalidProfileError(f"Unsupported driver role: {self.role!r}") from err
            else:
                raise InvalidProfileError(f"Driver role must be DriverRole enum or str, got {type(self.role)!r}.")

        if not isinstance(self.sensitivity_db, (int, float)) or isinstance(self.sensitivity_db, bool) or not math.isfinite(self.sensitivity_db):
            raise InvalidProfileError(f"sensitivity_db must be a finite float, got {self.sensitivity_db!r}.")
        object.__setattr__(self, "sensitivity_db", float(self.sensitivity_db))

        if not isinstance(self.depth_offset_mm, (int, float)) or isinstance(self.depth_offset_mm, bool) or not math.isfinite(self.depth_offset_mm):
            raise InvalidProfileError(f"depth_offset_mm must be a finite float, got {self.depth_offset_mm!r}.")
        object.__setattr__(self, "depth_offset_mm", float(self.depth_offset_mm))

        if not isinstance(self.polarity_inverted, bool):
            object.__setattr__(self, "polarity_inverted", bool(self.polarity_inverted))

        if self.nominal_impedance_ohms is not None:
            if not isinstance(self.nominal_impedance_ohms, (int, float)) or isinstance(self.nominal_impedance_ohms, bool) or not math.isfinite(self.nominal_impedance_ohms) or self.nominal_impedance_ohms <= 0.0:
                raise InvalidProfileError(f"nominal_impedance_ohms must be a positive finite float, got {self.nominal_impedance_ohms!r}.")
            object.__setattr__(self, "nominal_impedance_ohms", float(self.nominal_impedance_ohms))

        if self.limits is not None and not isinstance(self.limits, TransducerLimits):
            raise InvalidProfileError(f"limits must be a TransducerLimits instance, got {type(self.limits)!r}.")


class EnclosureType(str, Enum):
    """Acoustic enclosure alignment loading topology."""
    SEALED = "sealed"
    VENTED = "vented"
    BANDPASS = "bandpass"
    PASSIVE_RADIATOR = "passive_radiator"


@dataclass(frozen=True, slots=True)
class EnclosureProfile:
    """Immutable acoustic enclosure specification."""
    enclosure_type: EnclosureType
    volume_liters: float
    tuning_frequency_hz: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.enclosure_type, EnclosureType):
            if isinstance(self.enclosure_type, str):
                try:
                    object.__setattr__(self, "enclosure_type", EnclosureType(self.enclosure_type.lower()))
                except ValueError as err:
                    raise InvalidProfileError(f"Unsupported enclosure type: {self.enclosure_type!r}") from err
            else:
                raise InvalidProfileError(f"Enclosure type must be EnclosureType enum or str, got {type(self.enclosure_type)!r}.")

        if not isinstance(self.volume_liters, (int, float)) or isinstance(self.volume_liters, bool) or not math.isfinite(self.volume_liters) or self.volume_liters <= 0.0:
            raise InvalidProfileError(f"volume_liters must be a positive finite float, got {self.volume_liters!r}.")
        object.__setattr__(self, "volume_liters", float(self.volume_liters))

        if self.enclosure_type in (EnclosureType.VENTED, EnclosureType.BANDPASS, EnclosureType.PASSIVE_RADIATOR):
            if self.tuning_frequency_hz is None:
                raise InvalidProfileError(f"tuning_frequency_hz is required for {self.enclosure_type.value} enclosures.")
            if not isinstance(self.tuning_frequency_hz, (int, float)) or isinstance(self.tuning_frequency_hz, bool) or not math.isfinite(self.tuning_frequency_hz) or self.tuning_frequency_hz <= 0.0:
                raise InvalidProfileError(f"tuning_frequency_hz must be a positive finite float, got {self.tuning_frequency_hz!r}.")
            object.__setattr__(self, "tuning_frequency_hz", float(self.tuning_frequency_hz))
        else:
            if self.tuning_frequency_hz is not None:
                object.__setattr__(self, "tuning_frequency_hz", None)
