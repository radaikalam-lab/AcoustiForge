"""AcoustiForge Multi-Way Loudspeaker Graph Builder.

Constructs validated, deterministic ComputeGraphs for multi-way (e.g. 3-Way Woofer/Midrange/Tweeter)
loudspeaker systems from explicit Phase 3C acoustic synthesis results.

Normative Authority:
- docs/contracts/MULTIWAY_GRAPH_BUILDER_CONTRACT.md
- docs/phases/PHASE_4B_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from ..acoustic_math.alignment import DriverAlignmentResult
from ..acoustic_math.crossover import CrossoverSynthesisResult
from ..acoustic_math.equalizer import EQSynthesisResult
from ..acoustic_math.protection import ProtectionFilterResult
from ..acoustic_math.sensitivity import GainDesignResult
from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..graph.compute_graph import ComputeGraph
from ..nodes.biquad import BiquadCoefficients, BiquadNode
from ..nodes.delay import DelayNode
from ..nodes.gain import GainNode
from ..nodes.passthrough import PassThroughNode


class ThreeWayGraphBuilder:
    """Builder for constructing deterministic 3-way loudspeaker compute graphs.

    Consumes pre-computed, immutable Phase 3C/4A mathematical results and constructs a deterministic DAG.
    Performs NO hidden calculations, parameter derivations, or DSP executions.
    """

    def __init__(
        self,
        sample_rate: int,
        channels: int = 1,
        woofer_name: str = "woofer",
        midrange_name: str = "midrange",
        tweeter_name: str = "tweeter",
        graph_name: Optional[str] = None,
    ) -> None:
        """Initialize the ThreeWayGraphBuilder with stream configuration and driver branch identifiers.

        Args:
            sample_rate: Audio sampling rate in Hz.
            channels: Channel count (default: 1 for mono per crossover slice).
            woofer_name: Unique identifier prefix for woofer branch nodes.
            midrange_name: Unique identifier prefix for midrange branch nodes.
            tweeter_name: Unique identifier prefix for tweeter branch nodes.
            graph_name: Optional custom name for the constructed compute graph.

        Raises:
            InvalidSampleRateError: If sample_rate is non-positive.
            InvalidParameterError: If channels is non-positive or driver names are not distinct.
        """
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

        if not isinstance(channels, int) or isinstance(channels, bool) or channels <= 0:
            raise InvalidParameterError(f"channels must be a positive integer, got {channels!r}.")

        for name_label, name_val in [
            ("woofer_name", woofer_name),
            ("midrange_name", midrange_name),
            ("tweeter_name", tweeter_name),
        ]:
            if not isinstance(name_val, str) or not name_val.strip():
                raise InvalidParameterError(f"{name_label} must be a non-empty string, got {name_val!r}.")

        w = woofer_name.strip()
        m = midrange_name.strip()
        t = tweeter_name.strip()
        if len({w, m, t}) != 3:
            raise InvalidParameterError(
                f"woofer_name ({w!r}), midrange_name ({m!r}), and tweeter_name ({t!r}) must all be pairwise distinct."
            )

        self._sample_rate: int = sample_rate
        self._channels: int = channels
        self._woofer_name: str = w
        self._midrange_name: str = m
        self._tweeter_name: str = t
        self._graph_name: str = graph_name if graph_name is not None else "ThreeWayComputeGraph"

    def build_3way_graph(
        self,
        crossover_low: CrossoverSynthesisResult,
        crossover_high: CrossoverSynthesisResult,
        alignments: Optional[Mapping[str, DriverAlignmentResult]] = None,
        gains: Optional[Mapping[str, GainDesignResult]] = None,
        equalizers: Optional[Mapping[str, EQSynthesisResult]] = None,
        protections: Optional[Mapping[str, ProtectionFilterResult]] = None,
    ) -> ComputeGraph:
        """Build and freeze a 3-way loudspeaker compute graph from explicit mathematical results.

        Constructs the following deterministic processing pipeline:
            input ("input")
              ├── woofer:   [delay] → [gain] → [eq...] → [low_pass_crossover...] → [protection...] → output 0
              ├── midrange: [delay] → [gain] → [eq...] → [hp_crossover...] → [lp_crossover...] → [protection...] → output 1
              └── tweeter:  [delay] → [gain] → [eq...] → [high_pass_crossover...] → [protection...] → output 2

        Args:
            crossover_low: CrossoverSynthesisResult for LF/MF boundary (crossover_frequency_hz = f_low).
            crossover_high: CrossoverSynthesisResult for MF/HF boundary (crossover_frequency_hz = f_high).
            alignments: Optional mapping of driver name to DriverAlignmentResult.
            gains: Optional mapping of driver name to GainDesignResult.
            equalizers: Optional mapping of driver name to EQSynthesisResult.
            protections: Optional mapping of driver name to ProtectionFilterResult.

        Returns:
            Validated and frozen ComputeGraph ready for multi-channel PCM execution.

        Raises:
            InvalidParameterError: If crossover frequencies or sample rates are invalid.
        """
        for label, xo in [("crossover_low", crossover_low), ("crossover_high", crossover_high)]:
            if not isinstance(xo, CrossoverSynthesisResult):
                raise InvalidParameterError(f"Expected CrossoverSynthesisResult for {label}, got {type(xo)!r}.")
            if xo.sample_rate != self._sample_rate:
                raise InvalidParameterError(
                    f"{label} sample rate ({xo.sample_rate} Hz) does not match builder configured sample rate ({self._sample_rate} Hz)."
                )

        f_low = crossover_low.crossover_frequency_hz
        f_high = crossover_high.crossover_frequency_hz
        nyquist = self._sample_rate / 2.0

        if not (0.0 < f_low < f_high < nyquist):
            raise InvalidParameterError(
                f"3-Way crossover frequencies must satisfy 0 < f_low < f_high < Nyquist ({nyquist:.1f} Hz). "
                f"Got f_low={f_low:.1f} Hz, f_high={f_high:.1f} Hz."
            )

        if equalizers:
            for d_name, eq_res in equalizers.items():
                if eq_res is not None:
                    if not isinstance(eq_res, EQSynthesisResult):
                        raise InvalidParameterError(f"Expected EQSynthesisResult for driver {d_name!r}, got {type(eq_res)!r}.")
                    if eq_res.sample_rate != self._sample_rate:
                        raise InvalidParameterError(
                            f"EQSynthesisResult for driver {d_name!r} sample rate ({eq_res.sample_rate} Hz) "
                            f"does not match builder configured sample rate ({self._sample_rate} Hz)."
                        )

        graph = ComputeGraph(name=self._graph_name)

        # 1. Root input fan-out node
        root_input_id = "input"
        root_node = PassThroughNode(name=root_input_id)
        root_node.configure(self._sample_rate, self._channels)
        graph.add_node(root_input_id, root_node)
        graph.declare_input(root_input_id, "in")

        # 2. Build Woofer branch
        woofer_last_id = self._build_branch(
            graph=graph,
            driver_name=self._woofer_name,
            crossover_stages=[("crossover", crossover_low.low_pass_sections)],
            alignment=alignments.get(self._woofer_name) if alignments else None,
            gain_result=gains.get(self._woofer_name) if gains else None,
            equalizer=equalizers.get(self._woofer_name) if equalizers else None,
            protection=protections.get(self._woofer_name) if protections else None,
            root_source_id=root_input_id,
        )
        graph.declare_output(woofer_last_id, "out")

        # 3. Build Midrange bandpass branch (HP at f_low, LP at f_high)
        midrange_last_id = self._build_branch(
            graph=graph,
            driver_name=self._midrange_name,
            crossover_stages=[
                ("crossover.hp", crossover_low.high_pass_sections),
                ("crossover.lp", crossover_high.low_pass_sections),
            ],
            alignment=alignments.get(self._midrange_name) if alignments else None,
            gain_result=gains.get(self._midrange_name) if gains else None,
            equalizer=equalizers.get(self._midrange_name) if equalizers else None,
            protection=protections.get(self._midrange_name) if protections else None,
            root_source_id=root_input_id,
        )
        graph.declare_output(midrange_last_id, "out")

        # 4. Build Tweeter branch
        tweeter_last_id = self._build_branch(
            graph=graph,
            driver_name=self._tweeter_name,
            crossover_stages=[("crossover", crossover_high.high_pass_sections)],
            alignment=alignments.get(self._tweeter_name) if alignments else None,
            gain_result=gains.get(self._tweeter_name) if gains else None,
            equalizer=equalizers.get(self._tweeter_name) if equalizers else None,
            protection=protections.get(self._tweeter_name) if protections else None,
            root_source_id=root_input_id,
        )
        graph.declare_output(tweeter_last_id, "out")

        # 5. Validate and freeze graph
        graph.freeze()
        return graph

    def _build_branch(
        self,
        graph: ComputeGraph,
        driver_name: str,
        crossover_stages: Sequence[tuple[str, Sequence[BiquadCoefficients | BiquadNode]]],
        alignment: Optional[DriverAlignmentResult],
        gain_result: Optional[GainDesignResult],
        equalizer: Optional[EQSynthesisResult],
        protection: Optional[ProtectionFilterResult],
        root_source_id: str,
    ) -> str:
        """Construct sequential processing stages for a single driver branch."""
        branch_nodes: list[tuple[str, any]] = []

        # 1. Alignment Delay stage
        delay_frames = alignment.applied_delay_frames if alignment is not None else 0
        delay_id = f"{driver_name}.delay"
        delay_node = DelayNode(
            delay_frames=delay_frames,
            sample_rate=self._sample_rate,
            channels=self._channels,
            name=delay_id,
        )
        branch_nodes.append((delay_id, delay_node))

        # 2. Gain stage
        gain_db = gain_result.gain_db if gain_result is not None else 0.0
        gain_id = f"{driver_name}.gain"
        gain_node = GainNode(
            gain_db=gain_db,
            sample_rate=self._sample_rate,
            channels=self._channels,
            name=gain_id,
        )
        branch_nodes.append((gain_id, gain_node))

        # 3. Equalizer Filter stage (if present)
        if equalizer is not None and equalizer.sections:
            for idx, sec in enumerate(equalizer.sections):
                eq_id = f"{driver_name}.eq.{idx}"
                eq_node = BiquadNode.from_coefficients(
                    coefficients=sec,
                    sample_rate=self._sample_rate,
                    channels=self._channels,
                    name=eq_id,
                )
                branch_nodes.append((eq_id, eq_node))

        # 4. Crossover Filter stages
        for stage_prefix, sections in crossover_stages:
            for idx, sec in enumerate(sections):
                filt_id = f"{driver_name}.{stage_prefix}.{idx}"
                filt_node = BiquadNode.from_coefficients(
                    coefficients=sec,
                    sample_rate=self._sample_rate,
                    channels=self._channels,
                    name=filt_id,
                )
                branch_nodes.append((filt_id, filt_node))

        # 5. Protection Filter stage (if present)
        if protection is not None and protection.sections:
            for idx, sec in enumerate(protection.sections):
                prot_id = f"{driver_name}.protection.{idx}"
                prot_node = BiquadNode.from_coefficients(
                    coefficients=sec,
                    sample_rate=self._sample_rate,
                    channels=self._channels,
                    name=prot_id,
                )
                branch_nodes.append((prot_id, prot_node))

        # Register nodes into graph
        for node_id, node in branch_nodes:
            graph.add_node(node_id, node)

        # Connect root to first node in branch
        first_node_id = branch_nodes[0][0]
        graph.connect(root_source_id, "out", first_node_id, "in")

        # Connect internal sequential chain
        for i in range(len(branch_nodes) - 1):
            src_id = branch_nodes[i][0]
            tgt_id = branch_nodes[i + 1][0]
            graph.connect(src_id, "out", tgt_id, "in")

        last_node_id = branch_nodes[-1][0]
        return last_node_id
