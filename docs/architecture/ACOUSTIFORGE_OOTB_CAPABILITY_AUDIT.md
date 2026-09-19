# AcoustiForge Whole-of-Forge OOTB Capability & Architecture Audit

**Document Identifier:** `ARCH-AUDIT-2026-01`  
**Classification:** ARCHITECTURAL DECISION & STRATEGY REPORT  
**Target Repository:** `E:\AcoustiForge`  
**Baseline Commit:** `0ea8243 Freeze Phase 4C measurement ingestion and diagnostics`  
**Working State:** Phase 4D-3 Verified (`404 passed, 0 failures, 0 errors, 0 warnings`)  

---

## 1. Executive Summary

### Strategic Question:
> *"For every significant capability in AcoustiForge, should we BUILD it ourselves, WRAP an external implementation, USE an existing OOTB capability, BUY a commercial capability, DEFER it, or potentially REMOVE/REPLACE our current implementation?"*

### Core Strategic Answer:
**AcoustiForge must fundamentally own the *semantic core*—the domain contracts, physical-acoustic invariants, deterministic data models, mathematical formulas, and DAG scheduling rules that define loudspeaker and audio system computation.** 

AcoustiForge must **not** reinvent commodity infrastructure: general-purpose numerical solvers, low-level audio device drivers, 2D/3D plotting engines, GUI widgets, or complex database engines.

### Key Audit Conclusions:
1. **Semantic Ownership vs. Implementation Ownership:** AcoustiForge defines the *normative contracts* and maintains a clean, zero-dependency, inspectable **Native Reference Implementation** (Python + NumPy). Performance acceleration (e.g., C/Rust SIMD, GPU, SciPy backends) and commodity facilities (plotting, audio hardware I/O, GUI) belong in clearly segregated adapter/plugin layers.
2. **Current Implementation Health (Phases 0–4D):** The existing codebase is exceptionally clean, disciplined, and strictly contract-driven. There is zero bloat or frivolous third-party dependency in the core engine.
3. **Overengineering Audit:** The custom standard-library WAV parser (`wave` + `struct`) and biquad mathematical formulas are appropriate as self-contained reference implementations. Plotting and hardware I/O were correctly kept out of the core compute engine.
4. **Backend Pluggability Strategy:** For Phase 4D optimization and future DSP scaling, maintain the pure-NumPy reference solver as the authoritative golden baseline, while designing the contract to allow optional pluggable accelerated backends (e.g., SciPy, NLopt, C++/Rust extensions) without altering domain semantics.

---

## 2. Current Forge Architecture

AcoustiForge is structured as a strictly layered, unidirectional, deterministic computation platform:

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CONTROL & ACOUSTIC INTELLIGENCE PLANE (Offline, Pure, Deterministic)   │
│                                                                         │
│  [Measurement I/O] (.frd, .cal, .wav, .txt) ──► acoustiforge.io         │
│          │                                                              │
│          ▼                                                              │
│  [Domain Models & Invariants] ───────────────► acoustiforge.domain      │
│          │                                                              │
│          ▼                                                              │
│  [Acoustic Mathematics & Optimization] ──────► acoustiforge.acoustic_math│
│          │                                                              │
│          ▼                                                              │
│  [System DAG Builders] ──────────────────────► acoustiforge.builders    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ compiles & freezes DAG
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ REALTIME / DATAFLOW EXECUTION PLANE (ACE - Acoustic Compute Engine)     │
│                                                                         │
│  [Typed ComputeGraph] ───────────────────────► acoustiforge.graph       │
│          │ (single-producer ports, static topological schedule)         │
│          ▼                                                              │
│  [DSP Processing Nodes] (DF2T Biquad, Gain, Delay) ──► acoustiforge.nodes│
│          │                                                              │
│          ▼                                                              │
│  [PCM Buffer Contracts & Execution] ─────────► acoustiforge.contracts,  │
│                                                acoustiforge.engine      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Layering Rules Enforced:
- `Domain` $\to$ `Acoustic Math` $\to$ `Builders` $\to$ `ComputeGraph` $\to$ `Nodes` $\to$ `Engine` $\to$ `PCM Contracts`.
- **Zero upward imports:** Lower execution planes never import or depend upon control-plane abstractions.
- **Zero non-stdlib / non-NumPy dependencies:** Scanned and verified by `tests/test_dependency_isolation.py`.

---

## 3. Whole-of-Forge Capability Inventory

```
+---------------------------------------------------------------------------------------------------+
| ACOUSTIFORGE CAPABILITY MAP                                                                       |
+===================================================================================================+
| A. DOMAIN & CONTRACTS                                                                             |
|    1. PCM & Buffer Contracts (PCMBlock, AudioMetadata, ChannelLayout, Planar Float32)            |
|    2. Measurement Domain Models (FrequencyResponseData, ImpulseResponseData)                      |
|    3. Transducer & Enclosure Models (DriverProfile, EnclosureProfile, TransducerLimits)           |
|    4. Filter & Optimization Specifications (CrossoverSpec, TargetCurve, EqualizerBudget, OptSpec) |
|    5. Normative Interface Contracts (11 Frozen Architectural Contracts)                           |
+---------------------------------------------------------------------------------------------------+
| B. ACOUSTIC MATHEMATICS                                                                           |
|    1. Biquad Filter Design & Coefficient Calculation (RBJ Audio EQ Cookbook Formulas)             |
|    2. Crossover Filter Synthesis (Butterworth & Linkwitz-Riley 2nd/4th/8th Order Analog->Bilinear)|
|    3. Sensitivity Matching & Delay Alignment Mathematics                                          |
|    4. Driver Protection High-Pass Filter Derivation                                               |
|    5. Greedy Single-Driver Parametric EQ Synthesis                                                |
|    6. Acoustic Metrics & Response Analysis (F3/F6/F10, Passband Ripple, Spectral Tilt, RMS Error)|
|    7. Fractional-Octave Response Smoothing (Log-Spaced Gaussian/Moving Average)                  |
|    8. Time-Domain Windowing & Reflection Gating (Tukey, Hann, Rectangular Window Synthesis)       |
|    9. Discrete Fourier Transform & Spectral Extraction (FFT -> Magnitude/Phase FRD)               |
|   10. Measurement Diagnostics (SNR Estimation, Comb Notch Detection, Gate Cutoff Validity)        |
|   11. Biquad Complex Frequency Response H(e^jω) Evaluation                                        |
|   12. Multi-Transducer Complex Acoustic Summation (Phasor Vector Superposition)                   |
|   13. Deterministic Loss & Optimization Primitives (Golden-Section 1D, Coordinate Descent, Grids) |
+---------------------------------------------------------------------------------------------------+
| C. GRAPH EXECUTION PLANE                                                                          |
|    1. Typed Ports, Shapes & Direction System (PortDirection, PortShape, PortType)                 |
|    2. Directed Acyclic Graph Scheduler (Cycle Detection, Topological Sort, Single Producer)      |
|    3. DSP Processing Nodes (Direct Form II Transposed Biquad, Gain, Delay, PassThrough)           |
|    4. Sequential Pipeline Composers                                                               |
|    5. Multi-Way Loudspeaker Graph Synthesis Builders (2-Way Crossover, 3-Way MultiWay, Stereo Sys) |
+---------------------------------------------------------------------------------------------------+
| D. I/O & PARSERS                                                                                  |
|    1. ASCII Measurement Ingestion (.frd, .cal, .csv, .txt)                                        |
|    2. Uncompressed PCM WAV File Ingestion (16/24/32-bit Integer and Float)                        |
|    3. Realtime Audio Device Streaming (PortAudio / ASIO / WASAPI) [DEFERRED]                      |
|    4. Project File Persistence & Serialization [DEFERRED]                                         |
+---------------------------------------------------------------------------------------------------+
| E. VISUALIZATION & UX                                                                             |
|    1. Response & Phase Curve Plotting (Matplotlib / Plotly) [DEFERRED]                            |
|    2. ComputeGraph Topology Visualizer [DEFERRED]                                                 |
|    3. Graphical User Interface (GUI) [DEFERRED]                                                   |
+---------------------------------------------------------------------------------------------------+
| F. ADVANCED PHYSICAL MODELING                                                                     |
|    1. 3D Room Acoustic Simulation & Boundary Elements (BEM/FEM) [DEFERRED]                        |
|    2. Non-linear Transducer Volterra / Large-Signal Modeling [DEFERRED]                           |
+---------------------------------------------------------------------------------------------------+
```

---

## 4. Market & OOTB Ecosystem Landscape

| Domain / Capability | Commercial / Industry Standard | Open-Source Alternatives | Standard Python Ecosystem |
| :--- | :--- | :--- | :--- |
| **Acoustic Measurement & Analysis** | REW (Room EQ Wizard), CLIO, SoundCheck, Klippel dB-Lab, APx500 | pyFar, OpenSoundMeter | `scipy.signal`, `librosa` |
| **Loudspeaker Crossover & System CAD** | VituixCAD, LEAP-5, LspCAD, SoundEasy, BassBox Pro | XSim, SpeakerSim | None (Custom scripts) |
| **DSP Audio Graph Engines** | Max/MSP, PureData, JUCE AudioProcessorGraph | Faust, Csound, SuperCollider | `pedalboard` (Spotify), `scipy.signal` |
| **Biquad & IIR Filter Synthesis** | MATLAB Signal Processing Toolbox | Faust math, biquad-rs | `scipy.signal.iirfilter`, `scipy.signal.bilinear` |
| **Numerical Optimization Solvers** | KNITRO, TOMLAB, Intel MKL | NLopt, Ipopt, Ceres Solver | `scipy.optimize` (`minimize`, `differential_evolution`) |
| **Audio I/O & Streaming Drivers** | ASIO SDK (Steinberg), JUCE AudioDeviceManager | PortAudio, RtAudio, ALSA, JACK | `sounddevice`, `pyaudio`, `miniaudio` |
| **Plotting & 2D/3D Visualization** | OriginPro, MATLAB Graphics | D3.js, Vega | `matplotlib`, `plotly`, `bokeh`, `pyqtgraph` |
| **GUI Frameworks** | JUCE GUI, Qt Commercial | Dear ImGui, Slint, Flutter | `PyQt6`, `PySide6`, `Tauri` + React/Electron |
| **3D Room Acoustic Simulation** | EASE, Odeon, CATT-Acoustic, COMSOL Multiphysics | PyRoomAcoustics, SoundSpaces | None (Specialized C/C++ packages) |

---

## 5. Whole-of-Forge Decision Matrix

| Capability ID | Capability Name | Current Implementation | External Alternative | Recommendation | Strategic Rationale | Key Risk |
| :--- | :--- | :--- | :--- | :---: | :--- | :--- |
| **CAP-01** | PCM Buffer Contracts & Planar Float32 | `src/acoustiforge/contracts/pcm.py` | NumPy ndarray / C pointers | **BUILD** *(Owned)* | Defines fundamental ABI and memory immutability for audio frames. | Minimal. Pure Python + NumPy. |
| **CAP-02** | Acoustic Domain Models (`FrequencyResponseData`, `DriverProfile`, etc.) | `src/acoustiforge/domain/` | `pyfar.FrequencyData`, custom dicts | **BUILD** *(Owned)* | Core domain identity. Validated immutable dataclasses provide type safety. | Domain model drift if unmaintained. |
| **CAP-03** | Biquad Filter Design Formulas | `src/acoustiforge/nodes/biquad.py` | `scipy.signal.iirfilter` | **BUILD (Ref)** *(Owned)* | Simple closed-form formulas (RBJ Cookbook). Zero dependency, bit-exact. | Mathematical errors (mitigated by goldens). |
| **CAP-04** | Crossover Filter Synthesis (Butterworth/Linkwitz-Riley) | `src/acoustiforge/acoustic_math/crossover.py` | MATLAB / `scipy.signal` | **BUILD (Ref)** *(Owned)* | Core loudspeaker design differentiator. Exact Q-factor tables and bilinear mapping. | Out-of-spec filter orders. |
| **CAP-05** | DSP Node Execution (DF2T Biquad, Delay, Gain) | `src/acoustiforge/nodes/` | JUCE DSP, C++ SIMD, CMSIS-DSP | **BUILD (Ref)** / **WRAP (Future)** | Native reference provides verified golden behavior; pluggable C/Rust SIMD for realtime scaling. | High Python loop overhead in multi-block processing. |
| **CAP-06** | Typed ComputeGraph DAG Engine | `src/acoustiforge/graph/` | JUCE Graph, TensorFlow DAG, NetworkX | **BUILD** *(Owned)* | Static single-producer topological compile with typed buffer ports is central to ACE. | Generalizing graph beyond audio DAGs. |
| **CAP-07** | Sensitivity & Acoustic Delay Alignment | `src/acoustiforge/acoustic_math/alignment.py`, `sensitivity.py` | VituixCAD algorithms | **BUILD** *(Owned)* | Acoustic intelligence logic tailored to driver profiles. | Simple heuristics failing on non-flat drivers. |
| **CAP-08** | Single-Driver Parametric EQ Synthesis | `src/acoustiforge/acoustic_math/equalizer.py` | REW AutoEQ, `scipy.optimize` | **BUILD (Ref)** *(Owned)* | Deterministic greedy peak/shelf fitting matching `EqualizerBudget`. | Non-optimal band allocation on complex dips. |
| **CAP-09** | Acoustic Metrics ($F_3/F_6/F_{10}$, Ripple, Tilt, RMS) | `src/acoustiforge/acoustic_math/metrics.py` | pyFar audio metrics | **BUILD** *(Owned)* | Normative quantitative evaluation criteria required by automated optimizers. | Ambiguous cutoff detection on resonant peaks. |
| **CAP-10** | Fractional-Octave Smoothing | `src/acoustiforge/acoustic_math/metrics.py` | `scipy.ndimage`, pyFar | **BUILD (Ref)** *(Owned)* | Pure NumPy log-Gaussian kernel convolution with zero external dependencies. | Edge-frequency truncation distortion. |
| **CAP-11** | Reflection Gating & Windowing (Tukey, Hann) | `src/acoustiforge/acoustic_math/gating.py` | `scipy.signal.windows` | **BUILD (Ref)** *(Owned)* | Exact sample-accurate direct-sound gating formulas in pure NumPy. | Heuristic gate placement errors. |
| **CAP-12** | FFT Spectral Transformation | `acoustiforge.acoustic_math.gating` | `numpy.fft.rfft`, FFTW, KissFFT | **WRAP** *(NumPy FFT)* | AcoustiForge defines the spectral contract; delegates discrete Fourier transform to `np.fft.rfft`. | Sample-rate / frequency bin scaling errors. |
| **CAP-13** | Measurement Quality Diagnostics (SNR, comb notches) | `src/acoustiforge/acoustic_math/diagnostics.py` | REW Measurement Info | **BUILD** *(Owned)* | Control-plane sanity checks protecting downstream synthesis from bad data. | Heuristic false positives on transducer breakups. |
| **CAP-14** | Multi-Way Loudspeaker Graph Synthesis Builders | `src/acoustiforge/builders/` | VituixCAD / custom scripts | **BUILD** *(Owned)* | Translates acoustic synthesis results into validated execution DAGs. | Combinatorial builder proliferation. |
| **CAP-15** | Biquad Complex Frequency Response $H(e^{j\omega})$ | `acoustiforge.acoustic_math.optimization` | `scipy.signal.freqz` | **BUILD (Ref)** *(Owned)* | Vectorized algebraic evaluation on unit circle in pure NumPy with zero SciPy. | Denominator numerical singularity. |
| **CAP-16** | Multi-Driver Complex Acoustic Summation | `acoustiforge.acoustic_math.optimization` | VituixCAD summation engine | **BUILD** *(Owned)* | The definitive physical-acoustic superposition model $H_{\text{total}} = \sum H_k$. | Out-of-phase destructive cancellations. |
| **CAP-17** | Deterministic Loss & Optimization Primitives | `acoustiforge.acoustic_math.optimization` | `scipy.optimize`, NLopt, Ceres | **BUILD (Ref)** / **WRAP (Future)** | Native 1D golden-section and coordinate descent guarantee 100% determinism. | Slower convergence on high-dimensional problems. |
| **CAP-18** | ASCII Measurement File Parser (`.frd`, `.cal`, `.txt`) | `src/acoustiforge/io/parser.py` | Pandas, NumPy `genfromtxt` | **BUILD** *(Owned)* | Robust, zero-dependency text stream parsing with flexible comment/delimiter detection. | Weird formatting edge cases. |
| **CAP-19** | WAV Impulse File Ingestion | `src/acoustiforge/io/impulse_parser.py` | `soundfile`, `scipy.io.wavfile` | **BUILD (Ref)** *(Stdlib `wave`)* | Uncompressed PCM (16/24/32-bit int & float) parsed cleanly using stdlib `wave` + `struct`. | Non-standard or compressed RIFF chunks. |
| **CAP-20** | Audio Device Hardware Capture (ASIO/WASAPI/ALSA) | None (Explicitly deferred) | `sounddevice`, PortAudio | **USE OOTB / WRAP (Plugin)** | Commodity streaming. Implement as an optional adapter plugin outside core engine. | Non-deterministic latency, driver crashes. |
| **CAP-21** | Plotting & Acoustic Curve Visualization | None (Explicitly deferred) | `matplotlib`, `plotly`, `pyqtgraph` | **USE OOTB (Plugin)** | Commodity 2D plotting. Keep strictly out of core compute engine; consume via visualization adapter. | Heavy dependency bloat if imported into core. |
| **CAP-22** | Graphical User Interface (GUI) | None (Explicitly deferred) | Qt/PySide6, Tauri + React | **USE OOTB / WRAP (App)** | Standalone desktop application consuming AcoustiForge headless API. | Complex state synchronization. |
| **CAP-23** | 3D Room Acoustic Boundary Simulation (BEM/FEM) | None (Explicitly deferred) | EASE, PyRoomAcoustics | **DEFER / BUY** | High development cost, specialized physics domain. Out of scope for core loudspeaker CAD. | Extreme scientific complexity and compute burden. |
| **CAP-24** | Non-Linear Transducer Simulation (Klippel Large-Signal)| None (Explicitly deferred) | Klippel dB-Lab, SpeaQA | **DEFER** | Niche, requires complex non-linear Volterra / laser measurement data. | Unprovable models without physical laser bench. |
| **CAP-25** | Project Persistence & State Serialization | None (Explicitly deferred) | `dataclasses` asdict, JSON/SQLite | **USE OOTB** | Standard JSON/YAML serialization of domain value objects. | Schema evolution across versions. |

---

## 6. The Semantic Core: What AcoustiForge Must Own

AcoustiForge must **never delegate the semantic definition** of:

1. **Acoustic Domain Value Types:** `FrequencyResponseData`, `ImpulseResponseData`, `DriverProfile`, `CrossoverSpecification`, `AcousticTargetCurve`, `OptimizationSpecification`.
2. **Normative Contracts:** The 11 formal contracts governing PCM buffers, node composition, DAG execution, measurement ingestion, calibration, gating, diagnostics, metrics, multiway synthesis, and optimization.
3. **Physical-Acoustic Summation Model:** The complex superposition equation governing multi-transducer interactions ($H_{\text{total}}(f) = \sum_k H_k(f)$) and its $-240\text{ dB}$ magnitude floor.
4. **Deterministic Tie-Breaking & Invariants:** Exact IEEE 754 float64 reproducibility rules, monotonic loss guarantees, and boundary validation.
5. **Static DAG Execution Schedule:** Deterministic, single-producer, topologically sorted execution graph guaranteeing multi-block streaming reproducibility.

---

## 7. The Commodity Layer: What AcoustiForge Should Delegate

AcoustiForge should **delegate or wrap** commodity operational components:

1. **Discrete Fourier Transform Kernel:** Delegated to `numpy.fft.rfft` (and potentially Intel MKL / PocketFFT under the hood).
2. **Standard File Format Containers:** Use stdlib `wave` for basic WAV; wrap `soundfile` / `libsndfile` only in optional peripheral I/O plugins for exotic audio formats.
3. **Audio Hardware Drivers:** Use `sounddevice` (PortAudio wrapper) in a dedicated realtime capture/playback adapter package; keep core engine 100% headless.
4. **Visualization & Graph Rendering:** Use `matplotlib` or `plotly` in external CLI/GUI consumer tools; core engine returns structured data objects, not bitmaps.
5. **High-Dimensional Numerical Solvers (Optional Scaling):** When multi-branch joint optimization expands to 50+ parameters, wrap `scipy.optimize` or `nlopt` as optional secondary acceleration backends while preserving the native coordinate descent solver as the golden reference.

---

## 8. Reference Implementation Strategy

AcoustiForge will maintain a **Native Reference Implementation** across all core algorithms:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ACOUSTIFORGE CONTRACT                                                  │
│   (Normative specification, domain types, invariants, golden vectors)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
┌──────────────────────────────────┐       ┌──────────────────────────────────┐
│ NATIVE REFERENCE IMPLEMENTATION  │       │ ACCELERATED / EXTERNAL BACKENDS  │
│ - Pure Python + NumPy            │       │ (Optional plugins)               │
│ - Zero external C-extensions     │       │ - C++/Rust SIMD DSP Nodes        │
│ - 100% deterministic & inspectable│      │ - SciPy / NLopt Solvers          │
│ - Authoritative test golden      │       │ - GPU / CuPy FFT & Summation     │
│ - Guaranteed portability         │       │ - Hardware PortAudio I/O         │
└──────────────────────────────────┘       └──────────────────────────────────┘
```

### Why the Native Reference Implementation Must Exist:
- **Auditability & Scientific Trust:** Acousticians and audio engineers can inspect the exact equations without navigating complex external C/C++ codebases.
- **Zero-Dependency Guarantee:** AcoustiForge core runs everywhere standard Python and NumPy exist (Windows, Linux, macOS, embedded Raspberry Pi, serverless containers).
- **Test Integrity:** Serves as the immutable standard against which accelerated backends are validated.

---

## 9. Pluggable Backend Architecture

For future performance scaling, AcoustiForge should adopt a backend adapter pattern:

```python
# Conceptual Backend Protocol
class OptimizationSolverBackend(Protocol):
    def solve(
        self,
        objective_func: Callable[[np.ndarray], float],
        bounds: Sequence[tuple[float, float]],
        initial_params: np.ndarray,
        spec: OptimizationSpecification,
    ) -> tuple[np.ndarray, float, bool, int]: ...
```

- **Default Backend:** `NativeCoordinateDescentSolver` (Pure NumPy, 100% deterministic, zero dependencies).
- **Optional Backend:** `SciPyMinimizeSolver` (Installed via `pip install acoustiforge[scipy]`, uses L-BFGS-B or Differential Evolution for fast exploration).

---

## 10. Phase-by-Phase Assessment (Phases 0–4D)

| Phase | Core Capability | Justification | Current Implementation | Verdict |
| :--- | :--- | :--- | :--- | :---: |
| **Phase 0** | PCM Contracts & Reference Buffer Pipeline | Establishes planar float32 memory layout and validation. | Pure NumPy (`PCMBlock`) | **RETAIN (BUILD)** |
| **Phase 1** | DSP Processing Nodes & Biquad Math | Implements Direct Form II Transposed biquad, delay, gain. | Pure NumPy / Native math | **RETAIN (BUILD)** |
| **Phase 2B** | Typed ComputeGraph DAG Engine | Deterministic single-producer scheduling with cycle detection. | Pure Python DAG compiler | **RETAIN (BUILD)** |
| **Phase 3B** | Acoustic Domain Value Objects | Immutable domain models for drivers, enclosures, targets, crossovers. | Python `@dataclass(frozen=True)` | **RETAIN (BUILD)** |
| **Phase 3C** | Acoustic Mathematics & Synthesis | Closed-form crossover, sensitivity, alignment, protection math. | Pure NumPy acoustic math | **RETAIN (BUILD)** |
| **Phase 3D** | Acoustic Graph Builders | Compiles 2-way system math into frozen execution graphs. | `CrossoverGraphBuilder` | **RETAIN (BUILD)** |
| **Phase 4A** | Measurement Ingestion & Calibration | Ingests `.frd` / `.cal` tables, applies microphone calibration. | Text parser + math | **RETAIN (BUILD)** |
| **Phase 4B** | Acoustic Metrics & 3-Way Synthesis | Quantitative metrics ($F_3$, ripple, tilt) and 3-way DAG builder. | Pure NumPy math + builders | **RETAIN (BUILD)** |
| **Phase 4C** | Impulse Ingestion, Gating & Diagnostics | WAV/ASCII IR parsing, Tukey/Hann gating, FFT, SNR diagnostics. | Stdlib `wave` + `numpy.fft` | **RETAIN (BUILD / WRAP)** |
| **Phase 4D** | Complex Summation & Optimization | Multi-driver complex superposition and deterministic optimization. | Pure NumPy coordinate descent | **RETAIN (BUILD)** |

---

## 11. Overengineering & Technical Debt Audit

1. **WAV File Parser (`src/acoustiforge/io/impulse_parser.py`):**
   - *Current State:* Implemented via standard-library `wave` and `struct` (supports 16/24/32-bit integer and 32-bit float PCM).
   - *Evaluation:* **Keep as is.** It is ~300 lines of robust code, requires zero third-party packages, and parses standard measurement WAV files effortlessly. Delegating to `soundfile` would introduce `libsndfile` C-library binary distribution complexity without adding tangible value for impulse response analysis.
2. **Coordinate Descent Optimizer (`src/acoustiforge/acoustic_math/optimization.py`):**
   - *Current State:* Pure-NumPy 1D golden-section line search and coordinate descent solver.
   - *Evaluation:* **Keep as the Native Reference Backend.** It guarantees bit-exact determinism, has zero SciPy dependency, and executes in $< 100\text{ ms}$ for 2-way and 3-way systems.
3. **Graph Builder Proliferation:**
   - *Current State:* `CrossoverGraphBuilder` (2-way), `ThreeWayGraphBuilder` (3-way), `SystemTopologyBuilder` (stereo composition).
   - *Evaluation:* **Acceptable for now; generalize in Phase 5.** In Phase 5, consider a unified `NWaySystemGraphBuilder` parameterized by branch count ($K \ge 1$) to eliminate separate classes for 2-way, 3-way, 4-way, etc.

---

## 12. Missing Strategic Capabilities (Roadmap Post-Phase 4D)

1. **Automated Multi-Branch Parametric EQ Allocation (Phase 5):**
   - Joint allocation of peaking and shelving EQ filters across multiple branches driven by multi-transducer complex residual error.
2. **Pluggable Visualizer & Plotting Adapters (`acoustiforge-vis`):**
   - Dedicated visualization module wrapping Matplotlib / Plotly to plot frequency response magnitude, phase, group delay, step response, and crossover branch summation.
3. **Realtime Audio Stream Driver (`acoustiforge-io-realtime`):**
   - Optional adapter wrapping `sounddevice` (PortAudio) for live swept-sine measurement capture and realtime multi-channel loudspeaker DSP playback.
4. **Project File Serialization / JSON Schema:**
   - Standardized project export/import schema allowing loudspeaker designs to be saved, loaded, and exchanged.

---

## 13. Proposed Future Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│ ACOUSTIFORGE CORE ENGINE (Zero External C-Dependencies / Stdlib + NumPy)│
│                                                                         │
│  [Domain & Value Objects] ───────────────► acoustiforge.domain          │
│  [Normative Interface Contracts] ────────► acoustiforge.contracts       │
│  [Acoustic Mathematics & Forward Model] ─► acoustiforge.acoustic_math   │
│  [Native Reference Optimization Solver] ─► acoustiforge.acoustic_math   │
│  [Graph Builders & DAG Compiler] ────────► acoustiforge.builders, graph │
│  [DSP Processing Nodes & PCM Engine] ────► acoustiforge.nodes, engine   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ Extensible Backend & Plugin Interfaces
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ OPTIONAL ECOSYSTEM PLUGINS & ADAPTERS (External Packages)               │
│                                                                         │
│  [acoustiforge-scipy]  ──► Optional SciPy Solver (Fast Differential Evo)│
│  [acoustiforge-vis]    ──► Matplotlib & Plotly Visualizer Exporters     │
│  [acoustiforge-audio]  ──► SoundDevice / PortAudio Live Stream Drivers  │
│  [acoustiforge-gui]    ──► Desktop CAD GUI Application (Tauri / PyQt)   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Decision Summary & Capability Counts

```text
AUDIT DECISION BREAKDOWN:

Total Capabilities Audited: 25

BUILD (Owned Native Reference Implementation): 18
  - CAP-01: PCM Buffer Contracts & Planar Float32
  - CAP-02: Acoustic Domain Models
  - CAP-03: Biquad Filter Design Formulas
  - CAP-04: Crossover Filter Synthesis
  - CAP-05: DSP Node Reference Execution
  - CAP-06: Typed ComputeGraph DAG Engine
  - CAP-07: Sensitivity & Delay Alignment
  - CAP-08: Single-Driver Parametric EQ Synthesis
  - CAP-09: Acoustic Metrics & Quantitative Analysis
  - CAP-10: Fractional-Octave Smoothing
  - CAP-11: Reflection Gating & Windowing
  - CAP-13: Measurement Quality Diagnostics
  - CAP-14: Multi-Way Graph Builders
  - CAP-15: Biquad Complex Frequency Response
  - CAP-16: Multi-Driver Complex Acoustic Summation
  - CAP-17: Deterministic Optimization Primitives (Reference Solver)
  - CAP-18: ASCII Measurement Ingestion
  - CAP-19: WAV Impulse File Ingestion

WRAP (Internal Delegation with Owned Contract): 2
  - CAP-12: FFT Spectral Transformation (Wraps numpy.fft.rfft)
  - CAP-20: Realtime Audio Device Streaming (Future Plugin wrapping sounddevice)

USE OOTB (Peripheral / Non-Core Delegation): 3
  - CAP-21: Plotting & Visualization (Matplotlib / Plotly)
  - CAP-22: Graphical User Interface (PySide6 / Tauri)
  - CAP-25: Project Persistence & Serialization (JSON / SQLite)

BUY (Commercial Off-The-Shelf Alternative): 0
  - (No commercial capability justified for core; AcoustiForge remains open, auditable, and self-contained).

DEFER (Deferred to Future Major Milestones): 2
  - CAP-23: 3D Room Acoustic Boundary Simulation (BEM/FEM)
  - CAP-24: Non-Linear Transducer Simulation (Klippel Large-Signal)

REMOVE / REPLACE (Redundant Custom Code): 0
  - (Zero existing custom code recommended for deletion; existing codebase is strictly contract-aligned).
```

---

## 15. Final Governing Principle

> **"AcoustiForge must own the scientific semantics, mathematical definitions, physical invariants, and execution contracts that make audio engineering trustworthy, reproducible, and verifiable. It must delegate commodity infrastructure, device drivers, plotting, and numerical acceleration to established external tools through clean, decoupled adapters."**
