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


@dataclass(frozen=True, slots=True)
class OptimizationSpecification:
    """Immutable configuration and search bounds for multi-way system parameter optimization."""
    target_curve: AcousticTargetCurve
    crossover_family: CrossoverFamily
    crossover_order: int
    frequency_range_hz: tuple[float, float]
    crossover_bounds_hz: tuple[float, float]
    gain_bounds_db: tuple[float, float] = (-12.0, 12.0)
    delay_bounds_seconds: tuple[float, float] = (0.0, 0.005)
    ripple_weight: float = 0.0
    delay_weight: float = 0.0
    max_iterations: int = 50
    convergence_tolerance_db: float = 1e-5

    def __post_init__(self) -> None:
        if not isinstance(self.target_curve, AcousticTargetCurve):
            raise InvalidSpecificationError(
                f"target_curve must be an AcousticTargetCurve instance, got {type(self.target_curve)!r}."
            )

        if not isinstance(self.crossover_family, CrossoverFamily):
            if isinstance(self.crossover_family, str):
                try:
                    object.__setattr__(self, "crossover_family", CrossoverFamily(self.crossover_family.lower()))
                except ValueError as err:
                    raise InvalidSpecificationError(f"Unsupported crossover family: {self.crossover_family!r}") from err
            else:
                raise InvalidSpecificationError(
                    f"crossover_family must be CrossoverFamily enum or str, got {type(self.crossover_family)!r}."
                )

        if not isinstance(self.crossover_order, int) or isinstance(self.crossover_order, bool):
            raise InvalidSpecificationError(f"crossover_order must be an integer, got {self.crossover_order!r}.")

        if self.crossover_order not in (2, 4, 8):
            raise InvalidSpecificationError(
                f"Unsupported crossover order: {self.crossover_order}. Strictly supports 2nd, 4th, and 8th order."
            )

        if self.crossover_family == CrossoverFamily.LINKWITZ_RILEY and self.crossover_order % 2 != 0:
            raise InvalidSpecificationError("Linkwitz-Riley crossover order must be even.")

        # Validate frequency_range_hz
        if not isinstance(self.frequency_range_hz, (tuple, list)) or len(self.frequency_range_hz) != 2:
            raise InvalidSpecificationError("frequency_range_hz must be a tuple of 2 floats (f_min, f_max).")
        f_min, f_max = float(self.frequency_range_hz[0]), float(self.frequency_range_hz[1])
        if not math.isfinite(f_min) or not math.isfinite(f_max) or f_min <= 0.0 or f_max <= f_min:
            raise InvalidSpecificationError(
                f"frequency_range_hz must satisfy 0 < f_min < f_max, got ({f_min}, {f_max})."
            )
        object.__setattr__(self, "frequency_range_hz", (f_min, f_max))

        # Validate crossover_bounds_hz
        if not isinstance(self.crossover_bounds_hz, (tuple, list)) or len(self.crossover_bounds_hz) != 2:
            raise InvalidSpecificationError("crossover_bounds_hz must be a tuple of 2 floats (fc_min, fc_max).")
        fc_min, fc_max = float(self.crossover_bounds_hz[0]), float(self.crossover_bounds_hz[1])
        if not math.isfinite(fc_min) or not math.isfinite(fc_max) or fc_min <= 0.0 or fc_max <= fc_min:
            raise InvalidSpecificationError(
                f"crossover_bounds_hz must satisfy 0 < fc_min < fc_max, got ({fc_min}, {fc_max})."
            )
        object.__setattr__(self, "crossover_bounds_hz", (fc_min, fc_max))

        # Validate gain_bounds_db
        if not isinstance(self.gain_bounds_db, (tuple, list)) or len(self.gain_bounds_db) != 2:
            raise InvalidSpecificationError("gain_bounds_db must be a tuple of 2 floats (g_min, g_max).")
        g_min, g_max = float(self.gain_bounds_db[0]), float(self.gain_bounds_db[1])
        if not math.isfinite(g_min) or not math.isfinite(g_max) or g_max <= g_min:
            raise InvalidSpecificationError(
                f"gain_bounds_db must satisfy g_min < g_max, got ({g_min}, {g_max})."
            )
        object.__setattr__(self, "gain_bounds_db", (g_min, g_max))

        # Validate delay_bounds_seconds
        if not isinstance(self.delay_bounds_seconds, (tuple, list)) or len(self.delay_bounds_seconds) != 2:
            raise InvalidSpecificationError("delay_bounds_seconds must be a tuple of 2 floats (d_min, d_max).")
        d_min, d_max = float(self.delay_bounds_seconds[0]), float(self.delay_bounds_seconds[1])
        if not math.isfinite(d_min) or not math.isfinite(d_max) or d_min < 0.0 or d_max <= d_min:
            raise InvalidSpecificationError(
                f"delay_bounds_seconds must satisfy 0 <= d_min < d_max, got ({d_min}, {d_max})."
            )
        object.__setattr__(self, "delay_bounds_seconds", (d_min, d_max))

        # Weights & optimization settings
        for name, val in [("ripple_weight", self.ripple_weight), ("delay_weight", self.delay_weight)]:
            if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val) or val < 0.0:
                raise InvalidSpecificationError(f"{name} must be a non-negative finite float, got {val!r}.")
            object.__setattr__(self, name, float(val))

        if not isinstance(self.max_iterations, int) or isinstance(self.max_iterations, bool) or self.max_iterations < 1:
            raise InvalidSpecificationError(f"max_iterations must be an integer >= 1, got {self.max_iterations!r}.")

        if (
            not isinstance(self.convergence_tolerance_db, (int, float))
            or isinstance(self.convergence_tolerance_db, bool)
            or not math.isfinite(self.convergence_tolerance_db)
            or self.convergence_tolerance_db <= 0.0
        ):
            raise InvalidSpecificationError(
                f"convergence_tolerance_db must be a positive finite float, got {self.convergence_tolerance_db!r}."
            )
        object.__setattr__(self, "convergence_tolerance_db", float(self.convergence_tolerance_db))


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    """Immutable result container for multi-way system parameter optimization.

    Normative Authority:
    - docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
    """
    crossover_result: any  # CrossoverSynthesisResult | tuple[CrossoverSynthesisResult, CrossoverSynthesisResult]
    gain_results: dict[str, any]  # dict[str, GainDesignResult]
    alignment_results: dict[str, any]  # dict[str, DriverAlignmentResult]
    predicted_response: any  # FrequencyResponseData
    initial_metrics: any  # AcousticMetricsResult
    optimized_metrics: any  # AcousticMetricsResult
    initial_loss_db: float
    final_loss_db: float
    converged: bool
    iterations_completed: int

    def __post_init__(self) -> None:
        from ..acoustic_math.alignment import DriverAlignmentResult
        from ..acoustic_math.crossover import CrossoverSynthesisResult
        from ..acoustic_math.metrics import AcousticMetricsResult
        from ..acoustic_math.sensitivity import GainDesignResult
        from .measurements import FrequencyResponseData

        # 1. Validate crossover_result
        if isinstance(self.crossover_result, CrossoverSynthesisResult):
            pass
        elif isinstance(self.crossover_result, (tuple, list)) and len(self.crossover_result) == 2:
            x_low, x_high = self.crossover_result
            if not isinstance(x_low, CrossoverSynthesisResult) or not isinstance(x_high, CrossoverSynthesisResult):
                raise InvalidSpecificationError(
                    "3-Way crossover_result must be a tuple of (CrossoverSynthesisResult, CrossoverSynthesisResult)."
                )
            if x_high.crossover_frequency_hz < 1.5 * x_low.crossover_frequency_hz:
                raise InvalidSpecificationError(
                    f"3-Way crossover constraint violated: f_high ({x_high.crossover_frequency_hz:.1f} Hz) "
                    f"must be >= 1.5 * f_low ({x_low.crossover_frequency_hz:.1f} Hz)."
                )
            if x_low.sample_rate != x_high.sample_rate:
                raise InvalidSpecificationError(
                    f"3-Way crossover sample rates mismatch: {x_low.sample_rate} Hz vs {x_high.sample_rate} Hz."
                )
            object.__setattr__(self, "crossover_result", (x_low, x_high))
        else:
            raise InvalidSpecificationError(
                f"crossover_result must be CrossoverSynthesisResult or tuple of 2 CrossoverSynthesisResults, got {type(self.crossover_result)!r}."
            )

        # 2. Validate gain_results
        if not hasattr(self.gain_results, "items"):
            raise InvalidSpecificationError("gain_results must be a Mapping of driver names to GainDesignResult.")
        g_dict = {}
        for k, v in self.gain_results.items():
            if not isinstance(k, str) or not k.strip():
                raise InvalidSpecificationError(f"gain_results driver name must be non-empty string, got {k!r}.")
            if not isinstance(v, GainDesignResult):
                raise InvalidSpecificationError(f"gain_results[{k!r}] must be GainDesignResult, got {type(v)!r}.")
            g_dict[k.strip()] = v
        object.__setattr__(self, "gain_results", g_dict)

        # 3. Validate alignment_results
        if not hasattr(self.alignment_results, "items"):
            raise InvalidSpecificationError("alignment_results must be a Mapping of driver names to DriverAlignmentResult.")
        a_dict = {}
        for k, v in self.alignment_results.items():
            if not isinstance(k, str) or not k.strip():
                raise InvalidSpecificationError(f"alignment_results driver name must be non-empty string, got {k!r}.")
            if not isinstance(v, DriverAlignmentResult):
                raise InvalidSpecificationError(f"alignment_results[{k!r}] must be DriverAlignmentResult, got {type(v)!r}.")
            a_dict[k.strip()] = v
        object.__setattr__(self, "alignment_results", a_dict)

        # 4. Validate predicted_response
        if not isinstance(self.predicted_response, FrequencyResponseData):
            raise InvalidSpecificationError(
                f"predicted_response must be FrequencyResponseData, got {type(self.predicted_response)!r}."
            )

        # 5. Validate metrics
        if not isinstance(self.initial_metrics, AcousticMetricsResult):
            raise InvalidSpecificationError(
                f"initial_metrics must be AcousticMetricsResult, got {type(self.initial_metrics)!r}."
            )
        if not isinstance(self.optimized_metrics, AcousticMetricsResult):
            raise InvalidSpecificationError(
                f"optimized_metrics must be AcousticMetricsResult, got {type(self.optimized_metrics)!r}."
            )

        # 6. Validate losses & monotonicity
        if not isinstance(self.initial_loss_db, (int, float)) or isinstance(self.initial_loss_db, bool) or not math.isfinite(self.initial_loss_db):
            raise InvalidSpecificationError(f"initial_loss_db must be a finite float, got {self.initial_loss_db!r}.")
        if not isinstance(self.final_loss_db, (int, float)) or isinstance(self.final_loss_db, bool) or not math.isfinite(self.final_loss_db):
            raise InvalidSpecificationError(f"final_loss_db must be a finite float, got {self.final_loss_db!r}.")

        init_l = float(self.initial_loss_db)
        fin_l = float(self.final_loss_db)
        if fin_l > init_l + 1e-12:
            raise InvalidSpecificationError(
                f"Monotonicity invariant violated: final_loss_db ({fin_l:.6f}) > initial_loss_db ({init_l:.6f})."
            )
        object.__setattr__(self, "initial_loss_db", init_l)
        object.__setattr__(self, "final_loss_db", fin_l)

        # 7. Validate converged & iterations
        if not isinstance(self.converged, bool):
            raise InvalidSpecificationError(f"converged must be a bool, got {type(self.converged)!r}.")
        if not isinstance(self.iterations_completed, int) or isinstance(self.iterations_completed, bool) or self.iterations_completed < 0:
            raise InvalidSpecificationError(f"iterations_completed must be an integer >= 0, got {self.iterations_completed!r}.")
