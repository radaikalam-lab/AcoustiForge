# AcoustiForge — Phase 2A Architectural Discovery Report
# Typed Compute Graph Architecture Discovery

**Document ID:** `DOC-PHASE-2A-01`  
**Phase:** Phase 2A — Typed Compute Graph Architecture Discovery  
**Mode:** **DISCOVERY + ARCHITECTURAL SPECIFICATION ONLY (NO IMPLEMENTATION)**  
**Governing Authority Hierarchy:**  
1. `prompts/MASTER_PROMPT.md`
2. `docs/contracts/PCM_CONTRACT.md`
3. `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md`
4. `docs/ARCHITECTURE.md`
5. `docs/phases/PHASE_0_ACCEPTANCE_REPORT.md`
6. `docs/phases/PHASE_1A_DSP_NODE_CONTRACT_DISCOVERY.md`
7. `docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md`
8. `docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md`
9. `docs/phases/PHASE_1C_BIQUAD_NODE_IMPLEMENTATION_AND_VERIFICATION.md`
10. `docs/phases/PHASE_1D_PRIMITIVE_DSP_NODES_IMPLEMENTATION_AND_VERIFICATION.md`
11. `docs/contracts/NODE_COMPOSITION_CONTRACT.md`
12. `docs/phases/PHASE_1E_NODE_COMPOSITION_IMPLEMENTATION_AND_VERIFICATION.md`

---

## 1. Baseline & Discovery Audit

- **Baseline Test Suite Status:** 171 passed, 0 failed, 0 errors, 0 warnings (0.72s).
- **Proven Operational Primitives:**
  - `PassThroughNode`: Bit-exact reference node.
  - `GainNode`: Stateless scalar linear amplitude scaler ($\mathcal{L} = 0$).
  - `DelayNode`: Stateful integer frame delay line ($\mathcal{L} = D$).
  - `BiquadNode`: Stateful Direct Form II Transposed 2nd-order IIR filter ($\mathcal{L} = 0$).
  - `SequentialPipeline`: Immutable linear sequential execution engine ($\mathcal{L}_{\text{total}} = \sum \mathcal{L}_i$).
- **Discovered Scope Boundary:** Phase 2A is strictly architectural discovery and contract definition. No production graph code, executors, schedulers, registries, or serializers are implemented in this phase.

---

## 2. Governing Hierarchy & Non-Graph Principle

AcoustiForge adheres to the governing principle:
> **The graph must be earned through contract discovery.**  
> The typed computation graph must describe nodes, ports, edges, compatibility, execution ordering, state encapsulation, and latency propagation before any runtime graph framework is constructed.

---

## 3. Phase 1E Architectural Inheritance

Phase 1E established the foundation of linear node composition:
1. **Directional Link Compatibility:** $A_{\text{out}} \to B_{\text{in}}$ requires identical sample rates, channel counts, and tensor layout.
2. **State Encapsulation:** Nodes strictly retain internal state; composition engines never manipulate or merge state.
3. **Cumulative Latency:** $\mathcal{L}_{\text{total}} = \sum \mathcal{L}_i$.
4. **Arbitrary Block Continuity:** Processing invariant across irregular block sizes (1 to 500+ frames).
5. **Topology Immutability:** Execution topology is fixed after construction.

Phase 2A now asks: **What additional formal semantics are required to evolve linear sequences into general directed computation topologies?**

---

## 4. Graph Hypothesis

We evaluate the formal graph hypothesis:
$$\mathcal{G} = \langle \mathcal{V}, \mathcal{P}, \mathcal{E}, \mathcal{I}, \mathcal{S} \rangle$$
where:
- $\mathcal{V} = \{v_1, v_2, \dots, v_n\}$: Set of computational node instances.
- $\mathcal{P} = \mathcal{P}_{\text{in}} \cup \mathcal{P}_{\text{out}}$: Set of typed directional input and output ports associated with nodes.
- $\mathcal{E} \subseteq \mathcal{P}_{\text{out}} \times \mathcal{P}_{\text{in}}$: Set of directed communication edges connecting producer ports to consumer ports.
- $\mathcal{I}$: Graph-level invariants (type consistency, shape compatibility, acyclicity, latency alignment).
- $\mathcal{S}$: Deterministic topological execution schedule.

---

## 5. Node Model

A graph node $v \in \mathcal{V}$ is an instance of a computational operator conforming to the ACE Node Contract:
- **Node Instance Identity:** Unique identifier within the graph namespace (e.g., `"eq_low"`, `"delay_left"`).
- **Node Type Identity:** Canonical computational operator classification (e.g., `BiquadNode`, `GainNode`).
- **Port Declarations:** Explicit set of input ports $\mathcal{P}_{\text{in}}(v)$ and output ports $\mathcal{P}_{\text{out}}(v)$.
- **State Ownership:** Completely encapsulated private registers (e.g., DF-II-T delay lines, circular buffers).
- **Parameter Interface:** Isolated configuration parameters updated atomically without graph mutation.
- **Algorithmic Latency:** Inherent frame latency $\mathcal{L}(v) \ge 0$.

---

## 6. Port Model

Ports represent the discrete input/output interfaces of a node:
- **Port Identity:** Local identifier unique to the parent node (e.g., `"in"`, `"out"`, `"left_in"`, `"high_out"`).
- **Directionality:** Strictly `INPUT` or `OUTPUT`.
- **Data Contract / Type:** Semantic payload type (e.g., `PCM_STREAM`).
- **Shape Constraints:** Acceptable channel count, sample rate, and tensor representation.
- **Cardinality:**
  - `INPUT` port cardinality: Exactly 1 incoming edge (single producer; fan-in requires an explicit summing/mixing node).
  - `OUTPUT` port cardinality: 0 to $N$ outgoing edges (fan-out / multi-consumer support).

---

## 7. Edge Model

An edge $e \in \mathcal{E}$ is a directed connection:
$$e = (v_{\text{src}}, p_{\text{src}}) \longrightarrow (v_{\text{dst}}, p_{\text{dst}})$$
where $p_{\text{src}} \in \mathcal{P}_{\text{out}}(v_{\text{src}})$ and $p_{\text{dst}} \in \mathcal{P}_{\text{in}}(v_{\text{dst}})$.
- **Semantic Role:** Represents purely logical dataflow connectivity.
- **Non-Node Property:** An edge does NOT introduce hidden latency, buffering, attenuation, or processing.

---

## 8. Typing Model

AcoustiForge distinguishes **Type** from **Shape**:
- **Type ($\mathcal{T}$):** The semantic domain and mathematical interpretation of the signal (e.g., `PCM_FLOAT32`).
- **Compatibility Rule:** Edges are strictly valid only between ports of identical or explicitly convertible types:
$$\text{Type}(p_{\text{src}}) = \text{Type}(p_{\text{dst}})$$

---

## 9. Shape Model

Shape ($\mathcal{S}$) defines the dimensional and clock properties of the data payload:
$$\mathcal{S} = \langle C, f_s, \text{layout}, \text{dtype} \rangle$$
where:
- $C$: Discrete channel count ($1 \le C \le 2$ in Phase 1; $C \ge 1$ in future phases).
- $f_s$: Discrete clock sampling rate in Hz ($f_s > 0$).
- $\text{layout}$: Memory tensor arrangement (`PLANAR_C_CONTIGUOUS`).
- $\text{dtype}$: Numerical precision (`FLOAT32`).

---

## 10. Compatibility Model

A directed edge $e = p_{\text{src}} \to p_{\text{dst}}$ is **valid** if and only if:
1. **Type Match:** $\text{Type}(p_{\text{src}}) \equiv \text{Type}(p_{\text{dst}})$.
2. **Clock Match:** $f_s(p_{\text{src}}) == f_s(p_{\text{dst}})$.
3. **Channel Match:** $C(p_{\text{src}}) == C(p_{\text{dst}})$.
4. **Layout Match:** $\text{layout}(p_{\text{src}}) == \text{layout}(p_{\text{dst}})$.

If any condition fails, graph validation MUST reject the configuration with `IncompatibleNodeError`.

---

## 11. Topology Model & Structural Patterns

### 11.1 Linear Sequence
```
┌─────────┐      ┌─────────┐      ┌─────────┐
│ Node A  │ ────►│ Node B  │ ────►│ Node C  │
└─────────┘      └─────────┘      └─────────┘
```

### 11.2 Fan-Out (Branching)
```
                 ┌─────────┐
            ┌───►│ Node B  │
┌─────────┐ │    └─────────┘
│ Node A  │─┤
└─────────┘ │    ┌─────────┐
            └───►│ Node C  │
                 └─────────┘
```
- **Execution Rule:** Node A executes once. The output block $\mathbf{Y}_A$ is provided to both Node B and Node C as immutable read-only input.

### 11.3 Fan-In (Merging)
```
┌─────────┐
│ Node B  │───┐
└─────────┘   │  ┌─────────┐
              ├─►│ Node D  │ (Explicit Multi-Input / Summing Node)
┌─────────┐   │  └─────────┘
│ Node C  │───┘
└─────────┘
```
- **Execution Rule:** Direct multi-edge connection to a single input port is prohibited. Fan-in requires an explicit node with multiple input ports (e.g., `SummingNode` or `MixerNode`).

---

## 12. Graph Validation Model

Graph validation occurs prior to execution and enforces:
1. **Referential Integrity:** Every node referenced by an edge exists in the graph.
2. **Port Existence & Direction:** Source is an `OUTPUT` port; destination is an `INPUT` port.
3. **Single Producer Invariant:** Every input port has at most 1 incoming edge.
4. **Type & Shape Compatibility:** Producer and consumer port contracts match exactly.
5. **Acyclicity:** The graph topology contains no directed cycles ($\mathcal{G}$ is a Directed Acyclic Graph).
6. **Reachability / Completeness:** All required inputs of all nodes in the active graph are connected.

---

## 13. Cycle Policy & Feedback Boundary

- **Initial ACE Graph Rule:** Directed cycles are **strictly prohibited** in the primary compute graph ($\mathcal{G}$ must be a DAG).
- **Mathematical Rationale:** Unbounded algebraic loops ($y[n] = f(y[n])$) without explicit unit-delay boundaries produce non-causal or non-deterministic recurrence.
- **Future Feedback Specification:** Feedback loops must cross an explicit state-bearing delay boundary ($\mathcal{L} \ge 1$ frame) with declared initial conditions.

---

## 14. Execution-Order Model & Determinism

1. **Topological Sort:** Execution order is derived via topological sorting of the DAG.
2. **Deterministic Tie-Breaking:** When multiple nodes are ready for execution (in-degree = 0), ties are broken deterministically by alphabetical node instance identifier.
3. **Reproducibility Guarantee:** Given identical graph topology, parameters, and input stream, execution order and output samples are 100% reproducible.

---

## 15. State Encapsulation & Reset Model

- **Node Ownership:** Internal filter registers, delay histories, and accumulators are privately owned by their respective nodes.
- **Graph Reset:** `graph.reset()` iterates over all nodes in the topological schedule and invokes `node.reset()`, clearing memory lines to zero while preserving configurations.

---

## 16. Latency Model across Branching Topologies

For linear chains:
$$\mathcal{L}_{\text{chain}} = \sum_{k} \mathcal{L}_k$$

For branching and reconverging graphs:
```
            ┌─► B (L=5)  ─┐
A (L=0) ────┤             ├─► D (Summing)
            └─► C (L=15) ─┘
```
- **Path Latency:** Each path from graph input to node $D$ accumulates latency independently ($\mathcal{L}_{\text{path1}} = 5$, $\mathcal{L}_{\text{path2}} = 15$).
- **Latency Disparity:** If inputs to a multi-input node have unequal path latencies, the signals arrive temporally skewed ($\Delta \mathcal{L} = 10$ frames).
- **Latency Alignment:** Equalization requires an explicit `DelayNode` inserted into the shorter branch, or explicit multi-path alignment policies.

---

## 17. Buffer & Ownership Model

- **Immutable Block Passing:** A node's output `PCMBlock` is immutable.
- **Fan-Out Safety:** When Node A fans out to Node B and Node C, both receive the same read-only `PCMBlock`. Neither consumer may mutate the buffer in place.
- **Memory Optimization:** In-place buffer reuse is an engine-level optimization permitted only when a buffer has a single consumer and is not retained by state.

---

## 18. Graph Lifecycle

```
┌────────────┐        ┌─────────────┐        ┌────────────┐        ┌───────────┐
│  BUILDING  │ ─────► │  VALIDATED  │ ─────► │   FROZEN   │ ─────► │ EXECUTING │
└────────────┘        └─────────────┘        └────────────┘        └───────────┘
```
1. **`BUILDING`:** Nodes and edges are added.
2. **`VALIDATED`:** Invariants, port compatibility, and acyclicity are verified.
3. **`FROZEN`:** Topological execution schedule is computed; topology is made immutable.
4. **`EXECUTING`:** Audio blocks are processed through the static schedule.

---

## 19. Parameter Updates vs. Topology Mutation

- **Parameter Updates (Runtime Safe):** Changing $G_{\text{dB}}$ on a `GainNode` or filter cutoff on a `BiquadNode` is an atomic node parameter transaction. It does not require graph re-validation or schedule re-computation.
- **Topology Mutation (Structural Change):** Adding nodes, removing edges, or rewiring connections transitions the graph back to `BUILDING` mode and requires re-validation and re-freezing.

---

## 20. Error Model

Standardized typed exceptions derived from `AcoustiForgeError`:
- `InvalidGraphError`: Generic structural malformation.
- `IncompatibleNodeError`: Mismatch in sample rate, channels, or format across an edge.
- `CycleDetectedError`: Rejection of prohibited cyclic dependencies.
- `UnconnectedPortError`: Required input port lacks an incoming edge.
- `DuplicateEdgeError`: Attempting to connect multiple producers to a single input port.

---

## 21. Runtime Neutrality & Cross-Runtime Profile

- **Storage Neutrality:** The graph contract specifies logical dataflow, not memory allocator specifics.
- **Embedded C/C++ Profile:** The frozen topological schedule maps directly to an array of C function pointers and static intermediate buffer pointers in Tiny ACE Runtime.
- **Zero Heap Allocation in Hot Path:** Execution across pre-allocated buffers requires zero dynamic allocations per audio block.

---

## 22. Serialization & Declarative Representation

- **Declarative Schema (Future):** A graph can be serialized into a human-readable JSON/YAML representation capturing:
  - Graph ID and version
  - Node instance dictionary (types and parameters)
  - Edge connectivity list
- **Status:** Deferred to Phase 2C.

---

## 23. Compute Graph vs. Data/Knowledge Graph

- **Compute Graph (ACE):** Executable mathematical operator network transforming real-time signal tensors.
- **Data / Knowledge Graph:** Relational entity network describing physical systems, sensor metadata, calibration logs, and experiment provenance.
- **Principle:** AcoustiForge maintains a strict boundary between execution graphs and metadata/knowledge graphs.

---

## 24. Future Cross-Domain Scientific Extensibility

While Phase 2 operates on audio PCM tensors, the port/node/graph abstractions remain domain-neutral:
- **Audio:** `float32` planar audio $(C, N)$ @ $f_s$.
- **Vibration / Accelerometry:** $(3, N)$ @ $f_s$ with metric acceleration units.
- **Biomedical (ECG/EEG):** $(C, N)$ multi-lead physiological streams.
- **Scientific Tensors:** $(D_1, \dots, D_k)$ structured numerical streams.

---

## 25. Required Architectural Decisions (DEC-01 to DEC-25)

| Decision ID | Topic | Decision |
|---|---|---|
| **DEC-01** | Graph Definition | Graph $\mathcal{G} = \langle \mathcal{V}, \mathcal{P}, \mathcal{E} \rangle$ with explicit typed ports and directed edges. |
| **DEC-02** | Node Identity | Nodes possess unique instance string IDs within the graph namespace. |
| **DEC-03** | Port Identity | Ports possess local string identifiers unique to their parent node. |
| **DEC-04** | Port Typing | Ports declare semantic data type (`PCM_FLOAT32`) and dimensional shape constraints. |
| **DEC-05** | Type vs Shape | Signal domain (`Type`) is decoupled from dimensional properties (`Shape`). |
| **DEC-06** | Edge Definition | Edge is an immutable directed link $(v_{\text{src}}, p_{\text{src}}) \to (v_{\text{dst}}, p_{\text{dst}})$. |
| **DEC-07** | Directionality | Compatibility is strictly directional from producer to consumer. |
| **DEC-08** | Compatibility | Strict equality of type, sample rate, channels, and layout required across edges. |
| **DEC-09** | Graph Validity | Complete topological validation enforced before execution. |
| **DEC-10** | Cycle Policy | Directed cycles strictly prohibited in initial graph architecture. |
| **DEC-11** | Execution Order | Deterministic topological sort with alphabetical tie-breaking. |
| **DEC-12** | Determinism | Bit-exact reproducible execution order for identical graphs. |
| **DEC-13** | State Ownership | Private encapsulation of state by individual nodes. |
| **DEC-14** | Reset Semantics | Forward topological traversal invoking `node.reset()`. |
| **DEC-15** | Parameter Updates | Atomic updates on node instances without graph topology invalidation. |
| **DEC-16** | Topology Mutability | Topology immutable during execution (`FROZEN` lifecycle state). |
| **DEC-17** | Graph Lifecycle | Explicit states: `BUILDING` $\to$ `VALIDATED` $\to$ `FROZEN` $\to$ `EXECUTING`. |
| **DEC-18** | Latency Propagation | Path-specific latency tracking; cumulative latency calculated along each path. |
| **DEC-19** | Buffer Ownership | Output buffers are logically immutable upon release by producer. |
| **DEC-20** | Fan-Out Semantics | Producer output shared read-only across multiple consumers. |
| **DEC-21** | Fan-In Semantics | Single edge per input port; multi-signal merging requires explicit summing nodes. |
| **DEC-22** | Error Semantics | Explicit typed exceptions inheriting from `AcoustiForgeError`. |
| **DEC-23** | Runtime Neutrality | Graph contract is pure dataflow, mapping to Python, C/C++, and Cortex-M. |
| **DEC-24** | Serialization Status | Declarative serialization architecture specified; implementation deferred. |
| **DEC-25** | Cross-Domain Scope | Graph infrastructure is domain-neutral; audio PCM is the initial verified data contract. |

---

## 26. Architectural Alternatives Considered

1. **Graph Owns Nodes vs. Graph References Nodes:**
   - *Selected:* Graph references independently instantiated nodes.
   - *Rationale:* Preserves node testability in isolation and supports parameter management outside the graph wrapper.
2. **Dynamic Runtime Scheduling vs. Static Pre-Frozen Schedule:**
   - *Selected:* Static topological schedule computed during `freeze()`.
   - *Rationale:* Eliminates scheduling overhead in the real-time processing loop and guarantees deterministic execution.
3. **Implicit Single Port vs. Explicit Named Ports:**
   - *Selected:* Explicit named ports.
   - *Rationale:* Essential for branching, splitting, and future multi-input/multi-output nodes.

---

## 27. Conceptual Architecture Diagrams

### 27.1 Separation of Concerns
```
┌────────────────────────────────────────────────────────┐
│                      Graph Level                       │
│    Topology, Invariant Validation, Static Schedule     │
└───────────────────────────┬────────────────────────────┘
                            │ Contains
┌───────────────────────────▼────────────────────────────┐
│                       Edge Level                       │
│     Directed Producer Port ──► Consumer Port Links     │
└───────────────────────────┬────────────────────────────┘
                            │ Connects
┌───────────────────────────▼────────────────────────────┐
│                       Port Level                       │
│         Directionality, Type, Shape Constraints        │
└───────────────────────────┬────────────────────────────┘
                            │ Exposes
┌───────────────────────────▼────────────────────────────┐
│                       Node Level                       │
│      DSP Algorithms, Encapsulated State, Parameters    │
└────────────────────────────────────────────────────────┘
```

### 27.2 Graph Lifecycle State Machine
```
   ┌──────────┐      validate()      ┌───────────┐
   │ BUILDING │ ───────────────────► │ VALIDATED │
   └──────────┘                      └─────┬─────┘
        ▲                                  │ freeze()
        │ mutate()                         ▼
   ┌────┴─────┐      process()       ┌───────────┐
   │ EXECUTING│ ◄─────────────────── │  FROZEN   │
   └──────────┘                      └───────────┘
```

---

## 28. Explicit Non-Goals for Phase 2A

- **NO** graph implementation code (`GraphObject`, `ComputeGraph`, `GraphExecutor`).
- **NO** scheduler or dynamic queue execution.
- **NO** graph serialization or JSON persistence engines.
- **NO** universal `SignalObject` abstraction.
- **NO** sensor, medical, or microscopy integrations.
- **NO** hardware, MCU, or CMSIS bindings.

---

## 29. Acceptance Matrix

| Criterion | Requirement | Result |
|---|---|---|
| Baseline | 171 tests passing with 0 warnings | **PASS** |
| Discovery Scope | Complete discovery without code implementation | **SATISFIED** |
| Node Model | Defined with identity and port encapsulation | **SATISFIED** |
| Port Model | Defined with directionality and shape contracts | **SATISFIED** |
| Edge Model | Defined as directional logical dataflow | **SATISFIED** |
| Type vs Shape | Strict conceptual separation established | **SATISFIED** |
| Cycle Policy | Acyclicity enforced; feedback boundary defined | **SATISFIED** |
| Latency Propagation | Path latency and accumulation rules defined | **SATISFIED** |
| Buffer Ownership | Read-only immutability for fan-out established | **SATISFIED** |
| Architectural Decisions | 25 formal decisions (DEC-01 to DEC-25) documented | **SATISFIED** |
| Non-Goals | 100% adherence to discovery-only boundaries | **SATISFIED** |
| Code Hygiene | `git diff --check` passes; no code changes in `src/` | **SATISFIED** |

---

## 30. Phase 2B Handoff

The next logical phase is **Phase 2A.1 — Typed Compute Graph Contract Reconciliation & Freeze Preparation**, which will:
1. Reconcile port naming, cardinality constraints, and error hierarchies.
2. Formalize the normative `TYPED_COMPUTE_GRAPH_CONTRACT.md`.
3. Prepare the repository for explicit implementation authorization in Phase 2B.

---

```
PHASE 2A GRAPH DISCOVERY: COMPLETE
PHASE 2A GRAPH CONTRACT: READY FOR RECONCILIATION
PHASE 2A IMPLEMENTATION AUTHORIZATION: NOT REQUESTED
```
