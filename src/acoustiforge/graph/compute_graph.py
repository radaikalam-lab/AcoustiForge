"""AcoustiForge Typed Compute Graph.

Normative Authority:
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/phases/PHASE_2A_1_TYPED_COMPUTE_GRAPH_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import heapq
from enum import Enum
from typing import Any, Iterator, Optional, Sequence

from ..contracts.pcm import PCMBlock
from ..contracts.validation import (
    AcoustiForgeError,
    CycleDetectedError,
    DuplicateEdgeError,
    FrozenGraphError,
    IncompatibleNodeError,
    InvalidGraphError,
    MalformedBufferError,
    UnconnectedPortError,
    validate_metadata,
)
from ..nodes.base import BaseProcessingNode
from .edge import Edge
from .ports import Port, PortDirection, PortShape, PortType


class GraphLifecycle(str, Enum):
    """Formal structural lifecycle states of a compute graph."""
    BUILDING = "building"
    VALIDATED = "validated"
    FROZEN = "frozen"


class ComputeGraph:
    """Deterministic typed computation graph executing DAG topologies of ACE nodes.

    Conforms to CONTRACT-COMPUTE-GRAPH-01.
    """

    def __init__(self, name: Optional[str] = None) -> None:
        self._name: str = name if name is not None else self.__class__.__name__
        self._lifecycle: GraphLifecycle = GraphLifecycle.BUILDING
        self._nodes: dict[str, BaseProcessingNode] = {}
        self._ports: dict[str, dict[str, Port]] = {}
        self._edges: list[Edge] = []
        self._inputs: list[tuple[str, str]] = []
        self._outputs: list[tuple[str, str]] = []
        self._schedule: list[str] = []

    @property
    def name(self) -> str:
        """Identifier of this compute graph."""
        return self._name

    @property
    def lifecycle(self) -> GraphLifecycle:
        """Current structural lifecycle state of this graph."""
        return self._lifecycle

    @property
    def is_frozen(self) -> bool:
        """Whether the graph topology and schedule are frozen."""
        return self._lifecycle == GraphLifecycle.FROZEN

    @property
    def nodes(self) -> dict[str, BaseProcessingNode]:
        """Dictionary of registered node instances keyed by node_id."""
        return dict(self._nodes)

    @property
    def edges(self) -> tuple[Edge, ...]:
        """Tuple of registered directed edges."""
        return tuple(self._edges)

    @property
    def schedule(self) -> tuple[str, ...]:
        """Precomputed deterministic static topological execution schedule."""
        return tuple(self._schedule)

    @property
    def inputs(self) -> tuple[tuple[str, str], ...]:
        """Declared external graph inputs as ((node_id, port_id), ...)."""
        return tuple(self._inputs)

    @property
    def outputs(self) -> tuple[tuple[str, str], ...]:
        """Declared graph outputs as ((node_id, port_id), ...)."""
        return tuple(self._outputs)

    def _assert_building(self) -> None:
        """Raise FrozenGraphError if topology mutation is attempted while frozen."""
        if self._lifecycle == GraphLifecycle.FROZEN:
            raise FrozenGraphError("Cannot mutate graph topology while in FROZEN lifecycle state.")

    def add_node(
        self,
        node_id: str,
        node: BaseProcessingNode,
        auto_bind_ports: bool = True,
    ) -> None:
        """Register a processing node instance into the graph.

        Args:
            node_id: Unique string identifier for this node within the graph.
            node: BaseProcessingNode instance.
            auto_bind_ports: If True, automatically creates default 'in' and 'out' ports.

        Raises:
            FrozenGraphError: If graph is frozen.
            InvalidGraphError: If node_id already exists or is empty.
            TypeError: If node is not a BaseProcessingNode.
        """
        self._assert_building()

        if not isinstance(node_id, str) or not node_id.strip():
            raise InvalidGraphError(f"Invalid node_id: {node_id!r}. Must be a non-empty string.")

        if node_id in self._nodes:
            raise InvalidGraphError(f"Duplicate node ID: {node_id!r} already registered in graph.")

        if not isinstance(node, BaseProcessingNode):
            raise TypeError(f"Expected BaseProcessingNode instance, got {type(node)!r}.")

        self._nodes[node_id] = node
        self._ports[node_id] = {}

        if auto_bind_ports:
            shape: Optional[PortShape] = None
            if node._sample_rate is not None and node._channels is not None:
                shape = PortShape(sample_rate=node._sample_rate, channels=node._channels)

            self.add_port(
                Port(
                    node_id=node_id,
                    port_id="in",
                    direction=PortDirection.INPUT,
                    port_type=PortType.PCM,
                    shape=shape,
                    is_required=True,
                )
            )
            self.add_port(
                Port(
                    node_id=node_id,
                    port_id="out",
                    direction=PortDirection.OUTPUT,
                    port_type=PortType.PCM,
                    shape=shape,
                    is_required=True,
                )
            )

        self._lifecycle = GraphLifecycle.BUILDING

    def add_port(self, port: Port) -> None:
        """Register an explicit port on a node.

        Raises:
            FrozenGraphError: If graph is frozen.
            InvalidGraphError: If node does not exist or port ID already exists on node.
            TypeError: If port is not a Port instance.
        """
        self._assert_building()

        if not isinstance(port, Port):
            raise TypeError(f"Expected Port instance, got {type(port)!r}.")

        if port.node_id not in self._nodes:
            raise InvalidGraphError(
                f"Cannot add port {port.port_id!r}: node {port.node_id!r} is not registered in graph."
            )

        if port.port_id in self._ports[port.node_id]:
            raise InvalidGraphError(
                f"Port {port.port_id!r} already exists on node {port.node_id!r}."
            )

        self._ports[port.node_id][port.port_id] = port
        self._lifecycle = GraphLifecycle.BUILDING

    def get_port(self, node_id: str, port_id: str) -> Port:
        """Retrieve a registered port.

        Raises:
            InvalidGraphError: If node or port does not exist.
        """
        if node_id not in self._nodes:
            raise InvalidGraphError(f"Node {node_id!r} is not registered in graph.")
        if port_id not in self._ports[node_id]:
            raise InvalidGraphError(f"Port {port_id!r} not found on node {node_id!r}.")
        return self._ports[node_id][port_id]

    def get_node(self, node_id: str) -> BaseProcessingNode:
        """Retrieve a registered node instance."""
        if node_id not in self._nodes:
            raise InvalidGraphError(f"Node {node_id!r} is not registered in graph.")
        return self._nodes[node_id]

    def connect(
        self,
        source_node_id: str,
        source_port_id: str,
        target_node_id: str,
        target_port_id: str,
    ) -> Edge:
        """Create a directed edge from a producer output port to a consumer input port.

        Raises:
            FrozenGraphError: If graph is frozen.
            InvalidGraphError: If endpoints are invalid or directions are incorrect.
            DuplicateEdgeError: If target port already has an incoming edge or edge already exists.
        """
        self._assert_building()

        source_port = self.get_port(source_node_id, source_port_id)
        target_port = self.get_port(target_node_id, target_port_id)

        if source_port.direction != PortDirection.OUTPUT:
            raise InvalidGraphError(
                f"Source port {source_port.full_id} direction must be OUTPUT, got {source_port.direction.value}."
            )

        if target_port.direction != PortDirection.INPUT:
            raise InvalidGraphError(
                f"Target port {target_port.full_id} direction must be INPUT, got {target_port.direction.value}."
            )

        # Check single-producer invariant on target input port
        for edge in self._edges:
            if edge.target_node_id == target_node_id and edge.target_port_id == target_port_id:
                raise DuplicateEdgeError(
                    f"Target input port {target_port.full_id} already has an incoming edge from {edge.source_full_id}."
                )

        new_edge = Edge(
            source_node_id=source_node_id,
            source_port_id=source_port_id,
            target_node_id=target_node_id,
            target_port_id=target_port_id,
        )
        self._edges.append(new_edge)
        self._lifecycle = GraphLifecycle.BUILDING
        return new_edge

    def disconnect(
        self,
        source_node_id: str,
        source_port_id: str,
        target_node_id: str,
        target_port_id: str,
    ) -> None:
        """Remove an existing directed edge.

        Raises:
            FrozenGraphError: If graph is frozen.
            InvalidGraphError: If edge is not found.
        """
        self._assert_building()

        target_edge = Edge(
            source_node_id=source_node_id,
            source_port_id=source_port_id,
            target_node_id=target_node_id,
            target_port_id=target_port_id,
        )

        if target_edge not in self._edges:
            raise InvalidGraphError(f"Edge {target_edge} not found in graph.")

        self._edges.remove(target_edge)
        self._lifecycle = GraphLifecycle.BUILDING

    def declare_input(self, node_id: str, port_id: str = "in") -> None:
        """Explicitly declare an external graph input feeding a specific node input port.

        Raises:
            FrozenGraphError: If graph is frozen.
            InvalidGraphError: If port does not exist, is not INPUT, or is already declared.
        """
        self._assert_building()

        port = self.get_port(node_id, port_id)
        if port.direction != PortDirection.INPUT:
            raise InvalidGraphError(
                f"Declared graph input port {port.full_id} must have direction INPUT, got {port.direction.value}."
            )

        entry = (node_id, port_id)
        if entry in self._inputs:
            raise InvalidGraphError(f"Graph input {port.full_id} is already declared.")

        self._inputs.append(entry)
        self._lifecycle = GraphLifecycle.BUILDING

    def declare_output(self, node_id: str, port_id: str = "out") -> None:
        """Explicitly declare an external graph output from a specific node output port.

        Raises:
            FrozenGraphError: If graph is frozen.
            InvalidGraphError: If port does not exist, is not OUTPUT, or is already declared.
        """
        self._assert_building()

        port = self.get_port(node_id, port_id)
        if port.direction != PortDirection.OUTPUT:
            raise InvalidGraphError(
                f"Declared graph output port {port.full_id} must have direction OUTPUT, got {port.direction.value}."
            )

        entry = (node_id, port_id)
        if entry in self._outputs:
            raise InvalidGraphError(f"Graph output {port.full_id} is already declared.")

        self._outputs.append(entry)
        self._lifecycle = GraphLifecycle.BUILDING

    def validate(self) -> None:
        """Perform comprehensive structural and semantic graph validation.

        Verifies:
            1. Referential integrity of nodes, ports, edges, inputs, outputs.
            2. Single-producer constraint on every input port.
            3. Declared graph inputs have no incoming edges.
            4. All required input ports are connected or declared as graph inputs.
            5. Strict Type and Shape compatibility across all edges.
            6. Strict DAG acyclicity (CycleDetectedError on cycles).
            7. Deterministic static topological schedule generation.

        Raises:
            InvalidGraphError: If structural or referential invariants fail.
            UnconnectedPortError: If a required input port lacks an incoming edge.
            IncompatibleNodeError: If Type or Shape mismatches across an edge.
            CycleDetectedError: If a directed cycle exists.
        """
        if len(self._nodes) == 0:
            raise InvalidGraphError("Cannot validate an empty graph with no nodes.")

        # 1. Referential integrity & edge endpoint validity
        for edge in self._edges:
            src = self.get_port(edge.source_node_id, edge.source_port_id)
            tgt = self.get_port(edge.target_node_id, edge.target_port_id)

            if src.direction != PortDirection.OUTPUT:
                raise InvalidGraphError(f"Source port {src.full_id} must be OUTPUT.")
            if tgt.direction != PortDirection.INPUT:
                raise InvalidGraphError(f"Target port {tgt.full_id} must be INPUT.")

            # 5. Type and Shape compatibility
            if src.port_type != tgt.port_type:
                raise IncompatibleNodeError(
                    f"Port Type mismatch across edge {edge}: "
                    f"source type={src.port_type.value}, target type={tgt.port_type.value}."
                )

            if src.shape is not None and tgt.shape is not None:
                if src.shape != tgt.shape:
                    raise IncompatibleNodeError(
                        f"Port Shape mismatch across edge {edge}: "
                        f"source shape={src.shape}, target shape={tgt.shape}."
                    )

        # 2 & 3. Declared inputs must not have incoming edges
        declared_input_set = set(self._inputs)
        edge_targets = {(e.target_node_id, e.target_port_id) for e in self._edges}

        for in_entry in declared_input_set:
            if in_entry in edge_targets:
                raise InvalidGraphError(
                    f"Declared graph input port '{in_entry[0]}.{in_entry[1]}' cannot also have an incoming edge."
                )

        # 4. Required input connectivity
        for node_id, ports in self._ports.items():
            for port_id, port in ports.items():
                if port.direction == PortDirection.INPUT and port.is_required:
                    entry = (node_id, port_id)
                    if entry not in edge_targets and entry not in declared_input_set:
                        raise UnconnectedPortError(
                            f"Required input port {port.full_id} is not connected by an incoming edge "
                            f"and not declared as a graph input."
                        )

        # 6. Strict DAG acyclicity & deterministic topological schedule generation
        in_degree: dict[str, int] = {node_id: 0 for node_id in self._nodes}
        adj: dict[str, list[str]] = {node_id: [] for node_id in self._nodes}

        for edge in self._edges:
            src = edge.source_node_id
            tgt = edge.target_node_id
            adj[src].append(tgt)
            in_degree[tgt] += 1

        # Deterministic secondary ordering: alphabetical min-heap of node_id
        ready_queue: list[str] = [node_id for node_id, deg in in_degree.items() if deg == 0]
        heapq.heapify(ready_queue)

        computed_schedule: list[str] = []
        while ready_queue:
            current = heapq.heappop(ready_queue)
            computed_schedule.append(current)
            for neighbor in adj[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    heapq.heappush(ready_queue, neighbor)

        if len(computed_schedule) != len(self._nodes):
            raise CycleDetectedError("Cycle detected in compute graph: topology is not a strict DAG.")

        # Validate declared outputs
        if len(self._outputs) == 0:
            raise InvalidGraphError("Compute graph must declare at least one output.")

        for out_entry in self._outputs:
            port = self.get_port(out_entry[0], out_entry[1])
            if port.direction != PortDirection.OUTPUT:
                raise InvalidGraphError(
                    f"Declared graph output '{port.full_id}' is not an OUTPUT port."
                )

        self._schedule = computed_schedule
        self._lifecycle = GraphLifecycle.VALIDATED

    def freeze(self) -> None:
        """Validate and lock graph topology into an immutable executable state.

        Derives and stores the static deterministic topological schedule.

        Raises:
            InvalidGraphError / CycleDetectedError / IncompatibleNodeError: If validation fails.
        """
        self.validate()
        self._lifecycle = GraphLifecycle.FROZEN

    def reset(self) -> None:
        """Reset internal filter states and registers of all nodes in topological order.

        Preserves graph topology, parameters, and frozen schedule.

        Raises:
            FrozenGraphError: If graph is not frozen.
        """
        if not self.is_frozen:
            raise FrozenGraphError("Cannot reset graph before it is frozen.")

        for node_id in self._schedule:
            self._nodes[node_id].reset()

    def process(self, input_blocks: PCMBlock | dict[str, PCMBlock]) -> PCMBlock | dict[str, PCMBlock]:
        """Execute the compute graph over a single block of audio data.

        Args:
            input_blocks: Single canonical PCMBlock (if graph has 1 declared input)
                          or dict mapping 'node_id.port_id' to PCMBlock.

        Returns:
            Processed PCMBlock (if graph has 1 declared output)
            or dict mapping 'node_id.port_id' to PCMBlock.

        Raises:
            FrozenGraphError: If graph is not frozen.
            MalformedBufferError: If input blocks are invalid.
            InvalidGraphError: If input block mapping does not match declared graph inputs.
        """
        if not self.is_frozen:
            raise FrozenGraphError("Cannot execute graph: graph must be in FROZEN lifecycle state.")

        # 1. Resolve declared external graph inputs
        resolved_inputs: dict[str, PCMBlock] = {}
        if isinstance(input_blocks, PCMBlock):
            if len(self._inputs) != 1:
                raise InvalidGraphError(
                    f"Single PCMBlock supplied but graph has {len(self._inputs)} declared inputs: "
                    f"{[f'{n}.{p}' for n, p in self._inputs]}."
                )
            in_node, in_port = self._inputs[0]
            resolved_inputs[f"{in_node}.{in_port}"] = input_blocks
        elif isinstance(input_blocks, dict):
            for in_node, in_port in self._inputs:
                full_id = f"{in_node}.{in_port}"
                if full_id in input_blocks:
                    resolved_inputs[full_id] = input_blocks[full_id]
                elif in_port in input_blocks and len(self._inputs) == 1:
                    resolved_inputs[full_id] = input_blocks[in_port]
                else:
                    raise InvalidGraphError(
                        f"Missing input block for declared graph input '{full_id}'."
                    )
        else:
            raise MalformedBufferError(
                f"Expected PCMBlock or dict[str, PCMBlock], got {type(input_blocks)!r}."
            )

        # 2. Intermediate buffer store (full_port_id -> PCMBlock)
        port_buffers: dict[str, PCMBlock] = dict(resolved_inputs)

        # 3. Synchronous execution along precomputed static schedule
        for node_id in self._schedule:
            node = self._nodes[node_id]
            node_ports = self._ports[node_id]
            in_ports = [p for p in node_ports.values() if p.direction == PortDirection.INPUT]

            if not in_ports:
                # Source node with 0 input ports (if any)
                continue

            # Gather incoming blocks for this node
            collected_blocks: list[PCMBlock] = []
            for p in sorted(in_ports, key=lambda x: x.port_id):
                p_full = p.full_id
                if p_full in port_buffers:
                    collected_blocks.append(port_buffers[p_full])
                else:
                    incoming_edge = next(
                        (e for e in self._edges if e.target_node_id == node_id and e.target_port_id == p.port_id),
                        None,
                    )
                    if incoming_edge is None or incoming_edge.source_full_id not in port_buffers:
                        raise InvalidGraphError(
                            f"Missing input data buffer for port {p_full} during execution."
                        )
                    collected_blocks.append(port_buffers[incoming_edge.source_full_id])

            # Auto-configure node if unconfigured
            first_block = collected_blocks[0]
            if node._sample_rate is None or node._channels is None:
                node.configure(first_block.sample_rate, first_block.channels)
            else:
                if first_block.sample_rate != node._sample_rate:
                    raise IncompatibleNodeError(
                        f"Sample rate mismatch: Node '{node_id}' configured for {node._sample_rate} Hz, "
                        f"got {first_block.sample_rate} Hz."
                    )
                if first_block.channels != node._channels:
                    raise IncompatibleNodeError(
                        f"Channel count mismatch: Node '{node_id}' configured for {node._channels} channels, "
                        f"got {first_block.channels} channels."
                    )

            # Execute node
            if hasattr(node, "process_multi"):
                out_block = getattr(node, "process_multi")(*collected_blocks)
            elif len(collected_blocks) == 1:
                out_block = node.process(collected_blocks[0])
            else:
                out_block = node.process(*collected_blocks)

            # Store output block to node output port(s)
            out_ports = [p for p in node_ports.values() if p.direction == PortDirection.OUTPUT]
            if len(out_ports) == 1:
                port_buffers[out_ports[0].full_id] = out_block
            elif isinstance(out_block, dict):
                for p in out_ports:
                    port_buffers[p.full_id] = out_block[p.port_id]
            elif isinstance(out_block, (list, tuple)):
                for p, b in zip(out_ports, out_block):
                    port_buffers[p.full_id] = b

        # 4. Collect and return declared outputs
        if len(self._outputs) == 1:
            out_node, out_port = self._outputs[0]
            return port_buffers[f"{out_node}.{out_port}"]
        else:
            return {
                f"{out_node}.{out_port}": port_buffers[f"{out_node}.{out_port}"]
                for out_node, out_port in self._outputs
            }

    def process_stream(self, stream: Iterator[PCMBlock]) -> Iterator[PCMBlock]:
        """Process a stream of PCM blocks through the frozen compute graph."""
        for block in stream:
            out = self.process(block)
            if isinstance(out, PCMBlock):
                yield out
            else:
                raise InvalidGraphError(
                    "process_stream requires a graph with a single declared output."
                )

    def get_path_latency(self, target_node_id: str, target_port_id: str) -> int:
        """Calculate cumulative algorithmic latency in frames to a specific port.

        Args:
            target_node_id: Target node ID.
            target_port_id: Target port ID.

        Returns:
            Accumulated latency in frames.
        """
        port = self.get_port(target_node_id, target_port_id)
        if port.direction == PortDirection.INPUT:
            # If declared graph input: latency is 0
            if (target_node_id, target_port_id) in self._inputs:
                return 0
            # Otherwise from incoming edge
            edge = next(
                (e for e in self._edges if e.target_node_id == target_node_id and e.target_port_id == target_port_id),
                None,
            )
            if edge is None:
                return 0
            return self.get_path_latency(edge.source_node_id, edge.source_port_id)
        else:
            # Output port: node latency + max(path latencies to its input ports)
            node = self._nodes[target_node_id]
            node_latency = node.latency_frames if node.is_active else 0
            in_ports = [p for p in self._ports[target_node_id].values() if p.direction == PortDirection.INPUT]
            if not in_ports:
                return node_latency
            max_in_latency = max(self.get_path_latency(target_node_id, p.port_id) for p in in_ports)
            return max_in_latency + node_latency

    def get_output_latency(self, output_index: int = 0) -> int:
        """Return accumulated path latency in frames for a declared graph output."""
        if output_index < 0 or output_index >= len(self._outputs):
            raise IndexError(f"Output index {output_index} out of range for graph with {len(self._outputs)} outputs.")
        node_id, port_id = self._outputs[output_index]
        return self.get_path_latency(node_id, port_id)

    def detect_latency_skew(self) -> dict[str, int]:
        """Detect and report temporal latency skew across multi-input converging nodes.

        Returns:
            Dictionary mapping node_id to latency skew (max_latency - min_latency) in frames.
        """
        skew_report: dict[str, int] = {}
        for node_id, ports in self._ports.items():
            in_ports = [p for p in ports.values() if p.direction == PortDirection.INPUT]
            if len(in_ports) > 1:
                latencies = [self.get_path_latency(node_id, p.port_id) for p in in_ports]
                skew = max(latencies) - min(latencies)
                if skew > 0:
                    skew_report[node_id] = skew
        return skew_report
