# AcoustiForge Normative Contract: Typed Compute Graph

**Document ID:** `CONTRACT-COMPUTE-GRAPH-01`  
**Status:** **FROZEN & NORMATIVE**  
**Version:** `1.0.0`  
**Governing Authority:** `prompts/MASTER_PROMPT.md`  
**Reconciliation Authority:** `docs/phases/PHASE_2A_1_TYPED_COMPUTE_GRAPH_CONTRACT_RECONCILIATION.md`

---

## 1. Purpose

This contract establishes the universal mathematical, structural, and operational rules governing the definition, validation, scheduling, and execution of Typed Compute Graphs within the Acoustic Compute Engine (ACE).

---

## 2. Scope

This contract applies to all multi-node computational graph representations in AcoustiForge. It governs directed acyclic dataflow topologies, port typing, dimensional compatibility, deterministic scheduling, latency propagation, and memory ownership semantics across all ACE runtimes.

---

## 3. Normative Terminology

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, **RECOMMENDED**, **MAY**, and **OPTIONAL** in this document are to be interpreted as described in RFC 2119 / BCP 14.

---

## 4. Relationship to PCM Contract

1. All audio payload data traversing graph edges in Phase 2 MUST conform strictly to the frozen PCM Contract (`docs/contracts/PCM_CONTRACT.md`).
2. Graph execution MUST NOT mutate or violate canonical PCM block properties (`(channels, frames)`, `float32`, planar, C-contiguous layout).

---

## 5. Relationship to Node Composition Contract

1. This contract extends the linear composition semantics established in `docs/contracts/NODE_COMPOSITION_CONTRACT.md` to general directed acyclic graphs.
2. Every linear `SequentialPipeline` MUST remain fully representable as a 1-dimensional compute graph.

---

## 6. Graph Definition

A Typed Compute Graph $\mathcal{G}$ is formally defined as the 5-tuple:
$$\mathcal{G} = \langle \mathcal{V}, \mathcal{P}, \mathcal{E}, \mathcal{I}, \mathcal{S} \rangle$$
where:
- $\mathcal{V}$: Finite set of computational node instances.
- $\mathcal{P} = \mathcal{P}_{\text{in}} \cup \mathcal{P}_{\text{out}}$: Set of typed directional input and output ports.
- $\mathcal{E} \subseteq \mathcal{P}_{\text{out}} \times \mathcal{P}_{\text{in}}$: Set of directed communication edges.
- $\mathcal{I}$: Set of formal graph-level invariants.
- $\mathcal{S}$: Precomputed static topological execution schedule.

---

## 7. Node Identity & Scoping

1. Each node instance in $\mathcal{G}$ MUST possess a non-empty string identifier (`node_id`) that is unique within the graph namespace.
2. Node instance IDs MUST be immutable once the graph is frozen.
3. An active stateful node instance MUST NOT belong to more than one executing graph instance simultaneously.

---

## 8. Port Identity

1. Each port on a node MUST possess a non-empty string identifier (`port_id`) that is unique within its parent node's port namespace.
2. A port's global address within $\mathcal{G}$ is fully qualified as `node_id.port_id`.

---

## 9. Port Direction & Cardinality

1. A port MUST declare its direction as either `INPUT` or `OUTPUT`.
2. An `INPUT` port MUST accept at most one incoming directed edge ($\text{in-degree} \le 1$).
3. An `OUTPUT` port MAY connect to zero or more destination input ports ($\text{out-degree} \ge 0$).
4. Source nodes (zero input ports) and sink nodes (zero output ports) are valid computational elements.

---

## 10. Type Semantics

1. A port MUST declare its semantic payload Type $\mathcal{T}$ (e.g., `PCM`).
2. Type compatibility requires exact equality across an edge: $\text{Type}(p_{\text{src}}) \equiv \text{Type}(p_{\text{dst}})$.
3. Graph edges MUST NOT perform implicit semantic type conversion.

---

## 11. Shape Semantics

1. A port MUST declare its structural Shape $\mathcal{S} = \langle C, f_s, \text{layout}, \text{dtype} \rangle$.
2. In the reference Python runtime, canonical shape parameters are:
   - $C \in \{1, 2\}$ (Mono or Stereo).
   - $f_s \in \mathbb{Z}^+$ (Discrete sample clock rate in Hz).
   - $\text{layout} = \text{PLANAR\_C\_CONTIGUOUS}$.
   - $\text{dtype} = \text{float32}$.

---

## 12. Compatibility

A directed edge $e = (v_{\text{src}}, p_{\text{src}}) \to (v_{\text{dst}}, p_{\text{dst}})$ is valid if and only if:
1. $p_{\text{src}}$ is an `OUTPUT` port.
2. $p_{\text{dst}}$ is an `INPUT` port.
3. $\text{Type}(p_{\text{src}}) \equiv \text{Type}(p_{\text{dst}})$.
4. $\mathcal{S}(p_{\text{src}}) \equiv \mathcal{S}(p_{\text{dst}})$.

If any requirement is violated, graph validation MUST raise `IncompatibleNodeError`.

---

## 13. Edge Semantics

1. An edge represents purely logical dataflow routing from a producer port to a consumer port.
2. An edge MUST NOT introduce algorithmic latency, signal attenuation, buffering delay, or mathematical transformation.

---

## 14. Fan-Out Semantics

1. When an output port connects to multiple downstream input ports ($N \ge 2$), the producer node MUST execute exactly once per block.
2. The producer's output data MUST be delivered to all downstream consumers as logically immutable read-only input.
3. Downstream consumers MUST NOT mutate shared input buffers in place.

---

## 15. Fan-In Semantics

1. Direct connection of multiple edges to a single input port is strictly prohibited.
2. Multi-signal convergence (fan-in) MUST be achieved through an explicit multi-input computational node (e.g., a summing or mixing node).

---

## 16. Latency Propagation

1. Node algorithmic latency $\mathcal{L}(v) \in \mathbb{N}_0$ is an inherent property of each node operator.
2. Edge latency $\mathcal{L}(e) \equiv 0$.
3. For any directed path $\pi = (v_1, v_2, \dots, v_m)$, the path latency is strictly additive:
$$\mathcal{L}(\pi) = \sum_{k=1}^{m} \mathcal{L}(v_k)$$
4. The graph MUST report latency per declared graph output port as the accumulated latency along its driving path.

---

## 17. Latency Alignment

1. When multiple paths converge at a multi-input node, the graph validator MUST compute and report any temporal skew $\Delta \mathcal{L} = |\mathcal{L}_{\pi_1} - \mathcal{L}_{\pi_2}|$.
2. The graph engine MUST NOT silently insert delay lines or mutate signal alignment. Temporal alignment is the explicit responsibility of graph topology design.

---

## 18. DAG & Acyclicity Policy

1. All compute graphs in Phase 2 MUST be Directed Acyclic Graphs (DAGs).
2. Graph validation MUST detect and reject all directed cycles with `CycleDetectedError`.
3. Feedback loops requiring cyclic topologies are deferred to a dedicated future feedback profile.

---

## 19. Graph Validation

A graph MUST successfully pass validation before it can be frozen or executed. Validation verifies:
1. Referential integrity of all nodes and ports.
2. Single-producer invariant on all input ports.
3. Exact Type and Shape compatibility across every edge.
4. Absence of directed cycles (DAG validation).
5. All required input ports are connected.
6. Existence of a valid deterministic topological schedule.

---

## 20. Deterministic Execution Ordering

1. Execution order is derived via topological sorting of the DAG.
2. Determinism is normative across all conforming runtimes. The Python reference runtime MUST use a deterministic secondary ordering, with lexical node_id ordering as the reference policy. Other conforming runtimes MAY use an equivalent deterministic precomputed schedule representation, provided graph semantics and reproducibility are preserved.
3. Identical graph definitions, parameters, and input streams MUST produce 100% reproducible execution sequences and bit-exact outputs.

---

## 21. State Ownership & Encapsulation

1. Nodes privately encapsulate all internal delay lines, registers, and accumulators.
2. The compute graph MUST NOT directly inspect, modify, or merge private node state.

---

## 22. Reset Semantics

1. `graph.reset()` MUST iterate over all constituent nodes in topological order and invoke `node.reset()`.
2. Reset MUST clear internal state registers to initial silence while preserving all active configurations, parameters, and graph topology.

---

## 23. Parameter Update Semantics

1. Node parameter updates (`node.set_parameters(...)`) MUST be atomic transactions.
2. Node parameter updates MUST NOT invalidate frozen graph topology.
3. If an update modifies node latency, path latency properties MUST dynamically update while graph topology remains intact.

---

## 24. Buffer Ownership & Lifetime

1. Logical dataflow guarantees that intermediate data is immutable to downstream consumers.
2. Runtimes MAY optimize physical memory using buffer pools, pre-allocated static arrays, or safe in-place execution when single-consumer ownership is formally proven.

---

## 25. Graph Lifecycle

The formal structural lifecycle of a compute graph is:
$$\text{BUILDING} \xrightarrow{\text{validate()}} \text{VALIDATED} \xrightarrow{\text{freeze()}} \text{FROZEN}$$
- `BUILDING`: Nodes and edges may be added or removed.
- `VALIDATED`: Graph structure has passed all invariant checks.
- `FROZEN`: Topological schedule is fixed; topology is strictly immutable. Audio processing (`process()`) occurs only in the `FROZEN` state.

---

## 26. Error Model

All graph errors MUST inherit from `AcoustiForgeError`:
- `InvalidGraphError`: Base exception for graph-level failures.
- `CycleDetectedError`: Raised when a directed cycle is detected.
- `UnconnectedPortError`: Raised when a required input port lacks an incoming edge.
- `DuplicateEdgeError`: Raised when multiple edges target the same input port.
- `IncompatibleNodeError`: Raised when Type or Shape mismatch occurs across an edge.

---

## 27. Runtime Neutrality

1. This contract defines semantic dataflow rules independent of programming language or execution runtime.
2. Implementations in Python, native C/C++, or ARM Cortex-M CMSIS-DSP MUST preserve identical topological ordering and mathematical results.

---

## 28. Embedded Execution Implications

1. Real-time embedded execution MUST NOT perform heap allocations, reflection, or dynamic graph mutation in the audio processing loop.
2. A frozen graph MUST be translatable into a static schedule index array and pre-allocated buffer offsets.

---

## 29. Serialization Boundary

1. Future graph serialization (Phase 2C) MUST be declarative, storing only graph ID, version, node types, node parameters, and edge links.
2. Runtime sample buffers, transient state, and hardware handles MUST NEVER be serialized.

---

## 30. Domain-Neutral Architecture

1. Graph topology, scheduling, port binding, and lifecycle semantics are domain-neutral.
2. Audio PCM is the initial concrete payload domain contract for Phase 2.

---

## 31. Explicit Non-Goals

The following capabilities are explicitly non-goals for Phase 2:
- Dynamic runtime schedulers, event queues, and thread pools
- Asynchronous / multi-threaded graph dispatch
- Feedback loop scheduling
- Automatic signal resampling or downmixing
- Universal `SignalObject`
- Hardware, MCU, or CMSIS bindings

---

## 32. Phase 2B Implementation Boundary

Phase 2B is authorized to implement ONLY:
- Core graph data structures (`PortDirection`, `Port`, `Edge`, `ComputeGraph`)
- Graph construction, validation, and freezing mechanisms
- Static topological schedule generation with deterministic tie-breaking
- Single-block and stream execution across DAG topologies
- Fan-out buffer delivery
- Graph-level latency tracking and skew reporting
- Reset propagation and atomic parameter transaction support
- Comprehensive unit and integration verification suite
