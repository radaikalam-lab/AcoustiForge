# AcoustiForge Normative Contract: Multi-Way Loudspeaker Graph Builder
## Contract Identifier: `CONTRACT-MULTIWAY-BUILDER-01`
## Version: `1.0.0`

---

## 1. Purpose & Architectural Role

This contract defines the deterministic assembly of multi-way loudspeaker compute graphs (e.g. 3-Way Woofer/Midrange/Tweeter systems and Stereo 3-Way systems) from pre-computed acoustic synthesis results.

The multi-way synthesis pipeline:
$$\left. \begin{array}{l}
\text{CrossoverSynthesisResult (LF/MF Boundary)} \\
\text{CrossoverSynthesisResult (MF/HF Boundary)} \\
\text{DriverAlignmentResults (Per Driver)} \\
\text{GainDesignResults (Per Driver)} \\
\text{EQSynthesisResults (Per Driver)} \\
\text{ProtectionFilterResults (Per Driver)}
\end{array} \right\} \xrightarrow{\text{ThreeWayGraphBuilder.build\_3way\_graph()}} \text{ComputeGraph (Frozen DAG)}$$

### Architectural Boundaries:
- **Layer Placement:** Resides in the graph builders plane (`src/acoustiforge/builders/multiway_builder.py`).
- **Compute Isolation:** Consumes domain and mathematical results; constructs a standard Phase 2B `ComputeGraph`.
- **Zero Realtime Logic:** Graph building is performed strictly offline at build/initialization time.
- **Frozen Compute Plane:** Does NOT modify `ComputeGraph`, DSP nodes, or PCM block contracts.

---

## 2. Backward Compatibility & Non-Destructive Extension

1. **Frozen 2-Way Isolation:** The existing `CrossoverGraphBuilder.build_2way_graph` (Phase 3D / 4A) remains 100% frozen and untouched.
2. **Additive Class Structure:** 3-way graph construction is encapsulated in a dedicated `ThreeWayGraphBuilder` (and stereo extension `SystemTopologyBuilder.build_stereo_3way_graph`).
3. **Legacy Execution Invariant:** 2-way graph generation continues to produce bit-exact identical node IDs, static schedules, latencies, and multi-block PCM audio outputs.

---

## 3. Canonical 3-Way Loudspeaker Topology

A 3-way loudspeaker graph consists of a single root input distributing audio to three parallel, deterministic driver processing branches:

```
                            ┌─► [Woofer Branch]   ──► "woofer.*"   ──► Output 0
                            │
Input ("input.in") ─────────┼─► [Midrange Branch] ──► "midrange.*" ──► Output 1
                            │
                            └─► [Tweeter Branch]  ──► "tweeter.*"  ──► Output 2
```

### 3.1 Driver Branch Pipeline Sequences

#### 1. Woofer Branch (`woofer`):
$$\text{input} \longrightarrow [\text{delay}] \longrightarrow [\text{gain}] \longrightarrow [\text{eq}\dots] \longrightarrow [\text{crossover.lp}\dots] \longrightarrow [\text{protection}\dots] \longrightarrow \text{output}$$
- Crossover Filter: Low-pass sections synthesized at LF/MF crossover frequency $f_{\text{crossover, low}}$.

#### 2. Midrange Bandpass Branch (`midrange`):
$$\text{input} \longrightarrow [\text{delay}] \longrightarrow [\text{gain}] \longrightarrow [\text{eq}\dots] \longrightarrow [\text{crossover.hp}\dots] \longrightarrow [\text{crossover.lp}\dots] \longrightarrow [\text{protection}\dots] \longrightarrow \text{output}$$
- High-Pass Crossover: High-pass sections synthesized at LF/MF crossover frequency $f_{\text{crossover, low}}$.
- Low-Pass Crossover: Low-pass sections synthesized at MF/HF crossover frequency $f_{\text{crossover, high}}$.
- **Ordering Convention (Normative):** `crossover.hp` MUST precede `crossover.lp`. This ensures a deterministic static schedule and state memory layout.

#### 3. Tweeter Branch (`tweeter`):
$$\text{input} \longrightarrow [\text{delay}] \longrightarrow [\text{gain}] \longrightarrow [\text{eq}\dots] \longrightarrow [\text{crossover.hp}\dots] \longrightarrow [\text{protection}\dots] \longrightarrow \text{output}$$
- Crossover Filter: High-pass sections synthesized at MF/HF crossover frequency $f_{\text{crossover, high}}$.

---

## 4. Deterministic Node Naming Scheme

All node identifiers within the constructed `ComputeGraph` are strictly deterministic:

| Stage | Woofer Branch | Midrange Branch | Tweeter Branch |
| :--- | :--- | :--- | :--- |
| **Delay Node** | `f"{woofer}.delay"` | `f"{midrange}.delay"` | `f"{tweeter}.delay"` |
| **Gain Node** | `f"{woofer}.gain"` | `f"{midrange}.gain"` | `f"{tweeter}.gain"` |
| **Parametric EQ** | `f"{woofer}.eq.{idx}"` | `f"{midrange}.eq.{idx}"` | `f"{tweeter}.eq.{idx}"` |
| **Crossover (HP)** | *N/A* | `f"{midrange}.crossover.hp.{idx}"` | `f"{tweeter}.crossover.{idx}"` |
| **Crossover (LP)** | `f"{woofer}.crossover.{idx}"` | `f"{midrange}.crossover.lp.{idx}"` | *N/A* |
| **Protection Filter** | `f"{woofer}.protection.{idx}"` | `f"{midrange}.protection.{idx}"` | `f"{tweeter}.protection.{idx}"` |

- `idx` is 0-indexed integer corresponding to cascade section order ($0, 1, \dots, K-1$).
- Graph Input Port: `("input", "in")`.
- Graph Output Ports: `(woofer_last_node_id, "out")`, `(midrange_last_node_id, "out")`, `(tweeter_last_node_id, "out")`.

---

## 5. Optional Stage Omission Semantics

1. **Alignment Delay:** If `alignments` is `None` or driver entry omitted, `delay_frames = 0` is applied (DelayNode acts as a clean 0-latency identity buffer).
2. **Sensitivity Gain:** If `gains` is `None` or driver entry omitted, `gain_db = 0.0` ($1.0$ linear gain) is applied.
3. **Parametric EQ:** If `equalizers` is `None` or driver has zero EQ sections, zero EQ nodes are created, and gain connects directly to the first crossover filter.
4. **Protection Filters:** If `protections` is `None` or driver has zero protection sections, zero protection nodes are created, and the final crossover filter output becomes the declared graph branch output.

---

## 6. Crossover Frequency & Parameter Invariants

1. **Crossover Ordering:**
   $$0 < f_{\text{crossover, low}} < f_{\text{crossover, high}} < \frac{f_s}{2} \quad [\text{Hz}]$$
   A 3-way graph builder MUST reject configurations where $f_{\text{crossover, low}} \ge f_{\text{crossover, high}}$ with `InvalidParameterError`.
2. **Sample Rate Uniformity:**
   All input synthesis results (`crossover_low`, `crossover_high`, `equalizers`, `protections`) must match the builder configured `sample_rate`. Any mismatch raises `InvalidParameterError`.
3. **Graph Freezing:**
   The constructed graph is validated and frozen via `graph.freeze()` prior to returning, ensuring static cycle detection, topological scheduling, and single-producer port verification.

---

## 7. API Specification

```python
class ThreeWayGraphBuilder:
    """Builder for constructing deterministic 3-way loudspeaker compute graphs."""

    def __init__(
        self,
        sample_rate: int,
        channels: int = 1,
        woofer_name: str = "woofer",
        midrange_name: str = "midrange",
        tweeter_name: str = "tweeter",
        graph_name: Optional[str] = None,
    ) -> None: ...

    def build_3way_graph(
        self,
        crossover_low: CrossoverSynthesisResult,
        crossover_high: CrossoverSynthesisResult,
        alignments: Optional[Mapping[str, DriverAlignmentResult]] = None,
        gains: Optional[Mapping[str, GainDesignResult]] = None,
        equalizers: Optional[Mapping[str, EQSynthesisResult]] = None,
        protections: Optional[Mapping[str, ProtectionFilterResult]] = None,
    ) -> ComputeGraph: ...
```

---

## 8. Verification & Conformance Invariants

1. **Topology Determinism:** For identical parameters, graph construction produces identical node collections, edge lists, topological schedules, and latency values.
2. **PCM Execution:** Executing `ComputeGraph.process()` over sequential `PCMBlock` streams produces finite, bit-exact float32 arrays with zero state corruption.
3. **No Unconnected Ports:** Every port in the graph is fully connected; root input fans out cleanly to all 3 driver branches; all 3 branch endpoints are declared external outputs.
