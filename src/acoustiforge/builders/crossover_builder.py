"""AcoustiForge Crossover Graph Builder.

Translates explicit Phase 3C acoustic synthesis results into a validated, deterministic ComputeGraph.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from ..acoustic_math.alignment import DriverAlignmentResult
from ..acoustic_math.crossover import CrossoverSynthesisResult
from ..acoustic_math.protection import ProtectionFilterResult
from ..acoustic_math.sensitivity import GainDesignResult
from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..graph.compute_graph import ComputeGraph
from ..nodes.biquad import BiquadNode
from ..nodes.delay import DelayNode
from ..nodes.gain import GainNode
from ..nodes.passthrough import PassThroughNode


class CrossoverGraphBuilder:
    """Builder for constructing multi-way acoustic crossover compute graphs.

    Consumes pre-computed, immutable Phase 3C mathematical results and constructs a deterministic DAG.
    Performs NO hidden calculations, parameter derivations, or DSP executions.
    """

    def __init__(
        self,
        sample_rate: int,
        channels: int = 1,
        woofer_name: str = "woofer",
        tweeter_name: str = "tweeter",
        graph_name: Optional[str] = None,
    ) -> None:
        """Initialize the CrossoverGraphBuilder with stream configuration and driver branch identifiers.

        Args:
            sample_rate: Audio sampling rate in Hz.
            channels: Channel count (default: 1 for mono per crossover slice).
            woofer_name: Unique identifier prefix for woofer branch nodes.
            tweeter_name: Unique identifier prefix for tweeter branch nodes.
            graph_name: Optional custom name for the constructed compute graph.

        Raises:
            InvalidSampleRateError: If sample_rate is non-positive.
            InvalidParameterError: If channels is non-positive or driver names are invalid.
        """
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

        if not isinstance(channels, int) or isinstance(channels, bool) or channels <= 0:
            raise InvalidParameterError(f"channels must be a positive integer, got {channels!r}.")

        if not isinstance(woofer_name, str) or not woofer_name.strip():
            raise InvalidParameterError(f"woofer_name must be a non-empty string, got {woofer_name!r}.")

        if not isinstance(tweeter_name, str) or not tweeter_name.strip():
            raise InvalidParameterError(f"tweeter_name must be a non-empty string, got {tweeter_name!r}.")

        if woofer_name == tweeter_name:
            raise InvalidParameterError("woofer_name and tweeter_name must be distinct identifiers.")

        self._sample_rate: int = sample_rate
        self._channels: int = channels
        self._woofer_name: str = woofer_name.strip()
        self._tweeter_name: str = tweeter_name.strip()
        self._graph_name: str = graph_name if graph_name is not None else "CrossoverComputeGraph"

    def build_2way_graph(
        self,
        crossover_result: CrossoverSynthesisResult,
        alignments: Optional[Mapping[str, DriverAlignmentResult]] = None,
        gains: Optional[Mapping[str, GainDesignResult]] = None,
        protections: Optional[Mapping[str, ProtectionFilterResult]] = None,
    ) -> ComputeGraph:
        """Build and freeze a 2-way loudspeaker crossover compute graph from explicit mathematical results.

        Constructs the following deterministic processing pipeline:
            input ("input")
              ├── woofer:  [delay] → [gain] → [low_pass_crossover_sections...] → [protection_sections...] → output
              └── tweeter: [delay] → [gain] → [high_pass_crossover_sections...] → [protection_sections...] → output

        Args:
            crossover_result: Pre-computed CrossoverSynthesisResult containing low-pass and high-pass biquad sections.
            alignments: Optional mapping of driver name to DriverAlignmentResult.
            gains: Optional mapping of driver name to GainDesignResult.
            protections: Optional mapping of driver name to ProtectionFilterResult.

        Returns:
            Validated and frozen ComputeGraph ready for PCM execution.

        Raises:
            InvalidParameterError: If crossover result sample rate does not match builder configuration.
        """
        if not isinstance(crossover_result, CrossoverSynthesisResult):
            raise InvalidParameterError(
                f"Expected CrossoverSynthesisResult, got {type(crossover_result)!r}."
            )

        if crossover_result.sample_rate != self._sample_rate:
            raise InvalidParameterError(
                f"CrossoverSynthesisResult sample rate ({crossover_result.sample_rate} Hz) "
                f"does not match builder configured sample rate ({self._sample_rate} Hz)."
            )

        graph = ComputeGraph(name=self._graph_name)

        # 1. Root input fan-out node
        root_input_id = "input"
        root_node = PassThroughNode(name=root_input_id)
        root_node.configure(self._sample_rate, self._channels)
        graph.add_node(root_input_id, root_node)
        graph.declare_input(root_input_id, "in")

        # 2. Build woofer branch
        woofer_last_id = self._build_driver_branch(
            graph=graph,
            driver_name=self._woofer_name,
            crossover_sections=crossover_result.low_pass_sections,
            alignment=alignments.get(self._woofer_name) if alignments else None,
            gain_result=gains.get(self._woofer_name) if gains else None,
            protection=protections.get(self._woofer_name) if protections else None,
            root_source_id=root_input_id,
        )
        graph.declare_output(woofer_last_id, "out")

        # 3. Build tweeter branch
        tweeter_last_id = self._build_driver_branch(
            graph=graph,
            driver_name=self._tweeter_name,
            crossover_sections=crossover_result.high_pass_sections,
            alignment=alignments.get(self._tweeter_name) if alignments else None,
            gain_result=gains.get(self._tweeter_name) if gains else None,
            protection=protections.get(self._tweeter_name) if protections else None,
            root_source_id=root_input_id,
        )
        graph.declare_output(tweeter_last_id, "out")

        # 4. Validate and freeze graph
        graph.freeze()
        return graph

    def _build_driver_branch(
        self,
        graph: ComputeGraph,
        driver_name: str,
        crossover_sections: Sequence[BiquadNode | BiquadCoefficients],
        alignment: Optional[DriverAlignmentResult],
        gain_result: Optional[GainDesignResult],
        protection: Optional[ProtectionFilterResult],
        root_source_id: str,
    ) -> str:
        """Construct sequential processing stages for a single driver branch.

        Deterministic Node IDs:
        - Alignment Delay: f"{driver_name}.delay"
        - Sensitivity Gain: f"{driver_name}.gain"
        - Crossover Filters: f"{driver_name}.crossover.{idx}"
        - Protection Filters: f"{driver_name}.protection.{idx}"

        Returns:
            The node_id of the final processing stage in the branch.
        """
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

        # 3. Crossover Filter stage
        for idx, sec in enumerate(crossover_sections):
            filt_id = f"{driver_name}.crossover.{idx}"
            filt_node = BiquadNode.from_coefficients(
                coefficients=sec,
                sample_rate=self._sample_rate,
                channels=self._channels,
                name=filt_id,
            )
            branch_nodes.append((filt_id, filt_node))

        # 4. Protection Filter stage (if present)
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
