# AcoustiForge

**AcoustiForge** is a deterministic, contract-first computational acoustics and digital signal processing (DSP) platform. It provides mathematically authoritative acoustic optimization, frozen stateful compute graph compilation, low-latency PCM execution and capture abstractions, and an evidence-oriented runtime experience store with deterministic retrieval and analytics.

---

## 1. Architectural Principles

AcoustiForge is engineered around strict trust and determinism boundaries:

> **AI proposes. AcoustiForge validates and executes.**
> 
> **Runtime teaches the AI layer; runtime does not rewrite the acoustic Core.**
> 
> **The Experience Store is the historical evidence layer, NOT LLM memory.**
> 
> **Historical experience is advisory evidence, never an authoritative source of DSP parameters.**
> 
> **Temporal and solar context are explanatory variables, not measurements of human mood.**
> 
> **Behavioral engagement evidence must not be silently interpreted as satisfaction or psychological state.**

---

## 2. System Architecture

AcoustiForge provides two distinct, contract-governed pipelines with a defined physical measurement boundary: the **Deterministic DSP & Playback Execution Path** and the **Sequential Physical Measurement & Calibration Path**:

```text
                                USER / APPLICATION
                                       │
                                       ▼
                              Optional AI / Intent
                                       │
                                       ▼
                                 DesignIntent
                                       │
                                       ▼
                             VALIDATION FIREWALL
                                       │
                                       ▼
                          OptimizationSpecification
                                       │
                                       ▼
                          ┌────────────────────────┐
                          │   ACOUSTIFORGE CORE    │
                          │                        │
                          │ Acoustic Domain Models │
                          │ Acoustic Mathematics   │
                          │ Deterministic Optimizer│
                          │ Validation Firewall    │
                          └────────────┬───────────┘
                                       │
                                       ▼
                             OptimizationResult
                                       │
                                       ▼
                              Graph Compilation
                                       │
                                       ▼
                                 ComputeGraph (Frozen DAG)
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            │ [A] DSP PLAYBACK EXECUTION                          │ [B] MEASUREMENT & CAPTURE
            ▼                                                     ▼
     PCM Audio Execution                                Log-Sine Sweep Excitation
            │                                                     │
     ┌──────┴──────┐                                              ▼
     ▼             ▼                                    [AlsaExecutionBackend]
  Offline     Linux/ALSA                                (Playback to Speaker)
  Backend     (Playback)                                          │
                   │                                      (Physical Room Path)
                   │                                              │
                   │                                    [AlsaAudioCapture]
                   │                                    (Microphone Capture)
                   │                                              │
                   │                                              ▼
                   │                                    Farina Deconvolution
                   │                                              │
                   │                                              ▼
                   │                                    [ImpulseResponseData]
                   │                                              │
                   │                                              ▼
                   │                                      Reflection Gating
                   │                                              │
                   │                                              ▼
                   │                                    Microphone Calibration
                   │                                              │
                   │                                              ▼
                   │                                    [FrequencyResponseData]
                   │                                              │
                   └──────────────────────┬───────────────────────┘
                                          ▼
                                   Runtime Evidence
                                          │
                          ┌───────────────┼───────────────┐
                          ▼               ▼               ▼
                       Runtime        Temporal/        Engagement /
                       Metrics         Solar             Feedback
                          │               │               │
                          └───────────────┼───────────────┘
                                          ▼
                                   ExperienceStore (Append-Only JSONL)
                                          │
                          ┌───────────────┴───────────────┐
                          ▼                               ▼
                 ExperienceRetriever             ExperienceAnalytics
               (Structured Query Engine)        (Descriptive Summaries)
                          │                               │
                          └───────────────┬───────────────┘
                                          ▼
                                 Future AI Consumers
                              (Advisory Retrieval Context)
```

---

## 3. Core Acoustic Engine

The deterministic acoustic Core resides in `src/acoustiforge/domain/`, `src/acoustiforge/acoustic_math/`, and `src/acoustiforge/contracts/`. It represents the authoritative mathematical truth of the platform:

* **Acoustic Domain Models:** Immutable representations of complex frequency responses (`FrequencyResponseData`), impulse responses (`ImpulseResponseData`), transducer definitions (`DriverProfile`), enclosure models (`EnclosureModel`), and acoustic target curves (`AcousticTargetCurve`).
* **Acoustic Mathematics:** Minimum-phase Hilbert transforms, fractional delay interpolation, complex acoustic summation with phase interaction, Linkwitz-Riley (2nd/4th order) and Butterworth (2nd/4th order) biquad synthesis, and target curve metrics.
* **Deterministic Optimization:** Bounded coordinate descent combined with golden-section line search minimizing weighted acoustic SPL loss and group-delay error. The optimizer is strictly deterministic, dependency-free, and does not rely on opaque heuristic solvers.

---

## 4. Multi-Position Spatial Optimization (Track C)

Located in `src/acoustiforge/extensions/spatial_optimization.py`, the spatial optimization layer extends Core optimization across multiple measurement locations:

* **Multi-Position Contracts:** `SpatialMeasurementPosition`, `MultiPositionOptimizationSpecification`, and `MultiPositionOptimizationResult`.
* **Spatial Acoustic Weighting:** Evaluates complex acoustic summing across multiple listening positions with strictly normalized spatial weights ($\sum w_i = 1.0$).
* **Core Isolation:** Operates as an unprivileged extension layer, compiling results into canonical Core `OptimizationResult` structures without modifying Core math.

---

## 5. ComputeGraph & Stateful DSP Execution

Located in `src/acoustiforge/graph/` and `src/acoustiforge/builders/`:

* **ComputeGraph Lifecycle:** Explicit state-machine enforcement:
  $$\text{UNINITIALIZED} \longrightarrow \text{MUTABLE} \longrightarrow \text{FROZEN}$$
* **Stateful DSP Nodes:** Pure-math DSP node primitives including `BiquadFilterNode` (Direct Form II Transposed), `DelayNode` (circular ring-buffer delay), `GainNode` (scalar gain / phase inversion), and `PassThroughNode`.
* **Planar PCM Contract:** In-memory contiguous `float32` planar audio blocks (`PCMBlock`, `AudioMetadata`) guaranteeing block-continuity and memory state preservation.
* **Graph Compilation:** `compile_optimization_result_to_graph()` automatically maps synthesized biquad sections, delays, and branch gains into validated, immutable ComputeGraph topologies.

---

## 6. Audio Execution & Capture Subsystems

Located in `src/acoustiforge/execution/`:

* **`OfflineExecutionBackend`:** Synchronous, deterministic PCM block processing for simulation, automated testing, and offline rendering.
* **`LinuxExecutionBackend` / `AlsaExecutionBackend`:** Direct platform binding to Linux ALSA playback via Python `ctypes` and `libasound.so.2` (`snd_pcm_writei`) with automatic `-EPIPE` xrun recovery and zero third-party pip dependencies.
* **`AlsaAudioCapture`:** Linux ALSA audio recording engine (`snd_pcm_readi`) acquiring PCM from USB measurement microphones, performing hardware format conversion (Float32 / Int16 $\to$ Planar Float32 `PCMBlock`), and managing buffer overrun recovery.
* **Platform Status:** **Software Implemented & Native Linux Verified; Physical Hardware Validation Pending.** The native Linux ALSA userspace and library bindings are fully validated in live Linux environments (Debian Bookworm); physical Raspberry Pi / USB DAC playback and microphone calibration remain subject to the Phase 5-4C hardware validation gates (Gates A–E).

---

## 7. Acoustic Excitation & Measurement Pipeline

Located in `src/acoustiforge/acoustic_math/sweep.py`, `gating.py`, `calibration.py`, and `diagnostics.py`:

* **Logarithmic Sine Sweep Generator (`generate_log_sweep`):** Deterministic, Nyquist-bounded excitation signal generation with smooth cosine boundary tapers and configurable amplitude/duration.
* **Farina Inverse Filter & Deconvolution (`generate_inverse_sweep`, `deconvolve_sweep`):** Analytical $-6\text{ dB/octave}$ time-reversed inverse filter and linear FFT deconvolution to extract time-domain impulse responses ($IR$).
* **Reflection-Gated Measurement (`apply_reflection_gate`):** Isolates direct acoustic sound from room boundary reflections using configurable Hann, Tukey, and Half-Hann window tapers.
* **Microphone Calibration (`apply_microphone_calibration`):** Interpolates and subtracts laboratory microphone calibration files (`.cal`, `.txt`) across magnitude and phase.
* **Measurement Quality Diagnostics (`evaluate_measurement_quality`):** Evaluates SNR, low-frequency resolution limits, and reflection contamination notches.

---

## 8. AI DesignIntent Boundary

Located in `src/acoustiforge/intent/`:

The AI layer is an optional, provider-neutral boundary that translates natural language requests into high-level design intent:

```text
Natural Language / AI Query
            ↓
       DesignIntent
            ↓
  4-STAGE VALIDATION FIREWALL
  (Schema → Semantic → Acoustic Bounds → Presets)
            ↓
OptimizationSpecification / MultiPositionOptimizationSpecification
            ↓
    Deterministic Core
```

* **Intent Contracts:** `TargetCurveIntent`, `TonalBalanceIntent`, `CrossoverIntent`, `SpatialIntent`, `ConstraintIntent`, and `DesignIntent`.
* **Security & Isolation:** AI proposals are treated strictly as untrusted data. The AI layer cannot inject graph nodes, inject DSP filter coefficients, execute dynamic code, alter optimizer math, or access audio hardware handles.
* **Zero AI Dependencies:** The Core and Intent layers require zero LLM SDKs (no OpenAI, Anthropic, or LangChain dependencies).

---

## 9. Runtime Experience & Engagement Store

Located in `src/acoustiforge/experience/`:

Captures complete runtime episodes into an immutable, versioned historical evidence layer (`schema_version="1.1.0"`):

$$\text{Intent} \to \text{Specification} \to \text{Optimization} \to \text{Graph} \to \text{Execution} \to \text{Observations} \to \text{Temporal Context} \to \text{Engagement} \to \text{Feedback} \to \text{Outcome}$$

* **`ExperienceRecord`:** Top-level immutable dataclass with lossless JSON/JSONL serialization.
* **`ExperienceStore`:** Local-first, append-only JSONL storage engine with a fail-closed schema validation firewall on append and read.
* **`ExperienceCollector`:** Non-intrusive builder assembling pipeline runs without mutating Core or execution objects.
* **Segregated Subsystems:**
  * **Observed Telemetry:** Raw execution timings, buffer counts, and xruns.
  * **Derived Metrics:** Post-hoc calculations (`derived_realtime_margin`, `derived_throughput_samples_per_sec`).
  * **Temporal & Solar Context (`TemporalSolarContext`):** Relative diurnal features (`minutes_since_sunrise`, `minutes_until_sunset`, `daylight_fraction`, `day_phase`). **Strictly non-psychological; no mood inference.**
  * **Engagement Evidence (`EngagementMetrics`):** Behavioral telemetry (`listening_duration_s`, `replay_count`), explicit user ratings (`explicit_engagement_rating`), derived scores (`derived_engagement_score`), and session trajectory events (`ExperienceEvent`).
  * **Human Feedback (`HumanFeedback`):** Explicit subjective ratings (1.0–5.0) and qualitative notes.

---

## 10. Experience Retrieval & Descriptive Analytics

Located in `src/acoustiforge/experience/retrieval.py` and `src/acoustiforge/experience/analytics.py`:

* **`ExperienceRetriever`:** Multi-criteria structured query engine (`ExperienceQuery`) supporting conjunctive filtering across acoustic specifications, optimization losses, execution backends, platforms, engagement ratings, completion states, and diurnal day phases.
* **Deterministic Hierarchical Ranking:**
  1. Outcome Quality Tier (`SUCCESS` $\to$ `PARTIAL` $\to$ `UNKNOWN` $\to$ `REJECTED` $\to$ `FAILED`)
  2. Explicit Human Rating (highest rating first; unrated last)
  3. Acoustic Proximity ($|f_{\text{selected}} - f_{\text{target}}|$ ascending, if target frequency specified)
  4. Final Optimization Loss (`final_loss_db` ascending)
  5. Stable Immutable Tie-Breaker (`experience_id` lexicographical order)
* **`ExperienceAnalytics`:** Transparent descriptive statistical engine providing aggregations (`OptimizationAnalyticsSummary`, `EngagementAnalyticsSummary`, `RuntimeAnalyticsSummary`, `ExperienceAnalyticsSummary`) and multi-dimensional groupings (`group_by_crossover_family`, `group_by_day_phase`, `group_by_evidence_type`, `group_by_platform`).
* **Zero Vector DB / ML:** Pure deterministic Python stdlib logic without opaque vector databases, embeddings, or neural heuristics.

---

## 11. Evidence & Trust Hierarchy

AcoustiForge strictly isolates evidence classes:

| Evidence Tier | Definition | Examples |
|---|---|---|
| `SOFTWARE_OFFLINE` | Synthetic audio processing in memory. | `OfflineExecutionBackend` test sweeps. |
| `PHYSICAL_HARDWARE` | Live execution on platform hardware. | `AlsaExecutionBackend` on Linux ALSA targets. |
| `HYBRID_SIMULATION` | Mixed physical measurements + simulation. | Multi-position synthetic spatial optimization. |

### Data Categorization

* **Observed:** Directly measured execution facts (block durations, xruns, sample counts).
* **Explicit User-Reported:** Subjective ratings and qualitative feedback directly provided by the user.
* **Derived:** Post-hoc mathematical calculations (realtime margins, throughput).
* **AI Inference:** Hypothetical proposals or synthesized intents (untrusted advisory data).
* **Historical Precedent:** Validated records retrieved from the Experience Store.

---

## 12. Validation Matrix & Current Status

| Subsystem | Phase | Status |
|---|---|---|
| Canonical PCM Contract & Node Primitives | Phase 0–2D | **Frozen / Validated** |
| Acoustic Domain Models & Validation | Phase 3A–3B | **Frozen / Validated** |
| Measurement Ingestion & Diagnostics | Phase 4A–4C | **Frozen / Validated** |
| Deterministic Multi-Way Optimization & Graph Compilation | Phase 4D | **Frozen / Validated** |
| Multi-Position Spatial Optimization (Track C) | Phase 5-1 | **Frozen / Validated** |
| Linux / SBC Execution Abstraction | Phase 5-3 | **Frozen / Validated** |
| Linux ALSA Hardware Backend (Playback) | Phase 5-4 | **Native Linux Verified, Physical Hardware Pending** |
| AI DesignIntent Integration | Phase 5-5 | **Implemented / Validated** |
| Runtime Experience & Engagement Boundary | Phase 5-6 | **Implemented / Validated** |
| Experience Intelligence Discovery | Phase 5-7 | **Discovery Complete** |
| Experience Retrieval & Analytics | Phase 5-7A | **Implemented / Validated** |
| Sweep Generation & ALSA Capture (Unit B+C) | Phase 5-4C | **Implemented in Software / Verified in Simulation** |
| Physical Hardware Validation Gates (Gates A–E) | Phase 5-4C | **Pending Physical Hardware Execution** |
| Retrieval-Augmented Generation (RAG) | Phase 5-7B+ | **Deferred** |
| Preference Learning / ML Models | Future | **Deferred** |

---

## 13. Current Validation Snapshot

* **Latest Verified Regression:** `528 passed, 2 skipped, 0 failures, 0 errors, 0 warnings` under `pytest -q -W error`.
* **Core Mutation:** ZERO.
* **Track C Mutation:** ZERO.
* **Intent Mutation:** ZERO.
* **Experience Mutation:** ZERO.
* **New Third-Party Dependencies:** ZERO.

---

## 14. Repository Structure

```text
E:\AcoustiForge\
├── docs/
│   └── architecture/                     # Architectural specifications and phase reports
│       ├── CURRENT_ARCHITECTURE_STATUS.md
│       ├── COMMERCIALIZATION_READINESS_ASSESSMENT.md
│       ├── PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md
│       ├── PHASE_5_1_TRACK_C_MULTI_POSITION_IMPLEMENTATION.md
│       ├── PHASE_5_3_LINUX_SBC_EXECUTION_HOOK_IMPLEMENTATION.md
│       ├── PHASE_5_4_LINUX_ALSA_HARDWARE_BACKEND.md
│       ├── PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md
│       ├── PHASE_5_4C_UNIT_BC_IMPLEMENTATION.md
│       ├── PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md
│       ├── PHASE_5_6_RUNTIME_EXPERIENCE_BOUNDARY.md
│       ├── PHASE_5_7_EXPERIENCE_INTELLIGENCE_DISCOVERY.md
│       └── PHASE_5_7A_EXPERIENCE_RETRIEVAL_ANALYTICS.md
├── src/
│   └── acoustiforge/
│       ├── __init__.py
│       ├── domain/                       # Immutable acoustic value types & validation
│       ├── acoustic_math/                # Deterministic acoustic mathematics, optimization & sweep engine
│       │   ├── sweep.py                  # Log-sine sweep generator & Farina deconvolution
│       │   ├── gating.py                 # Reflection gating & windowing
│       │   ├── calibration.py            # Microphone calibration
│       │   └── optimization.py           # Coordinate descent optimizer
│       ├── graph/                        # Stateful DSP nodes & ComputeGraph DAG
│       ├── contracts/                    # PCM & audio stream contracts
│       ├── builders/                     # Pipeline & Crossover graph builders
│       ├── extensions/                   # Track C spatial optimization extension
│       │   └── spatial_optimization.py
│       ├── execution/                    # Platform execution abstractions & ALSA binding
│       │   ├── interface.py
│       │   ├── offline.py
│       │   ├── linux.py
│       │   └── alsa.py                   # Playback backend & AlsaAudioCapture engine
│       ├── intent/                       # AI DesignIntent boundary & validation firewall
│       │   ├── contracts.py
│       │   ├── provider.py
│       │   └── adapter.py
│       └── experience/                   # Experience Store, Retrieval & Analytics
│           ├── contracts.py              # Schema v1.1.0 ExperienceRecord & Engagement
│           ├── store.py                  # Local-first append-only JSONL store
│           ├── collector.py              # Pipeline episode assembly
│           ├── retrieval.py              # Multi-criteria search & deterministic ranking
│           └── analytics.py              # Transparent descriptive analytics
└── tests/                                # 528 unit & integration regression tests
```

---

## 15. Getting Started

### Prerequisites

* Python 3.12 or 3.13
* Standard development tooling (PowerShell or Bash)

### Installation (Development Mode)

```bash
# Clone the repository
git clone https://github.com/radaikalam-lab/AcoustiForge.git
cd AcoustiForge

# Install in editable mode with development dependencies
pip install -e .[dev]
```

### Running the Test Suite

Execute the full deterministic test suite with strict zero-warning enforcement:

```bash
pytest -q -W error
```

---

## 16. Architecture & Contract Documentation Map

| Document | Scope |
|---|---|
| [`CURRENT_ARCHITECTURE_STATUS.md`](docs/architecture/CURRENT_ARCHITECTURE_STATUS.md) | Single authoritative snapshot of current system capabilities, readiness, and physical validation gates. |
| [`COMMERCIALIZATION_READINESS_ASSESSMENT.md`](docs/architecture/COMMERCIALIZATION_READINESS_ASSESSMENT.md) | System-level commercialization gap audit across hardware, software, measurement, and deployment. |
| [`PHASE_5_4C_UNIT_BC_IMPLEMENTATION.md`](docs/architecture/PHASE_5_4C_UNIT_BC_IMPLEMENTATION.md) | Deterministic sweep generation, Farina deconvolution, and ALSA capture implementation report. |
| [`PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md`](docs/architecture/PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md) | Discovery protocol defining the 5-stage physical hardware validation gates (Gates A–E). |
| [`PHASE_5_4_LINUX_ALSA_HARDWARE_BACKEND.md`](docs/architecture/PHASE_5_4_LINUX_ALSA_HARDWARE_BACKEND.md) | Native Linux ALSA `libasound.so.2` ctypes playback integration. |
| [`PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md`](docs/architecture/PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md) | AI DesignIntent boundary and 4-stage validation firewall. |
| [`PHASE_5_6_RUNTIME_EXPERIENCE_BOUNDARY.md`](docs/architecture/PHASE_5_6_RUNTIME_EXPERIENCE_BOUNDARY.md) | Immutable ExperienceRecord, solar context, and engagement capture. |
| [`PHASE_5_7A_EXPERIENCE_RETRIEVAL_ANALYTICS.md`](docs/architecture/PHASE_5_7A_EXPERIENCE_RETRIEVAL_ANALYTICS.md) | Production ExperienceRetriever and ExperienceAnalytics implementation. |
| [`PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md`](docs/architecture/PHASE_4D_7_OPTIMIZER_COMPILATION_AND_FREEZE.md) | Multi-way optimization math and ComputeGraph freeze. |
| [`PHASE_5_1_TRACK_C_MULTI_POSITION_IMPLEMENTATION.md`](docs/architecture/PHASE_5_1_TRACK_C_MULTI_POSITION_IMPLEMENTATION.md) | Spatial multi-position acoustic optimization. |

---

## 17. Current Roadmap & Deferred Items

### Implemented & Validated in Software

* Deterministic acoustic domain modeling and biquad filter synthesis.
* Multi-way single- and multi-position spatial optimization.
* Frozen ComputeGraph compilation and stateful PCM block processing.
* Offline execution backend, native Linux ALSA playback, and ALSA audio capture.
* Deterministic logarithmic sine sweep generation and Farina deconvolution engine.
* End-to-end simulated physical measurement pipeline harness.
* AI DesignIntent translation with strict fail-closed validation firewall.
* Local append-only JSONL Experience Store with engagement and solar context.
* Gate A-S: Digital / Software ALSA playback, format negotiation, and lifecycle verification.

### Pending Physical Hardware Validation (Phase 5-4C)

* **Gate A-H — Physical ALSA Playback:** Physical verification of continuous streaming to physical USB DAC / audio interface on Linux host.
* **Gate B — Raw Acoustic Measurement:** Physical sweep playback and USB measurement microphone capture.
* **Gate C — Measurement Repeatability:** Verification of baseline repeatability ($\sigma < 0.3\text{ dB}$).
* **Gate D — Bounded DSP Execution:** Real-time hardware playback through active `ComputeGraph`.
* **Gate E — Re-Measurement & Causal Delta:** Quantifying physical acoustic improvement vs predicted response.

### Deferred Capabilities

* Retrieval-Augmented Generation (RAG) and prompt context formatting (`ExperiencePromptContext`).
* Dense vector databases and neural embeddings.
* Preference learning, supervised ranking models, and LLM fine-tuning.
* Calibrated ambient room environmental sensors (temperature, humidity, noise SPL).

---

## 18. Commercial & Design Philosophy

AcoustiForge is built for high-reliability embedded audio and computational acoustic productization. The software architecture strictly isolates non-deterministic components (AI proposals, external user feedback, environmental observations) from the authoritative mathematical Core.

AcoustiForge guarantees that all audio processed by the platform is mathematically bounded, physically safe, bit-exact across identical configurations, and 100% verifiable.
