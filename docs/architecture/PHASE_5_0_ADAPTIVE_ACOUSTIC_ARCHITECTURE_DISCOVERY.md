# Phase 5-0: Adaptive Acoustic Intelligence Architecture & Optional Extension Hooks

**Date:** 2026-09-19  
**Status:** FROZEN AS OPTIONAL EXTENSION-HOOK ARCHITECTURE (PHASE 5-0R)  
**Target Repository:** `E:\AcoustiForge`  
**Verified Baseline:** Commit `Phase 4D-7 Freeze` (`434 passed, 0 failed, 0 errors, 0 warnings`)  
**Companion Documents:**
- `docs/architecture/PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md`
- `docs/architecture/PHASE_4D_6_EXECUTABLE_CONTINUITY_BENCHMARK.md`
- `docs/architecture/PHASE_4D_5_REVIEW_AND_FORWARD_REQUIREMENTS.md`
- `docs/architecture/ACOUSTIFORGE_OOTB_CAPABILITY_AUDIT.md`
- `docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md`
- `docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md`
- `docs/contracts/PCM_CONTRACT.md`

---

## 1. Executive Summary

Phase 4 of AcoustiForge established and froze the **deterministic acoustic control plane**: a machine-precision, analytically validated pipeline that ingests acoustic measurements, constructs complex transfer function models, optimizes multi-way crossover/gain/delay parameters via **Bounded Coordinate Descent + Golden-Section Line Search**, validates monotonicity and constraint satisfaction, and deterministically compiles the resulting `OptimizationResult` into an executable `ComputeGraph` DSP engine operating on raw float32 PCM samples.

Phase 5 defines an **Optional Extension-Hook Architecture** around this independently complete, self-contained AcoustiForge Core.

### The Primary Architectural Principle:
> **AcoustiForge Core must remain independently complete, self-contained, and fully functional without AI, external sensors, user-preference models, Raspberry Pi SBCs, room intelligence engines, provenance databases, cloud services, or any other Phase 5 extension.**

Phase 5 defines **OPTIONAL EXTENSION CAPABILITIES**, not mandatory core dependencies. The external ecosystem may extend AcoustiForge, but AcoustiForge Core never depends on the ecosystem.

```text
                    OPTIONAL EXTERNAL WORLD
    ┌────────────────────────────────────────────────────┐
    │                                                    │
    │  AI / ML              Sensors                     │
    │  User Preferences     Room Measurements           │
    │  GUI / Application    Vehicle Context             │
    │  External Optimizer   Edge Controller             │
    │  Research Tools       Future Services             │
    │                                                    │
    └───────────────────────┬────────────────────────────┘
                            │
                            ▼
                PROPOSED EXTENSION HOOKS
                            │
                            ▼
                    VALIDATION BOUNDARY
                            │
                            ▼
             ┌──────────────────────────────┐
             │       ACOUSTIFORGE CORE      │
             │                              │
             │ Domain Models                │
             │ Acoustic Mathematics         │
             │ Deterministic Optimization   │
             │ Invariant Validation         │
             │ OptimizationResult           │
             │ Graph Compilation            │
             │ ComputeGraph                 │
             │ DSP Execution Engine         │
             └──────────────────────────────┘
```

**Core Invariants of the Extension Architecture:**
1. **AcoustiForge Core is Self-Sufficient:** Core domain workflows (e.g., `OptimizationSpecification` $\rightarrow$ `OptimizationResult` $\rightarrow$ `ComputeGraph`) operate with 100% completeness in isolation.
2. **AI Proposes, AcoustiForge Decides:** When an AI or heuristic system is connected via an extension hook, it is strictly advisory. AcoustiForge remains the sole authority for physical feasibility, filter stability, parameter bounds, and complex acoustic summation.
3. **No Direct DSP Tampering:** External systems cannot directly mutate live filter coefficients or execute inside the per-sample audio path. All proposals must pass through explicit AcoustiForge validation boundaries.
4. **Timescale Decoupling:** Optional supervisory and adaptation tasks (seconds/minutes) operate outside the deterministic realtime audio execution loop (microseconds/samples).

---

## 2. Three-Tier Architectural Distinction

To preserve modularity and prevent dependency creep, the architecture explicitly distinguishes:

### A. Core Contracts (Mandatory, Implemented & Frozen in Core)
These are the native, frozen domain objects and algorithms that constitute AcoustiForge Core:
* `FrequencyResponseData`, `ImpulseResponseData`
* `DriverProfile`, `EnclosureProfile`, `TransducerLimits`
* `AcousticTargetCurve`, `CrossoverSpecification`
* `OptimizationSpecification`, `OptimizationResult`
* Machine-precision complex summation kernel ($H_{\text{total}}(f)$)
* Bounded Coordinate Descent + Golden-Section Line Search optimizer
* `ComputeGraph`, `BiquadNode`, `GainNode`, `DelayNode`, `SumNode`
* `compile_optimization_result_to_graph`

### B. Extension Hooks (Proposed Architectural Concepts / Interfaces)
Clean, lightweight conceptual extension interfaces through which external systems may optionally provide data or receive results. **These are proposed architectural concepts, not yet implemented production APIs:**
* `MeasurementProviderHook`: Proposed interface for external measurement acquisition tools to feed core `FrequencyResponseData`.
* `DesignIntentAdapterHook`: Proposed adapter translating high-level intent proposals into `OptimizationSpecification`.
* `ContextStateHook`: Proposed interface for optional environmental/spatial telemetry.
* `PreferenceProviderHook`: Proposed interface for subjective user preference models.
* `ProvenanceObserverHook`: Proposed observer subscribing to optimization/compilation events for audit logging.
* `ExecutionBackendHook`: Proposed adapter for transpiling or exporting `ComputeGraph` to external hardware targets.

### C. External Implementations (Optional Concrete Implementations of Hooks)
Future external tools, devices, or platforms that may implement the proposed hooks:
* Raspberry Pi / Linux embedded daemon
* Local LLM or cloud AI intent service
* Calibrated USB microphone acquisition application
* Automotive cabin CAN-bus context listener
* Subjective A/B testing user interface

**Cardinal Rule:** AcoustiForge Core requires neither B nor C to execute its full mathematical, optimization, and DSP suite.

---

## 3. Generic Extension Model vs. Direct Workflows

`DesignIntent` is **not** a mandatory gateway into AcoustiForge. Direct, unmediated workflows remain the primary native interface:

### 3.1 Direct Native Workflow (Primary & Fully Supported)
```text
Application / User
        │
        ▼
OptimizationSpecification (Core Contract)
        │
        ▼
AcoustiForge Optimizer (Core Engine)
        │
        ▼
OptimizationResult (Core Contract)
        │
        ▼
ComputeGraph (Core DSP)
```

### 3.2 Optional Measurement Extension
```text
Measurement Hardware / Scanner
        │
        ▼ (MeasurementProviderHook — Proposed)
FrequencyResponseData (Core Contract)
        │
        ▼
AcoustiForge Core
```

### 3.3 Optional AI / High-Level Intent Extension
```text
AI Agent / Natural Language UI
        │
        ▼
DesignIntent (Optional Proposal Concept)
        │
        ▼ (DesignIntentAdapterHook — Proposed)
OptimizationSpecification (Core Contract)
        │
        ▼
AcoustiForge Core
```

### 3.4 Optional Context / Automotive Extension
```text
Vehicle / Room Sensors
        │
        ▼
ContextState (Optional Context Concept)
        │
        ▼ (ContextAdapterHook — Proposed)
OptimizationSpecification (Core Contract)
        │
        ▼
AcoustiForge Core
```

In every case, data enters AcoustiForge Core exclusively through validated Core domain contracts.

---

## 4. Reclassified: AcousticState as an Optional Context Model

`AcousticState` is an **Optional Context Model**.

### 4.1 Role & Scope
`AcousticState` is a proposed conceptual abstraction useful for external room-aware orchestrators, multi-position measurement harnesses, and embedded environmental scanners. AcoustiForge Core does **not** require `AcousticState` to perform multi-way loudspeaker optimization.

```text
External Room Scanner / Sensor Array
                 │
                 ▼
        AcousticState (Proposed Context Model)
                 │
                 ▼ (External Context Adapter)
   FrequencyResponseData / TargetCurve (Core Contracts)
                 │
                 ▼
          AcoustiForge Core
```

### 4.2 Candidate Conceptual Data Structure
```python
@dataclass(frozen=True, slots=True)
class SpatialMeasurement:
    """Optional spatial measurement container for external multi-mic harnesses (Conceptual)."""
    position_id: str
    coordinates_xyz_meters: tuple[float, float, float]
    frequency_response: FrequencyResponseData
    weight: float = 1.0

@dataclass(frozen=True, slots=True)
class EnvironmentalConditions:
    """Optional atmospheric telemetry container (Conceptual)."""
    temperature_celsius: float = 20.0
    relative_humidity_pct: float = 50.0

    @property
    def speed_of_sound_mps(self) -> float:
        return 331.3 * math.sqrt(1.0 + self.temperature_celsius / 273.15)

@dataclass(frozen=True, slots=True)
class AcousticState:
    """Optional external snapshot aggregating spatial and environmental telemetry (Conceptual)."""
    state_id: str
    timestamp_utc: float
    environment: EnvironmentalConditions
    spatial_measurements: tuple[SpatialMeasurement, ...]
```

---

## 5. Reclassified: DesignIntent as an Optional Proposal Contract

`DesignIntent` is an **Optional High-Level Semantic Proposal Contract**.

### 5.1 Purpose & Boundary
`DesignIntent` serves callers (human operators, AI assistants, heuristic rule engines) who express acoustic desires at a higher semantic level than explicit mathematical filter bands:
* *"Increase perceived warmth by +1.5 dB"*
* *"Prioritize spatial consistency for primary listener"*
* *"Target a neutral mastering studio response curve"*

`DesignIntent` is translated into a standard `OptimizationSpecification` via an external **Intent Adapter**. The core Phase 4 optimizer remains completely oblivious to AI, natural language, or intent semantics.

### 5.2 Candidate Intent Contract (Conceptual)
```python
@dataclass(frozen=True, slots=True)
class DesignIntent:
    """Optional high-level design proposal object (Conceptual)."""
    intent_id: str
    target_curve_name: str
    tonal_tilt_db_per_octave: float = 0.0
    bass_boost_db: float = 0.0
    crossover_family_preference: CrossoverFamily = CrossoverFamily.LINKWITZ_RILEY
    smoothness_priority: float = 1.0
```

---

## 6. AI & Design Intelligence Boundary

AI is **one possible consumer/provider** of AcoustiForge extension hooks, not a core component of the engine.

```text
┌────────────────────────────────────────────────────────────────────────┐
│             OPTIONAL AI / DESIGN INTELLIGENCE EXTENSION                │
│                                                                        │
│   WHAT AI CAN PROPOSE VIA EXTENSION HOOKS:                             │
│   ✔ Recommend candidate AcousticTargetCurve modifications              │
│   ✔ Translate user natural language requests into DesignIntent         │
│   ✔ Suggest candidate crossover search regions based on driver specs   │
│   ✔ Recommend spatial weighting matrices across listening positions    │
│                                                                        │
│   WHAT AI CANNOT DO (CORE INVARIANTS):                                 │
│   ✖ Cannot bypass AcoustiForge parameter bounds or validation          │
│   ✖ Cannot directly mutate live Biquad, Gain, or Delay node state      │
│   ✖ Cannot execute inside the per-sample audio processing loop         │
│   ✖ Cannot alter or redefine complex acoustic transfer functions       │
│   ✖ Cannot override filter stability or excursion limits               │
└────────────────────────────────────────────────────────────────────────┘
```

**Key Axiom:** AI is optional; validation is mandatory for any proposal entering the deterministic control plane.

---

## 7. Reclassified: User Preferences as an Optional Extension

Subjective user feedback modeling is an external capability sitting above AcoustiForge.

```text
User Feedback (App / UI)
          │
          ▼
PreferenceObservation (Proposed Model)
          │
          ▼
UserPreferenceProfile (Proposed Model)
          │
          ▼ (External Preference Inference)
     DesignIntent (Proposed Concept)
          │
          ▼ (Intent Adapter)
OptimizationSpecification (Core Contract)
          │
          ▼
   AcoustiForge Core
```

AcoustiForge Core operates with complete independence whether user preference models exist or not.

---

## 8. Reclassified: Provenance as an Optional Observer Service

Reproducibility in AcoustiForge Core is fundamentally achieved by its **deterministic mathematical architecture** (pure functions, frozen immutable data objects, bit-exact repeatability under documented benchmark conditions).

AcoustiForge Core provides deterministic/reproducible computation under documented conditions; formal artifact identity, content hashing, and persistent provenance are proposed extension capabilities:

```text
AcoustiForge Core Pipeline Execution
  (Specification -> Optimizer -> Result -> ComputeGraph)
                    │
                    ▼ (Proposed ProvenanceObserverHook)
             ProvenanceRecord (Proposed)
  (Cryptographic hashes of inputs, trajectory, and compiled graph)
                    │
                    ▼
          External Audit Logger
```

AcoustiForge Core does not require a database, network connection, or provenance service to function.

---

## 9. Reclassified: Edge / Raspberry Pi as an Optional Deployment Target

Raspberry Pi and embedded SBCs are **Optional Deployment Targets**, not architectural prerequisites.

### 9.1 Target Hook Pattern
```text
AcoustiForge ComputeGraph
            │
            ▼ (Proposed ExecutionBackendHook)
            ├── Reference Engine (Python / NumPy — Native Core)
            ├── Embedded Linux / Raspberry Pi ALSA Service (Proposed)
            ├── C99 Header-Only Static Transpilation (Proposed Future Target)
            ├── ARM Cortex-M / CMSIS-DSP Target (Proposed Future Target)
            └── SHARC DSP Target (Proposed Future Target)
```

### 9.2 Realtime vs. Supervisory Process Separation
Process isolation (separating a realtime audio rendering thread from an asynchronous optimization thread) is an **optional deployment pattern** for live systems requiring dynamic re-tuning. The reference AcoustiForge library remains a clean, single-process Python package.

---

## 10. Reclassified: Multi-Position Optimization as an Optional Extension

Single-position acoustic optimization is fully complete, self-contained, and valid in Phase 4.

Multi-position spatial optimization is a **Proposed Optional Objective Extension**:

$$\mathcal{L}_{\text{multi}}(\mathbf{p}) = \sum_{m=1}^M w_m \cdot \mathcal{L}\left( H_{\text{total}}(f; \mathbf{p}), T(f), \text{band}_m \right)$$

* Spatial aggregation operates by evaluating the existing forward model across multiple validated `FrequencyResponseData` instances and summing the scalar losses.
* It does not require altering the frozen Phase 4 optimization solver.
* We make no unverified claims of global convexity; coordinate descent remains a deterministic bounded local search algorithm.

---

## 11. Vehicle / Cabin Stress Test as an Extension Consumer

The automotive cabin scenario demonstrates how complex external contexts interact with AcoustiForge through extension hooks without polluting the core:

* **Static Tuning (Calibration Hook):** Driver delays, crossover points, and cabin EQ are computed offline using standard core contracts.
* **Dynamic Road Noise (Context Hook):** Ambient cabin noise sensors provide noise floor telemetry via an external context hook, adjusting a tonal tilt offset on the target curve.
* **Safety Invariant:** Core `DriverProfile` transducer limits prevent road-noise compensation from demanding excursion beyond physical driver limits ($x_{\text{max}}$).

---

## 12. OOTB & Capability Ownership Audit (Reconciled)

| Capability | Ownership Classification | Boundary Description |
|---|---|---|
| **Acoustic Domain Math & Summation** | **BUILD / OWN (Core)** | Machine-precision complex forward model, biquad synthesis, phase summation. |
| **Deterministic Optimization** | **BUILD / OWN (Core)** | Bounded Coordinate Descent + Golden-Section Line Search. |
| **Typed ComputeGraph Runtime** | **BUILD / OWN (Core)** | Frozen DAG with Biquad, Gain, Delay, and Sum nodes. |
| **Domain Models & Validation** | **BUILD / OWN (Core)** | Immutable measurement and specification value objects. |
| **Audio I/O (ALSA / PortAudio)** | **HOOK / WRAP (Extension)** | External hardware audio interface wrappers. |
| **Measurement Microphones** | **HOOK / WRAP (Extension)** | External measurement acquisition tools. |
| **AI / LLM Intent Engines** | **HOOK / WRAP (Extension)** | External advisory intelligence services proposing `DesignIntent`. |
| **User Preference Tracking** | **HOOK / WRAP (Extension)** | External subjective feedback database. |
| **Provenance Logging** | **HOOK / WRAP (Extension)** | Optional audit trail observer. |
| **Embedded C99 Export** | **FUTURE EXTENSION TARGET (Extension)** | Proposed future static code generation from `ComputeGraph`. |

---

## 13. Master Architecture Diagram (Layered Extension Model)

```text
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                             OPTIONAL EXTERNAL LAYER                                  ║
║                                                                                      ║
║   AI Assistants        Room Sensors / Mics      User Feedback UI      Vehicle CAN    ║
║   (Intent Proposer)    (Spatial Measurements)   (Preference Model)    (Noise Telemetry)
╚══════════════════════════════════════════════════════════════════════════════════════╝
                                       │
                                       ▼ (Proposed Extension Hooks)
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                        OPTIONAL ADAPTER & CONTEXT LAYER                              │
│                                                                                      │
│   • IntentAdapterHook (Proposed)       • MeasurementProviderHook (Proposed)          │
│   • ContextStateHook (Proposed)        • PreferenceProviderHook (Proposed)           │
│   • ProvenanceObserverHook (Proposed)  • ExecutionBackendHook (Proposed)             │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼ (Translates to Core Contracts)
═══════════════════════════════════════╪════════════════════════════════════════════════
   STRICT VALIDATION BOUNDARY          │ Invariant & Bound Checking
═══════════════════════════════════════╪════════════════════════════════════════════════
                                       ▼
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                          ACOUSTIFORGE CORE (FROZEN)                                  ║
║                                                                                      ║
║   Domain Models:      FrequencyResponseData, DriverProfile, OptimizationSpec...      ║
║   Acoustic Math:      Machine-Precision Complex Summation H_total(f)                 ║
║   Optimizer:          Bounded Coordinate Descent + Golden-Section Line Search        ║
║   Graph Engine:       Frozen Typed ComputeGraph DAG (Delay -> Gain -> Biquads)       ║
║   Execution:          Deterministic Sample-Domain Float32 PCM Processing             ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
                                       │
                                       ▼ (Compiled Graph / Execution Output)
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                        OPTIONAL HARDWARE & DEPLOYMENT TARGETS                        │
│                                                                                      │
│   • Reference NumPy Engine (Native Core)      • Embedded Linux / Raspberry Pi SBC    │
│   • C99 Header-Only Export (Proposed Target)  • Multi-Channel I2S/TDM DAC Hardware   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Architectural Decision Records (ADRs — Reconciled)

### ADR-501: Optional High-Level DesignIntent Contract
* **Decision:** `DesignIntent` is an optional high-level semantic proposal contract. Direct construction of `OptimizationSpecification` remains the primary native workflow for AcoustiForge Core.
* **Rationale:** Preserves core simplicity while allowing AI and natural language applications to plug in cleanly through an optional adapter.

### ADR-502: Optional Concurrency & Process Separation Pattern
* **Decision:** Realtime audio process isolation is an optional deployment pattern for live embedded hardware systems. AcoustiForge Core remains an unencumbered, single-process Python library.
* **Rationale:** Embedded live adaptation benefits from process separation; core mathematical design and offline verification do not require IPC overhead.

### ADR-503: Decoupled Provenance Observer Pattern
* **Decision:** AcoustiForge Core provides deterministic/reproducible computation under documented benchmark conditions. Formal artifact identity, content hashing, and persistent provenance are proposed extension capabilities handled by an optional provenance observer without introducing mandatory database dependencies into Core.
* **Rationale:** Guarantees auditability when required, while maintaining zero external dependencies for standard core execution.

### ADR-504: Optional Multi-Position Objective Extension
* **Decision:** Multi-position optimization is an optional higher-level objective aggregation ($\sum w_m \mathcal{L}_m$) evaluating the core forward model across multiple spatial measurements. Single-position optimization remains fully supported and primary.
* **Rationale:** Extends spatial capability without modifying the frozen Phase 4 optimization kernel.

---

## 15. Decoupled Phase 5 Optional Extension Roadmap

Rather than an obligatory sequential waterfall, Phase 5 capabilities are structured as **independent, decoupled tracks**:

```text
Phase 5-0: Optional Extension-Hook Architecture & Discovery (FROZEN / COMPLETE)
    └── Defines clean extension boundaries around the frozen AcoustiForge Core.

Optional Independent Extension Tracks:

    Track A — Measurement & AcousticState Hooks
    └── Standardized interfaces for external multi-mic scanners and calibration ingest.

    Track B — DesignIntent & Intent Compiler
    └── Optional translation adapter from high-level intent goals to OptimizationSpecification.

    Track C — Multi-Position Spatial Optimization
    └── Optional multi-measurement objective aggregation engine (Σ w_i L_i).

    Track D — Cryptographic Provenance Observer
    └── Optional SHA-256 audit logger recording optimization trajectories and graph hashes.

    Track E — Embedded Edge Runtime Architecture
    └── Optional double-buffered parameter update and process isolation for live SBCs.

    Track F — Hardware Execution & C99 Transpilation
    └── Optional static C99 / fixed-point export of frozen ComputeGraphs.

    Track G — User Preference Modeling
    └── Optional subjective rating and A/B preference inference hooks.

    Track H — AI & Design Intelligence Integrations
    └── Optional advisory AI connectors proposing target curves and design intents.
```

**Key Independence Guarantee:**
* Track H (AI) does **not** depend on Track E (Raspberry Pi).
* Track E (Raspberry Pi) does **not** depend on Track H (AI).
* Track D (Provenance) does **not** depend on Track H (AI).
* Track C (Multi-Position) does **not** depend on Track H (AI).
* **AcoustiForge Core requires none of them.**

---

## 16. Epistemic Boundaries & Scientific Claims

In accordance with strict AcoustiForge engineering discipline:
* We do **NOT** claim global optimization convergence guarantees (coordinate descent is a deterministic bounded local search algorithm).
* We do **NOT** claim AI replaces empirical measurement or physical acoustic validation.
* We do **NOT** claim inverse room cancellation of non-minimum-phase reflections.
* We **DO** claim that AcoustiForge Core provides a proven, deterministic, self-contained acoustic control plane under documented benchmark conditions, and that Phase 5 establishes clean, optional extension hooks allowing external systems to safely interact with it without compromising its mathematical integrity.

---

## 17. Verification & Regression Evidence

* **Baseline Test Suite:** 434 passed in 2.10s
* **Post-Reconciliation Test Suite:** 434 passed in 2.11s
* **Failures:** 0
* **Errors:** 0
* **Warnings:** 0
* **Production Code Modified:** 0 files (`src/acoustiforge/*` untouched).
* **Phase 4 Contracts Modified:** 0 files.
* **External Dependencies Added:** 0 (Python standard library + NumPy only).

```powershell
pytest -q -W error
434 passed in 2.11s
```

---

## 18. Phase 5-0R Conclusion & Freeze

Phase 5-0R has successfully reconciled and frozen the Phase 5 architecture. AcoustiForge Core remains the independent, self-contained, deterministic acoustic engine. All adaptive, intelligent, contextual, and hardware-specific capabilities plug into it through **optional, validated extension hooks**.
