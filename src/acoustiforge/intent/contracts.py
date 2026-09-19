"""AcoustiForge AI Design-Intent Value Objects and Contracts.

Defines high-level semantic intent objects representing user and AI design desires
prior to deterministic validation and compilation into Core specifications.

Normative Authority:
- docs/architecture/PHASE_5_0_ADAPTIVE_ACOUSTIC_ARCHITECTURE_DISCOVERY.md
- docs/architecture/PHASE_5_1_EXTENSION_SELECTION_AND_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence, Union

from ..contracts.validation import (
    AcoustiForgeError,
    InvalidParameterError,
)
from ..domain.validation import InvalidSpecificationError
from ..domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    OptimizationSpecification,
)
from ..extensions.spatial_optimization import (
    MultiPositionOptimizationSpecification,
    SpatialMeasurementPosition,
)


# ==============================================================================
# Intent Exceptions
# ==============================================================================

class IntentValidationError(InvalidParameterError):
    """Raised when an untrusted AI or user DesignIntent fails validation."""


class UnsupportedIntentError(IntentValidationError):
    """Raised when an intent requests a capability or preset not supported by Core."""


# ==============================================================================
# Intent Component Dataclasses
# ==============================================================================

@dataclass(frozen=True, slots=True)
class TargetCurveIntent:
    """High-level semantic intent for target frequency response curve.

    Attributes:
        preset_name: Named target curve preset (e.g., 'flat'). Unsupported presets are rejected.
        points: Custom discrete target coordinate points ((freq_hz, mag_db), ...).
        target_spl_db: Base target SPL level for flat curve synthesis (default: 85.0 dB).
    """
    preset_name: Optional[str] = "flat"
    points: Optional[tuple[tuple[float, float], ...]] = None
    target_spl_db: float = 85.0

    def __post_init__(self) -> None:
        if self.preset_name is not None and not isinstance(self.preset_name, str):
            raise IntentValidationError(f"preset_name must be a string or None, got {type(self.preset_name)!r}.")

        if not isinstance(self.target_spl_db, (int, float)) or isinstance(self.target_spl_db, bool) or not math.isfinite(self.target_spl_db):
            raise IntentValidationError(f"target_spl_db must be a finite float, got {self.target_spl_db!r}.")

        if self.points is not None:
            if not isinstance(self.points, (tuple, list)) or len(self.points) < 2:
                raise IntentValidationError("Custom target points must contain at least 2 coordinate pairs.")
            validated_pts = []
            for pt in self.points:
                if not isinstance(pt, (tuple, list)) or len(pt) != 2:
                    raise IntentValidationError(f"Each point must be a (freq_hz, mag_db) tuple, got {pt!r}.")
                f, m = float(pt[0]), float(pt[1])
                if not math.isfinite(f) or not math.isfinite(m) or f <= 0.0:
                    raise IntentValidationError(f"Point frequencies must be positive finite floats, got ({f}, {m}).")
                validated_pts.append((f, m))
            object.__setattr__(self, "points", tuple(validated_pts))

        object.__setattr__(self, "target_spl_db", float(self.target_spl_db))
        if self.preset_name is not None:
            object.__setattr__(self, "preset_name", self.preset_name.strip().lower())


@dataclass(frozen=True, slots=True)
class TonalBalanceIntent:
    """High-level semantic tonal modifiers (warmth, brightness, shelf, tilt).

    All modifications are mapped deterministically into target curve anchor points;
    they do not alter the deterministic Core optimizer algorithm.
    """
    warmth_db: float = 0.0
    brightness_db: float = 0.0
    low_shelf_db: float = 0.0
    high_shelf_db: float = 0.0
    tilt_db_per_octave: float = 0.0

    def __post_init__(self) -> None:
        for name, val in [
            ("warmth_db", self.warmth_db),
            ("brightness_db", self.brightness_db),
            ("low_shelf_db", self.low_shelf_db),
            ("high_shelf_db", self.high_shelf_db),
            ("tilt_db_per_octave", self.tilt_db_per_octave),
        ]:
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
                raise IntentValidationError(f"{name} must be a finite float, got {val!r}.")
            # Sanity bound check on extreme values
            if abs(float(val)) > 24.0:
                raise IntentValidationError(f"{name} magnitude {val} dB exceeds safety envelope (±24 dB).")
            object.__setattr__(self, name, float(val))


@dataclass(frozen=True, slots=True)
class CrossoverIntent:
    """High-level user preference for multi-way crossover topology and search region."""
    family: Optional[CrossoverFamily] = None
    order: Optional[int] = None
    target_frequency_hz: Optional[float] = None
    search_band_hz: Optional[tuple[float, float]] = None

    def __post_init__(self) -> None:
        if self.family is not None:
            if isinstance(self.family, str):
                try:
                    object.__setattr__(self, "family", CrossoverFamily(self.family.lower()))
                except ValueError as err:
                    raise IntentValidationError(f"Unsupported crossover family: {self.family!r}") from err
            elif not isinstance(self.family, CrossoverFamily):
                raise IntentValidationError(f"family must be CrossoverFamily or str, got {type(self.family)!r}.")

        if self.order is not None:
            if not isinstance(self.order, int) or isinstance(self.order, bool):
                raise IntentValidationError(f"crossover order must be an integer, got {self.order!r}.")
            if self.order not in (2, 4, 8):
                raise IntentValidationError(f"Unsupported crossover order {self.order}. Must be 2, 4, or 8.")

        if self.target_frequency_hz is not None:
            if not isinstance(self.target_frequency_hz, (int, float)) or isinstance(self.target_frequency_hz, bool) or not math.isfinite(self.target_frequency_hz) or self.target_frequency_hz <= 0.0:
                raise IntentValidationError(f"target_frequency_hz must be positive finite float, got {self.target_frequency_hz!r}.")
            object.__setattr__(self, "target_frequency_hz", float(self.target_frequency_hz))

        if self.search_band_hz is not None:
            if not isinstance(self.search_band_hz, (tuple, list)) or len(self.search_band_hz) != 2:
                raise IntentValidationError("search_band_hz must be a tuple of 2 floats (fc_min, fc_max).")
            fc_min, fc_max = float(self.search_band_hz[0]), float(self.search_band_hz[1])
            if not math.isfinite(fc_min) or not math.isfinite(fc_max) or fc_min <= 0.0 or fc_max <= fc_min:
                raise IntentValidationError(f"search_band_hz must satisfy 0 < fc_min < fc_max, got ({fc_min}, {fc_max}).")
            object.__setattr__(self, "search_band_hz", (fc_min, fc_max))


@dataclass(frozen=True, slots=True)
class SpatialIntent:
    """High-level semantic intent for listening position prioritization (Track C)."""
    profile_name: str = "single_position"
    positions: Optional[tuple[SpatialMeasurementPosition, ...]] = None
    weights: Optional[tuple[float, ...]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.profile_name, str) or not self.profile_name.strip():
            raise IntentValidationError(f"profile_name must be a non-empty string, got {self.profile_name!r}.")
        object.__setattr__(self, "profile_name", self.profile_name.strip().lower())

        if self.positions is not None:
            if not isinstance(self.positions, (tuple, list)) or len(self.positions) == 0:
                raise IntentValidationError("positions must be a non-empty sequence if provided.")
            for pos in self.positions:
                if not isinstance(pos, SpatialMeasurementPosition):
                    raise IntentValidationError(f"Expected SpatialMeasurementPosition, got {type(pos)!r}.")
            object.__setattr__(self, "positions", tuple(self.positions))

        if self.weights is not None:
            if not isinstance(self.weights, (tuple, list)) or len(self.weights) == 0:
                raise IntentValidationError("weights must be a non-empty sequence of positive floats.")
            for w in self.weights:
                if not isinstance(w, (int, float)) or isinstance(w, bool) or not math.isfinite(w) or w < 0.0:
                    raise IntentValidationError(f"Position weights must be non-negative finite floats, got {w!r}.")
            object.__setattr__(self, "weights", tuple(float(w) for w in self.weights))


@dataclass(frozen=True, slots=True)
class ConstraintIntent:
    """Constraints and bounds mapped directly to supported Core specification fields."""
    frequency_range_hz: Optional[tuple[float, float]] = None
    gain_bounds_db: Optional[tuple[float, float]] = None
    delay_bounds_seconds: Optional[tuple[float, float]] = None
    ripple_weight: Optional[float] = None
    delay_weight: Optional[float] = None
    max_iterations: Optional[int] = None
    convergence_tolerance_db: Optional[float] = None

    def __post_init__(self) -> None:
        if self.frequency_range_hz is not None:
            if not isinstance(self.frequency_range_hz, (tuple, list)) or len(self.frequency_range_hz) != 2:
                raise IntentValidationError("frequency_range_hz must be (f_min, f_max).")
            f_min, f_max = float(self.frequency_range_hz[0]), float(self.frequency_range_hz[1])
            if not math.isfinite(f_min) or not math.isfinite(f_max) or f_min <= 0.0 or f_max <= f_min:
                raise IntentValidationError(f"frequency_range_hz must satisfy 0 < f_min < f_max, got ({f_min}, {f_max}).")
            object.__setattr__(self, "frequency_range_hz", (f_min, f_max))

        if self.gain_bounds_db is not None:
            if not isinstance(self.gain_bounds_db, (tuple, list)) or len(self.gain_bounds_db) != 2:
                raise IntentValidationError("gain_bounds_db must be (g_min, g_max).")
            g_min, g_max = float(self.gain_bounds_db[0]), float(self.gain_bounds_db[1])
            if not math.isfinite(g_min) or not math.isfinite(g_max) or g_max <= g_min:
                raise IntentValidationError(f"gain_bounds_db must satisfy g_min < g_max, got ({g_min}, {g_max}).")
            object.__setattr__(self, "gain_bounds_db", (g_min, g_max))

        if self.delay_bounds_seconds is not None:
            if not isinstance(self.delay_bounds_seconds, (tuple, list)) or len(self.delay_bounds_seconds) != 2:
                raise IntentValidationError("delay_bounds_seconds must be (d_min, d_max).")
            d_min, d_max = float(self.delay_bounds_seconds[0]), float(self.delay_bounds_seconds[1])
            if not math.isfinite(d_min) or not math.isfinite(d_max) or d_min < 0.0 or d_max <= d_min:
                raise IntentValidationError(f"delay_bounds_seconds must satisfy 0 <= d_min < d_max, got ({d_min}, {d_max}).")
            object.__setattr__(self, "delay_bounds_seconds", (d_min, d_max))

        for name, val in [("ripple_weight", self.ripple_weight), ("delay_weight", self.delay_weight)]:
            if val is not None:
                if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < 0.0:
                    raise IntentValidationError(f"{name} must be non-negative float, got {val!r}.")
                object.__setattr__(self, name, float(val))

        if self.max_iterations is not None:
            if not isinstance(self.max_iterations, int) or isinstance(self.max_iterations, bool) or self.max_iterations < 1:
                raise IntentValidationError(f"max_iterations must be integer >= 1, got {self.max_iterations!r}.")

        if self.convergence_tolerance_db is not None:
            if not isinstance(self.convergence_tolerance_db, (int, float)) or isinstance(self.convergence_tolerance_db, bool) or not math.isfinite(self.convergence_tolerance_db) or self.convergence_tolerance_db <= 0.0:
                raise IntentValidationError(f"convergence_tolerance_db must be positive float, got {self.convergence_tolerance_db!r}.")
            object.__setattr__(self, "convergence_tolerance_db", float(self.convergence_tolerance_db))


# ==============================================================================
# Top-Level Design Intent Container
# ==============================================================================

@dataclass(frozen=True, slots=True)
class DesignIntent:
    """Top-level immutable user/AI design intent proposal object.

    Represents what the user or AI proposes to accomplish, cleanly decoupled from
    the deterministic OptimizationSpecification executed by AcoustiForge Core.
    """
    intent_id: str
    query_text: str
    target_curve: TargetCurveIntent = field(default_factory=TargetCurveIntent)
    tonal_balance: TonalBalanceIntent = field(default_factory=TonalBalanceIntent)
    crossover: CrossoverIntent = field(default_factory=CrossoverIntent)
    spatial: SpatialIntent = field(default_factory=SpatialIntent)
    constraints: ConstraintIntent = field(default_factory=ConstraintIntent)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.intent_id, str) or not self.intent_id.strip():
            raise IntentValidationError(f"intent_id must be a non-empty string, got {self.intent_id!r}.")
        if not isinstance(self.query_text, str):
            raise IntentValidationError(f"query_text must be a string, got {type(self.query_text)!r}.")

        object.__setattr__(self, "intent_id", self.intent_id.strip())
        object.__setattr__(self, "query_text", self.query_text.strip())


# ==============================================================================
# Audit & Translation Record
# ==============================================================================

@dataclass(frozen=True, slots=True)
class IntentTranslationRecord:
    """Structured audit record of intent proposal, validation, and Core translation.

    Provides complete explainability for what was requested, validated, accepted,
    and translated into the authoritative Core specification.
    """
    intent_id: str
    query_text: str
    validation_status: str  # "ACCEPTED", "REJECTED", "MODIFIED"
    accepted_items: tuple[str, ...]
    rejected_items: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    specification: Optional[Union[OptimizationSpecification, MultiPositionOptimizationSpecification]] = None
    result_reference: Optional[str] = None
