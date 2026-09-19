"""AcoustiForge Typed Compute Graph Test Suite.

Verifies CONTRACT-COMPUTE-GRAPH-01 conformance for Phase 2B.
"""

from __future__ import annotations

import numpy as np
import pytest

from acoustiforge.contracts.pcm import AudioMetadata, ChannelLayout, PCMBlock
from acoustiforge.contracts.validation import (
    CycleDetectedError,
    DuplicateEdgeError,
    FrozenGraphError,
    IncompatibleNodeError,
    InvalidGraphError,
    MalformedBufferError,
    UnconnectedPortError,
)
from acoustiforge.engine.sequential import SequentialPipeline
from acoustiforge.graph.compute_graph import ComputeGraph, GraphLifecycle
from acoustiforge.graph.edge import Edge
from acoustiforge.graph.ports import Port, PortDirection, PortShape, PortType
from acoustiforge.nodes.base import BaseProcessingNode
from acoustiforge.nodes.biquad import BiquadNode, FilterType
from acoustiforge.nodes.delay import DelayNode
from acoustiforge.nodes.gain import GainNode
from acoustiforge.nodes.passthrough import PassThroughNode


# --- Minimal Test Double for Multi-Input Convergence (Test-Only) ---

class TwoInputSummerNode(BaseProcessingNode):
    """Test-only multi-input summing node for fan-in topology verification."""

    def __init__(self, name: str = "TwoInputSummer") -> None:
        super().__init__(name=name)

    @property
    def latency_frames(self) -> int:
        return 0

    def process(self, block: PCMBlock) -> PCMBlock:
        return block

    def process_multi(self, block_a: PCMBlock, block_b: PCMBlock) -> PCMBlock:
        summed = block_a.samples + block_b.samples
        return PCMBlock(samples=summed, metadata=block_a.metadata)


# --- Fixtures ---

@pytest.fixture
def mono_metadata() -> AudioMetadata:
    return AudioMetadata(sample_rate=48000, channels=1)


@pytest.fixture
def stereo_metadata() -> AudioMetadata:
    return AudioMetadata(sample_rate=48000, channels=2)


@pytest.fixture
def mono_block(mono_metadata: AudioMetadata) -> PCMBlock:
    rng = np.random.default_rng(42)
    samples = rng.standard_normal((1, 256)).astype(np.float32)
    return PCMBlock(samples=samples, metadata=mono_metadata)


@pytest.fixture
def stereo_block(stereo_metadata: AudioMetadata) -> PCMBlock:
    rng = np.random.default_rng(42)
    samples = rng.standard_normal((2, 256)).astype(np.float32)
    return PCMBlock(samples=samples, metadata=stereo_metadata)


# --- 1. Construction & Registration Tests ---

class TestGraphConstruction:
    def test_empty_graph_initialization(self) -> None:
        graph = ComputeGraph(name="TestGraph")
        assert graph.name == "TestGraph"
        assert graph.lifecycle == GraphLifecycle.BUILDING
        assert not graph.is_frozen
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0
        assert len(graph.schedule) == 0
        assert len(graph.inputs) == 0
        assert len(graph.outputs) == 0

    def test_add_node_success(self) -> None:
        graph = ComputeGraph()
        gain = GainNode(gain_db=-3.0)
        graph.add_node("gain_1", gain)

        assert "gain_1" in graph.nodes
        assert graph.get_node("gain_1") is gain

        # Verify auto-bound default ports
        in_port = graph.get_port("gain_1", "in")
        out_port = graph.get_port("gain_1", "out")
        assert in_port.direction == PortDirection.INPUT
        assert out_port.direction == PortDirection.OUTPUT
        assert in_port.port_type == PortType.PCM
        assert out_port.port_type == PortType.PCM
        assert in_port.full_id == "gain_1.in"
        assert out_port.full_id == "gain_1.out"

    def test_add_duplicate_node_id_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        with pytest.raises(InvalidGraphError, match="Duplicate node ID"):
            graph.add_node("gain_1", GainNode())

    def test_add_invalid_node_type_rejected(self) -> None:
        graph = ComputeGraph()
        with pytest.raises(TypeError):
            graph.add_node("bad_node", "not_a_node")  # type: ignore

    def test_add_invalid_node_id_rejected(self) -> None:
        graph = ComputeGraph()
        with pytest.raises(InvalidGraphError):
            graph.add_node("", GainNode())
        with pytest.raises(InvalidGraphError):
            graph.add_node("   ", GainNode())

    def test_explicit_port_addition(self) -> None:
        graph = ComputeGraph()
        summer = TwoInputSummerNode()
        graph.add_node("summer", summer, auto_bind_ports=False)

        p_in_a = Port(node_id="summer", port_id="in_a", direction=PortDirection.INPUT)
        p_in_b = Port(node_id="summer", port_id="in_b", direction=PortDirection.INPUT)
        p_out = Port(node_id="summer", port_id="out", direction=PortDirection.OUTPUT)

        graph.add_port(p_in_a)
        graph.add_port(p_in_b)
        graph.add_port(p_out)

        assert graph.get_port("summer", "in_a") == p_in_a
        assert graph.get_port("summer", "in_b") == p_in_b
        assert graph.get_port("summer", "out") == p_out

    def test_add_port_to_nonexistent_node_rejected(self) -> None:
        graph = ComputeGraph()
        p = Port(node_id="ghost", port_id="in", direction=PortDirection.INPUT)
        with pytest.raises(InvalidGraphError, match="not registered"):
            graph.add_port(p)

    def test_add_duplicate_port_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain", GainNode())
        p = Port(node_id="gain", port_id="in", direction=PortDirection.INPUT)
        with pytest.raises(InvalidGraphError, match="already exists"):
            graph.add_port(p)


# --- 2. Edge & Connection Tests ---

class TestGraphEdges:
    def test_connect_valid_edge(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())

        edge = graph.connect("gain_1", "out", "gain_2", "in")
        assert isinstance(edge, Edge)
        assert edge.source_node_id == "gain_1"
        assert edge.source_port_id == "out"
        assert edge.target_node_id == "gain_2"
        assert edge.target_port_id == "in"
        assert len(graph.edges) == 1

    def test_connect_wrong_port_direction_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())

        # INPUT -> INPUT
        with pytest.raises(InvalidGraphError, match="direction must be OUTPUT"):
            graph.connect("gain_1", "in", "gain_2", "in")

        # OUTPUT -> OUTPUT
        with pytest.raises(InvalidGraphError, match="direction must be INPUT"):
            graph.connect("gain_1", "out", "gain_2", "out")

    def test_single_producer_constraint_violation_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())
        graph.add_node("sink", GainNode())

        graph.connect("gain_1", "out", "sink", "in")
        with pytest.raises(DuplicateEdgeError, match="already has an incoming edge"):
            graph.connect("gain_2", "out", "sink", "in")

    def test_disconnect_edge(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())
        graph.connect("gain_1", "out", "gain_2", "in")
        assert len(graph.edges) == 1

        graph.disconnect("gain_1", "out", "gain_2", "in")
        assert len(graph.edges) == 0

    def test_disconnect_nonexistent_edge_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())
        with pytest.raises(InvalidGraphError, match="not found"):
            graph.disconnect("gain_1", "out", "gain_2", "in")


# --- 3. Validation & DAG Tests ---

class TestGraphValidation:
    def test_validate_empty_graph_rejected(self) -> None:
        graph = ComputeGraph()
        with pytest.raises(InvalidGraphError, match="empty graph"):
            graph.validate()

    def test_validate_unconnected_required_port_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())
        graph.declare_input("gain_1", "in")
        graph.declare_output("gain_2", "out")
        # gain_2.in is not connected
        with pytest.raises(UnconnectedPortError, match="not connected"):
            graph.validate()

    def test_validate_declared_input_with_edge_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain_1", GainNode())
        graph.add_node("gain_2", GainNode())
        graph.connect("gain_1", "out", "gain_2", "in")
        graph.declare_input("gain_1", "in")
        graph.declare_input("gain_2", "in")  # invalid: gain_2.in is already driven by edge
        graph.declare_output("gain_2", "out")
        with pytest.raises(InvalidGraphError, match="cannot also have an incoming edge"):
            graph.validate()

    def test_validate_cycle_detection_2_nodes(self) -> None:
        graph = ComputeGraph()
        graph.add_node("A", GainNode())
        graph.add_node("B", GainNode())
        p_A_in2 = Port("A", "in2", PortDirection.INPUT, is_required=False)
        graph.add_port(p_A_in2)

        graph.declare_input("A", "in")
        graph.declare_output("B", "out")
        graph.connect("A", "out", "B", "in")
        graph.connect("B", "out", "A", "in2")

        with pytest.raises(CycleDetectedError, match="Cycle detected"):
            graph.validate()

    def test_validate_shape_mismatch_rejected(self) -> None:
        graph = ComputeGraph()
        g1 = GainNode()
        g1.configure(sample_rate=48000, channels=1)
        g2 = GainNode()
        g2.configure(sample_rate=44100, channels=1)  # Mismatched sample rate

        graph.add_node("g1", g1)
        graph.add_node("g2", g2)
        graph.connect("g1", "out", "g2", "in")
        graph.declare_input("g1", "in")
        graph.declare_output("g2", "out")

        with pytest.raises(IncompatibleNodeError, match="Shape mismatch"):
            graph.validate()

    def test_validate_missing_declared_output_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("g1", GainNode())
        graph.declare_input("g1", "in")
        with pytest.raises(InvalidGraphError, match="at least one output"):
            graph.validate()


# --- 4. Lifecycle & Immutability Tests ---

class TestGraphLifecycle:
    def test_lifecycle_transitions(self) -> None:
        graph = ComputeGraph()
        assert graph.lifecycle == GraphLifecycle.BUILDING

        graph.add_node("g1", GainNode())
        graph.declare_input("g1", "in")
        graph.declare_output("g1", "out")

        graph.validate()
        assert graph.lifecycle == GraphLifecycle.VALIDATED
        assert not graph.is_frozen

        graph.freeze()
        assert graph.lifecycle == GraphLifecycle.FROZEN
        assert graph.is_frozen

    def test_mutation_after_freeze_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("g1", GainNode())
        graph.declare_input("g1", "in")
        graph.declare_output("g1", "out")
        graph.freeze()

        with pytest.raises(FrozenGraphError):
            graph.add_node("g2", GainNode())

        with pytest.raises(FrozenGraphError):
            graph.add_port(Port("g1", "extra", PortDirection.INPUT))

        with pytest.raises(FrozenGraphError):
            graph.connect("g1", "out", "g1", "in")

        with pytest.raises(FrozenGraphError):
            graph.disconnect("g1", "out", "g1", "in")

        with pytest.raises(FrozenGraphError):
            graph.declare_input("g1", "in")

        with pytest.raises(FrozenGraphError):
            graph.declare_output("g1", "out")

    def test_process_before_freeze_rejected(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        graph.add_node("g1", GainNode())
        graph.declare_input("g1", "in")
        graph.declare_output("g1", "out")

        with pytest.raises(FrozenGraphError, match="must be in FROZEN"):
            graph.process(mono_block)

    def test_reset_before_freeze_rejected(self) -> None:
        graph = ComputeGraph()
        graph.add_node("g1", GainNode())
        with pytest.raises(FrozenGraphError, match="before it is frozen"):
            graph.reset()


# --- 5. Scheduling & Determinism Tests ---

class TestGraphScheduling:
    def test_linear_schedule(self) -> None:
        graph = ComputeGraph()
        graph.add_node("node_C", GainNode())
        graph.add_node("node_A", GainNode())
        graph.add_node("node_B", GainNode())

        graph.connect("node_A", "out", "node_B", "in")
        graph.connect("node_B", "out", "node_C", "in")
        graph.declare_input("node_A", "in")
        graph.declare_output("node_C", "out")

        graph.freeze()
        assert graph.schedule == ("node_A", "node_B", "node_C")

    def test_diamond_schedule_with_lexical_tie_breaking(self) -> None:
        # Topology:
        #        ┌→ branch_B ─┐
        # input ─┤            ├→ sink
        #        └→ branch_A ─┘
        graph = ComputeGraph()
        summer = TwoInputSummerNode()
        graph.add_node("src", PassThroughNode())
        graph.add_node("branch_B", GainNode())
        graph.add_node("branch_A", GainNode())
        graph.add_node("sink", summer, auto_bind_ports=False)

        graph.add_port(Port("sink", "in_a", PortDirection.INPUT))
        graph.add_port(Port("sink", "in_b", PortDirection.INPUT))
        graph.add_port(Port("sink", "out", PortDirection.OUTPUT))

        graph.declare_input("src", "in")
        graph.connect("src", "out", "branch_B", "in")
        graph.connect("src", "out", "branch_A", "in")
        graph.connect("branch_A", "out", "sink", "in_a")
        graph.connect("branch_B", "out", "sink", "in_b")
        graph.declare_output("sink", "out")

        graph.freeze()
        # branch_A and branch_B both become ready at the same time; branch_A < branch_B alphabetically
        assert graph.schedule == ("src", "branch_A", "branch_B", "sink")


# --- 6. Fan-Out Execution Tests ---

class TestFanOutExecution:
    def test_fan_out_executes_producer_once(self, mono_block: PCMBlock) -> None:
        class ExecutionCounterNode(BaseProcessingNode):
            def __init__(self) -> None:
                super().__init__()
                self.execution_count = 0

            @property
            def latency_frames(self) -> int:
                return 0

            def process(self, block: PCMBlock) -> PCMBlock:
                self.execution_count += 1
                return block.copy()

        graph = ComputeGraph()
        producer = ExecutionCounterNode()
        consumer_1 = GainNode(gain_db=-6.0)
        consumer_2 = GainNode(gain_db=-12.0)

        graph.add_node("producer", producer)
        graph.add_node("c1", consumer_1)
        graph.add_node("c2", consumer_2)

        graph.connect("producer", "out", "c1", "in")
        graph.connect("producer", "out", "c2", "in")
        graph.declare_input("producer", "in")
        graph.declare_output("c1", "out")
        graph.declare_output("c2", "out")

        graph.freeze()

        result = graph.process(mono_block)
        assert isinstance(result, dict)
        assert "c1.out" in result
        assert "c2.out" in result

        # Producer must have executed exactly ONCE
        assert producer.execution_count == 1

        # Check math on both branches
        expected_c1 = consumer_1.process(mono_block)
        expected_c2 = consumer_2.process(mono_block)
        np.testing.assert_allclose(result["c1.out"].samples, expected_c1.samples, rtol=1e-6)
        np.testing.assert_allclose(result["c2.out"].samples, expected_c2.samples, rtol=1e-6)


# --- 7. Execution Across DSP Primitives & Multi-Block Continuity ---

class TestDSPExecutionAndContinuity:
    def test_passthrough_execution(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        graph.add_node("pass", PassThroughNode())
        graph.declare_input("pass", "in")
        graph.declare_output("pass", "out")
        graph.freeze()

        out = graph.process(mono_block)
        assert isinstance(out, PCMBlock)
        np.testing.assert_array_equal(out.samples, mono_block.samples)

    def test_gain_execution(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        gain = GainNode(gain_db=6.0)
        graph.add_node("gain", gain)
        graph.declare_input("gain", "in")
        graph.declare_output("gain", "out")
        graph.freeze()

        out = graph.process(mono_block)
        assert isinstance(out, PCMBlock)
        expected = mono_block.samples * (10.0 ** (6.0 / 20.0))
        np.testing.assert_allclose(out.samples, expected, rtol=1e-6)

    def test_delay_multi_block_continuity(self, mono_metadata: AudioMetadata) -> None:
        delay_frames = 10
        delay_node = DelayNode(delay_frames=delay_frames)

        graph = ComputeGraph()
        graph.add_node("delay", delay_node)
        graph.declare_input("delay", "in")
        graph.declare_output("delay", "out")
        graph.freeze()

        # Stream of 3 small blocks (each 8 frames < 10 frames delay)
        rng = np.random.default_rng(123)
        total_samples = rng.standard_normal((1, 24)).astype(np.float32)
        b1 = PCMBlock(samples=total_samples[:, :8], metadata=mono_metadata)
        b2 = PCMBlock(samples=total_samples[:, 8:16], metadata=mono_metadata)
        b3 = PCMBlock(samples=total_samples[:, 16:24], metadata=mono_metadata)

        out1 = graph.process(b1)
        out2 = graph.process(b2)
        out3 = graph.process(b3)

        assert isinstance(out1, PCMBlock) and isinstance(out2, PCMBlock) and isinstance(out3, PCMBlock)
        concatenated = np.concatenate([out1.samples, out2.samples, out3.samples], axis=1)

        # Direct delay verification
        expected = np.zeros((1, 24), dtype=np.float32)
        expected[:, 10:] = total_samples[:, :14]
        np.testing.assert_allclose(concatenated, expected, rtol=1e-6)

    def test_biquad_multi_block_continuity(self, mono_metadata: AudioMetadata) -> None:
        biquad_node = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0, q=0.7071)

        graph = ComputeGraph()
        graph.add_node("biquad", biquad_node)
        graph.declare_input("biquad", "in")
        graph.declare_output("biquad", "out")
        graph.freeze()

        # Compare single 512-frame block vs 4x128-frame stream
        rng = np.random.default_rng(456)
        full_samples = rng.standard_normal((1, 512)).astype(np.float32)
        full_block = PCMBlock(samples=full_samples, metadata=mono_metadata)

        # Baseline single block via fresh node
        ref_node = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0, q=0.7071)
        ref_node.configure(mono_metadata.sample_rate, mono_metadata.channels)
        ref_out = ref_node.process(full_block)

        # Multi-block via graph
        blocks = [
            PCMBlock(samples=full_samples[:, i * 128 : (i + 1) * 128], metadata=mono_metadata)
            for i in range(4)
        ]
        graph_outs = list(graph.process_stream(iter(blocks)))
        graph_concatenated = np.concatenate([b.samples for b in graph_outs], axis=1)

        np.testing.assert_allclose(graph_concatenated, ref_out.samples, rtol=1e-6, atol=1e-7)


# --- 8. Reset Semantics Tests ---

class TestGraphReset:
    def test_reset_clears_state_and_preserves_topology(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        delay = DelayNode(delay_frames=32)
        biquad = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=500.0)

        graph.add_node("delay", delay)
        graph.add_node("biquad", biquad)
        graph.connect("delay", "out", "biquad", "in")
        graph.declare_input("delay", "in")
        graph.declare_output("biquad", "out")
        graph.freeze()

        # Run block 1 to populate delay lines & filter state
        _ = graph.process(mono_block)

        # Reset graph
        graph.reset()

        # Verify graph is still frozen and operational
        assert graph.is_frozen

        # Run fresh block from initial silence
        out_after_reset = graph.process(mono_block)

        # Create fresh comparison reference
        ref_delay = DelayNode(delay_frames=32)
        ref_biquad = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=500.0)
        ref_pipeline = SequentialPipeline([ref_delay, ref_biquad])
        expected = ref_pipeline.process(mono_block)

        assert isinstance(out_after_reset, PCMBlock)
        np.testing.assert_allclose(out_after_reset.samples, expected.samples, rtol=1e-6)


# --- 9. Latency & Latency Skew Tests ---

class TestGraphLatency:
    def test_linear_path_latency(self) -> None:
        graph = ComputeGraph()
        graph.add_node("gain", GainNode(gain_db=-3.0))  # 0 frames
        graph.add_node("delay_1", DelayNode(delay_frames=16))  # 16 frames
        graph.add_node("biquad", BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0))  # 0 frames
        graph.add_node("delay_2", DelayNode(delay_frames=8))  # 8 frames

        graph.connect("gain", "out", "delay_1", "in")
        graph.connect("delay_1", "out", "biquad", "in")
        graph.connect("biquad", "out", "delay_2", "in")
        graph.declare_input("gain", "in")
        graph.declare_output("delay_2", "out")
        graph.freeze()

        assert graph.get_path_latency("gain", "in") == 0
        assert graph.get_path_latency("gain", "out") == 0
        assert graph.get_path_latency("delay_1", "out") == 16
        assert graph.get_path_latency("biquad", "out") == 16
        assert graph.get_path_latency("delay_2", "out") == 24
        assert graph.get_output_latency(0) == 24

    def test_multi_input_latency_skew_detection(self) -> None:
        # Topology:
        #        ┌→ delay_A (D=5)  ─┐
        # input ─┤                  ├→ summer
        #        └→ delay_B (D=15) ─┘
        graph = ComputeGraph()
        summer = TwoInputSummerNode()
        graph.add_node("src", PassThroughNode())
        graph.add_node("delay_A", DelayNode(delay_frames=5))
        graph.add_node("delay_B", DelayNode(delay_frames=15))
        graph.add_node("summer", summer, auto_bind_ports=False)

        graph.add_port(Port("summer", "in_a", PortDirection.INPUT))
        graph.add_port(Port("summer", "in_b", PortDirection.INPUT))
        graph.add_port(Port("summer", "out", PortDirection.OUTPUT))

        graph.declare_input("src", "in")
        graph.connect("src", "out", "delay_A", "in")
        graph.connect("src", "out", "delay_B", "in")
        graph.connect("delay_A", "out", "summer", "in_a")
        graph.connect("delay_B", "out", "summer", "in_b")
        graph.declare_output("summer", "out")
        graph.freeze()

        skew = graph.detect_latency_skew()
        assert "summer" in skew
        # Skew = |15 - 5| = 10 frames
        assert skew["summer"] == 10


# --- 10. SequentialPipeline Equivalence Tests (Mandatory Conformance Gate) ---

class TestSequentialPipelineEquivalence:
    def test_three_stage_pipeline_golden_equivalence(self, stereo_metadata: AudioMetadata) -> None:
        """Verify that a linear ComputeGraph produces 100% bit-exact output to SequentialPipeline."""
        # Nodes for SequentialPipeline
        p_gain = GainNode(gain_db=-6.0)
        p_biquad = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1200.0, q=0.7071)
        p_delay = DelayNode(delay_frames=12)
        pipeline = SequentialPipeline([p_gain, p_biquad, p_delay])

        # Nodes for ComputeGraph (identical initial parameters)
        g_gain = GainNode(gain_db=-6.0)
        g_biquad = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1200.0, q=0.7071)
        g_delay = DelayNode(delay_frames=12)

        graph = ComputeGraph(name="LinearEquivalentGraph")
        graph.add_node("stage1_gain", g_gain)
        graph.add_node("stage2_biquad", g_biquad)
        graph.add_node("stage3_delay", g_delay)

        graph.connect("stage1_gain", "out", "stage2_biquad", "in")
        graph.connect("stage2_biquad", "out", "stage3_delay", "in")
        graph.declare_input("stage1_gain", "in")
        graph.declare_output("stage3_delay", "out")
        graph.freeze()

        # Generate multi-block pseudo-random stereo stream
        rng = np.random.default_rng(999)
        for block_idx in range(5):
            samples = rng.standard_normal((2, 128)).astype(np.float32)
            block = PCMBlock(samples=samples, metadata=stereo_metadata)

            pipe_out = pipeline.process(block)
            graph_out = graph.process(block)

            assert isinstance(graph_out, PCMBlock)
            np.testing.assert_array_equal(
                graph_out.samples,
                pipe_out.samples,
                err_msg=f"Mismatch between ComputeGraph and SequentialPipeline on block {block_idx}",
            )
            assert graph_out.metadata == pipe_out.metadata


# --- 11. Parameter Updates & Inactive Node Tests ---

class TestGraphParameterUpdates:
    def test_parameter_updates_in_frozen_graph(self, mono_block: PCMBlock) -> None:
        """Verify that atomic parameter updates to nodes in a frozen graph take effect immediately."""
        graph = ComputeGraph()
        gain = GainNode(gain_db=0.0)
        delay = DelayNode(delay_frames=0)
        graph.add_node("gain", gain)
        graph.add_node("delay", delay)
        graph.connect("gain", "out", "delay", "in")
        graph.declare_input("gain", "in")
        graph.declare_output("delay", "out")
        graph.freeze()

        # Step 1: 0 dB gain, 0 frame delay
        out1 = graph.process(mono_block)
        assert isinstance(out1, PCMBlock)
        np.testing.assert_array_equal(out1.samples, mono_block.samples)
        assert graph.get_output_latency() == 0

        # Step 2: Update parameters
        gain.set_parameters(gain_db=6.0)
        delay.set_parameters(delay_frames=8)

        # Latency should dynamically update
        assert graph.get_output_latency() == 8

        # Execution should reflect new gain & delay
        out2 = graph.process(mono_block)
        assert isinstance(out2, PCMBlock)
        expected_gain = mono_block.samples * (10.0 ** (6.0 / 20.0))
        # Initial 8 frames will be 0 from delay line transition
        np.testing.assert_allclose(out2.samples[:, 8:], expected_gain[:, :248], rtol=1e-6)

    def test_inactive_node_latency(self) -> None:
        graph = ComputeGraph()
        delay = DelayNode(delay_frames=16)
        graph.add_node("delay", delay)
        graph.declare_input("delay", "in")
        graph.declare_output("delay", "out")
        graph.freeze()

        assert graph.get_output_latency() == 16
        delay.is_active = False
        assert graph.get_output_latency() == 0


# --- 12. Multiple Graph Inputs / Outputs & Dictionary Mapping ---

class TestMultipleIOAndDictMapping:
    def test_multi_input_multi_output_execution(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        g1 = GainNode(gain_db=3.0)
        g2 = GainNode(gain_db=-3.0)
        graph.add_node("g1", g1)
        graph.add_node("g2", g2)
        graph.declare_input("g1", "in")
        graph.declare_input("g2", "in")
        graph.declare_output("g1", "out")
        graph.declare_output("g2", "out")
        graph.freeze()

        # Execute using dict input
        result = graph.process({
            "g1.in": mono_block,
            "g2.in": mono_block,
        })
        assert isinstance(result, dict)
        assert "g1.out" in result and "g2.out" in result

        expected_g1 = g1.process(mono_block)
        expected_g2 = g2.process(mono_block)
        np.testing.assert_allclose(result["g1.out"].samples, expected_g1.samples, rtol=1e-6)
        np.testing.assert_allclose(result["g2.out"].samples, expected_g2.samples, rtol=1e-6)

    def test_missing_input_in_dict_raises_error(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        graph.add_node("g1", GainNode())
        graph.add_node("g2", GainNode())
        graph.declare_input("g1", "in")
        graph.declare_input("g2", "in")
        graph.declare_output("g1", "out")
        graph.freeze()

        with pytest.raises(InvalidGraphError, match="Missing input"):
            graph.process({"g1.in": mono_block})

    def test_process_stream_on_multi_output_graph_raises_error(self, mono_block: PCMBlock) -> None:
        graph = ComputeGraph()
        graph.add_node("g1", GainNode())
        graph.add_node("g2", GainNode())
        graph.declare_input("g1", "in")
        graph.connect("g1", "out", "g2", "in")
        graph.declare_output("g1", "out")
        graph.declare_output("g2", "out")
        graph.freeze()

        with pytest.raises(InvalidGraphError, match="process_stream requires a graph with a single declared output"):
            list(graph.process_stream(iter([mono_block])))

