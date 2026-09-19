# AcoustiForge — Phase 2A.1 Architectural Reconciliation Report
# Typed Compute Graph Contract Reconciliation & Freeze

**Document ID:** `DOC-PHASE-2A-1-RECONCILIATION-01`  
**Phase:** Phase 2A.1 — Typed Compute Graph Contract Reconciliation & Freeze  
**Mode:** **RECONCILIATION + NORMATIVE CONTRACT FREEZE ONLY (NO IMPLEMENTATION)**  
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
13. `docs/phases/PHASE_2A_TYPED_COMPUTE_GRAPH_ARCHITECTURE_DISCOVERY.md`

---

## 1. Executive Summary & Baseline Verification

- **Baseline Test Suite Status:** 171 passed, 0 failed, 0 errors, 0 warnings (0.71s).
- **Phase Mode:** Strictly Architectural Reconciliation and Normative Contract Freeze.
- **Production Code Status:** Zero lines of code in `src/` modified or created.
- **Deliverables Produced:**
  1. `docs/phases/PHASE_2A_1_TYPED_COMPUTE_GRAPH_CONTRACT_RECONCILIATION.md` (This Report)
  2. `docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md` (Normative Frozen Contract)

---

## 2. Governing Document Reconciliation & Authority Hierarchy

All Phase 2A proposals have been subjected to hostile architectural audit against the governing hierarchy. Where Phase 2A proposals introduced implementation-specific assumptions, conflated type with representation, or proposed implicit coercion, they have been corrected and reconciled as detailed below.

---

## 3. Hostile Architectural Audit of Phase 2A Proposals

### 3.1 Hostile Issue 1: Type vs. Numerical Representation Conflation
- **Phase 2A Proposal:** Defined port type as `PCM_FLOAT32`.
- **Hostile Review Finding:** Conflates the semantic data contract (`PCM` audio stream) with the computational numerical precision format (`float32`). Violates `RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md` (Section 3), which establishes storage representation independence (e.g., future `Q31`, `Q15` on Cortex-M).
- **Reconciliation Decision:** Decouple Semantic Type (`PCM`) from Numerical Representation (`float32`). The Phase 2 graph contract governs `PCM` semantic streams whose active numerical format in the reference runtime is `float32`.
- **Implicit Conversion Policy:** Prohibit all implicit edge coercion. Type or format conversion requires explicit converter nodes.

### 3.2 Hostile Issue 2: Type vs. Shape Separation
- **Phase 2A Proposal:** Grouped channels, sample rate, layout, and dtype under shape.
- **Hostile Review Finding:** Substantially correct, but requires strict formal boundary:
  - **Type ($\mathcal{T}$):** Mathematical/semantic domain (e.g., `PCM`).
  - **Shape ($\mathcal{S}$):** Dimensional and clock parameters $\langle C, f_s, \text{layout}, \text{dtype} \rangle$.
- **Reconciliation Decision:** Compatibility across an edge strictly requires exact equality of both Type and Shape:
$$\text{Type}(p_{\text{src}}) \equiv \text{Type}(p_{\text{dst}}) \land \mathcal{S}(p_{\text{src}}) \equiv \mathcal{S}(p_{\text{dst}})$$

### 3.3 Hostile Issue 3: Identity & Scoping Model
- **Phase 2A Proposal:** Proposed string instance IDs without clear scoping or cross-graph ownership rules.
- **Hostile Review Finding:** Unscoped node instances could lead to shared mutable runtime state across independent graphs.
- **Reconciliation Decision:**
  - **Graph ID:** Scoped locally to the application context.
  - **Node Instance ID:** Unique string within the enclosing graph namespace.
  - **Port ID:** Local string identifier unique within its parent node (`"in"`, `"out"`, etc.).
  - **Edge ID:** Composite address: `(src_node_id, src_port_id) -> (dst_node_id, dst_port_id)`.
  - **Node Sharing Rule:** Node instances MUST NOT be shared across executing graph instances to prevent state corruption.

### 3.4 Hostile Issue 4: Port Cardinality & Fan-In
- **Phase 2A Proposal:** Input ports accept 1 edge; output ports accept $N$ edges.
- **Hostile Review Finding:** Correct. However, source nodes (zero input ports) and sink nodes (zero output ports) must be explicitly accommodated.
- **Reconciliation Decision:**
  - Input port cardinality: $\le 1$ incoming edge (exactly 1 for required inputs).
  - Output port cardinality: $0 \dots N$ outgoing edges (fan-out).
  - Fan-In Rule: Connecting multiple producers to a single input port is strictly prohibited. Merging multiple streams requires explicit summing/mixing nodes.

### 3.5 Hostile Issue 5: Fan-Out & Semantic vs. Physical Storage
- **Phase 2A Proposal:** Fan-out delivers shared read-only buffer to all consumers.
- **Hostile Review Finding:** Risk of mandating Python object immutability onto embedded C/C++ runtimes.
- **Reconciliation Decision:** State the semantic rule independently of runtime storage:
  - *Semantic Rule:* A consumer MUST NOT mutate a producer's logical output while other consumers depend on it.
  - *Runtime Implementation:* Runtimes MAY use shared immutable buffers, reference counting, static buffer pools, or explicit copies, provided semantic isolation is preserved.

### 3.6 Hostile Issue 6: Fan-In Latency Alignment & Skew
- **Phase 2A Proposal:** Noted latency disparity across converging branches.
- **Hostile Review Finding:** Must forbid automatic graph rewriting or silent delay insertion.
- **Reconciliation Decision:**
  - The graph validator detects and reports temporal skew ($\Delta \mathcal{L} = |\mathcal{L}_{\text{path1}} - \mathcal{L}_{\text{path2}}|$).
  - The graph MUST NOT silently insert `DelayNode` instances or shift buffers.
  - Latency alignment is the explicit responsibility of graph construction.

### 3.7 Hostile Issue 7: Latency Propagation Model
- **Phase 2A Proposal:** Additive path latency.
- **Hostile Review Finding:** Correctly distinguishes algorithmic latency from hardware buffer latency.
- **Reconciliation Decision:**
  - Node algorithmic latency: $\mathcal{L}(v) \ge 0$ frames.
  - Edge latency: $\mathcal{L}(e) \equiv 0$ frames (logical links contain zero hidden delay).
  - Path latency: $\mathcal{L}_{\text{path}} = \sum_{v \in \text{path}} \mathcal{L}(v)$.
  - Graph output latency: Reported per declared graph output port as the accumulated latency along its driving path.

### 3.8 Hostile Issue 8: DAG Policy vs. Future Feedback Loops
- **Phase 2A Proposal:** Initial graph is a DAG, with speculative feedback discussion.
- **Hostile Review Finding:** Ordinary directed cycles produce algebraic deadlocks without explicit unit delay registers.
- **Reconciliation Decision:** All compute graphs in Phase 2B MUST be strictly **Directed Acyclic Graphs (DAGs)**. Feedback topologies are explicitly deferred to a dedicated future feedback profile.

### 3.9 Hostile Issue 9: Deterministic Execution Ordering
- **Phase 2A Proposal:** Topological sort with alphabetical string ID tie-breaking.
- **Hostile Review Finding:** Alphabetical tie-breaking is a Python reference implementation mechanism, not a universal mathematical requirement.
- **Reconciliation Decision:**
  - *Semantic Requirement:* Execution order MUST be deterministic and reproducible for identical graph topologies.
  - *Reference Runtime Policy:* Topological sort with deterministic secondary ordinal/lexical tie-breaking.
  - *Embedded Profile:* Statically computed topological schedule index array.

### 3.10 Hostile Issue 10: Graph Lifecycle State Model
- **Phase 2A Proposal:** Included `EXECUTING` as a lifecycle state.
- **Hostile Review Finding:** Conflates structural graph definition state with real-time runtime invocation.
- **Reconciliation Decision:** Formalize the structural graph lifecycle:
$$\text{BUILDING} \xrightarrow{\text{validate()}} \text{VALIDATED} \xrightarrow{\text{freeze()}} \text{FROZEN}$$
Processing (`process()`) and `reset()` are operational methods executed on a `FROZEN` graph without altering lifecycle state.

### 3.11 Hostile Issue 11: Parameter Updates vs. Topology Mutation
- **Phase 2A Proposal:** Distinguished parameter updates from topology mutation.
- **Hostile Review Finding:** Fully supported.
- **Reconciliation Decision:**
  - Node-local parameter updates (`node.set_parameters(...)`) are atomic transactions that do NOT invalidate the frozen graph schedule.
  - Latency-affecting parameter updates (e.g., `DelayNode.set_parameters`) update path latency properties dynamically without invalidating graph topology.
  - Topology mutations (adding nodes, removing edges) require un-freezing to `BUILDING`.

### 3.12 Hostile Issue 12: State Ownership & Encapsulation
- **Phase 2A Proposal:** Nodes privately own state.
- **Hostile Review Finding:** Fully supported by Phase 1A.1 and 1E.
- **Reconciliation Decision:** The graph never accesses or merges private node state. Graph `reset()` traverses nodes in topological order, invoking `node.reset()`.

### 3.13 Hostile Issue 13: Buffer Ownership & Lifetime
- **Phase 2A Proposal:** Output buffers are immutable upon release.
- **Hostile Review Finding:** Reconciled with embedded runtime flexibility in Section 3.5.

### 3.14 Hostile Issue 14: Validation Layers
- **Phase 2A Proposal:** Multi-stage validation.
- **Hostile Review Finding:** Structural validation must occur during `validate()` and `freeze()`, NEVER per-sample in `process()`.
- **Reconciliation Decision:**
  - *Freeze-time validation:* Referential integrity, port matching, acyclicity, schedule derivation.
  - *Runtime validation:* Validating input `PCMBlock` metadata against graph input ports.

### 3.15 Hostile Issue 15: Error Hierarchy
- **Phase 2A Proposal:** Proposed 5 graph exceptions.
- **Hostile Review Finding:** Reconciled under `AcoustiForgeError`.
- **Reconciliation Decision:**
  - `InvalidGraphError` (base graph exception)
  - `CycleDetectedError` (acyclicity violation)
  - `UnconnectedPortError` (missing required connection)
  - `DuplicateEdgeError` (multiple incoming edges to single input)
  - Reuses existing `IncompatibleNodeError` for Type/Shape mismatches.

### 3.16 Hostile Issue 16: Graph vs. Node Boundary
- **Reconciliation Decision:** The graph owns topology, routing, and scheduling. Nodes own algorithms, parameters, state, and local math.

### 3.17 Hostile Issue 17: Compute Graph vs. Data/Knowledge Graph
- **Reconciliation Decision:** Compute graphs represent real-time signal transformations. Knowledge/data graphs represent entity relationships. Strict boundary maintained.

### 3.18 Hostile Issue 18: Serialization Boundary
- **Reconciliation Decision:** Declarative schema must record topology, node types, port names, and parameters. Transient state, buffers, and hardware handles are NEVER serialized. Implementation deferred to Phase 2C.

### 3.19 Hostile Issue 19: Runtime Neutrality
- **Reconciliation Decision:** Graph dataflow semantics are 100% runtime-neutral, mapping cleanly to Python, native C/C++, and Cortex-M CMSIS-DSP.

### 3.20 Hostile Issue 20: Microcontroller & Real-Time Profile
- **Reconciliation Decision:** Real-time profile requires static scheduling, zero hot-path allocations, and pre-allocated buffer pools.

### 3.21 Hostile Issue 21: Cross-Domain Extensibility Boundary
- **Reconciliation Decision:** Graph dataflow semantics are domain-neutral; audio PCM is the initial normative payload contract.

### 3.22 Hostile Issue 22: Node Instance Sharing
- **Reconciliation Decision:** Sharing active stateful node instances across executing graphs is strictly prohibited.

### 3.23 Hostile Issue 23: Topology Mutation Invariants
- **Reconciliation Decision:** Frozen graphs cannot be structurally mutated during execution.

### 3.24 Hostile Issue 24: Graph Output Ports
- **Reconciliation Decision:** Graph outputs must be explicitly declared output ports, rather than guessing from unconsumed edges.

### 3.25 Hostile Issue 25: Minimum Scope Containment
- **Reconciliation Decision:** Eliminate dynamic scheduling, graph rewriting, automatic fusion, and automatic resampling from Phase 2.

---

## 4. Reconciliation Decision Table (DEC-01 to DEC-25)

| Decision | Phase 2A Proposal | Review Finding | Final Decision | Normative Consequence |
|---|---|---|---|---|
| **DEC-01** | Graph Definition | Needs explicit input/output boundaries | **ACCEPT WITH MODIFICATION** | Graph $\mathcal{G} = \langle \mathcal{V}, \mathcal{P}, \mathcal{E}, \mathcal{I}, \mathcal{S} \rangle$ with declared boundaries |
| **DEC-02** | Node Identity | String ID within graph | **ACCEPT** | Local unique string ID per node in graph namespace |
| **DEC-03** | Port Identity | Local string per node | **ACCEPT** | Local unique string ID per port on node |
| **DEC-04** | Port Semantic Type | Conflated `PCM_FLOAT32` | **ACCEPT WITH MODIFICATION** | Semantic Type (`PCM`) decoupled from dtype (`float32`) |
| **DEC-05** | Type/Shape Split | Grouped all in shape | **ACCEPT WITH MODIFICATION** | Type = domain; Shape = $\langle C, f_s, \text{layout}, \text{dtype} \rangle$ |
| **DEC-06** | Edge Definition | Logical directed link | **ACCEPT** | Immutable link $(v_{\text{src}}, p_{\text{src}}) \to (v_{\text{dst}}, p_{\text{dst}})$ |
| **DEC-07** | Directionality | Producer to consumer | **ACCEPT** | Directed link compatibility evaluated strictly $p_{\text{src}} \to p_{\text{dst}}$ |
| **DEC-08** | Strict Compatibility | Exact matching | **ACCEPT** | Exact equality of Type, $f_s$, channels, layout, dtype required |
| **DEC-09** | Graph Validation | Multi-stage | **ACCEPT** | Enforced at `validate()` / `freeze()`; zero per-sample validation overhead |
| **DEC-10** | DAG Policy | Mentioned future feedback | **ACCEPT WITH MODIFICATION** | Strict DAG required for Phase 2B; feedback deferred to separate profile |
| **DEC-11** | Deterministic Ordering | Alphabetical tie-breaking | **ACCEPT WITH MODIFICATION** | Topological sort + deterministic tie-breaking (lexical in ref runtime) |
| **DEC-12** | Determinism | Bit-exact output | **ACCEPT** | Identical graph + inputs produce 100% reproducible execution |
| **DEC-13** | State Ownership | Encapsulated in node | **ACCEPT** | Private node state; graph never inspects or mutates node memory |
| **DEC-14** | Reset Semantics | Forward traversal | **ACCEPT** | Topological forward traversal calling `node.reset()`; preserves config |
| **DEC-15** | Parameter Updates | Atomic transactions | **ACCEPT** | Node parameter updates do not invalidate frozen topology |
| **DEC-16** | Topology Immutability | Frozen during execution | **ACCEPT** | Structural mutation requires unfreezing back to `BUILDING` |
| **DEC-17** | Lifecycle Model | Included `EXECUTING` state | **ACCEPT WITH MODIFICATION** | Structural lifecycle: `BUILDING` $\to$ `VALIDATED` $\to$ `FROZEN` |
| **DEC-18** | Latency Model | Additive path latency | **ACCEPT** | $\mathcal{L}_{\text{path}} = \sum \mathcal{L}_v$; reported per declared graph output |
| **DEC-19** | Buffer Ownership | Immutable block passing | **ACCEPT WITH MODIFICATION** | Semantic read-only guarantee decoupled from physical memory strategy |
| **DEC-20** | Fan-Out Semantics | Shared read-only buffer | **ACCEPT** | Single producer execution shared safely across $N$ consumers |
| **DEC-21** | Fan-In Semantics | Single edge per input | **ACCEPT** | Merging requires explicit multi-input summing/mixing nodes |
| **DEC-22** | Error Model | 5 typed exceptions | **ACCEPT** | Typed hierarchy derived from `AcoustiForgeError` |
| **DEC-23** | Runtime Neutrality | Storage neutral | **ACCEPT** | Pure dataflow semantics mapping to Python, C/C++, and Cortex-M |
| **DEC-24** | Serialization | JSON/YAML schema | **DEFER** | Declarative schema defined; implementation deferred to Phase 2C |
| **DEC-25** | Domain Neutrality | Domain-neutral graph | **ACCEPT** | Graph engine is domain-neutral; audio PCM is initial concrete payload |

---

## 5. Architectural Alternatives Table

| Topic | Alternative | Reason Rejected/Deferred | Frozen Choice |
|---|---|---|---|
| **Semantic Type vs. Float32** | Conflate as `PCM_FLOAT32` | Prevents future fixed-point / Q31 embedded profiles | Decoupled: Type (`PCM`) + Shape ($\text{dtype}=\text{float32}$) |
| **Edge Type Conversion** | Implicit coercion on edge | Hidden resampling/remixing causes non-deterministic quality loss | Explicit conversion nodes required |
| **Execution Ordering** | Dynamic runtime queue | High overhead; non-deterministic execution in real-time loops | Pre-computed static topological schedule |
| **Feedback Topologies** | Schedulable cycles | Algebraic loops deadlock without explicit unit delays | Strict DAG policy for Phase 2B |
| **Graph Lifecycle** | Dynamic mutable runtime | Race conditions and invalid state during real-time streaming | Static `BUILDING` $\to$ `VALIDATED` $\to$ `FROZEN` |
| **Latency Alignment** | Automatic delay insertion | Graph engine must not silently mutate signal delay | Explicit delay nodes; validator reports skew |
| **Buffer Management** | Universal Python immutability | Incompatible with zero-copy embedded C/C++ static memory | Semantic read-only guarantee with storage-neutral runtime |
| **Node Instance Sharing** | Shared nodes across graphs | Causes state corruption and cross-thread race conditions | Prohibited: node instance belongs to single graph |
| **Topology Repair** | Auto-wire dangling ports | Silent auto-connection creates hard-to-debug behaviors | Explicit validation failure on unconnected required ports |
| **Graph Output Discovery** | Inferred from dangling edges | Ambiguous intent when intermediate nodes have unconsumed taps | Explicitly declared graph output ports |

---

## 6. Phase 2B Implementation Authorization Boundary

Phase 2B is authorized to implement **ONLY** the minimal required core graph infrastructure:
- `PortDirection` (`INPUT`, `OUTPUT`)
- `Port` (port identity, direction, parent node, type, shape)
- `Edge` (source port, destination port)
- `ComputeGraph` (construction, node/edge registration, validation, freezing, execution, reset)
- Topological sort and static schedule generation
- Fan-out buffer dispatch
- Cumulative path latency calculation
- Comprehensive unit and integration test suite

Phase 2B is **NOT** authorized to implement:
- Dynamic runtime schedulers, event buses, or async runners
- Graph serialization (JSON/YAML) or persistence engines
- Universal `SignalObject` or multi-domain sensors
- Hardware drivers, CMSIS bindings, or C++ kernels
- Feedback loop schedulers or automatic latency equalizers

---

## 7. Scope Audit

- **Production Code Status:** Zero modifications in `src/`.
- **Dependency Isolation:** 100% standard library + NumPy.
- **Hardware Isolation:** Zero hardware, MCU, RTOS, or CMSIS code.
- **Premature Abstractions:** Zero graph execution code implemented.

---

## 8. Acceptance Matrix

| Item | Requirement | Status |
|---|---|---|
| Baseline Verification | 171 tests passing with 0 warnings | **PASS** |
| Governing Document Reconciliation | Authority hierarchy strictly respected | **PASS** |
| DEC-01..DEC-25 Reconciled | All 25 decisions explicitly audited and classified | **PASS** |
| Type vs. Shape Boundary | Formally decoupled | **PASS** |
| Port Identity & Cardinality | Frozen | **PASS** |
| Edge & Fan-Out Semantics | Frozen | **PASS** |
| Fan-In & Latency Alignment | Frozen (no silent delay insertion) | **PASS** |
| DAG & Acyclicity Policy | Frozen | **PASS** |
| Deterministic Schedule Policy | Frozen | **PASS** |
| State Ownership & Reset | Frozen | **PASS** |
| Lifecycle & Immutability | Frozen (`BUILDING` $\to$ `VALIDATED` $\to$ `FROZEN`) | **PASS** |
| Error Hierarchy | Frozen under `AcoustiForgeError` | **PASS** |
| Runtime Neutrality | Frozen | **PASS** |
| Phase 2B Scope Boundary | Explicitly defined and contained | **PASS** |
| No Implementation in Phase 2A.1 | `src/` untouched; 171/171 tests passing | **PASS** |

---

```
PHASE 2A.1 GRAPH RECONCILIATION: COMPLETE
PHASE 2A.1 GRAPH CONTRACT: FROZEN
PHASE 2A.1 IMPLEMENTATION AUTHORIZATION: NOT REQUESTED
```
