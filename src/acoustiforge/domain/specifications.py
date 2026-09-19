"""AcoustiForge Acoustic Specification and Budget Value Objects.

Normative Authority:
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from .validation import (
    InvalidSpecificationError,
    validate_target_points,
)


class CrossoverFamily(str, Enum):
    """Canonical filter alignment families for acoustic crossovers."""
    LINKWITZ_RILEY = "linkwitz_riley"
    BUTTERWORTH = "butterworth"


@dataclass(frozen=True, slots=True)
class CrossoverSpecification:
    """Immutable specification for an acoustic crossover filter stage."""
    family: CrossoverFamily
    order: int
    frequency_hz: float

    def __post_init__(self) -> None:
        if not isinstance(self.family, CrossoverFamily):
            if isinstance(self.family, str):
                try:
                    object.__setattr__(self, "family", CrossoverFamily(self.family.lower()))
                except ValueError as err:
                    raise InvalidSpecificationError(f"Unsupported crossover family: {self.family!r}") from err
            else:
                raise InvalidSpecificationError(f"Crossover family must be CrossoverFamily enum or str, got {type(self.family)!r}.")

        if not isinstance(self.order, int) or isinstance(self.order, bool):
            raise InvalidSpecificationError(f"Crossover order must be an integer, got {self.order!r}.")

        if self.order not in (2, 4, 8):
            raise InvalidSpecificationError(
                f"Unsupported crossover order: {self.order}. Phase 3 strictly supports 2nd, 4th, and 8th order."
            )

        if self.family == CrossoverFamily.LINKWITZ_RILEY and self.order % 2 != 0:
            raise InvalidSpecificationError("Linkwitz-Riley crossover order must be even.")

        if not isinstance(self.frequency_hz, (int, float)) or isinstance(self.frequency_hz, bool) or not math.isfinite(self.frequency_hz) or self.frequency_hz <= 0.0:
            raise InvalidSpecificationError(f"Crossover frequency must be a positive finite number in Hz, got {self.frequency_hz!r}.")

        object.__setattr__(self, "frequency_hz", float(self.frequency_hz))


@dataclass(frozen=True, slots=True)
class AcousticTargetCurve:
    """Immutable acoustic target frequency response curve data container."""
    name: str
    points: tuple[tuple[float, float], ...]

    def __init__(self, name: str, points: Sequence[tuple[float, float]]) -> None:
        if not isinstance(name, str) or not name.strip():
            raise InvalidSpecificationError(f"Target curve name must be a non-empty string, got {name!r}.")

        validated_points = validate_target_points(points)
        object.__setattr__(self, "name", name.strip())
        object.__setattr__(self, "points", validated_points)

    @property
    def frequencies(self) -> tuple[float, ...]:
        """Tuple of discrete target curve frequencies in Hz."""
        return tuple(pt[0] for pt in self.points)

    @property
    def magnitudes_db(self) -> tuple[float, ...]:
        """Tuple of discrete target curve magnitudes in dB."""
        return tuple(pt[1] for pt in self.points)

    @property
    def num_points(self) -> int:
        """Number of discrete coordinate points defining the target curve."""
        return len(self.points)


@dataclass(frozen=True, slots=True)
class EqualizerBudget:
    """Immutable budget and constraints for parametric equalizer synthesis."""
    max_bands: int
    max_boost_db: float = 6.0
    max_cut_db: float = 12.0
    min_q: float = 0.5
    max_q: float = 10.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_bands, int) or isinstance(self.max_bands, bool) or self.max_bands < 1:
            raise InvalidSpecificationError(f"max_bands must be an integer >= 1, got {self.max_bands!r}.")

        for param_name, val, min_val in [
            ("max_boost_db", self.max_boost_db, 0.0),
            ("max_cut_db", self.max_cut_db, 0.0),
            ("min_q", self.min_q, 0.01),
        ]:
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < min_val:
                raise InvalidSpecificationError(f"{param_name} must be a finite float >= {min_val}, got {val!r}.")

        if not isinstance(self.max_q, (int, float)) or isinstance(self.max_q, bool) or not math.isfinite(self.max_q) or self.max_q < self.min_q:
            raise InvalidSpecificationError(f"max_q must be a finite float >= min_q ({self.min_q}), got {self.max_q!r}.")

        object.__setattr__(self, "max_boost_db", float(self.max_boost_db))
        object.__setattr__(self, "max_cut_db", float(self.max_cut_db))
        object.__setattr__(self, "min_q", float(self.min_q))
        object.__setattr__(self, "max_q", float(self.max_q))


@dataclass(frozen=True, slots=True)
class TransducerLimits:
    """Immutable physical electrical and mechanical operational limits of a loudspeaker driver."""
    x_max_mm: float
    p_max_rms_watts: float
    f_s_hz: float
    r_e_ohms: float

    def __post_init__(self) -> None:
        for param_name, val in [
            ("x_max_mm", self.x_max_mm),
            ("p_max_rms_watts", self.p_max_rms_watts),
            ("f_s_hz", self.f_s_hz),
            ("r_e_ohms", self.r_e_ohms),
        ]:
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val <= 0.0:
                raise InvalidSpecificationError(f"Transducer limit '{param_name}' must be a positive finite float, got {val!r}.")
            object.__setattr__(self, param_name, float(val))
