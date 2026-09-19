# AcoustiForge Phase 3A: Acoustic Domain Model Discovery
## Domain Objects, Acoustic Operations & Control-Plane Boundary

**Project:** AcoustiForge  
**Architecture:** ACE — Acoustic Compute Engine  
**Phase:** 3A — Acoustic Domain Model Discovery  
**Status:** **DISCOVERY COMPLETE & DOMAIN MODEL SPECIFIED**  
**Governing Authority:** `prompts/MASTER_PROMPT.md`, `docs/ARCHITECTURE.md`, `docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md`, `docs/phases/PHASE_2D_ENTITY_ACTION_ARCHITECTURE_DISCOVERY.md`  

---

## 1. Executive Summary & Baseline

AcoustiForge has successfully established:
- **Phase 0 & 0.1:** Canonical PCM Contract (`PCMBlock`, `AudioMetadata`) and runtime-neutral architecture.
- **Phase 1A–1E:** DSP Node contracts, mathematical foundations, and sequential composition (`PassThroughNode`, `GainNode`, `DelayNode`, `BiquadNode`, `SequentialPipeline`).
- **Phase 2A–2B:** Typed Compute Graph (`ComputeGraph`, `Port`, `Edge`) with static topological scheduling, fan-out delivery, and DAG validation.
- **Phase 2D:** Entity / Action Architecture Discovery, which established the necessity of an **Acoustic Intelligence / Control Plane** *above* the compute engine while prohibiting generic, dynamic entity-action frameworks in the core.

**Baseline Verification:**
```text
pytest -q -W error
210 passed in 0.71s (0 failed, 0 errors, 0 warnings)
```

The objective of Phase 3A is to discover the **minimum, concrete acoustic domain vocabulary and operations** required to translate real-world physical acoustic knowledge into valid, deterministic AcoustiForge `ComputeGraph` configurations.

---

## 2. Methodology: Problem-Driven Discovery

Rather than starting from abstract object-oriented patterns ("Entity", "Action", "CommandBus"), this discovery begins from concrete physical acoustic problems encountered in loudspeaker engineering, room calibration, transducer protection, and active multi-way crossover design:

$$\text{Physical Acoustic Problem} \xrightarrow{\text{Required Data}} \text{Domain Object} \xrightarrow{\text{Synthesis Operation}} \text{ComputeGraph Configuration} \xrightarrow{\text{Deterministic Execution}} \text{PCM Output}$$

---

## 3. Analysis of Real-World Acoustic Problems

### 3.1 Problem 1: Active Multi-Way Crossover & Transducer Alignment

#### Physical Reality:
- Loudspeaker drivers (woofers, midranges, tweeters) operate efficiently over restricted bandwidths.
- Different drivers have unequal acoustic sensitivities (e.g., Tweeter = 91 dB SPL @ 1W/1m, Woofer = 86 dB SPL @ 1W/1m).
- Driver voice-coils are physically offset in depth on the speaker baffle, introducing acoustic path-length differences ($\Delta d = 15\text{ mm} \implies \Delta t \approx 43.7\ \mu\text{s}$).

#### Required Domain Information:
1. Crossover topology: Filter family (Linkwitz-Riley, Butterworth), order ($N=2, 4, 8$), crossover corner frequencies ($f_c$).
2. Driver physical attributes: Nominal passband, sensitivity offset ($\Delta G\text{ dB}$), acoustic center depth offset ($\Delta d\text{ mm}$), polarity reversal.

#### Required Domain Objects:
- `CrossoverSpecification`:
  - `family`: `LinkwitzRiley` | `Butterworth`
  - `order`: `2` | `4` | `8`
  - `frequency_hz`: `float`
- `DriverProfile`:
  - `name`: `str`
  - `role`: `WOOFER` | `MIDRANGE` | `TWEETER` | `SUBWOOFER`
  - `sensitivity_db`: `float`
  - `depth_offset_mm`: `float`
  - `polarity_inverted`: `bool`

#### Required Acoustic Operation:
- `synthesize_crossover_graph(spec: CrossoverSpecification, drivers: Sequence[DriverProfile], sample_rate: int) -> ComputeGraph`
  1. Computes cascaded 2nd-order Biquad filter coefficients for low-pass and high-pass sections.
  2. Calculates required inter-driver delay frames:
     $$D = \left\lfloor \frac{\Delta d}{c_{\text{sound}}} \cdot f_s \right\rceil$$
  3. Calculates sensitivity matching attenuation:
     $$G_{\text{trim}} = \min(\text{sensitivities}) - \text{sensitivity}_i$$
  4. Builds and freezes `ComputeGraph` with input fan-out into $N$ driver branches, each containing:
     $$\text{Input} \xrightarrow{\text{fan-out}} [\text{DelayNode}] \to [\text{GainNode}] \to [\text{BiquadNode Cascade}] \to \text{Driver Output}$$

---

### 3.2 Problem 2: Loudspeaker Frequency Response Equalization (Target Curve Matching)

#### Physical Reality:
- Driver frequency response on a baffle deviates from ideal due to baffle diffraction step (+6 dB boost in high frequencies), cone breakup resonances, and enclosure compliance.
- The acoustic goal is to match a target acoustic response (e.g., flat on-axis, Harman Target, diffuse field).

#### Required Domain Information:
1. Measured raw acoustic frequency response: array of discrete frequencies $f_k$, magnitude $M_k\text{ (dB SPL)}$, phase $\phi_k\text{ (rad)}$.
2. Acoustic target curve: target magnitude $T_k\text{ (dB SPL)}$ and tolerance envelope.
3. Parametric EQ budget: Maximum number of biquad bands $B_{\text{max}}$, max boost limit (e.g., $+6\text{ dB}$), allowable Q range ($0.5 \le Q \le 10$).

#### Required Domain Objects:
- `FrequencyResponseData`:
  - `frequencies_hz`: `np.ndarray` (strictly positive, monotonic)
  - `magnitude_db`: `np.ndarray`
  - `phase_rad`: `Optional[np.ndarray]`
- `AcousticTargetCurve`:
  - `name`: `str`
  - `points`: `tuple[tuple[float, float], ...]` (frequency, target dB)
- `EqualizerBudget`:
  - `max_bands`: `int`
  - `max_boost_db`: `float`
  - `max_cut_db`: `float`
  - `min_q`: `float`
  - `max_q`: `float`

#### Required Acoustic Operation:
- `fit_parametric_equalizer(measurement: FrequencyResponseData, target: AcousticTargetCurve, budget: EqualizerBudget, sample_rate: int) -> tuple[BiquadCoefficients, ...]`
  - Extracts error curve $E(f) = T(f) - M(f)$.
  - Performs iterative peak/notch fitting to synthesize an optimal cascade of 2nd-order Peaking and Shelving filters.

---

### 3.3 Problem 3: Transducer Infrasonic & Thermal Protection

#### Physical Reality:
- Vented/ported enclosures exhibit rapid acoustic unloading below the port tuning frequency $F_b$ (cone excursion increases exponentially, exceeding $X_{\text{max}}$).
- Excessive electrical RMS power causes voice-coil overheating and thermal destruction.

#### Required Domain Information:
1. Enclosure physical tuning frequency $F_b$ and box type (SEALED, VENTED, PASSIVE_RADIATOR).
2. Driver mechanical limits ($X_{\text{max}}$ in mm, resonance $F_s$, electrical resistance $R_e$).
3. Protection policy (infrasonic high-pass order, corner frequency).

#### Required Domain Objects:
- `EnclosureProfile`:
  - `enclosure_type`: `SEALED` | `VENTED` | `BANDPASS`
  - `tuning_frequency_hz`: `Optional[float]` ($F_b$)
  - `volume_liters`: `float` ($V_b$)
- `TransducerLimits`:
  - `x_max_mm`: `float`
  - `p_max_rms_watts`: `float`
  - `f_s_hz`: `float`
  - `r_e_ohms`: `float`

#### Required Acoustic Operation:
- `design_infrasonic_protection_filter(enclosure: EnclosureProfile, limits: TransducerLimits, sample_rate: int) -> BiquadCoefficients`
  - Generates a high-pass filter (e.g. 3rd-order Butterworth at $0.8 \cdot F_b$) preventing excursion damage.

---

### 3.4 Problem 4: Acoustic Measurement & Impulse Response Deconvolution

#### Physical Reality:
- Acoustic measurement requires generating an excitation stimulus (logarithmic sine sweep), recording the acoustic output via a calibrated microphone, deconvolving the system response, and time-gating reflections.

#### Required Domain Objects:
- `SineSweepSpecification`:
  - `start_frequency_hz`: `float`
  - `stop_frequency_hz`: `float`
  - `duration_seconds`: `float`
  - `sample_rate`: `int`
- `ImpulseResponseData`:
  - `samples`: `np.ndarray` (1D float32)
  - `sample_rate`: `int`
  - `peak_index`: `int` ($t=0$ arrival time)
- `MicrophoneCalibration`:
  - `sensitivity_mv_per_pa`: `float`
  - `calibration_curve`: `Optional[FrequencyResponseData]`

#### Required Acoustic Operations:
- `generate_log_sine_sweep(spec: SineSweepSpecification) -> tuple[PCMBlock, np.ndarray]` (returns sweep block and inverse filter array).
- `deconvolve_impulse_response(recorded_block: PCMBlock, inverse_filter: np.ndarray) -> ImpulseResponseData`.
- `window_impulse_response(ir: ImpulseResponseData, window_type: str, left_ms: float, right_ms: float) -> FrequencyResponseData`.

---

## 4. Formal Taxonomy of Acoustic Domain Elements

Based on the genuine engineering requirements identified above, the Acoustic Intelligence & Control Plane is partitioned into:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ACOUSTIC DOMAIN VOCABULARY (PHASE 3)                     │
│                                                                             │
│  1. VALUE OBJECTS (Immutable, Validated Domain Data):                       │
│     ├── FrequencyResponseData       (f, magnitude, phase)                   │
│     ├── ImpulseResponseData         (h[n], fs, t0)                          │
│     ├── DriverProfile               (role, sensitivity, offset, TS-params)  │
│     ├── EnclosureProfile            (type, volume, tuning Fb)               │
│     ├── TransducerLimits            (Xmax, Prms, Fs, Re)                    │
│     ├── AcousticTargetCurve         (frequency-target pairs)                │
│     ├── CrossoverSpecification      (family, order, fc)                     │
│     └── EqualizerBudget             (bands, max boost/cut, Q bounds)        │
│                                                                             │
│  2. DOMAIN OPERATIONS (Pure Functional Transformers & Synthesizers):        │
│     ├── synthesize_crossover_biquads() -> tuple[BiquadCoefficients, ...]    │
│     ├── calculate_alignment_delay()    -> int (frames)                      │
│     ├── fit_parametric_equalizer()     -> tuple[BiquadCoefficients, ...]    │
│     ├── design_infrasonic_filter()     -> BiquadCoefficients                │
│     ├── generate_log_sine_sweep()      -> tuple[PCMBlock, np.ndarray]       │
│     └── deconvolve_impulse_response()  -> ImpulseResponseData               │
│                                                                             │
│  3. GRAPH BUILDERS / FACTORIES (Control-to-Dataflow Orchestrators):         │
│     ├── CrossoverGraphBuilder          -> ComputeGraph                      │
│     ├── RoomCorrectionGraphBuilder     -> ComputeGraph                      │
│     └── SystemTopologyBuilder          -> ComputeGraph                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Architectural Boundary & Invariants

```text
┌─────────────────────────────────────────────────────────────────────────┐
│              ACOUSTIC INTELLIGENCE / CONTROL PLANE                      │
│                                                                         │
│   • Domain Value Objects (DriverProfile, EnclosureProfile, etc.)        │
│   • Acoustic Synthesis Operations (Filter design, Auto-EQ, Calibration) │
│   • Graph Builders (Constructs and configures ComputeGraph)             │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ (One-way declarative configuration)
                                     │  - Creates ComputeGraph
                                     │  - Adds nodes & edges
                                     │  - Freezes graph
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ACE DATAFLOW COMPUTE PLANE                           │
│                                                                         │
│   • ComputeGraph, Port, Edge, GraphLifecycle                            │
│   • BaseProcessingNode (GainNode, DelayNode, BiquadNode)                │
│   • PCMBlock, AudioMetadata                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### Invariants:
1. **Unidirectional Dependency:** The Acoustic Intelligence Plane depends on the ACE Compute Plane. The ACE Compute Plane (`src/acoustiforge/graph/`, `nodes/`, `contracts/`) **MUST NEVER** import or reference domain objects.
2. **Zero Runtime Overhead:** Real-time audio processing (`ComputeGraph.process()`) operates solely on `PCMBlock` without inspecting domain objects or invoking synthesis routines.
3. **Pure Value Objects:** Domain objects must be immutable, slot-based dataclasses with strict validation.
4. **No Heavy Framework Bloat:** Prohibit dynamic entity registries, event brokers, polymorphic command buses, and runtime reflection.

---

## 6. Recommendations & Implementation Roadmap

| Phase | Scope | Objective |
| :--- | :--- | :--- |
| **Phase 3A** | Discovery & Architectural Analysis | Reconcile acoustic problems, define domain value objects and synthesis operations. (**COMPLETE**) |
| **Phase 3B** | Domain Objects & Value Types | Implement strongly-typed acoustic dataclasses (`DriverProfile`, `CrossoverSpecification`, `FrequencyResponseData`, `EnclosureProfile`). |
| **Phase 3C** | Filter Synthesis & Crossover Operations | Implement pure filter synthesis operations (`synthesize_crossover_biquads`, alignment delay calculation). |
| **Phase 3D** | Acoustic Graph Builders & Verification | Implement `CrossoverGraphBuilder` and end-to-end multi-way acoustic system verification. |

---

## 7. Final Phase Status

```
PHASE 3A DOMAIN DISCOVERY: COMPLETE
PHASE 3A DOMAIN VOCABULARY: DEFINED
PHASE 3A CONTROL-PLANE BOUNDARY: FROZEN
PHASE 3A PRODUCTION CODE CHANGES: NONE (0 FILES MODIFIED IN SRC/)
```
