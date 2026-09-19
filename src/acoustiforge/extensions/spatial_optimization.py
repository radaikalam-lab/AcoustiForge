"""AcoustiForge Multi-Position Spatial Optimization Extension (Track C).

Composes the frozen Phase 4 Core deterministic forward model, objective evaluation,
and coordinate descent optimizer across multiple spatial measurement positions.

Normative Authority:
- docs/architecture/PHASE_5_1_EXTENSION_SELECTION_AND_DISCOVERY.md
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Mapping, Optional, Sequence, Union
import numpy as np

from ..acoustic_math.alignment import DEFAULT_SPEED_OF_SOUND_MPS, DriverAlignmentResult
from ..acoustic_math.crossover import CrossoverSynthesisResult, synthesize_crossover_biquads
from ..acoustic_math.metrics import AcousticMetricsResult, calculate_response_metrics
from ..acoustic_math.optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    coordinate_descent_search,
    evaluate_acoustic_target_loss,
    is_candidate_better,
    validate_frequency_grid_matching,
)
from ..acoustic_math.sensitivity import GainDesignResult
from ..contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
    NumericalEvaluationError,
)
from ..domain.measurements import FrequencyResponseData
from ..domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    OptimizationResult,
)
from ..domain.validation import InvalidSpecificationError


# ==============================================================================
# Domain Value Objects
# ==============================================================================

@dataclass(frozen=True, slots=True)
class SpatialMeasurementPosition:
    """Immutable measurement dataset captured at a single discrete spatial location.

    Attributes:
        name: Non-empty identifier for the spatial position (e.g., 'Listening_Position_1', 'Left', 'Center').
        driver_responses: Mapping of driver/branch identifiers to FrequencyResponseData measurements.
        coordinates: Optional (x, y, z) spatial coordinates in meters relative to reference.
    """
    name: str
    driver_responses: dict[str, FrequencyResponseData]
    coordinates: Optional[tuple[float, float, float]] = None

    def __init__(
        self,
        name: str,
        driver_responses: Mapping[str, FrequencyResponseData],
        coordinates: Optional[tuple[float, float, float]] = None,
    ) -> None:
        if not isinstance(name, str) or not name.strip():
            raise InvalidSpecificationError(f"Position name must be a non-empty string, got {name!r}.")

        if not hasattr(driver_responses, "items") or len(driver_responses) == 0:
            raise InvalidSpecificationError("driver_responses must be a non-empty mapping of driver names to FrequencyResponseData.")

        validated_drivers: dict[str, FrequencyResponseData] = {}
        for d_name, d_resp in driver_responses.items():
            if not isinstance(d_name, str) or not d_name.strip():
                raise InvalidSpecificationError(f"Driver name in spatial position must be non-empty string, got {d_name!r}.")
            if not isinstance(d_resp, FrequencyResponseData):
                raise InvalidSpecificationError(
                    f"Driver response for {d_name!r} must be FrequencyResponseData instance, got {type(d_resp)!r}."
                )
            validated_drivers[d_name.strip()] = d_resp

        if coordinates is not None:
            if not isinstance(coordinates, (tuple, list)) or len(coordinates) != 3:
                raise InvalidSpecificationError("coordinates must be a 3-element tuple/list of floats (x, y, z).")
            for c_val in coordinates:
                if not isinstance(c_val, (int, float)) or isinstance(c_val, bool) or not math.isfinite(c_val):
                    raise InvalidSpecificationError(f"coordinates must contain finite floats, got {c_val!r}.")
            object.__setattr__(self, "coordinates", (float(coordinates[0]), float(coordinates[1]), float(coordinates[2])))
        else:
            object.__setattr__(self, "coordinates", None)

        object.__setattr__(self, "name", name.strip())
        object.__setattr__(self, "driver_responses", validated_drivers)

    @property
    def driver_names(self) -> tuple[str, ...]:
        """Return tuple of driver names present in this position."""
        return tuple(self.driver_responses.keys())


@dataclass(frozen=True, slots=True)
class MultiPositionOptimizationSpecification:
    """Immutable specification for multi-position spatial acoustic optimization.

    Attributes:
        positions: Tuple of SpatialMeasurementPosition objects (minimum 1).
        spatial_weights: Tuple of non-negative weights summing to 1.0 (length matches positions).
        target_curve: AcousticTargetCurve value object.
        crossover_family: Crossover filter family (LINKWITZ_RILEY or BUTTERWORTH).
        crossover_order: Crossover filter order (2, 4, or 8).
        frequency_range_hz: Active optimization passband (f_min, f_max) in Hz.
        crossover_bounds_hz: Crossover frequency search bounds (fc_min, fc_max) in Hz.
        gain_bounds_db: Branch gain search bounds (g_min, g_max) in dB.
        delay_bounds_seconds: Branch delay search bounds (d_min, d_max) in seconds.
        ripple_weight: Passband ripple penalty weight.
        delay_weight: Delay regularization penalty weight.
        sample_rate: System audio sampling rate in Hz.
        driver_order: Optional explicit ordering of driver branch identifiers.
        max_iterations: Maximum coordinate descent search cycles.
        convergence_tolerance_db: Loss reduction threshold for convergence.
        golden_iterations: Line search iteration budget per coordinate.
    """
    positions: tuple[SpatialMeasurementPosition, ...]
    spatial_weights: tuple[float, ...]
    target_curve: AcousticTargetCurve
    crossover_family: CrossoverFamily
    crossover_order: int
    frequency_range_hz: tuple[float, float]
    crossover_bounds_hz: tuple[float, float]
    gain_bounds_db: tuple[float, float] = (-12.0, 12.0)
    delay_bounds_seconds: tuple[float, float] = (0.0, 0.005)
    ripple_weight: float = 0.0
    delay_weight: float = 0.0
    sample_rate: int = 48000
    driver_order: Optional[tuple[str, ...]] = None
    max_iterations: int = 50
    convergence_tolerance_db: float = 1e-5
    golden_iterations: int = 20

    def __post_init__(self) -> None:
        # 1. Validate positions sequence
        if not isinstance(self.positions, (tuple, list)) or len(self.positions) == 0:
            raise InvalidSpecificationError("positions must be a non-empty sequence of SpatialMeasurementPosition.")

        pos_list = []
        seen_names = set()
        for idx, pos in enumerate(self.positions):
            if not isinstance(pos, SpatialMeasurementPosition):
                raise InvalidSpecificationError(f"Expected SpatialMeasurementPosition at index {idx}, got {type(pos)!r}.")
            if pos.name in seen_names:
                raise InvalidSpecificationError(f"Duplicate spatial position name: {pos.name!r}.")
            seen_names.add(pos.name)
            pos_list.append(pos)
        object.__setattr__(self, "positions", tuple(pos_list))

        # 2. Validate spatial weights
        if not isinstance(self.spatial_weights, (tuple, list)):
            raise InvalidSpecificationError("spatial_weights must be a sequence of floats.")
        if len(self.spatial_weights) != len(self.positions):
            raise InvalidSpecificationError(
                f"spatial_weights count ({len(self.spatial_weights)}) must match positions count ({len(self.positions)})."
            )

        validated_weights = []
        for idx, w in enumerate(self.spatial_weights):
            if not isinstance(w, (int, float)) or isinstance(w, bool) or not math.isfinite(w):
                raise InvalidSpecificationError(f"Spatial weight at index {idx} must be a finite float, got {w!r}.")
            if w < 0.0:
                raise InvalidSpecificationError(f"Spatial weight at index {idx} cannot be negative, got {w!r}.")
            validated_weights.append(float(w))

        weight_sum = sum(validated_weights)
        if not math.isclose(weight_sum, 1.0, abs_tol=1e-6):
            raise InvalidSpecificationError(
                f"Spatial weights must sum to 1.0 (tolerance 1e-6), got sum = {weight_sum:.8f}."
            )
        object.__setattr__(self, "spatial_weights", tuple(validated_weights))

        # 3. Validate driver order & topology consistency across all positions
        ref_drivers = self.positions[0].driver_names
        if self.driver_order is not None:
            if not isinstance(self.driver_order, (tuple, list)) or len(self.driver_order) == 0:
                raise InvalidSpecificationError("driver_order must be a non-empty sequence of driver name strings.")
            d_order = tuple(str(d).strip() for d in self.driver_order)
            if len(set(d_order)) != len(d_order):
                raise InvalidSpecificationError(f"Duplicate driver name in driver_order: {d_order}.")
            object.__setattr__(self, "driver_order", d_order)
        else:
            object.__setattr__(self, "driver_order", ref_drivers)

        expected_drivers = set(self.driver_order)
        if len(expected_drivers) not in (2, 3):
            raise InvalidSpecificationError(
                f"Multi-position optimization supports 2-way or 3-way topologies, got {len(expected_drivers)} drivers: {tuple(expected_drivers)}."
            )

        for pos in self.positions:
            pos_driver_set = set(pos.driver_responses.keys())
            if not expected_drivers.issubset(pos_driver_set):
                missing = expected_drivers - pos_driver_set
                raise InvalidSpecificationError(
                    f"Position {pos.name!r} is missing required driver measurement(s): {tuple(missing)}."
                )

        # 4. Validate sample_rate
        if not isinstance(self.sample_rate, int) or isinstance(self.sample_rate, bool) or self.sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {self.sample_rate!r}.")

        # 5. Frequency grid validation across ALL driver measurements across ALL positions
        all_responses = []
        for pos in self.positions:
            for d_name in self.driver_order:
                all_responses.append(pos.driver_responses[d_name])
        validate_frequency_grid_matching(all_responses, self.sample_rate)

        # 6. Target curve validation
        if not isinstance(self.target_curve, AcousticTargetCurve):
            raise InvalidSpecificationError(
                f"target_curve must be an AcousticTargetCurve instance, got {type(self.target_curve)!r}."
            )

        # 7. Crossover family & order
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

        # 8. Bounds and optimization settings
        if not isinstance(self.frequency_range_hz, (tuple, list)) or len(self.frequency_range_hz) != 2:
            raise InvalidSpecificationError("frequency_range_hz must be a tuple of 2 floats (f_min, f_max).")
        f_min, f_max = float(self.frequency_range_hz[0]), float(self.frequency_range_hz[1])
        if not math.isfinite(f_min) or not math.isfinite(f_max) or f_min <= 0.0 or f_max <= f_min:
            raise InvalidSpecificationError(
                f"frequency_range_hz must satisfy 0 < f_min < f_max, got ({f_min}, {f_max})."
            )
        object.__setattr__(self, "frequency_range_hz", (f_min, f_max))

        if not isinstance(self.crossover_bounds_hz, (tuple, list)) or len(self.crossover_bounds_hz) != 2:
            raise InvalidSpecificationError("crossover_bounds_hz must be a tuple of 2 floats (fc_min, fc_max).")
        fc_min, fc_max = float(self.crossover_bounds_hz[0]), float(self.crossover_bounds_hz[1])
        if not math.isfinite(fc_min) or not math.isfinite(fc_max) or fc_min <= 0.0 or fc_max <= fc_min:
            raise InvalidSpecificationError(
                f"crossover_bounds_hz must satisfy 0 < fc_min < fc_max, got ({fc_min}, {fc_max})."
            )
        object.__setattr__(self, "crossover_bounds_hz", (fc_min, fc_max))

        if not isinstance(self.gain_bounds_db, (tuple, list)) or len(self.gain_bounds_db) != 2:
            raise InvalidSpecificationError("gain_bounds_db must be a tuple of 2 floats (g_min, g_max).")
        g_min, g_max = float(self.gain_bounds_db[0]), float(self.gain_bounds_db[1])
        if not math.isfinite(g_min) or not math.isfinite(g_max) or g_max <= g_min:
            raise InvalidSpecificationError(
                f"gain_bounds_db must satisfy g_min < g_max, got ({g_min}, {g_max})."
            )
        object.__setattr__(self, "gain_bounds_db", (g_min, g_max))

        if not isinstance(self.delay_bounds_seconds, (tuple, list)) or len(self.delay_bounds_seconds) != 2:
            raise InvalidSpecificationError("delay_bounds_seconds must be a tuple of 2 floats (d_min, d_max).")
        d_min, d_max = float(self.delay_bounds_seconds[0]), float(self.delay_bounds_seconds[1])
        if not math.isfinite(d_min) or not math.isfinite(d_max) or d_min < 0.0 or d_max <= d_min:
            raise InvalidSpecificationError(
                f"delay_bounds_seconds must satisfy 0 <= d_min < d_max, got ({d_min}, {d_max})."
            )
        object.__setattr__(self, "delay_bounds_seconds", (d_min, d_max))

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

        if not isinstance(self.golden_iterations, int) or isinstance(self.golden_iterations, bool) or self.golden_iterations < 1:
            raise InvalidSpecificationError(f"golden_iterations must be an integer >= 1, got {self.golden_iterations!r}.")


@dataclass(frozen=True, slots=True)
class MultiPositionOptimizationResult:
    """Immutable result container for multi-position spatial acoustic parameter optimization.

    Attributes:
        parameters: Optimal parameter vector as 1D float64 array.
        parameter_names: Names corresponding to each coordinate in parameters.
        spatial_losses: Mapping of position names to scalar target loss in dB at the optimum.
        total_loss: Aggregated spatial loss sum(w_i * L_i) in dB at the optimum.
        initial_loss: Aggregated spatial loss sum(w_i * L_i) in dB at initial parameters.
        converged: Whether coordinate descent converged within convergence_tolerance_db.
        iterations_completed: Number of coordinate descent iteration cycles completed.
        crossover_result: CrossoverSynthesisResult (2-way) or tuple of 2 CrossoverSynthesisResults (3-way).
        gain_results: Mapping of driver names to GainDesignResult.
        alignment_results: Mapping of driver names to DriverAlignmentResult.
        predicted_responses: Mapping of position names to summed FrequencyResponseData.
    """
    parameters: np.ndarray
    parameter_names: tuple[str, ...]
    spatial_losses: dict[str, float]
    total_loss: float
    initial_loss: float
    converged: bool
    iterations_completed: int
    crossover_result: Union[CrossoverSynthesisResult, tuple[CrossoverSynthesisResult, CrossoverSynthesisResult]]
    gain_results: dict[str, GainDesignResult]
    alignment_results: dict[str, DriverAlignmentResult]
    predicted_responses: dict[str, FrequencyResponseData]

    def __post_init__(self) -> None:
        if not isinstance(self.total_loss, (int, float)) or not math.isfinite(self.total_loss):
            raise InvalidSpecificationError(f"total_loss must be a finite float, got {self.total_loss!r}.")
        if not isinstance(self.initial_loss, (int, float)) or not math.isfinite(self.initial_loss):
            raise InvalidSpecificationError(f"initial_loss must be a finite float, got {self.initial_loss!r}.")

        init_l = float(self.initial_loss)
        fin_l = float(self.total_loss)
        if fin_l > init_l + 1e-12:
            raise InvalidSpecificationError(
                f"Monotonicity invariant violated: total_loss ({fin_l:.6f}) > initial_loss ({init_l:.6f})."
            )

    def to_optimization_result(
        self,
        position_name_or_index: Union[str, int] = 0,
        initial_metrics: Optional[AcousticMetricsResult] = None,
        optimized_metrics: Optional[AcousticMetricsResult] = None,
    ) -> OptimizationResult:
        """Convert multi-position result to a standard Core OptimizationResult for downstream compilation.

        Args:
            position_name_or_index: Position identifier or index whose predicted response is used as primary.
            initial_metrics: Optional AcousticMetricsResult for initial state (computed automatically if None).
            optimized_metrics: Optional AcousticMetricsResult for optimized state (computed automatically if None).

        Returns:
            Standard Core OptimizationResult instance compatible with compile_optimization_result_to_graph.
        """
        if isinstance(position_name_or_index, int):
            pos_names = list(self.predicted_responses.keys())
            if not (0 <= position_name_or_index < len(pos_names)):
                raise InvalidParameterError(
                    f"Position index {position_name_or_index} out of range [0, {len(pos_names) - 1}]."
                )
            selected_name = pos_names[position_name_or_index]
        else:
            selected_name = str(position_name_or_index)
            if selected_name not in self.predicted_responses:
                raise InvalidParameterError(f"Position name {selected_name!r} not found in predicted responses.")

        primary_resp = self.predicted_responses[selected_name]

        if optimized_metrics is None:
            optimized_metrics = calculate_response_metrics(
                measurement=primary_resp,
            )

        if initial_metrics is None:
            initial_metrics = optimized_metrics

        return OptimizationResult(
            crossover_result=self.crossover_result,
            gain_results=self.gain_results,
            alignment_results=self.alignment_results,
            predicted_response=primary_resp,
            initial_metrics=initial_metrics,
            optimized_metrics=optimized_metrics,
            initial_loss_db=self.initial_loss,
            final_loss_db=self.total_loss,
            converged=self.converged,
            iterations_completed=self.iterations_completed,
        )


# ==============================================================================
# Multi-Position Objective Composition & Optimization Execution
# ==============================================================================

def _unpack_parameters(
    params: np.ndarray,
    is_three_way: bool,
    spec: MultiPositionOptimizationSpecification,
) -> tuple[
    Union[CrossoverSynthesisResult, tuple[CrossoverSynthesisResult, CrossoverSynthesisResult]],
    list[Sequence[any]],  # branch biquads per driver
    list[float],          # gains per driver
    list[float],          # delays per driver
]:
    """Unpack parameter vector into crossover filters, branch gains, and branch delays."""
    if not is_three_way:
        fc = float(params[0])
        tweeter_gain = float(params[1])
        tweeter_delay = float(params[2])

        crossover_spec = CrossoverSpecification(
            family=spec.crossover_family,
            order=spec.crossover_order,
            frequency_hz=fc,
        )
        xover_res = synthesize_crossover_biquads(crossover_spec, spec.sample_rate)

        branch_biquads = [
            xover_res.low_pass_sections,
            xover_res.high_pass_sections,
        ]
        branch_gains = [0.0, tweeter_gain]
        branch_delays = [0.0, tweeter_delay]
        return xover_res, branch_biquads, branch_gains, branch_delays
    else:
        fc_low = float(params[0])
        fc_high = float(params[1])
        mid_gain = float(params[2])
        tweet_gain = float(params[3])
        mid_delay = float(params[4])
        tweet_delay = float(params[5])

        spec_low = CrossoverSpecification(
            family=spec.crossover_family,
            order=spec.crossover_order,
            frequency_hz=fc_low,
        )
        spec_high = CrossoverSpecification(
            family=spec.crossover_family,
            order=spec.crossover_order,
            frequency_hz=fc_high,
        )
        xover_low = synthesize_crossover_biquads(spec_low, spec.sample_rate)
        xover_high = synthesize_crossover_biquads(spec_high, spec.sample_rate)

        branch_biquads = [
            xover_low.low_pass_sections,
            tuple(xover_low.high_pass_sections) + tuple(xover_high.low_pass_sections),
            xover_high.high_pass_sections,
        ]
        branch_gains = [0.0, mid_gain, tweet_gain]
        branch_delays = [0.0, mid_delay, tweet_delay]
        return (xover_low, xover_high), branch_biquads, branch_gains, branch_delays


def build_multi_position_objective(
    spec: MultiPositionOptimizationSpecification,
) -> Callable[[np.ndarray], float]:
    """Construct the composite multi-position spatial acoustic objective function.

    Equation:
        L_multi(p) = sum_{m=1}^M w_m * L_m(p)

    where L_m(p) is evaluated via Core evaluate_acoustic_target_loss using
    Core complex forward model summation over the spatial measurements at position m.

    Args:
        spec: MultiPositionOptimizationSpecification value object.

    Returns:
        Deterministic callable f(p) -> float representing aggregated spatial loss in dB.
    """
    if not isinstance(spec, MultiPositionOptimizationSpecification):
        raise InvalidSpecificationError(
            f"Expected MultiPositionOptimizationSpecification, got {type(spec)!r}."
        )

    is_three_way = len(spec.driver_order) == 3
    driver_names = spec.driver_order
    weights = spec.spatial_weights
    positions = spec.positions
    target_curve = spec.target_curve
    freq_range = spec.frequency_range_hz
    ripple_weight = spec.ripple_weight
    delay_weight = spec.delay_weight
    delay_bounds = spec.delay_bounds_seconds
    sample_rate = spec.sample_rate

    # Pre-extract frequency grid from first measurement
    freq_grid = positions[0].driver_responses[driver_names[0]].frequencies_hz

    def multi_position_objective(params: np.ndarray) -> float:
        _, branch_biquads, branch_gains, branch_delays = _unpack_parameters(
            params, is_three_way, spec
        )

        total_loss = 0.0
        for m_idx, pos in enumerate(positions):
            w_m = weights[m_idx]
            if w_m == 0.0:
                continue

            # Calculate branch complex responses for this spatial position
            branch_responses = []
            for d_idx, d_name in enumerate(driver_names):
                d_resp = pos.driver_responses[d_name]
                b_resp = calculate_branch_complex_response(
                    driver_response=d_resp,
                    biquads=branch_biquads[d_idx],
                    gain_db=branch_gains[d_idx],
                    delay_seconds=branch_delays[d_idx],
                    sample_rate=sample_rate,
                )
                branch_responses.append(b_resp)

            # Sum complex responses
            pos_sum_frd = calculate_acoustic_complex_summation(
                branch_responses=branch_responses,
                frequencies_hz=freq_grid,
            )

            # Evaluate scalar loss for position m
            pos_loss = evaluate_acoustic_target_loss(
                predicted_response=pos_sum_frd,
                target_curve=target_curve,
                frequency_range_hz=freq_range,
                ripple_weight=ripple_weight,
                delay_weight=delay_weight,
                delays_seconds=branch_delays,
                delay_bounds_seconds=delay_bounds,
            )

            total_loss += w_m * pos_loss

        return float(total_loss)

    return multi_position_objective


def optimize_multi_position(
    spec: MultiPositionOptimizationSpecification,
) -> MultiPositionOptimizationResult:
    """Execute multi-position spatial acoustic optimization using the deterministic Core optimizer.

    Args:
        spec: MultiPositionOptimizationSpecification value object.

    Returns:
        MultiPositionOptimizationResult containing optimal parameters and per-position metrics.
    """
    if not isinstance(spec, MultiPositionOptimizationSpecification):
        raise InvalidSpecificationError(
            f"Expected MultiPositionOptimizationSpecification, got {type(spec)!r}."
        )

    is_three_way = len(spec.driver_order) == 3
    driver_names = spec.driver_order
    sample_rate = spec.sample_rate

    # Configure bounds and initial parameters
    if not is_three_way:
        fc_mid = float(math.sqrt(spec.crossover_bounds_hz[0] * spec.crossover_bounds_hz[1]))
        bounds = [
            spec.crossover_bounds_hz,
            spec.gain_bounds_db,
            spec.delay_bounds_seconds,
        ]
        initial_params = np.array([fc_mid, 0.0, 0.0], dtype=np.float64)
        param_names = (
            "crossover_frequency_hz",
            f"{driver_names[1]}_gain_db",
            f"{driver_names[1]}_delay_seconds",
        )
        constraints = None
    else:
        fc_min, fc_max = spec.crossover_bounds_hz
        fc_low_init = fc_min + 0.25 * (fc_max - fc_min)
        fc_high_init = fc_min + 0.75 * (fc_max - fc_min)
        if fc_high_init < 1.5 * fc_low_init:
            fc_high_init = 1.5 * fc_low_init

        bounds = [
            spec.crossover_bounds_hz,
            spec.crossover_bounds_hz,
            spec.gain_bounds_db,
            spec.gain_bounds_db,
            spec.delay_bounds_seconds,
            spec.delay_bounds_seconds,
        ]
        initial_params = np.array(
            [fc_low_init, fc_high_init, 0.0, 0.0, 0.0, 0.0],
            dtype=np.float64,
        )
        param_names = (
            "crossover_low_hz",
            "crossover_high_hz",
            f"{driver_names[1]}_gain_db",
            f"{driver_names[2]}_gain_db",
            f"{driver_names[1]}_delay_seconds",
            f"{driver_names[2]}_delay_seconds",
        )
        # 3-Way crossover separation constraint: fc_high >= 1.5 * fc_low
        constraints = [
            lambda p: p[1] >= 1.5 * p[0],
        ]

    # Build multi-position objective
    objective_func = build_multi_position_objective(spec)

    # Initial loss at baseline parameters
    initial_loss = float(objective_func(initial_params))

    # Run deterministic coordinate descent search
    best_params, best_loss, converged, iterations = coordinate_descent_search(
        objective_func=objective_func,
        bounds=bounds,
        initial_params=initial_params,
        max_iterations=spec.max_iterations,
        convergence_tolerance_db=spec.convergence_tolerance_db,
        golden_iterations=spec.golden_iterations,
        constraints=constraints,
    )

    # Re-evaluate final state across all positions
    xover_result, branch_biquads, branch_gains, branch_delays = _unpack_parameters(
        best_params, is_three_way, spec
    )

    freq_grid = spec.positions[0].driver_responses[driver_names[0]].frequencies_hz

    spatial_losses: dict[str, float] = {}
    predicted_responses: dict[str, FrequencyResponseData] = {}

    for pos in spec.positions:
        branch_responses = []
        for d_idx, d_name in enumerate(driver_names):
            d_resp = pos.driver_responses[d_name]
            b_resp = calculate_branch_complex_response(
                driver_response=d_resp,
                biquads=branch_biquads[d_idx],
                gain_db=branch_gains[d_idx],
                delay_seconds=branch_delays[d_idx],
                sample_rate=sample_rate,
            )
            branch_responses.append(b_resp)

        pos_sum_frd = calculate_acoustic_complex_summation(
            branch_responses=branch_responses,
            frequencies_hz=freq_grid,
        )
        predicted_responses[pos.name] = pos_sum_frd

        p_loss = evaluate_acoustic_target_loss(
            predicted_response=pos_sum_frd,
            target_curve=spec.target_curve,
            frequency_range_hz=spec.frequency_range_hz,
            ripple_weight=spec.ripple_weight,
            delay_weight=spec.delay_weight,
            delays_seconds=branch_delays,
            delay_bounds_seconds=spec.delay_bounds_seconds,
        )
        spatial_losses[pos.name] = float(p_loss)

    # Build GainDesignResult and DriverAlignmentResult mappings
    gain_results: dict[str, GainDesignResult] = {}
    alignment_results: dict[str, DriverAlignmentResult] = {}

    for d_idx, d_name in enumerate(driver_names):
        g_val = branch_gains[d_idx]
        d_val = branch_delays[d_idx]

        gain_results[d_name] = GainDesignResult(
            driver_name=d_name,
            sensitivity_db=0.0,
            reference_sensitivity_db=0.0,
            gain_db=g_val,
            gain_linear=float(10.0 ** (g_val / 20.0)),
            polarity_inverted=False,
        )

        applied_frames = int(round(d_val * float(sample_rate)))
        depth_mm = d_val * DEFAULT_SPEED_OF_SOUND_MPS * 1000.0

        alignment_results[d_name] = DriverAlignmentResult(
            driver_name=d_name,
            physical_delay_seconds=d_val,
            requested_delay_frames=d_val * float(sample_rate),
            applied_delay_frames=applied_frames,
            depth_offset_mm=depth_mm,
            reference_depth_mm=0.0,
            sample_rate=sample_rate,
            speed_of_sound_mps=DEFAULT_SPEED_OF_SOUND_MPS,
        )

    return MultiPositionOptimizationResult(
        parameters=best_params,
        parameter_names=param_names,
        spatial_losses=spatial_losses,
        total_loss=best_loss,
        initial_loss=initial_loss,
        converged=converged,
        iterations_completed=iterations,
        crossover_result=xover_result,
        gain_results=gain_results,
        alignment_results=alignment_results,
        predicted_responses=predicted_responses,
    )
