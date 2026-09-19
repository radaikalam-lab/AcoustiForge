"""Tests for Phase 3D Acoustic Graph Builders.

Verifies structural topology, port binding, deterministic node naming, and DAG invariants.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
"""

from __future__ import annotations

import pytest

from acoustiforge.acoustic_math.alignment import DriverAlignmentResult
from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads
from acoustiforge.acoustic_math.protection import design_infrasonic_protection_filter
from acoustiforge.acoustic_math.sensitivity import GainDesignResult
from acoustiforge.builders.crossover_builder import CrossoverGraphBuilder
from acoustiforge.builders.system_builder import SystemTopologyBuilder
from acoustiforge.contracts.validation import InvalidParameterError, InvalidSampleRateError
from acoustiforge.domain.specifications import CrossoverFamily, CrossoverSpecification
from acoustiforge.graph.compute_graph import ComputeGraph, GraphLifecycle


class TestGraphBuilders:
    """Structural verification of acoustic compute graph generation."""

    def test_crossover_graph_builder_minimal_structure(self) -> None:
        """Verify minimal 2-way LR-4 crossover graph construction and frozen state."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2000.0,
        )
        synth_result = synthesize_crossover_biquads(spec, sample_rate=48000)

        builder = CrossoverGraphBuilder(sample_rate=48000, woofer_name="woofer", tweeter_name="tweeter")
        graph = builder.build_2way_graph(crossover_result=synth_result)

        assert isinstance(graph, ComputeGraph)
        assert graph.is_frozen
        assert graph.lifecycle == GraphLifecycle.FROZEN

        # Expected nodes:
        # root: "input"
        # woofer: "woofer.delay", "woofer.gain", "woofer.crossover.0", "woofer.crossover.1"
        # tweeter: "tweeter.delay", "tweeter.gain", "tweeter.crossover.0", "tweeter.crossover.1"
        expected_nodes = {
            "input",
            "woofer.delay",
            "woofer.gain",
            "woofer.crossover.0",
            "woofer.crossover.1",
            "tweeter.delay",
            "tweeter.gain",
            "tweeter.crossover.0",
            "tweeter.crossover.1",
        }
        assert set(graph.nodes.keys()) == expected_nodes

        # Inputs and outputs
        assert graph.inputs == (("input", "in"),)
        assert graph.outputs == (
            ("woofer.crossover.1", "out"),
            ("tweeter.crossover.1", "out"),
        )

        # Deterministic schedule is computed
        assert len(graph.schedule) == len(expected_nodes)
        assert graph.schedule[0] == "input"

    def test_crossover_graph_builder_full_pipeline_with_protection(self) -> None:
        """Verify full 2-way graph with alignment, gain, crossover, and protection stages."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2000.0,
        )
        synth = synthesize_crossover_biquads(spec, sample_rate=48000)

        alignments = {
            "woofer": DriverAlignmentResult("woofer", 0.0, 0.0, 0, 50.0, 50.0, 48000, 343.2),
            "tweeter": DriverAlignmentResult("tweeter", 0.0001, 4.8, 5, 15.0, 50.0, 48000, 343.2),
        }
        gains = {
            "woofer": GainDesignResult("woofer", 86.0, 86.0, 0.0, 1.0, False),
            "tweeter": GainDesignResult("tweeter", 90.0, 86.0, -4.0, 0.630957, False),
        }
        protections = {
            "woofer": design_infrasonic_protection_filter(cutoff_frequency_hz=30.0, sample_rate=48000, order=2, driver_name="woofer"),
        }

        builder = CrossoverGraphBuilder(sample_rate=48000, woofer_name="woofer", tweeter_name="tweeter")
        graph = builder.build_2way_graph(
            crossover_result=synth,
            alignments=alignments,
            gains=gains,
            protections=protections,
        )

        # Woofer output should now be from protection filter
        assert graph.outputs == (
            ("woofer.protection.0", "out"),
            ("tweeter.crossover.1", "out"),
        )

        # Parameters on delay and gain nodes match explicit inputs
        woofer_delay = graph.get_node("woofer.delay")
        tweeter_delay = graph.get_node("tweeter.delay")
        assert woofer_delay.delay_frames == 0
        assert tweeter_delay.delay_frames == 5

        woofer_gain = graph.get_node("woofer.gain")
        tweeter_gain = graph.get_node("tweeter.gain")
        assert woofer_gain.gain_db == 0.0
        assert tweeter_gain.gain_db == -4.0

    def test_system_topology_builder_stereo_2way(self) -> None:
        """Verify SystemTopologyBuilder creates a valid stereo 2-way DAG."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=2,
            frequency_hz=1500.0,
        )
        synth = synthesize_crossover_biquads(spec, sample_rate=48000)

        sys_builder = SystemTopologyBuilder(sample_rate=48000)
        graph = sys_builder.build_stereo_2way_graph(crossover_result=synth)

        assert graph.is_frozen
        # Should have 2 inputs (left.input, right.input) and 4 outputs (left/right woofer/tweeter)
        assert len(graph.inputs) == 2
        assert len(graph.outputs) == 4

    def test_deterministic_repeated_construction(self) -> None:
        """Verify multiple invocations of builder produce identical node IDs and schedule."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2000.0,
        )
        synth = synthesize_crossover_biquads(spec, sample_rate=48000)

        builder = CrossoverGraphBuilder(sample_rate=48000)
        g1 = builder.build_2way_graph(crossover_result=synth)
        g2 = builder.build_2way_graph(crossover_result=synth)

        assert g1.schedule == g2.schedule
        assert list(g1.nodes.keys()) == list(g2.nodes.keys())
        assert [str(e) for e in g1.edges] == [str(e) for e in g2.edges]

    def test_invalid_builder_inputs(self) -> None:
        """Verify strict parameter checking in builder constructor and methods."""
        with pytest.raises(InvalidSampleRateError):
            CrossoverGraphBuilder(sample_rate=0)

        with pytest.raises(InvalidParameterError, match="channels"):
            CrossoverGraphBuilder(sample_rate=48000, channels=0)

        with pytest.raises(InvalidParameterError, match="distinct"):
            CrossoverGraphBuilder(sample_rate=48000, woofer_name="same", tweeter_name="same")
