# AcoustiForge — Phase 1E Architectural Discovery & Reconciliation
# Node Composition Contract Discovery & Specification

**Document ID:** `DOC-PHASE-1E-DISCOVERY-01`  
**Phase:** Phase 1E — Node Composition Contract Discovery  
**Status:** **FROZEN SPECIFICATION & RECONCILIATION**  
**Normative Governing Documents:**  
- `prompts/MASTER_PROMPT.md`
- `docs/contracts/PCM_CONTRACT.md`
- `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md`
- `docs/phases/PHASE_0_ACCEPTANCE_REPORT.md`
- `docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md`
- `docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md`
- `docs/phases/PHASE_1C_BIQUAD_NODE_IMPLEMENTATION_AND_VERIFICATION.md`
- `docs/phases/PHASE_1D_PRIMITIVE_DSP_NODES_IMPLEMENTATION_AND_VERIFICATION.md`

---

## 1. Executive Summary & Baseline

AcoustiForge has successfully implemented and verified four foundational processing nodes:
1. `PassThroughNode` (Phase 0) — Bit-exact identity operator.
2. `BiquadNode` (Phase 1C) — Stateful recursive 2nd-order IIR filter with 0 algorithmic latency.
3. `GainNode` (Phase 1D) — Stateless scalar linear amplitude scaler with 0 algorithmic latency.
4. `DelayNode` (Phase 1D) — Stateful integer-delay operator with $D$ frames algorithmic latency.

**Current Baseline:** 127 tests passing, 0 failures, 0 errors, 0 warnings.

**Phase 1E Objective:** Discover, formalize, freeze, and minimally implement the deterministic composition contract required to execute compatible ACE processing nodes sequentially (`Node A` $\to$ `Node B` $\to$ `Node C`) **without** introducing a generalized computation graph framework.

---

## 2. Governing Authority & Non-Graph Principle

In accordance with `MASTER_PROMPT.md` and Phase 1D:
> **The architecture must earn its abstractions.**  
> We do NOT implement `GraphObject`, `SignalObject`, `ComputeGraph`, `GraphExecutor`, `Scheduler`, `NodeRegistry`, or `PluginRegistry` in Phase 1E.  
> The typed computation graph must emerge from proven, frozen node composition contracts, not precede them.

---

## 3. Composition Observations from Phase 1D

Phase 1D demonstrated direct sequential processing:
```
input PCMBlock ──► GainNode ──► DelayNode ──► BiquadNode ──► output PCMBlock
```

Key empirical findings:
1. **Shape Invariance:** All current nodes preserve channel count, sample rate, frame count, and tensor layout (`(channels, frames)`, `float32`).
2. **Directional Link Compatibility:** Connecting Node A to Node B requires that Node A's output format strictly matches Node B's expected input format.
3. **State Isolation:** Each node encapsulates its own internal registers/buffers without cross-node interference.
4. **Latency Composability:** Total algorithmic latency is strictly additive ($\mathcal{L}_{\text{total}} = \sum \mathcal{L}_i$).
5. **Arbitrary Block Continuity:** The composition is invariant across chunk boundaries (e.g., 1 frame, 17 frames, 512 frames).

---

## 4. Architectural Decisions (DEC-01 to DEC-12)

### DEC-01: Node Shape Representation
- **Decision:** A node's computational shape is represented by its configured stream dimensions: `(channels, sample_rate, dtype, layout)`.
- **Rationale:** Audio nodes in Phase 1 operate uniformly on 2D planar arrays `(channels, frames)` with `float32` dtype.
- **Alternatives Considered:** Generic ND tensors (rejected as premature).
- **Consequences:** Nodes explicitly declare input/output compatibility.

### DEC-02: Directional Compatibility
- **Decision:** Compatibility is evaluated directionally: $\text{Compatible}(A_{\text{out}}, B_{\text{in}})$.
- **Rationale:** While current Phase 1 nodes are symmetric ($C_{\text{in}} = C_{\text{out}}$), future nodes (e.g., mono-to-stereo spatializers or downmixers) will transform shape asymmetrically.
- **Consequences:** Pipelines validate stage transitions sequentially from producer to consumer.

### DEC-03: Latency Representation & Accumulation
- **Decision:** Algorithmic latency $\mathcal{L}$ is an explicit integer frame property on each node. Total sequential latency is $\mathcal{L}_{\text{total}} = \sum \mathcal{L}_i$.
- **Rationale:** Algorithmic latency represents mathematical time displacement ($y[n] = x[n - \mathcal{L}]$) and is independent of hardware or buffer latency.
- **Consequences:** Latency is accurately composable and verifiable via independent tests.

### DEC-04: State Ownership & Encapsulation
- **Decision:** Nodes maintain complete ownership of their own state registers and history buffers.
- **Rationale:** Composition engines must not inspect or mutate internal node memory.
- **Consequences:** Guarantees modularity and embedded memory isolation.

### DEC-05: Reset Propagation
- **Decision:** Pipeline reset invokes `node.reset()` on all constituent nodes in deterministic forward declaration order.
- **Rationale:** Ensures all state lines are cleared to initial silence while preserving configurations.
- **Consequences:** Stream processing after reset bit-exactly reproduces initial cold-start behavior.

### DEC-06: Parameter Update Interaction
- **Decision:** Parameter updates occur directly on individual nodes via `node.set_parameters(...)` and do not alter pipeline topology.
- **Rationale:** Reconfiguring a filter or gain does not break the sequential pipeline structure.
- **Consequences:** State preservation or reset policies remain governed by the respective node contract (e.g., Biquad preserves state; Delay resets history).

### DEC-07: Sequential Execution Ordering
- **Decision:** Execution proceeds strictly in forward declaration order: $y_k = \text{Node}_k(y_{k-1})$.
- **Rationale:** Deterministic linear execution without branching or parallelism.
- **Consequences:** Zero runtime scheduling overhead; predictable single-pass performance.

### DEC-08: Pipeline Topology Immutability
- **Decision:** The list of nodes in a sequential pipeline is fixed as an immutable tuple at construction time.
- **Rationale:** Prevents runtime race conditions and unvalidated mutations.
- **Consequences:** Pipeline topology cannot be altered while processing.

### DEC-09: Metadata Propagation & Validation
- **Decision:** `AudioMetadata` flows along with sample arrays in `PCMBlock`. Each node validates incoming metadata against its configuration.
- **Rationale:** Guarantees immediate deterministic failure on sample-rate or channel mismatch.
- **Consequences:** No silent misconfigurations or corruptions.

### DEC-10: Failure Semantics
- **Decision:** Mismatches between connected stages raise typed exceptions (`IncompatibleNodeError`, `MalformedBufferError`).
- **Rationale:** Standardized exception hierarchy inheriting from `AcoustiForgeError`.
- **Consequences:** Clear, diagnosable failure modes.

### DEC-11: Numerical Conformance Propagation
- **Decision:** The numerical conformance tier of a pipeline is bounded by the least precise stage in the chain.
- **Rationale:** Composition of a `NUMERICALLY_EQUIVALENT` node with a `BIT_EXACT` node results in `NUMERICALLY_EQUIVALENT` output.
- **Consequences:** Realistic, auditable conformance claims.

### DEC-12: Runtime Neutrality
- **Decision:** Composition semantics are runtime-neutral and storage-independent.
- **Rationale:** The Python reference model maps directly to future embedded C/C++ static function pointers and buffer arrays.
- **Consequences:** No reliance on dynamic Python graph executors.

---

## 5. Candidate Minimal Sequential Execution Primitive

To formalize the composition contract without introducing a graph engine, we define:

```python
class SequentialPipeline(BaseProcessingNode):
    """Immutable sequential processing pipeline composing compatible processing nodes."""

    def __init__(self, nodes: Sequence[BaseProcessingNode], name: Optional[str] = None) -> None:
        ...
```

### 5.1 Contract Guarantees
1. **Immutability:** `self._nodes = tuple(nodes)` (immutable sequence).
2. **Validation:** Rejects empty sequences or non-`BaseProcessingNode` instances.
3. **Lifecycle Propagation:**
   - `configure(fs, channels)` configures all child nodes in order.
   - `reset()` resets all child nodes in forward declaration order.
   - `latency_frames` returns $\sum \text{node.latency\_frames}$.
4. **Processing:** Linear forward pass $y_{i} = \text{node}_i.\text{process}(y_{i-1})$.
5. **Bypass:** When `is_active = False`, returns `block.copy()`.

---

## 6. Deferred Concerns (Explicit Scope Boundary)

The following concerns are explicitly **DEFERRED** to future graph phases:
- Branching, fan-out, fan-in, parallel processing
- Typed compute graphs (`ComputeGraph`, `GraphExecutor`)
- Generalized scientific data objects (`SignalObject`, `GraphObject`)
- Dynamic topological sorting and dependency resolution
- Node registries, plugin registries, graph serialization

---

## 7. Acceptance Criteria

Phase 1E is satisfied when:
1. The composition discovery document is complete.
2. `SequentialPipeline` is implemented in `src/acoustiforge/engine/sequential.py` adhering to DEC-01..DEC-12.
3. Comprehensive contract tests in `tests/test_composition_contract.py` and `tests/test_sequential_pipeline.py` pass.
4. Cumulative latency, state isolation, parameter isolation, arbitrary block continuity, and reset propagation are verified.
5. Zero regressions across all 127 existing tests.
