# AcoustiForge — Phase 4 Architectural Discovery Report
## Discovery of Next Additive Capabilities, Ingestion Contracts & Vertical Slices

---

## 1. Executive Summary

With Phase 3C (*Acoustic Mathematics*) and Phase 3D (*Acoustic Graph Builders*) verified and frozen, AcoustiForge possesses a complete, deterministic, unidirectional pipeline:
$$\text{Phase 3B Domain Data} \longrightarrow \text{Phase 3C Acoustic Mathematics} \longrightarrow \text{Phase 3D Graph Builders} \longrightarrow \text{ComputeGraph} \longrightarrow \text{DSP Nodes} \longrightarrow \text{PCM Execution}$$

This discovery phase investigates:
> *"What is the next smallest architectural capability that creates a meaningful acoustic-system vertical slice without destabilizing the frozen compute, mathematical, and domain architecture?"*

**Core Discovery Finding:**
The current system can execute synthesis and graph translation, but currently relies on manually constructed in-memory domain models. The smallest, highest-leverage, non-breaking capability is **Measurement Ingestion & Calibration Preprocessing** (Candidate A & B) feeding into **Measurement-Driven Parametric EQ Graph Synthesis** (Candidate E).

This discovery explicitly recommends:
1. **Zero modifications to existing frozen layers** (Phase 3B domain, Phase 3C math, Phase 3D builders, and Phase 2B ComputeGraph remain 100% frozen).
2. **Zero runtime/hardware entanglements** (ingestion, calibration, and analysis remain offline control-plane operations outside the realtime PCM loop).
3. **Strict contract-first additive modules** (e.g. `acoustiforge.io` / `acoustiforge.calibration`) preserving the stdlib + NumPy dependency footprint.

---

## 2. Frozen Baseline

- **Phase 3B Domain Scope:** Frozen (`DriverProfile`, `EnclosureProfile`, `TransducerLimits`, `CrossoverSpecification`, `AcousticTargetCurve`, `FrequencyResponseData`, `ImpulseResponseData`).
- **Phase 3C Mathematics Scope:** Frozen (`synthesize_crossover_biquads`, `calculate_driver_alignment`, `calculate_sensitivity_gain`, `evaluate_target_curve`, `design_infrasonic_protection_filter`, `derive_protection_filter_for_driver`, `synthesize_parametric_eq`).
- **Phase 3D Graph Builders Scope:** Frozen (`CrossoverGraphBuilder`, `SystemTopologyBuilder`).
- **ACE Compute Plane:** Frozen (`ComputeGraph`, `BiquadNode`, `GainNode`, `DelayNode`, `PassThroughNode`).
- **Baseline Test Suite:** 279 passed in 0.98s (`pytest -q -W error`).

---

## 3. Current Architectural Boundary

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PASSIVE DOMAIN LAYER (Phase 3B - FROZEN)                │
│ Specifications, Profiles, Measurements, Constraints         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ACOUSTIC MATHEMATICS (Phase 3C - FROZEN)                 │
│ Closed-form Filter Synthesis, Alignment, Target Eval, EQ    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. GRAPH BUILDERS (Phase 3D - FROZEN)                       │
│ Deterministic Translation → Strict DAG Topology             │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ACE DATAFLOW / COMPUTE PLANE (Phase 2B - FROZEN)         │
│ ComputeGraph, Static Schedule, Single-Producer Ports        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. DSP / EXECUTION PLANE (Phase 0/1 - FROZEN)               │
│ DF-II-T Biquad, Scalar Gain, Delay, PCMBlock Execution      │
└─────────────────────────────────────────────────────────────┘
```

The dependency direction must remain strictly top-to-bottom. Upward dependencies are forbidden.

---

## 4. Candidate Next Capabilities

We investigated six candidate capability areas:

1. **Candidate A — Measurement Ingestion & Parsers:** Standardized text/CSV/FRD/REW measurement data parsing into `FrequencyResponseData` / `ImpulseResponseData`.
2. **Candidate B — Microphone Calibration:** Application of microphone calibration frequency response curves ($M_{\text{cal}}(f)$) to raw measurement data.
3. **Candidate C — Acoustic Response Analysis & Metrics:** Quantitative metric calculations (RMS deviation, $F_3$/$F_{10}$ bandwidth limits, spectral tilt, narrow-band resonance identification).
4. **Candidate D — Multi-Way & Complex System Synthesis:** Extension of graph builders to 3-way/4-way crossover topologies, subwoofers, and asymmetric acoustic filters.
5. **Candidate E — Measurement-Driven Parametric EQ Graph Builder:** An end-to-end vertical slice taking measured driver response, target curve, and budget $\to$ synthesized EQ $\to$ `ComputeGraph` inserting EQ stages into driver branches.
6. **Candidate F — Hardware Abstraction & Real-Time Audio I/O:** Sound card / ADC-DAC streaming loop (e.g. PyAudio / sounddevice / PortAudio).

---

## 5. Capability-by-Capability Analysis

| Candidate | User Problem Solved | Domain Layer | Math Layer | Builders Layer | ComputeGraph | Risk | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Ingestion** | Ingest real measurement files (.csv, .txt, .frd) without manual coding | REUSE | REUSE | REUSE | REUSE | **LOW** | **STRONG ADOPT** |
| **B. Calibration** | Correct for measurement microphone frequency aberrations | EXTEND | EXTEND | REUSE | REUSE | **LOW** | **STRONG ADOPT** |
| **C. Analysis** | Provide objective quantitative metrics on acoustic behavior | REUSE | EXTEND | REUSE | REUSE | **LOW** | **ADOPT** |
| **D. Multi-Way** | Support 3-way (Woofer/Mid/Tweeter) & Subwoofer systems | REUSE | REUSE | EXTEND | REUSE | **LOW** | **ADOPT** |
| **E. EQ Builder** | Automated measurement correction graph assembly | REUSE | REUSE | EXTEND | REUSE | **LOW** | **STRONG ADOPT** |
| **F. Hardware I/O** | Realtime microphone input & speaker playback | NEW | NEW | REUSE | EXTEND | **HIGH** | **DEFER** |

---

## 6. Detailed Capability Evaluation

### 6.1 Candidate A: Measurement Ingestion
- **Problem:** Users need to import measurement data from standard acoustic measurement tools (REW, CLIO, SoundEasy, ARTA, Klippel text/CSV exports) without writing manual Python array wrappers.
- **Domain Impact:** Pure reuse of `FrequencyResponseData` and `ImpulseResponseData`.
- **Math Impact:** Zero new DSP or math required.
- **Contract:** Strict formatting, header parsing, delimiter auto-detection, NaN/Inf rejection, strictly positive ascending frequencies, phase unwrapping/normalization.
- **Verification:** Golden raw text files with known output array values.

### 6.2 Candidate B: Microphone Calibration
- **Problem:** Measurement microphones have non-flat high-frequency or low-frequency responses documented in `.cal` / `.mic` calibration files.
- **Domain Impact:** Add immutable `MicrophoneCalibrationData` or reuse `FrequencyResponseData`.
- **Math Impact:** Deterministic complex/magnitude subtraction:
  $$M_{\text{corrected}}(f) = M_{\text{raw}}(f) - M_{\text{cal}}(f)$$
- **Verification:** Exact golden correction vectors.

### 6.3 Candidate C: Acoustic Response Analysis
- **Problem:** Automated evaluation of loudspeaker performance: passband ripple, $-3\text{ dB}$ / $-6\text{ dB}$ cutoff frequencies, mean sensitivity, spectral tilt, and resonance Q estimation.
- **Domain Impact:** Pure reuse of Phase 3B objects.
- **Math Impact:** Pure stateless functions in `acoustic_math/analysis.py`.
- **Verification:** Analytical responses (e.g. perfect 2nd-order Butterworth high-pass has known $f_{-3\text{dB}}$).

### 6.4 Candidate D: Multi-Way Graph Builders (3-Way / Subwoofer)
- **Problem:** 3-way systems require Bandpass (Midrange) synthesis: cascaded High-Pass ($f_{\text{c, low}}$) and Low-Pass ($f_{\text{c, high}}$) filters.
- **Domain Impact:** Pure reuse of Phase 3B specifications and driver profiles.
- **Builders Impact:** `MultiWayCrossoverGraphBuilder` (Woofer, Midrange, Tweeter, Subwoofer).
- **Verification:** 3-way LR-4 summation verification ($|H_{\text{LP}} + H_{\text{BP}} + H_{\text{HP}}| = 1.0$).

### 6.5 Candidate E: Measurement-Driven EQ Graph Integration
- **Problem:** Directly constructing a `ComputeGraph` containing both crossover filters and driver linearization parametric EQ biquad stages derived from measured data.
- **Domain Impact:** Pure reuse of `FrequencyResponseData`, `AcousticTargetCurve`, `EqualizerBudget`.
- **Builders Impact:** Add EQ biquad cascade (`f"{driver}.eq.{idx}"`) into branch topology.
- **Verification:** Correct topological insertion, parameter assignment, and execution.

### 6.6 Candidate F: Hardware Abstraction / Real-Time Execution
- **Problem:** Interfacing ACE with physical audio interfaces (ASIO, CoreAudio, ALSA, WASAPI) for live measurement and processing.
- **Risk Assessment:** **HIGH RISK**. Introduces OS audio drivers, thread scheduling, buffer underruns, non-deterministic latency, C library bindings (PortAudio), and platform-specific behavior.
- **Verdict:** **DEFER**. AcoustiForge's strength is pure deterministic computational acoustics. Physical streaming should only be considered after all offline control-plane capabilities are proven.

---

## 7. Existing Contract Reuse

| Module | Existing Status | Phase 4 Utilization |
| :--- | :--- | :--- |
| `FrequencyResponseData` | Phase 3B Frozen | Reused directly as canonical measurement output |
| `ImpulseResponseData` | Phase 3B Frozen | Reused directly for time-domain impulse measurements |
| `AcousticTargetCurve` | Phase 3B Frozen | Reused for target error evaluation |
| `EqualizerBudget` | Phase 3B Frozen | Reused for EQ parameter constraints |
| `DriverProfile` / `EnclosureProfile` | Phase 3B Frozen | Reused for system definitions |
| `BiquadCoefficients` / `BiquadNode` | Phase 1B / 2B Frozen | Reused for all filter stages |
| `ComputeGraph` | Phase 2B Frozen | Reused without modification as execution DAG |

---

## 8. Required New Contracts

If Phase 4 focuses on Ingestion, Calibration, and Multi-Way Graph Composition, the following narrow contracts would be established:

1. **Measurement File Ingestion Contract (`MEASUREMENT_INGESTION_CONTRACT.md`):**
   - Supported formats: Space/Tab/Comma-delimited ASCII, standard REW text exports, FRD format.
   - Column order detection: (Frequency, Magnitude, Optional Phase).
   - Frequency validation: Strictly positive ($f > 0$), strictly ascending, finite, non-empty.
   - Magnitude validation: Finite dB SPL values.
2. **Microphone Calibration Contract (`MICROPHONE_CALIBRATION_CONTRACT.md`):**
   - Format: Frequency vs sensitivity offset (dB).
   - Interpolation: Log-frequency linear interpolation matching `evaluate_target_curve`.
   - Application: Subtraction of calibration curve from raw response.
3. **Multi-Way Graph Builder Contract (`MULTIWAY_GRAPH_BUILDER_CONTRACT.md`):**
   - Bandpass midrange biquad cascading.
   - Deterministic naming: `f"{driver}.crossover.lp.{i}"` and `f"{driver}.crossover.hp.{i}"`.

---

## 9. Layering & Dependency Audit

Dependency hierarchy remains strictly unidirectional:

```
          ┌────────────────────────────┐
          │      Ingestion / I/O       │
          └─────────────┬──────────────┘
                        │
                        ▼
          ┌────────────────────────────┐
          │     Domain Value Types     │
          └─────────────┬──────────────┘
                        │
                        ▼
          ┌────────────────────────────┐
          │    Acoustic Mathematics    │
          └─────────────┬──────────────┘
                        │
                        ▼
          ┌────────────────────────────┐
          │       Graph Builders       │
          └─────────────┬──────────────┘
                        │
                        ▼
          ┌────────────────────────────┐
          │   ComputeGraph / Nodes     │
          └────────────────────────────┘
```

- **Zero upward dependencies.**
- **Zero dependencies from `ComputeGraph` or `nodes` on ingestion or domain layers.**
- **Zero new external dependencies:** Standard library (`csv`, `io`, `pathlib`) + `numpy`.

---

## 10. Runtime, Persistence, and Entity/Action Impact

- **Runtime Impact:** None. Ingestion, calibration, and graph construction occur offline during graph setup. Once frozen, `ComputeGraph.process()` executes at full compiled C/NumPy speed.
- **Persistence Impact:** None. Standard file read operations consume filesystem files directly into in-memory immutable domain objects without databases or ORMs.
- **Entity/Action Impact:** Zero justification for an Entity/Action framework. Pure function transformations (`text_file -> FrequencyResponseData`, `math(measurement, target) -> result`, `builder(results) -> ComputeGraph`) remain simpler, faster, and 100% testable.

---

## 11. Minimal Vertical Slice Options for Phase 4

### Option 1 (Recommended): Measurement-to-Linearized-Graph Vertical Slice
$$\text{Raw Measurement File (.frd / .csv)} \xrightarrow{\text{Ingestion}} \text{Raw FRD} \xrightarrow{\text{Calibration}} \text{Calibrated FRD} \xrightarrow{\text{EQ Math}} \text{EQ Results} \xrightarrow{\text{3D Builder}} \text{ComputeGraph}$$
- **Why:** Delivers a complete real-world workflow from raw measurement data to calibrated, equalized PCM DSP execution.
- **Risk:** LOW.
- **Footprint:** stdlib + NumPy only.

### Option 2: 3-Way Loudspeaker System Vertical Slice
$$\text{Low/High Crossover Specs} + 3 \times \text{Driver Profiles} \xrightarrow{\text{3C Math}} \text{LP/BP/HP Results} \xrightarrow{\text{3-Way Builder}} \text{ComputeGraph (Woofer/Mid/Tweeter)}$$
- **Why:** Extends the 2-way vertical slice to 3-way and 4-way systems.
- **Risk:** LOW.

---

## 12. Deferred Capabilities

The following remain explicitly deferred:
- **Hardware audio driver integration (ASIO/WASAPI/PortAudio).**
- **Nonlinear loudspeaker modeling (excursion limit simulation, thermal compression).**
- **Complex boundary element / finite element room modeling (BEM/FEM).**
- **Machine learning / AI optimization.**
- **GUI / Visualization plotting packages (Matplotlib/Qt).**

---

## 13. Phase 4 Entry Criteria

Before Phase 4 implementation begins:
1. Formally freeze Phase 3C + 3D closure (COMPLETE in commit `31e5414`).
2. Finalize normative `MEASUREMENT_INGESTION_CONTRACT.md` and `CALIBRATION_CONTRACT.md`.
3. Provide version-controlled golden reference measurement files (.frd, .csv, .cal) with frozen expected numerical values.
4. Establish independent test suite for parsers, error handling, calibration application, and graph integration.
5. Guarantee 0 warnings under `pytest -q -W error`.

---

## 14. Discovery Verdict

```
PHASE 4 ARCHITECTURAL DISCOVERY: COMPLETE
PHASE 4 IMPLEMENTATION STATUS: DISCOVERY ONLY — NO IMPLEMENTATION

RECOMMENDED NEXT PHASE:
  PHASE 4A — MEASUREMENT INGESTION, CALIBRATION & MEASUREMENT-DRIVEN GRAPH SYNTHESIS
```
