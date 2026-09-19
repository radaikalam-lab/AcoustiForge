# AcoustiForge Normative Contract: Node Composition & Sequential Execution

**Document ID:** `CONTRACT-COMPOSITION-01`  
**Status:** **FROZEN & NORMATIVE**  
**Version:** `1.0.0`  
**Governing Authority:** `prompts/MASTER_PROMPT.md`

---

## 1. Scope & Purpose

This contract establishes the normative mathematical and software rules for composing compatible processing nodes (`BaseProcessingNode`) in the Acoustic Compute Engine (ACE).

This specification governs sequential (linear) node composition. Generalized graph topologies (DAGs, branching, cyclic execution) remain outside the scope of this contract.

---

## 2. Node Shape & Metadata Invariance

### 2.1 Stream Shape
A processing node operates on canonical discrete audio tensors:
$$\mathbf{X} \in \mathbb{R}^{C \times N}$$
where:
- $C \in \{1, 2\}$ is the channel count (Mono or Stereo).
- $N \ge 1$ is the temporal frame count.
- Format is planar, C-contiguous, single-precision IEEE 754 `float32`.

### 2.2 Metadata Invariance
For all Phase 1 primitive computational nodes:
$$\text{Metadata}_{\text{out}} \equiv \text{Metadata}_{\text{in}}$$
Nodes MUST NOT silently alter sample rate, channel count, channel layout, or frame count unless explicitly contracted as a dimensional transformer (e.g., resampler or spatializer).

---

## 3. Directional Link Compatibility

Given an upstream producer node $A$ and a downstream consumer node $B$, the connection $A \to B$ is **valid** if and only if:
1. $f_s(A) = f_s(B)$ (Sample rates are identical).
2. $C(A) = C(B)$ (Channel counts are identical).
3. $\text{dtype}(A) = \text{dtype}(B) = \text{float32}$.
4. $\text{layout}(A) = \text{layout}(B)$.

If any condition is violated, the composition MUST be deterministically rejected with `IncompatibleNodeError`. Automatic resampling, remixing, or format casting is strictly prohibited.

---

## 4. Algorithmic Latency Composition

### 4.1 Single Node Latency
Each node $i$ reports its inherent algorithmic latency $\mathcal{L}_i \in \mathbb{N}_0$ in units of temporal frames:
- `PassThroughNode`: $\mathcal{L} = 0$
- `GainNode`: $\mathcal{L} = 0$
- `BiquadNode`: $\mathcal{L} = 0$
- `DelayNode`: $\mathcal{L} = D$ ($D \ge 0$)

### 4.2 Cumulative Sequential Latency
For an ordered sequence of active nodes $[N_1, N_2, \dots, N_K]$:
$$\mathcal{L}_{\text{total}} = \sum_{k=1}^{K} \mathcal{L}_k$$
When a node is deactivated (`is_active = False`), its contribution to the pipeline latency drops to `0`.

---

## 5. State Encapsulation & Reset Semantics

1. **State Isolation:** Each node maintains exclusive encapsulation of its state variables ($\mathbf{S}_k$). Composition wrappers MUST NOT access, share, or merge node states.
2. **Deterministic Reset:** Pipeline reset invokes `reset()` on every constituent node in forward declaration order ($k = 1 \dots K$).
3. **Configuration Preservation:** Reset MUST zero state registers/delay buffers while preserving all configured filter parameters, gains, delay lengths, sample rates, and channel allocations.

---

## 6. Sequential Pipeline Execution Semantics

### 6.1 Linear Execution
For input block $\mathbf{X}_0$:
$$\mathbf{X}_k = \begin{cases} N_k.\text{process}(\mathbf{X}_{k-1}) & \text{if } N_k.\text{is\_active} \\ \mathbf{X}_{k-1} & \text{otherwise} \end{cases} \quad \text{for } k = 1, \dots, K$$
$$\mathbf{Y} = \mathbf{X}_K$$

### 6.2 Arbitrary Block Continuity
For any stream partitioned into arbitrary consecutive blocks $[\mathbf{X}^{(1)}, \mathbf{X}^{(2)}, \dots, \mathbf{X}^{(M)}]$:
$$\text{Pipeline}.\text{process}(\mathbf{X}^{(1)}) \mathbin{\Vert} \dots \mathbin{\Vert} \text{Pipeline}.\text{process}(\mathbf{X}^{(M)}) \equiv \text{Pipeline}.\text{process}(\mathbf{X}^{(1)} \mathbin{\Vert} \dots \mathbin{\Vert} \mathbf{X}^{(M)})$$
subject to the accumulated numerical precision tolerance of the participating nodes.

---

## 7. Topology Immutability

1. The sequence of nodes in a `SequentialPipeline` is fixed at construction.
2. Nodes cannot be dynamically added, removed, or reordered during execution.
3. Parameter mutation is restricted to individual node parameter updates (`set_parameters`) and does not alter pipeline structure.
