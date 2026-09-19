# AcoustiForge Phase 2D: Entity / Action Architecture Discovery

**Project:** AcoustiForge  
**Architecture:** ACE — Acoustic Compute Engine  
**Phase:** 2D — Entity / Action Architecture Discovery  
**Status:** **DISCOVERY COMPLETE & ARCHITECTURAL ANALYSIS FROZEN**  
**Governing Authority:** `prompts/MASTER_PROMPT.md`, `docs/ARCHITECTURE.md`, `docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md`  

---

## 1. Executive Summary & Baseline

AcoustiForge has successfully completed Phase 0 through Phase 2B, establishing:
- **Canonical PCM Contract:** Formally validated planar `float32` audio tensor model (`PCMBlock`, `AudioMetadata`).
- **DSP Primitives:** Deterministic, stateful and stateless node implementations (`PassThroughNode`, `GainNode`, `DelayNode`, `BiquadNode`).
- **Sequential Composition:** Linear pipeline chaining (`SequentialPipeline`).
- **Typed Compute Graph:** Synchronous DAG dataflow execution engine (`ComputeGraph`, `Port`, `Edge`) with static topological scheduling, fan-out buffer safety, and latency skew detection.

**Baseline Test Verification:**
```text
pytest -q -W error
210 passed in 0.73s (0 failed, 0 errors, 0 warnings)
```

The objective of Phase 2D is an evidence-driven architectural investigation into whether AcoustiForge requires an **Entity / Action Model**, where it sits relative to the ACE execution engine, and what structural boundaries must govern its eventual introduction.

---

## 2. Governing Architecture & Current Layers

The current AcoustiForge architecture operates across four proven layers:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      CANONICAL PCM CONTRACT                             │
│       Planar (channels, frames), float32, AudioMetadata, C-contiguous   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         DSP NODE CONTRACT                               │
│     BaseProcessingNode: process(), configure(), reset(), latency_frames │
│     GainNode, DelayNode, BiquadNode, PassThroughNode                    │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    TYPED COMPUTE GRAPH (ACE DATAFLOW)                   │
│     ComputeGraph: DAG topology, Port, Edge, static topological schedule, │
│     zero-allocation per block, fan-out delivery, lifecycle (FROZEN)     │
└─────────────────────────────────────────────────────────────────────────┘
```

The Typed Compute Graph answers a single, precise architectural question:
> *"How do blocks of PCM audio move through mathematical processing nodes deterministically in real time?"*

It deliberately does not answer:
- *"What physical loudspeaker or microphone does this filter chain calibrate?"*
- *"How are filter coefficients computed from target frequency responses?"*
- *"What high-level acoustic policies or protection limits govern the system?"*
- *"How are parameter changes batched, audited, or orchestrated at runtime?"*

---

## 3. The Central Question: Why Entity / Action?

### 3.1 What is an "Entity"?
In computational acoustics and audio system engineering, an **Entity** is a domain object representing physical or logical acoustic components, including:
- **Acoustic Transducers:** Woofers, tweeters, subwoofers, microphones with physical parameters (Thiele-Small parameters: $F_s$, $Q_{ts}$, $V_{as}$, sensitivity, thermal time constants, excursion limit $X_{\text{max}}$).
- **Physical Environments:** Enclosures (sealed box volume $V_b$, ported tuning $F_b$), listening rooms (RT60 reverberation profile, boundary distances).
- **Acoustic Targets / Profiles:** Target frequency response curves, crossover target alignments (Linkwitz-Riley 4th order, Butterworth), room target curves (Harman, B&K).
- **Hardware Targets / Endpoints:** Embedded MCU targets, DAC/amplifier stage configurations, calibration tables.

### 3.2 What is an "Action"?
An **Action** is a discrete, declarative or procedural operation executed in the control or modeling plane, including:
- **Synthesis / Design Actions:** `SynthesizeBiquadFilter(target_curve, measurement_data) -> BiquadCoefficients`.
- **Calibration / Analysis Actions:** `MeasureImpulseResponse(input_sweep, recorded_pcm) -> AcousticProfile`.
- **Control Orchestration Actions:** `ApplyPreset(graph, preset_entity)`, `CrossfadeMute(graph, duration_ms)`, `SetVolume(graph, gain_db)`.
- **Deployment / Code Generation Actions:** `ExportStaticScheduleC(graph, target_mcu)`.

---

## 4. Hostile Analysis: 12 Central Inquiries

| # | Inquiry | Analysis & Evidence | Conclusion |
| :--- | :--- | :--- | :--- |
| **1** | **What problem does Entity/Action solve?** | Separates real-world acoustic domain modeling and control-plane command orchestration from real-time mathematical signal processing. | Solves domain representation & control orchestration. |
| **2** | **Does that problem already have an adequate solution in ACE?** | No. The current codebase only has DSP math (`BiquadNode`), data structures (`PCMBlock`), and graph dataflow (`ComputeGraph`). It possesses zero concepts of speakers, rooms, or calibration workflows. | Problem is unaddressed by current layers. |
| **3** | **Does the problem belong in the Compute Graph?** | **NO.** Injecting acoustic entity metadata or action dispatchers into `ComputeGraph` would violate single-responsibility, bloat real-time audio threads, and destroy embedded runtime neutrality. | Compute Graph MUST remain pure dataflow. |
| **4** | **Does it belong in the DSP node model?** | **NO.** DSP nodes must remain pure mathematical transforms ($y[n] = f(x[n], \theta)$). A `BiquadNode` should not know if it is a tweeter crossover or a room notch filter. | DSP nodes must remain domain-agnostic. |
| **5** | **Does it belong in application / control plane?** | **YES.** Entity and Action models belong strictly in the Control Plane / Acoustic Intelligence Layer *above* the Typed Compute Graph. | Sits in the Control/Intelligence Plane. |
| **6** | **Does Entity/Action introduce unnecessary abstraction?** | If implemented as a heavy generic framework (e.g. dynamic event bus, global entity registries, reflection engines), YES. If implemented as focused, strongly-typed domain dataclasses and pure functional transformers, NO. | Must be minimal, typed, and concrete. |
| **7** | **Does it improve ergonomics?** | Yes. Users configure high-level objects (`SpeakerSystem(woofer=..., tweeter=...)`) rather than manually wiring low-level biquad coefficient matrices and gain multipliers. | Substantially improves acoustic ergonomics. |
| **8** | **Does it improve extensibility?** | Yes. New acoustic drivers, enclosure types, and filter design algorithms can be added without modifying graph execution or DSP kernels. | Excellent architectural separation. |
| **9** | **Does it improve auditability & provenance?** | Yes. Capturing which measurement data and calibration action generated a specific DSP graph configuration enables reproducibility and traceability. | Provides clear acoustic provenance. |
| **10** | **Does it improve future automation?** | Yes. Automated calibration (e.g. Auto-EQ, thermal limit modeling, driver protection) requires querying transducer entities and applying corrective actions to the graph. | Critical enabler for acoustic intelligence. |
| **11** | **Does it create architectural coupling?** | High risk if bidirectional. The execution graph must NOT depend on Entities. Coupling must be strictly unidirectional: `Entity/Action` depends on and configures `ComputeGraph`, never vice-versa. | Requires strict unidirectional dependency. |
| **12** | **Is the model appropriate for ACE at all?** | Yes, as the *outer layer* of AcoustiForge (the "Acoustic Intelligence" layer envisioned in `docs/ARCHITECTURE.md`), while ACE Core remains the inner dataflow engine. | Appropriate for outer acoustic platform. |

---

## 5. Architectural Separation of Concerns

The architecture must strictly maintain two distinct planes:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│              CONTROL & ACOUSTIC INTELLIGENCE PLANE                      │
│                                                                         │
│   Entities (Domain Models):                                             │
│     - Transducer (woofer, tweeter, SPL curve, Thiele-Small, limits)     │
│     - Enclosure (sealed, vented, acoustic impedance)                    │
│     - Measurement (impulse response, frequency response, distortion)    │
│     - CalibrationProfile (target curves, EQ targets)                    │
│                                                                         │
│   Actions (Functional Procedures & Orchestration):                      │
│     - Filter Design: DesignLinkwitzRileyCrossover(freq) -> Coeffs       │
│     - Auto-EQ: FitParametricEQ(measurement, target) -> BiquadParams     │
│     - Orchestration: DeployProfileToGraph(graph, profile)               │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │  (One-way parameter configuration
                                     │   & declarative topology build)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    DATAFLOW & EXECUTION PLANE (ACE)                     │
│                                                                         │
│   ComputeGraph & Processing Nodes:                                      │
│     - Synchronous, deterministic, real-time audio block execution       │
│     - Zero knowledge of physical speakers, enclosures, or rooms         │
│     - Operates strictly on PCMBlock and numerical filter parameters     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Concrete Acoustic Scenarios

### Scenario A: Two-Way Active Crossover & Transducer Protection
1. **Entities:**
   - `TransducerEntity("Tweeter", f_res=1200 Hz, p_max_watts=20, sensitivity_db=90)`
   - `TransducerEntity("Woofer", f_res=45 Hz, p_max_watts=80, sensitivity_db=87)`
   - `CrossoverSpecification(type="LinkwitzRiley", order=4, frequency_hz=2400)`
2. **Action:**
   - `BuildTwoWayCrossoverGraph(spec, woofer, tweeter) -> ComputeGraph`
3. **Execution:**
   - The action calculates biquad coefficients for low-pass and high-pass filters, adds gain offset for sensitivity matching, instantiates `ComputeGraph`, connects edges, freezes the graph, and returns a ready-to-execute DAG.

### Scenario B: Room Calibration & Auto-EQ
1. **Entities:**
   - `MeasurementEntity(frequency_vector, magnitude_db, phase_rad)`
   - `TargetCurveEntity(type="HarmanInRoom", bass_boost_db=4.0, treble_tilt_db=-1.5)`
2. **Action:**
   - `SynthesizeRoomCorrectionFilters(measurement, target, max_bands=6) -> list[BiquadParameters]`
   - `UpdateGraphEqualizer(graph, biquad_params)` (invokes atomic parameter transactions on existing frozen graph nodes).

---

## 7. Explicit Anti-Patterns & Prohibitions

To prevent architectural decay, any future Entity/Action design MUST obey these rules:

1. **NO Entity / Action objects in the Real-Time DSP Loop:**
   Audio sample processing (`node.process()` and `graph.process()`) must remain pure numerical matrix math. No entity lookups, reflection, or dynamic action dispatches per block.
2. **NO Heavy Dynamic Registries or Event Buses:**
   Avoid heavyweight frameworks (`EntityRegistry`, `CommandBus`, `EventDispatcher`, runtime reflection). Prefer typed Python dataclasses, pure functions, and explicit orchestration.
3. **NO Bidirectional Coupling:**
   `ComputeGraph` and `BaseProcessingNode` MUST NEVER import or reference `Entity` or `Action` modules.
4. **Embedded Target Neutrality:**
   Actions that design filters or calibrate profiles run on the host/control machine (Python or offline tooling). The resulting parameters and static schedule are deployed to embedded targets as raw C arrays and integer tables.

---

## 8. Final Discovery Verdict

```
PHASE 2D VERDICT: ADOPT WITH RESTRICTIONS
```

### Recommendation:
1. **ADOPT** the concept of an **Acoustic Intelligence & Control Plane** (comprising Domain Entities and Calibration/Orchestration Actions) as the outer governing layer above ACE.
2. **RESTRICT** implementation to future dedicated phases (Phase 3+ Acoustic Profiling, Measurement, and Calibration).
3. **PRESERVE** the strict boundary: `ComputeGraph` (Phase 2B) is complete, self-contained, and completely decoupled from Entity/Action concepts.

---

## 9. Final Phase Status

```
PHASE 2D DISCOVERY: COMPLETE
PHASE 2D ARCHITECTURAL RECOMMENDATION: ADOPT WITH RESTRICTIONS (DEFERRED TO PHASE 3)
PHASE 2D PRODUCTION CODE CHANGES: NONE (0 FILES MODIFIED IN SRC/)
```
