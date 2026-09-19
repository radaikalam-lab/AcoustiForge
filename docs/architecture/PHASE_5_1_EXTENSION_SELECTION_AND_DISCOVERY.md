# Phase 5-1: Extension Selection & Architectural Discovery (Revised)

**Date:** 2026-09-19  
**Status:** REVISED ARCHITECTURAL SELECTION & DISCOVERY REPORT  
**Target Repository:** `E:\AcoustiForge`  
**Verified Baseline:** Commit `Phase 4D-7 Freeze` / `Phase 5-0R Freeze` (`434 passed, 0 failed, 0 errors, 0 warnings`)  
**Companion Documents:**
- `docs/architecture/PHASE_5_0_ADAPTIVE_ACOUSTIC_ARCHITECTURE_DISCOVERY.md`
- `docs/architecture/PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md`
- `docs/architecture/PHASE_4D_6_EXECUTABLE_CONTINUITY_BENCHMARK.md`
- `docs/architecture/PHASE_4D_5_REVIEW_AND_FORWARD_REQUIREMENTS.md`
- `docs/architecture/ACOUSTIFORGE_OOTB_CAPABILITY_AUDIT.md`
- `docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md`

---

## 1. Executive Baseline & Purpose

Phase 5-0R established and froze the **Optional Extension-Hook Architecture**:
> **AcoustiForge Core is the deterministic acoustic engine. Everything intelligent, contextual, adaptive, external, or hardware-specific plugs into it through optional, validated extension hooks.**

The purpose of this Phase 5-1 discovery exercise is to evaluate all nine candidate extension tracks (Tracks A through I) and determine on empirical, architectural, and mathematical evidence:
> **Which single optional Phase 5 extension, if any, is technically ready, mathematically justified, and minimally scoped to implement first?**

### Current Repository State
* **Test Suite:** 434 passed, 0 failed, 0 errors, 0 warnings (`pytest -q -W error` in 2.15s).
* **Core Stability:** Phase 4 mathematical control plane and domain models are frozen.
* **Production Dependencies:** Standard library + NumPy (zero third-party audio/ML/solver dependencies).

---

## 2. Phase 5-0R Architectural Constraints & Selection Criteria

Any candidate selected for initial Phase 5 implementation must strictly satisfy five non-negotiable architectural invariants:

1. **Zero Core Mutation:** The extension must be implementable entirely outside AcoustiForge Core (`src/acoustiforge/domain/`, `src/acoustiforge/acoustic_math/`, `src/acoustiforge/graph/`, `src/acoustiforge/contracts/`). Core must remain 100% functional if the extension is deleted.
2. **Consumption of Existing Core Contracts:** The extension must consume existing frozen contracts (`FrequencyResponseData`, `OptimizationSpecification`, `OptimizationResult`, `ComputeGraph`) rather than altering their schemas.
3. **Deterministic & Offline Testability:** The extension must be 100% testable in a standard test runner (`pytest`) without requiring physical audio hardware, live sensors, external network services, or GPUs.
4. **Availability of Independent Analytical Goldens:** The extension’s correctness must be verifiable against closed-form mathematical or independent synthetic baselines.
5. **No Cascading Dependencies:** Implementing the extension must not force the creation of any other extension track.

---

## 3. Repository Capability Inventory & Existing Substrate

A thorough inspection of the repository reveals the existing reusable substrate for each track:

| Subsystem | Existing Reusable Assets in Core | Readiness for Extension |
|---|---|---|
| **Measurement Ingestion** | WAV PCM parser (16/24/32-bit float), ASCII FRD/ZMA parser, reflection gating (Tukey/Hann), SNR diagnostics, microphone calibration normalization. | High. Can already produce valid `FrequencyResponseData` from arbitrary files. |
| **Complex Forward Model** | Machine-precision complex summation kernel $H_{\text{total}}(f) = \sum H_k(f)$, biquad response evaluation, grid matching validator. | Full. Vectorized across frequency grids up to Nyquist. |
| **Optimization Solver** | `coordinate_descent_search` with `golden_section_line_search`, normative tie-breaking, bound/constraint enforcement. | Full. Functional design accepts arbitrary deterministic objective callables `f(p) -> float`. |
| **Graph Runtime** | `ComputeGraph` DAG, `BiquadNode` (DF-II-T), `GainNode`, `DelayNode`, `SumNode`, `compile_optimization_result_to_graph`. | Full. Frozen execution on raw float32 PCM blocks. |
| **Domain Validation** | Strict exception hierarchy (`InvalidSpecificationError`, `InvalidParameterError`, `UnstableFilterError`, etc.). | Full. Catches degenerate bounds, invalid orders, or pole instability. |

---

## 4. Track-by-Track Assessment (Tracks A through I)

### Track A — Measurement & AcousticState Hooks
* **Concept:** External multi-microphone scanner interfaces and an `AcousticState` context container.
* **Analysis:** Core already directly ingests WAV and ASCII files into `FrequencyResponseData`. A formal `AcousticState` container or scanner hook would add another data container without adding new mathematical or design capabilities.
* **Readiness:** Medium.
* **Value for Phase 5-1:** Low/Redundant. Core does not need an intermediate scanner layer to operate.

### Track B — DesignIntent & Intent Compiler
* **Concept:** High-level proposal contract (tonal tilt, target curve presets, warmth/brightness tags) translated deterministically into `OptimizationSpecification`.
* **Analysis:** Well-scoped and decoupled, but its primary utility is serving as a translation bridge for Track H (AI) or a graphical user interface. Without an AI engine or GUI actively generating intent proposals, Track B provides limited immediate stand-alone utility over direct `OptimizationSpecification` construction.
* **Readiness:** High.
* **Value for Phase 5-1:** Medium (Foundational for AI, but secondary in isolation).

### Track C — Multi-Position Spatial Optimization (SELECTED IMPLEMENTATION CANDIDATE)
* **Concept:** Multi-measurement objective aggregation evaluating the complex forward model across $M$ spatial observation points:
  $$\mathcal{L}_{\text{multi}}(\mathbf{p}) = \sum_{m=1}^M w_m \cdot \mathcal{L}\left( H_{\text{total}, m}(f; \mathbf{p}), T(f) \right)$$
* **Analysis:** Solves a foundational physical reality: optimizing a loudspeaker for a single microphone location frequently creates severe destructive interference or peaks at adjacent listening seats. Track C leverages 100% of existing Core math (forward model, grid validation, coordinate descent solver) by wrapping the objective function without mutating Core.
* **Readiness:** **Very High.** Core optimizer accepts any objective callable.
* **Value for Phase 5-1:** **Very High.** Immediately provides multi-seat acoustic optimization capability, validated with synthetic spatial offsets and analytical trade-off goldens.

### Track D — Cryptographic Provenance Observer
* **Concept:** Non-invasive observer computing SHA-256 hashes of input measurements, specifications, optimizer trajectories, and compiled graphs into an immutable `ProvenanceRecord`.
* **Analysis:** Highly decoupled and lightweight (stdlib `hashlib` + `json`), but provides compliance/audit logging rather than acoustic design capability.
* **Readiness:** High.
* **Value for Phase 5-1:** Medium (Valuable for auditability, but lower immediate acoustic leverage than Track C).

### Track E — Embedded Edge Runtime Architecture
* **Concept:** Process isolation (realtime audio process vs supervisory optimization process) with lock-free parameter double-buffering for embedded Linux / Raspberry Pi SBCs.
* **Analysis:** Requires IPC infrastructure, shared memory, or threading harnesses. Unnecessary for offline workstation design workflows.
* **Readiness:** Low/Medium.
* **Value for Phase 5-1:** Low (Premature before standalone execution targets are established).

### Track F — Hardware Execution & C99 Transpilation
* **Concept:** Static code generation translating a frozen `ComputeGraph` into standalone C99 code for microcontrollers / DSP chips.
* **Analysis:** Highly valuable for embedded deployment, but represents a code-generation / compiler task rather than an acoustic optimization capability.
* **Readiness:** Medium.
* **Value for Phase 5-1:** Medium (Desirable for Phase 5-2/5-3 once spatial optimization is settled).

### Track G — User Preference Modeling
* **Concept:** Subjective rating models, A/B preference tracking, and user preference inference.
* **Analysis:** Requires human subjective datasets or interactive listening tests. Premature in an automated unit test suite.
* **Readiness:** Low.
* **Value for Phase 5-1:** Low.

### Track H — AI & Design Intelligence Integrations
* **Concept:** Advisory AI proposing candidate target curves or `DesignIntent` objects.
* **Analysis:** Relies on Track B (`DesignIntent`) as its target representation. Implementing Track H first would be building a consumer before its interface is established.
* **Readiness:** Low.
* **Value for Phase 5-1:** Low/Premature.

### Track I — Desktop / Headphone Audio Execution Hook (NEW CANDIDATE)
* **Concept:** Host-audio integration boundary allowing an AcoustiForge `ComputeGraph` to process PCM audio streams destined for desktop audio output devices (including headphones), initially targeting Windows desktop.
* **Analysis:** Explores utilizing the frozen `ComputeGraph -> PCMBlock` execution boundary as an optional centralized DSP processing stage for host OS audio. Does not modify Core, but requires future discovery into OS audio endpoints, buffer scheduling, latency, and driver interfaces.
* **Readiness:** Medium (Discovery concept).
* **Value for Phase 5-1:** High as a future execution target; does not supersede Track C as the first implementation candidate.

---

## 5. Comparative Evaluation Matrix

| Track | Core Mutation | Dependency Impact | Offline Testability | Analytical Goldens | Acoustic Leverage | Overall Readiness |
|---|---|---|---|---|---|---|
| **Track A (Measurement/AcousticState)** | None | None | Full | High | Low | Medium |
| **Track B (DesignIntent Compiler)** | None | None | Full | High | Medium | High |
| **Track C (Multi-Position Optimization)** | **None** | **None** | **Full** | **Very High** | **Very High** | **Very High (Selected)** |
| **Track D (Provenance Observer)** | None | None | Full | High | Medium | High |
| **Track E (Edge Runtime / IPC)** | None | IPC / OS | Partial (Hardware-linked) | Medium | Low | Low |
| **Track F (C99 Transpilation)** | None | C Compiler | High | High | High | Medium |
| **Track G (User Preferences)** | None | None | Low (Needs human data) | Low | Low | Low |
| **Track H (AI Integration)** | None | LLM / API | Low | Medium | Medium | Low |
| **Track I (Desktop/Headphone Audio Hook)** | None | None (at discovery) | Medium (Needs OS audio) | High (PCM continuity) | High | Medium (Candidate) |

---

## 6. Selection Conclusion: Preserving Track C Selection

Based on rigorous repository evidence, **Track C — Multi-Position Spatial Optimization** remains the selected candidate for the first Phase 5 implementation.

### Technical Rationale:
1. **Immediate Mathematical & Physical Value:** Real-world sound systems are listened to in spatial zones (e.g. driver + passenger in automotive; couch center + couch left/right in home audio). Optimizing for one point produces destructive spatial side-effects. Track C directly solves spatial compromise optimization.
2. **Zero Core Modifications Required:** The Phase 4 `coordinate_descent_search` solver was architected as a pure functional higher-order function taking `objective_func: Callable[[np.ndarray], float]`. Track C constructs a multi-position objective wrapper that feeds directly into the frozen solver.
3. **Pure Composition of Core Contracts:** Operates by aggregating multiple standard `FrequencyResponseData` measurements with normalized spatial weights $w_m$.
4. **Strong Independent Golden Parity:** Spatial trade-offs between two synthetic drivers with known spatial delays $(\Delta\tau_1, \Delta\tau_2)$ can be solved analytically and verified to machine precision.
5. **Zero External Dependencies:** Implemented entirely using Python stdlib + NumPy.

---

## 7. Track I Architectural Discovery & Boundary Specification

Track I is recognized as an optional future execution/I/O extension that exploits the natural `ComputeGraph -> PCMBlock` execution seam.

### 7.1 Concept & Architectural Boundary
```text
Music / Host Application
           │
           ▼
Windows Audio Endpoint / Audio Source
           │
           ▼ (Proposed Execution Hook — Track I)
      ComputeGraph (Frozen Core DSP)
           │
           ▼
Physical Audio Device / DAC Output
           │
           ▼
       Headphones
```

### 7.2 Core Independence & Operating System Separation
* **AcoustiForge Core is Self-Sufficient:** Core operates with 100% mathematical and DSP completeness without Windows, headphones, virtual audio cables, PortAudio, WASAPI, ASIO, or any OS-specific audio framework.
* **Centralized DSP Processing Stage:** AcoustiForge may serve as an optional centralized DSP processing stage in the desktop audio path. The host operating system remains responsible for audio transport and device integration.
* **Important Distinction from Headphone Calibration:** Track I concerns desktop audio execution and PCM routing (`PCM source -> AcoustiForge DSP -> PCM output`). Headphone calibration is an independent measurement-driven design process (`Headphone Measurement -> FRD -> Target -> Optimization -> ComputeGraph`).

### 7.3 Track I Specification Summary
```text
Track I — Desktop / Headphone Audio Execution Hook

Classification:
Optional Execution / I/O Extension

Initial target:
Windows desktop

Purpose:
Optional centralized DSP processing stage for desktop PCM audio.

Core modification:
NONE

Core dependency:
NONE

New dependency:
NONE at discovery stage

Potential consumer:
Headphones / desktop audio output

Primary architectural boundary:
PCM ↔ Execution Hook ↔ ComputeGraph

Open questions:
- Windows audio endpoint mechanism (Virtual endpoint, WASAPI loopback, or application stream hook)
- Buffer scheduling and frame-size matching (Host frame count vs ComputeGraph block size)
- Latency and buffer underrun/overrun mitigation
- Sample format conversion (e.g. 16/24-bit integer PCM ↔ float32 canonical tensor)
- Realtime thread priority and lock-free execution
- Atomic parameter update boundaries during live playback

Implementation status:
NOT IMPLEMENTED (Architectural candidate for future execution tracks)
```

---

## 8. Proposed Phase 5-1 Implementation Boundary (Track C)

```text
Extension:                    Track C — Multi-Position Spatial Optimization
Module Location:              src/acoustiforge/extensions/spatial_optimization.py (NEW)
Contracts/Domain Objects:     MultiPositionOptimizationSpecification, MultiPositionOptimizationResult
Core Changes Required:        NONE (0 files modified in Core)
Dependency Impact:            NONE (Python stdlib + NumPy only)
External Hardware Required:   NONE (100% offline, deterministic)

Mathematical Specification:
    Given M spatial measurement sets {FRD_1, ..., FRD_M} and spatial weights {w_1, ..., w_M} with Σ w_i = 1.0:
    L_multi(p) = Σ_{m=1}^M w_m * evaluate_optimization_objective(
        predicted_response = calculate_acoustic_complex_summation(H_branch,m(p)),
        target_curve       = target_curve,
        frequency_range_hz = frequency_range_hz,
        ripple_weight      = ripple_weight,
        delay_weight       = delay_weight
    )

Validation Strategy:
    1. 2-Position Analytical Spatial Delay Compromise:
       - Position 1: Tweeter leading by +100 us.
       - Position 2: Tweeter lagging by -100 us.
       - Equal weights (w1 = 0.5, w2 = 0.5) -> Optimal delay tau* = 0.0 us.
       - Asymmetric weights (w1 = 0.8, w2 = 0.2) -> Optimal delay shifts predictably toward Position 1.
    2. 3-Position Room Zone Optimization:
       - Left, Center, Right listening positions with multi-driver crossover optimization.
    3. Monotonicity & Invariant Verification:
       - L_multi(p_final) <= L_multi(p_initial).
    4. Negative Validation:
       - Grid mismatch across spatial measurements -> InvalidParameterError.
       - Negative or unnormalized spatial weights -> InvalidSpecificationError.
       - Missing driver measurements at any position -> InvalidParameterError.

Rollback Strategy:
    - Pure deletion of src/acoustiforge/extensions/spatial_optimization.py and tests/test_spatial_optimization.py.
    - Zero impact on Core or test baseline (434 tests remain intact).
```

---

## 9. Explicit Non-Goals for Phase 5-1

* **DO NOT** modify any file in `src/acoustiforge/domain/`, `src/acoustiforge/acoustic_math/`, `src/acoustiforge/graph/`, or `src/acoustiforge/builders/`.
* **DO NOT** implement Track I, WASAPI, PortAudio, or desktop audio drivers.
* **DO NOT** implement AI or LLM integrations.
* **DO NOT** implement Raspberry Pi or hardware audio drivers.
* **DO NOT** implement room simulation or 3D ray tracing.
* **DO NOT** implement C99 transpilation in this milestone.

---

## 10. Verification & Regression Gate

* **Baseline Test Suite:** 434 passed in 2.15s (`pytest -q -W error`).
* **Production Code Modified:** None.
* **Phase 4 Contracts Modified:** None.
* **Phase 5-0R Architecture Modified:** None.

```powershell
pytest -q -W error
434 passed in 2.15s
```

---

## 11. Conclusion

Phase 5-1 revised discovery establishes that **Track C (Multi-Position Spatial Optimization)** remains the single selected candidate for initial implementation, while **Track I (Desktop / Headphone Audio Execution Hook)** is formalized as a clean, decoupled future execution candidate.
