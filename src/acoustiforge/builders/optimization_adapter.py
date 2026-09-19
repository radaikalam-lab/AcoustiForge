"""AcoustiForge Optimization Result Graph Compilation Adapter.

Translates validated OptimizationResult instances into executable ComputeGraph DAGs.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/contracts/MULTIWAY_GRAPH_BUILDER_CONTRACT.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/phases/PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md
"""

from __future__ import annotations

from typing import Mapping, Optional
import math

from ..acoustic_math.crossover import CrossoverSynthesisResult
from ..contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
)
from ..domain.validation import InvalidSpecificationError
from ..domain.specifications import OptimizationResult
from ..graph.compute_graph import ComputeGraph
from .crossover_builder import CrossoverGraphBuilder
from .multiway_builder import ThreeWayGraphBuilder


def compile_optimization_result_to_graph(
    result: OptimizationResult,
    sample_rate: Optional[int] = None,
    channels: int = 1,
    woofer_name: str = "woofer",
    midrange_name: str = "midrange",
    tweeter_name: str = "tweeter",
    graph_name: Optional[str] = None,
) -> ComputeGraph:
    """Compile an OptimizationResult directly into a validated, frozen ComputeGraph.

    Detects topology deterministically from result.crossover_result:
    - 2-Way Topology: If crossover_result is a CrossoverSynthesisResult.
      Uses CrossoverGraphBuilder to construct woofer and tweeter branches.
    - 3-Way Topology: If crossover_result is a tuple of (crossover_low, crossover_high).
      Uses ThreeWayGraphBuilder to construct woofer, midrange, and tweeter branches.

    Normative Invariants:
    1. result must be a valid OptimizationResult instance.
    2. Zero Parameter Drift: All gains, delays, and biquad filter sections are mapped
       directly to the DSP nodes without modification, rounding, or re-interpretation.
    3. Sample Rate Consistency: If sample_rate is provided, it must match the synthesis
       sample rate; otherwise sample rate is derived directly from the crossover result.
    4. Topology Compatibility: Validates that required driver branch names exist in
       result.gain_results and result.alignment_results.

    Args:
        result: Validated OptimizationResult instance.
        sample_rate: Optional audio sampling rate in Hz.
        channels: Channel count (default: 1 for mono per crossover slice).
        woofer_name: Unique identifier for woofer branch (default: "woofer").
        midrange_name: Unique identifier for midrange branch (default: "midrange").
        tweeter_name: Unique identifier for tweeter branch (default: "tweeter").
        graph_name: Optional custom identifier for the constructed compute graph.

    Returns:
        Validated and frozen ComputeGraph ready for PCM execution.

    Raises:
        InvalidParameterError: If result is not OptimizationResult, sample rate mismatches,
                               or required driver names are missing.
        InvalidSpecificationError: If crossover topology or constraints are invalid.
        InvalidSampleRateError: If sample_rate is non-positive.
    """
    if not isinstance(result, OptimizationResult):
        raise InvalidParameterError(
            f"Expected OptimizationResult instance, got {type(result)!r}."
        )

    if not isinstance(channels, int) or isinstance(channels, bool) or channels <= 0:
        raise InvalidParameterError(f"channels must be a positive integer, got {channels!r}.")

    # 1. 2-Way Topology Compilation
    if isinstance(result.crossover_result, CrossoverSynthesisResult):
        xover = result.crossover_result
        effective_fs = xover.sample_rate

        if sample_rate is not None:
            if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
                raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")
            if sample_rate != effective_fs:
                raise InvalidParameterError(
                    f"Specified sample_rate ({sample_rate} Hz) does not match OptimizationResult crossover sample rate ({effective_fs} Hz)."
                )

        w_name = woofer_name.strip()
        t_name = tweeter_name.strip()
        if w_name == t_name:
            raise InvalidParameterError(f"woofer_name ({w_name!r}) and tweeter_name ({t_name!r}) must be distinct.")

        # Validate that gain and alignment results contain keys for both branches
        if w_name not in result.gain_results:
            raise InvalidParameterError(f"Missing gain result for 2-way woofer branch {w_name!r}.")
        if t_name not in result.gain_results:
            raise InvalidParameterError(f"Missing gain result for 2-way tweeter branch {t_name!r}.")
        if w_name not in result.alignment_results:
            raise InvalidParameterError(f"Missing alignment result for 2-way woofer branch {w_name!r}.")
        if t_name not in result.alignment_results:
            raise InvalidParameterError(f"Missing alignment result for 2-way tweeter branch {t_name!r}.")

        builder = CrossoverGraphBuilder(
            sample_rate=effective_fs,
            channels=channels,
            woofer_name=w_name,
            tweeter_name=t_name,
            graph_name=graph_name if graph_name is not None else "Optimized2WayComputeGraph",
        )

        return builder.build_2way_graph(
            crossover_result=xover,
            alignments=result.alignment_results,
            gains=result.gain_results,
        )

    # 2. 3-Way Topology Compilation
    elif isinstance(result.crossover_result, (tuple, list)) and len(result.crossover_result) == 2:
        x_low, x_high = result.crossover_result
        if not isinstance(x_low, CrossoverSynthesisResult) or not isinstance(x_high, CrossoverSynthesisResult):
            raise InvalidSpecificationError(
                "3-Way crossover_result must contain two CrossoverSynthesisResult instances (x_low, x_high)."
            )

        effective_fs = x_low.sample_rate
        if x_high.sample_rate != effective_fs:
            raise InvalidParameterError(
                f"3-Way crossover low sample rate ({effective_fs} Hz) does not match crossover high ({x_high.sample_rate} Hz)."
            )

        if sample_rate is not None:
            if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
                raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")
            if sample_rate != effective_fs:
                raise InvalidParameterError(
                    f"Specified sample_rate ({sample_rate} Hz) does not match OptimizationResult crossover sample rate ({effective_fs} Hz)."
                )

        w_name = woofer_name.strip()
        m_name = midrange_name.strip()
        t_name = tweeter_name.strip()
        if len({w_name, m_name, t_name}) != 3:
            raise InvalidParameterError(
                f"woofer ({w_name!r}), midrange ({m_name!r}), and tweeter ({t_name!r}) must all be pairwise distinct."
            )

        # Validate that gain and alignment results contain keys for all 3 branches
        for b_name in (w_name, m_name, t_name):
            if b_name not in result.gain_results:
                raise InvalidParameterError(f"Missing gain result for 3-way branch {b_name!r}.")
            if b_name not in result.alignment_results:
                raise InvalidParameterError(f"Missing alignment result for 3-way branch {b_name!r}.")

        builder_3w = ThreeWayGraphBuilder(
            sample_rate=effective_fs,
            channels=channels,
            woofer_name=w_name,
            midrange_name=m_name,
            tweeter_name=t_name,
            graph_name=graph_name if graph_name is not None else "Optimized3WayComputeGraph",
        )

        return builder_3w.build_3way_graph(
            crossover_low=x_low,
            crossover_high=x_high,
            alignments=result.alignment_results,
            gains=result.gain_results,
        )

    else:
        raise InvalidSpecificationError(
            f"Unsupported crossover_result type in OptimizationResult: {type(result.crossover_result)!r}."
        )
