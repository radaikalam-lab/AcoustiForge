"""AcoustiForge System Topology Builder.

Minimal composition layer building multi-channel (e.g. Stereo 2-Way) loudspeaker compute graphs.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..acoustic_math.alignment import DriverAlignmentResult
from ..acoustic_math.crossover import CrossoverSynthesisResult
from ..acoustic_math.protection import ProtectionFilterResult
from ..acoustic_math.sensitivity import GainDesignResult
from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..graph.compute_graph import ComputeGraph
from .crossover_builder import CrossoverGraphBuilder


class SystemTopologyBuilder:
    """Minimal composition builder for stereo 2-way loudspeaker systems."""

    def __init__(
        self,
        sample_rate: int,
        graph_name: Optional[str] = None,
    ) -> None:
        """Initialize the SystemTopologyBuilder with stream sample rate.

        Args:
            sample_rate: Audio sampling rate in Hz.
            graph_name: Optional custom graph identifier.

        Raises:
            InvalidSampleRateError: If sample_rate is non-positive.
        """
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

        self._sample_rate: int = sample_rate
        self._graph_name: str = graph_name if graph_name is not None else "Stereo2WayComputeGraph"

    def build_stereo_2way_graph(
        self,
        crossover_result: CrossoverSynthesisResult,
        alignments: Optional[Mapping[str, DriverAlignmentResult]] = None,
        gains: Optional[Mapping[str, GainDesignResult]] = None,
        protections: Optional[Mapping[str, ProtectionFilterResult]] = None,
    ) -> ComputeGraph:
        """Build and freeze a complete stereo 2-way loudspeaker compute graph.

        Constructs independent left and right channel 2-way crossover topologies with deterministic node IDs:
            left_in ("left.input")   -> left.woofer.*  & left.tweeter.*
            right_in ("right.input") -> right.woofer.* & right.tweeter.*

        Args:
            crossover_result: Pre-computed CrossoverSynthesisResult.
            alignments: Optional driver alignment results.
            gains: Optional driver gain results.
            protections: Optional driver protection results.

        Returns:
            Validated and frozen ComputeGraph with 2 inputs and 4 outputs.
        """
        graph = ComputeGraph(name=self._graph_name)

        # Left channel sub-builder
        left_builder = CrossoverGraphBuilder(
            sample_rate=self._sample_rate,
            channels=1,
            woofer_name="left.woofer",
            tweeter_name="left.tweeter",
        )
        # Right channel sub-builder
        right_builder = CrossoverGraphBuilder(
            sample_rate=self._sample_rate,
            channels=1,
            woofer_name="right.woofer",
            tweeter_name="right.tweeter",
        )

        # Build Left channel
        root_left_id = "left.input"
        from ..nodes.passthrough import PassThroughNode
        left_in_node = PassThroughNode(name=root_left_id)
        left_in_node.configure(self._sample_rate, 1)
        graph.add_node(root_left_id, left_in_node)
        graph.declare_input(root_left_id, "in")

        left_woofer_last = left_builder._build_driver_branch(
            graph=graph,
            driver_name="left.woofer",
            crossover_sections=crossover_result.low_pass_sections,
            alignment=alignments.get("woofer") or alignments.get("left.woofer") if alignments else None,
            gain_result=gains.get("woofer") or gains.get("left.woofer") if gains else None,
            protection=protections.get("woofer") or protections.get("left.woofer") if protections else None,
            root_source_id=root_left_id,
        )
        graph.declare_output(left_woofer_last, "out")

        left_tweeter_last = left_builder._build_driver_branch(
            graph=graph,
            driver_name="left.tweeter",
            crossover_sections=crossover_result.high_pass_sections,
            alignment=alignments.get("tweeter") or alignments.get("left.tweeter") if alignments else None,
            gain_result=gains.get("tweeter") or gains.get("left.tweeter") if gains else None,
            protection=protections.get("tweeter") or protections.get("left.tweeter") if protections else None,
            root_source_id=root_left_id,
        )
        graph.declare_output(left_tweeter_last, "out")

        # Build Right channel
        root_right_id = "right.input"
        right_in_node = PassThroughNode(name=root_right_id)
        right_in_node.configure(self._sample_rate, 1)
        graph.add_node(root_right_id, right_in_node)
        graph.declare_input(root_right_id, "in")

        right_woofer_last = right_builder._build_driver_branch(
            graph=graph,
            driver_name="right.woofer",
            crossover_sections=crossover_result.low_pass_sections,
            alignment=alignments.get("woofer") or alignments.get("right.woofer") if alignments else None,
            gain_result=gains.get("woofer") or gains.get("right.woofer") if gains else None,
            protection=protections.get("woofer") or protections.get("right.woofer") if protections else None,
            root_source_id=root_right_id,
        )
        graph.declare_output(right_woofer_last, "out")

        right_tweeter_last = right_builder._build_driver_branch(
            graph=graph,
            driver_name="right.tweeter",
            crossover_sections=crossover_result.high_pass_sections,
            alignment=alignments.get("tweeter") or alignments.get("right.tweeter") if alignments else None,
            gain_result=gains.get("tweeter") or gains.get("right.tweeter") if gains else None,
            protection=protections.get("tweeter") or protections.get("right.tweeter") if protections else None,
            root_source_id=root_right_id,
        )
        graph.declare_output(right_tweeter_last, "out")

        graph.freeze()
        return graph
