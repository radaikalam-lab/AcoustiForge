# AcoustiForge — Phase 4B Architectural Discovery Report
## Measurement → Acoustic Intelligence Next Capability

---

## 1. Executive Summary

With Phase 4A (*Measurement Ingestion, Microphone Calibration, and Measurement-Driven EQ Integration*) verified and frozen at commit `a4fafa3` (301 passed, 0 failures, 0 errors, 0 warnings under `pytest -q -W error`), AcoustiForge has achieved a verified vertical slice connecting external measurement ASCII files (`.frd`, `.csv`, `.txt`, `.cal`) to parametric EQ synthesis, 2-way crossover graph assembly, and multi-block PCM stream execution.

Phase 4B discovery addresses the next architectural milestone:
> *"What is the next computational capability in the Acoustic Intelligence / Control Plane that delivers substantial system design value, maintains mathematical rigor and strict dependency isolation, and cleanly extends the frozen Phase 0–4A foundation without physical overreach or runtime entanglement?"*

### Key Discovery Conclusions:
1. **Primary Recommendation:** **Candidate B (Acoustic Response Analysis & Metrics)** paired closely with **Candidate C (Multi-Way 3-Way/N-Way Graph Synthesis)**. Specifically, Candidate B establishes closed-form, deterministic metric evaluations over `FrequencyResponseData` (such as $F_3$/$F_{10}$ cutoff bandwidths, passband ripple, RMS target error, spectral slope, and crossover-region coherence), providing the missing objective evaluation feedback loop needed before automated multi-way optimization.
2. **Impulse Response Ingestion (Candidate A):** Feasible via standard-library `wave` + NumPy FFT, but requires formalizing windowing (Tukey/Hann), gate window placement, and time-of-flight phase alignment contracts. Recommended as a dedicated follow-up ingestion phase once frequency-domain analysis is complete.
3. **Multi-Way System Optimization (Candidate D):** High value, but requires response metrics (Candidate B) and 3-way graph building (Candidate C) as analytical primitives before deterministic multi-branch budget allocation can be reliably performed.
4. **Strict Scope & Dependency Preservation:** All analysis, synthesis, and graph assembly remains strictly offline control-plane execution using only standard Python and NumPy. Hardware I/O (Candidate G), room simulation (Candidate F), and AI/ML optimization remain strictly deferred.

---

## 2. Frozen Baseline

The current baseline is permanently frozen across all prior layers:
- **Phase 0 (PCM Contract):** `PCMBlock`, `AudioMetadata`, `ChannelLayout`, float32 planar buffers, and non-blocking multi-block stream execution.
- **Phase 1 (DSP Compute Plane):** `BiquadNode` (Direct Form II Transposed), `GainNode`, `DelayNode`, `PassThroughNode`, and sequential composition.
- **Phase 2B (Typed ComputeGraph):** Directed acyclic graph execution, typed single-producer ports (`PortDirection`, `PortShape`, `PortType`), cycle detection, static topological scheduling, fan-out, and latency tracking.
- **Phase 3B (Acoustic Domain Model):** Immutable domain value objects (`DriverProfile`, `EnclosureProfile`, `TransducerLimits`, `CrossoverSpecification`, `AcousticTargetCurve`, `EqualizerBudget`, `FrequencyResponseData`, `ImpulseResponseData`).
- **Phase 3C (Acoustic Mathematics):** Closed-form synthesis for Butterworth/Linkwitz-Riley crossovers, delay alignment, sensitivity matching, target curve evaluation, driver protection derivation, and greedy parametric EQ synthesis.
- **Phase 3D (Acoustic Graph Builders):** `CrossoverGraphBuilder` (2-way mono crossover graph) and `SystemTopologyBuilder` (stereo 2-way composition).
- **Phase 4A (Measurement Pipeline):** IO parser (`parse_measurement_file`, `parse_measurement_text`), `MeasurementImportResult`, microphone calibration math (`apply_microphone_calibration`), and additive EQ graph builder insertion.
- **Verification Baseline:** 301 passed tests, 0 warnings under `pytest -q -W error`.

---

## 3. Current Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│ CONTROL / ACOUSTIC INTELLIGENCE PLANE (Offline, Deterministic)        │
│                                                                        │
│  [Measurement File] (.frd, .csv, .txt, .cal)                           │
│          │                                                             │
│          ▼ (acoustiforge.io)                                           │
│  [MeasurementImportResult] ──► [FrequencyResponseData (Raw)]           │
│                                           │                            │
│  [Microphone Calibration Curve] ──────────┼────────────────────────────┤
│                                           ▼ (acoustiforge.acoustic_math)│
│                            [FrequencyResponseData (Calibrated)]         │
│                                           │                            │
│  [AcousticTargetCurve] ───────────────────┼────────────────────────────┤
│  [EqualizerBudget]    ───────────────────┼────────────────────────────┤
│                                           ▼                            │
│                                [EQSynthesisResult]                     │
│                                           │                            │
│  [CrossoverSpecification] ────────────────┼────────────────────────────┤
│  [DriverAlignmentResult]  ────────────────┼────────────────────────────┤
│  [GainDesignResult]       ────────────────┼────────────────────────────┤
│  [ProtectionFilterResult] ────────────────┼────────────────────────────┤
│                                           ▼ (acoustiforge.builders)    │
│                              [CrossoverGraphBuilder]                   │
└───────────────────────────────────────────┬────────────────────────────┘
                                            │ produces frozen DAG
                                            ▼
┌────────────────────────────────────────────────────────────────────────┐
│ COMPUTE / REALTIME DATAFLOW PLANE (Frozen Phase 2B/1/0)                │
│                                                                        │
│                       [ComputeGraph (Frozen)]                          │
│                                   │                                    │
│       ┌───────────────────────────┴───────────────────────────┐        │
│       ▼                                                       ▼        │
│  [Woofer Branch]                                      [Tweeter Branch] │
│  [delay] → [gain] → [eq..] → [xo..] → [prot..]        [delay] → [gain] │
│                                                       → [eq..] → [xo..]│
│                                                                        │
│                 Input PCMBlock ──► Process ──► Output PCMBlocks        │
└────────────────────────────────────────────────────────────────────────┘
```

The dependency direction remains strictly one-way: Control/Intelligence Plane $\to$ Compute Plane $\to$ DSP Nodes $\to$ PCM.

---

## 4. Discovery Candidates (A–G Detailed Analysis)

### Candidate A: Impulse Response / Time-Domain Measurement Ingestion

1. **Purpose:** Ingest acoustic time-domain impulse response measurements (e.g. uncompressed 16/24/32-bit float/integer WAV files, raw ASCII IR text) and transform them into frequency-domain `FrequencyResponseData` via gated discrete Fourier analysis.
2. **User/System Value:** Enables processing raw measurement data directly from impulse-response capture tools without requiring third-party tools (like REW or CLIO) to pre-export frequency response text.
3. **Existing Reusable Components:** `ImpulseResponseData` (Phase 3B domain), `FrequencyResponseData`, `acoustiforge.io.result.MeasurementImportResult`.
4. **New Contracts Required:** `IMPULSE_RESPONSE_INGESTION_CONTRACT.md` (defining WAV/text decoding, time-window gating policies, FFT length and zero-padding, minimum phase extraction, and frequency vector derivation).
5. **New Domain Objects Required:** `WindowSpecification` (Tukey, Hann, Rectangular, Left/Right gate onset and duration in ms/samples).
6. **New Mathematical Operations Required:** Discrete window generation, gated FFT, magnitude/phase extraction ($20\log_{10}|H(f)|$, $\angle H(f)$), fractional-octave smoothing (1/3, 1/6, 1/12, 1/24 octave).
7. **Graph-Builder Impact:** None (offline ingestion).
8. **ComputeGraph Impact:** None.
9. **DSP Impact:** None.
10. **Dependency Impact:** Python standard library `wave` module + `numpy.fft`. No external packages required.
11. **Runtime Implications:** Offline control-plane execution only.
12. **Physical-Acoustic Assumptions:** Time-gating assumes reflection-free anechoic windowing; gate placement directly affects low-frequency resolution cutoff ($f_{\text{min}} \approx 1 / T_{\text{gate}}$).
13. **Testing Strategy:** Analytical impulse responses (Dirac delta, delayed delta, simple single-pole filter response) with independently computed FFT spectra.
14. **Golden-Vector Requirements:** Synthetic impulse responses with exact closed-form Fourier transform solutions.
15. **Scope Risk:** **MEDIUM** (WAV file parsing, gating heuristics, FFT resolution trade-offs).
16. **Architectural Risk:** **LOW** (strictly additive within `acoustiforge.io`).
17. **Recommended Sequencing:** Follow-up ingestion phase after frequency response analysis and multi-way synthesis.
- **Risk Classification:**
  - *Architectural Risk:* **LOW**
  - *Implementation Scope:* **MEDIUM**
  - *Dependency Risk:* **LOW** (stdlib `wave` + `np.fft`)
  - *Physical-Validation Risk:* **MEDIUM** (reflection gating boundaries)

---

### Candidate B: Acoustic Response Analysis & Metrics

1. **Purpose:** Provide pure, deterministic, closed-form mathematical analysis and quantitative acoustic metrics computed directly from `FrequencyResponseData` (and comparisons between responses or against `AcousticTargetCurve`).
2. **User/System Value:** Gives designers and automated algorithms objective metrics to evaluate driver behavior, measure enclosure tuning cutoff, quantify EQ error reduction, detect passband ripple, and verify crossover summation flatness.
3. **Existing Reusable Components:** `FrequencyResponseData`, `AcousticTargetCurve`, `acoustiforge.acoustic_math` package structure.
4. **New Contracts Required:** `ACOUSTIC_METRICS_CONTRACT.md` (defining exact analytical formulations for $F_3$, $F_6$, $F_{10}$ cutoffs, passband RMS error, maximum peak/dip deviation, spectral tilt, and band-limited response variance).
5. **New Domain Objects Required:** `AcousticMetricsResult` (immutable container for calculated metrics).
6. **New Mathematical Operations Required:**
   - Cutoff frequency detection ($F_3, F_6, F_{10}$ relative to passband reference sensitivity).
   - Passband average sensitivity calculation (energy-averaged or dB-averaged across specified band).
   - RMS and peak tracking error relative to target curve ($E_{\text{rms}} = \sqrt{\frac{1}{N}\sum (M(f_i) - T(f_i))^2}$).
   - Fractional-octave smoothing (deterministic log-spaced Gaussian or rectangular kernels).
   - Response ripple and spectral slope (linear regression of $M(f)$ vs $\log_2(f)$ in dB/octave).
7. **Graph-Builder Impact:** None (offline evaluation).
8. **ComputeGraph Impact:** None.
9. **DSP Impact:** None.
10. **Dependency Impact:** Zero new dependencies (pure NumPy array math).
11. **Runtime Implications:** Purely offline; executes in sub-millisecond time.
12. **Physical-Acoustic Assumptions:** Metrics evaluate discrete data points; $F_3$ detection assumes a monotonic rolloff region near the band edges.
13. **Testing Strategy:** Canonical mathematical curves (flat, idealized 2nd/4th order high-pass and low-pass responses, tilted lines, sinusoidal ripple) with hand-calculated golden numbers.
14. **Golden-Vector Requirements:** Analytical polynomials and filter curves with exact closed-form integrals and cutoffs.
15. **Scope Risk:** **LOW** (clear mathematical boundaries).
16. **Architectural Risk:** **LOW** (pure stateless functions in `acoustic_math/analysis.py`).
17. **Recommended Sequencing:** **HIGHEST PRIORITY** (immediate candidate for Phase 4B; needed by optimization and synthesis).
- **Risk Classification:**
  - *Architectural Risk:* **LOW**
  - *Implementation Scope:* **LOW**
  - *Dependency Risk:* **LOW** (pure NumPy)
  - *Physical-Validation Risk:* **LOW** (computational metrics over data)

---

### Candidate C: Multi-Way System Response Synthesis (3-Way & N-Way Graph Builders)

1. **Purpose:** Generalize acoustic graph construction from 2-way systems to 3-way (Woofer, Midrange, Tweeter), 4-way, and Subwoofer-augmented loudspeaker systems with bandpass midrange driver branches.
2. **User/System Value:** Allows engineering real-world 3-way and 2.1 systems where midrange drivers require cascaded high-pass and low-pass crossover filters, independent alignment delays, gains, protection filters, and EQ cascades.
3. **Existing Reusable Components:** `ComputeGraph`, `BiquadNode`, `GainNode`, `DelayNode`, `PassThroughNode`, `CrossoverSpecification`, `CrossoverSynthesisResult`, `DriverAlignmentResult`, `GainDesignResult`, `ProtectionFilterResult`, `EQSynthesisResult`.
4. **New Contracts Required:** `MULTIWAY_GRAPH_BUILDER_CONTRACT.md` (defining deterministic node naming for N-way branches, bandpass midrange composition, multi-crossover frequency validation, and port routing).
5. **New Domain Objects Required:** `MultiWaySpecification` or `SystemBranchSpecification` (declaring driver roles: SUBWOOFER, WOOFER, MIDRANGE, TWEETER, and crossover cutoffs $f_{\text{low}}, f_{\text{high}}$).
6. **New Mathematical Operations Required:** Bandpass crossover synthesis (composition of cascaded high-pass and low-pass crossover biquads for midrange channels).
7. **Graph-Builder Impact:** Introduces `MultiWayGraphBuilder` or extends `SystemTopologyBuilder` without touching the frozen `CrossoverGraphBuilder.build_2way_graph`.
8. **ComputeGraph Impact:** Zero (uses existing DAG execution, fan-out, and multi-output routing).
9. **DSP Impact:** Zero.
10. **Dependency Impact:** Zero.
11. **Runtime Implications:** Construct-time only; graph processes multi-channel PCM deterministically.
12. **Physical-Acoustic Assumptions:** Crossover frequencies must satisfy $f_{\text{crossover, 1}} < f_{\text{crossover, 2}} < \dots < f_{\text{nyquist}}$ with adequate driver bandwidth overlap.
13. **Testing Strategy:** Structural DAG topology validation, deterministic node ID validation (`midrange.crossover.hp.0`, `midrange.crossover.lp.0`, `midrange.eq.0`), schedule determinism, and multi-block PCM bit-exact verification.
14. **Golden-Vector Requirements:** Analytical filter topologies and known multi-channel PCM impulse responses.
15. **Scope Risk:** **LOW** (straightforward generalization of Phase 3D graph builder patterns).
16. **Architectural Risk:** **LOW** (additive builder layer; frozen layers untouched).
17. **Recommended Sequencing:** **HIGH PRIORITY** (logical companion to Candidate B for Phase 4B/4C).
- **Risk Classification:**
  - *Architectural Risk:* **LOW**
  - *Implementation Scope:* **LOW-MEDIUM**
  - *Dependency Risk:* **LOW**
  - *Physical-Validation Risk:* **LOW**

---

### Candidate D: Measurement-Driven Multi-Way System Optimization

1. **Purpose:** Deterministically optimize crossover frequencies, relative driver gains, alignment delays, and per-driver EQ budget allocations by evaluating the acoustic complex summation of measured driver responses against a system-level acoustic target curve.
2. **User/System Value:** Automates the iterative trial-and-error process of loudspeaker system voicing and crossover design using measured transducer data.
3. **Existing Reusable Components:** `FrequencyResponseData`, `AcousticTargetCurve`, `CrossoverSpecification`, `synthesize_crossover_biquads`, `calculate_driver_alignment`, `synthesize_parametric_eq`.
4. **New Contracts Required:** `MULTIWAY_OPTIMIZATION_CONTRACT.md` (defining objective cost function, bounded parameter space, deterministic grid/coordinate descent search, and constraint enforcement).
5. **New Domain Objects Required:** `MultiWayOptimizationTarget`, `OptimizationResult`.
6. **New Mathematical Operations Required:**
   - Multi-transducer acoustic complex summation: $H_{\text{total}}(f) = \sum_k H_{\text{driver}, k}(f) \cdot H_{\text{filter}, k}(f) \cdot e^{-j 2\pi f \tau_k}$.
   - Deterministic bounded search / gradient-free coordinate descent (using pure NumPy; no SciPy minimize).
   - Composite penalty formulation (tracking error + excursion/protection penalty + EQ budget penalty).
7. **Graph-Builder Impact:** Consumes optimization results to feed graph builders directly.
8. **ComputeGraph Impact:** None.
9. **DSP Impact:** None.
10. **Dependency Impact:** Requires careful pure-NumPy optimization implementation to avoid SciPy dependency.
11. **Runtime Implications:** Offline control-plane execution (can take 100ms–2s depending on grid density).
12. **Physical-Acoustic Assumptions:** Assumes linear acoustic superposition in the far field on-axis; does not account for off-axis directivity without multi-angle measurement data.
13. **Testing Strategy:** Synthetic transducers with known optimal crossover points and gain offsets; verify that optimizer converges to analytical minimum within strict tolerance.
14. **Golden-Vector Requirements:** Deterministic test cases with mathematically unique global optima.
15. **Scope Risk:** **MEDIUM-HIGH** (complexity of multi-parameter search, convergence guarantees, pure-NumPy optimization).
16. **Architectural Risk:** **MEDIUM** (requires rigorous mathematical bounding to avoid unbounded heuristic complexity).
17. **Recommended Sequencing:** Position after Response Analysis (Candidate B) and Multi-Way Builders (Candidate C).
- **Risk Classification:**
  - *Architectural Risk:* **MEDIUM**
  - *Implementation Scope:* **HIGH**
  - *Dependency Risk:* **MEDIUM** (pure-NumPy constraint requires bespoke bounded solvers)
  - *Physical-Validation Risk:* **MEDIUM** (on-axis summation vs spatial radiation)

---

### Candidate E: Dedicated Measurement Quality & Diagnostic Layer

1. **Purpose:** Perform automated diagnostic analysis on ingested `FrequencyResponseData` to identify measurement defects (e.g. low signal-to-noise ratio, room reflection comb-filtering notches, insufficient frequency span, clipping flat-tops, phase wrapping anomalies, non-physical phase slopes).
2. **User/System Value:** Protects downstream filter synthesis from fitting filters to measurement artifacts or room reflections rather than genuine transducer behavior.
3. **Existing Reusable Components:** `FrequencyResponseData`, `MeasurementImportResult`.
4. **New Contracts Required:** `MEASUREMENT_DIAGNOSTICS_CONTRACT.md` (defining threshold criteria, quality flags, and confidence masks).
5. **New Domain Objects Required:** `MeasurementQualityReport`, `QualityFlag` enum.
6. **New Mathematical Operations Required:** Local derivative analysis ($\frac{dM}{d\log f}$), sharp notch detection ($Q > 20$ dips indicative of interference rather than minimum-phase transducer response), high-frequency noise floor estimation.
7. **Graph-Builder Impact:** None.
8. **ComputeGraph Impact:** None.
9. **DSP Impact:** None.
10. **Dependency Impact:** Zero.
11. **Runtime Implications:** Offline.
12. **Physical-Acoustic Assumptions:** Distinguishing transducer breakup from room reflection comb filtering without time-domain impulse gating is inherently heuristic.
13. **Testing Strategy:** Synthetic frequency curves with injected noise, narrow reflection notches, and truncated bandwidths.
14. **Golden-Vector Requirements:** Curated measurement vectors with defined defect signatures.
15. **Scope Risk:** **LOW-MEDIUM**.
16. **Architectural Risk:** **LOW**.
17. **Recommended Sequencing:** Can be incorporated as a lightweight diagnostic utility alongside Candidate B.
- **Risk Classification:**
  - *Architectural Risk:* **LOW**
  - *Implementation Scope:* **LOW-MEDIUM**
  - *Dependency Risk:* **LOW**
  - *Physical-Validation Risk:* **MEDIUM** (heuristic distinction between room and transducer)

---

### Candidate F: Room / Environment Response Modeling

1. **Purpose:** Model room acoustic boundary interactions (modes, Schroeder frequency, boundary loading/boundary gain, multi-position spatial averaging) to synthesize low-frequency room correction filters.
2. **User/System Value:** Addresses room resonance peaks below 300 Hz.
3. **Existing Reusable Components:** `FrequencyResponseData`, `AcousticTargetCurve`, `synthesize_parametric_eq`.
4. **New Contracts Required:** `ROOM_ACOUSTICS_CONTRACT.md`.
5. **New Domain Objects Required:** `RoomDimensions`, `SpatialMeasurementSet`, `RoomCorrectionProfile`.
6. **New Mathematical Operations Required:** Modal density calculation, multi-point complex/power spatial averaging, steady-state target curve generation.
7. **Graph-Builder Impact:** Room EQ insertion at master input or per-channel input.
8. **ComputeGraph Impact:** None.
9. **DSP Impact:** None.
10. **Dependency Impact:** Zero.
11. **Runtime Implications:** Offline.
12. **Physical-Acoustic Assumptions:** Highly assumption-heavy (rectangular room geometry, uniform wall absorption, linear time-invariant wave propagation); high risk of over-promising physical accuracy without 3D spatial field validation.
13. **Testing Strategy:** Idealized rectangular enclosure Green's function modal vectors.
14. **Golden-Vector Requirements:** Analytical rectangular modal solutions.
15. **Scope Risk:** **HIGH**.
16. **Architectural Risk:** **HIGH** (prone to physical acoustic overreach and unprovable claims).
17. **Recommended Sequencing:** Defer until core transducer and multi-way intelligence is thoroughly mature.
- **Risk Classification:**
  - *Architectural Risk:* **HIGH**
  - *Implementation Scope:* **HIGH**
  - *Dependency Risk:* **LOW**
  - *Physical-Validation Risk:* **HIGH** (room geometry, boundary conditions, microphone positioning)

---

### Candidate G: Hardware & Real-Time Audio I/O

1. **Purpose:** Stream audio directly to/from soundcards, USB audio interfaces, ASIO, WASAPI, or ALSA drivers in real time.
2. **User/System Value:** Enables live microphone measurement acquisition and direct speaker playback.
3. **Existing Reusable Components:** `PCMBlock`, `ComputeGraph`.
4. **New Contracts Required:** `HARDWARE_AUDIO_IO_CONTRACT.md`.
5. **New Domain Objects Required:** `AudioDeviceDescriptor`, `StreamConfiguration`.
6. **New Mathematical Operations Required:** None (pure systems engineering/IO).
7. **Graph-Builder Impact:** None.
8. **ComputeGraph Impact:** Connects `ComputeGraph.process()` to a realtime callback thread.
9. **DSP Impact:** Realtime thread-safety constraints, buffer underflow/overflow handling.
10. **Dependency Impact:** **CRITICAL**. Requires `sounddevice`, `PyAudio`, `pyaudio`, `cffi`, or native OS bindings.
11. **Runtime Implications:** Non-deterministic realtime thread scheduling, hardware driver latency, platform-dependent audio stacks (Windows/Linux/macOS).
12. **Physical-Acoustic Assumptions:** Hardware gain calibration, loopback timing reference, ADC/DAC linearity.
13. **Testing Strategy:** Mock audio device drivers, loopback devices.
14. **Golden-Vector Requirements:** None.
15. **Scope Risk:** **HIGH** (OS-specific audio subsystem instability, threading, C-library bindings).
16. **Architectural Risk:** **HIGH** (violates current runtime neutrality and pure-Python dependency isolation).
17. **Recommended Sequencing:** **STRICTLY DEFERRED**. Belongs in an external runtime adapter application, not the core ACE engine.
- **Risk Classification:**
  - *Architectural Risk:* **HIGH**
  - *Implementation Scope:* **HIGH**
  - *Dependency Risk:* **HIGH** (external C-library wrappers)
  - *Physical-Validation Risk:* **HIGH** (hardware dependent)

---

## 5. Existing Capability Reuse Audit

| Component | Location | Current Status | Phase 4B Reusability |
| :--- | :--- | :--- | :--- |
| `PCMBlock`, `AudioMetadata` | `src/acoustiforge/contracts/` | Frozen (Phase 0) | **Reusable As-Is** |
| `BiquadNode`, `GainNode`, `DelayNode` | `src/acoustiforge/nodes/` | Frozen (Phase 1) | **Reusable As-Is** |
| `ComputeGraph`, `Edge`, `Port` | `src/acoustiforge/graph/` | Frozen (Phase 2B) | **Reusable As-Is** |
| `FrequencyResponseData` | `src/acoustiforge/domain/measurements.py` | Frozen (Phase 3B) | **Reusable As-Is** (core data carrier for all analysis) |
| `ImpulseResponseData` | `src/acoustiforge/domain/measurements.py` | Frozen (Phase 3B) | **Reusable As-Is** (ready for Candidate A) |
| `AcousticTargetCurve`, `EqualizerBudget` | `src/acoustiforge/domain/specifications.py` | Frozen (Phase 3B) | **Reusable As-Is** |
| `DriverProfile`, `EnclosureProfile` | `src/acoustiforge/domain/profiles.py` | Frozen (Phase 3B) | **Reusable As-Is** |
| `synthesize_crossover_biquads` | `src/acoustiforge/acoustic_math/crossover.py` | Frozen (Phase 3C) | **Reusable As-Is** |
| `calculate_driver_alignment` | `src/acoustiforge/acoustic_math/alignment.py` | Frozen (Phase 3C) | **Reusable As-Is** |
| `calculate_sensitivity_gain` | `src/acoustiforge/acoustic_math/sensitivity.py` | Frozen (Phase 3C) | **Reusable As-Is** |
| `evaluate_target_curve` | `src/acoustiforge/acoustic_math/target_curve.py` | Frozen (Phase 3C) | **Reusable As-Is** |
| `derive_protection_filter_for_driver` | `src/acoustiforge/acoustic_math/protection.py` | Frozen (Phase 3C) | **Reusable As-Is** |
| `synthesize_parametric_eq` | `src/acoustiforge/acoustic_math/equalizer.py` | Frozen (Phase 3C) | **Reusable As-Is** |
| `apply_microphone_calibration` | `src/acoustiforge/acoustic_math/calibration.py` | Frozen (Phase 4A) | **Reusable As-Is** |
| `CrossoverGraphBuilder` | `src/acoustiforge/builders/crossover_builder.py` | Frozen (Phase 4A) | **Reusable As-Is** |
| `SystemTopologyBuilder` | `src/acoustiforge/builders/system_builder.py` | Frozen (Phase 3D) | **Reusable with additive 3-way extension** |
| `io.parser`, `io.result` | `src/acoustiforge/io/` | Frozen (Phase 4A) | **Reusable As-Is** |

---

## 6. Candidate Contract Analysis

For the recommended Phase 4B vertical slice, two normative contracts are identified:

### 1. `ACOUSTIC_METRICS_CONTRACT.md` (`CONTRACT-ACOUSTIC-METRICS-01`)
- **Input:** `FrequencyResponseData`, optional `AcousticTargetCurve`, optional frequency band $[f_{\text{min}}, f_{\text{max}}]$.
- **Output:** Immutable `AcousticMetricsResult` containing:
  - `passband_sensitivity_db`: Energy-weighted mean SPL in reference band.
  - `f3_hz`, `f6_hz`, `f10_hz`: Cutoff frequencies where SPL drops by $3.0\text{ dB}$, $6.0\text{ dB}$, and $10.0\text{ dB}$ relative to passband reference.
  - `rms_target_error_db`: Root-mean-square tracking error against target curve.
  - `peak_positive_error_db`, `peak_negative_error_db`: Maximum peak and dip deviations.
  - `spectral_tilt_db_per_oct`: Linear regression slope in dB/octave over defined frequency span.
  - `passband_ripple_db`: Peak-to-peak deviation within the declared passband.
- **Invariants:**
  - Stateless, pure mathematical functions.
  - Frequency bounds must satisfy $0 < f_{\text{min}} < f_{\text{max}} \le f_{\text{highest}}$.
  - Deterministic tie-breaking and exact log10-frequency interpolation when cutoff falls between measurement bins.
  - Inputs remain 100% immutable.
- **Error Model:** Raises `InvalidParameterError` on non-positive or inverted frequency spans, non-finite data, or insufficient frequency resolution.
- **Dependency Direction:** `acoustiforge.acoustic_math.metrics` $\to$ `acoustiforge.domain.measurements`.

### 2. `MULTIWAY_GRAPH_BUILDER_CONTRACT.md` (`CONTRACT-MULTIWAY-BUILDER-01`)
- **Input:** Crossover synthesis results for multiple crossover boundaries (e.g. LF/MF cutoff and MF/HF cutoff), per-driver alignment results, gain results, equalizer results, and protection filter results.
- **Output:** Frozen, validated `ComputeGraph` executing an N-way loudspeaker topology.
- **Invariants:**
  - Backward compatibility: 2-way invocation reproduces Phase 3D/4A graph topology and bit-exact PCM output.
  - Midrange bandpass branch ordering:
    $$\text{input} \longrightarrow [\text{delay}] \longrightarrow [\text{gain}] \longrightarrow [\text{eq}\dots] \longrightarrow [\text{crossover.hp}\dots] \longrightarrow [\text{crossover.lp}\dots] \longrightarrow [\text{protection}\dots] \longrightarrow \text{output}$$
  - Deterministic node IDs: `f"{driver_name}.crossover.{hp|lp}.{idx}"`, `f"{driver_name}.eq.{idx}"`, `f"{driver_name}.delay"`, `f"{driver_name}.gain"`.
- **Error Model:** Raises `InvalidParameterError` on mismatched sample rates, overlapping/inverted crossover cutoff frequencies, or disconnected branches.

---

## 7. Domain Model Analysis

### Entity / Action Framework Check:
**Verdict: NOT AUTHORIZED.**
We strictly reaffirm that generic `Entity`, `Action`, `Command`, `Proposal`, and `Workflow` frameworks must NOT be introduced. All acoustic operations are modelled as pure, stateless deterministic functions returning strongly typed, immutable dataclass results.

### New Value Types for Phase 4B:
1. **`AcousticMetricsResult`** (Dataclass, frozen, slots):
   ```python
   @dataclass(frozen=True, slots=True)
   class AcousticMetricsResult:
       passband_sensitivity_db: float
       f3_hz: Optional[float]
       f6_hz: Optional[float]
       f10_hz: Optional[float]
       rms_target_error_db: Optional[float]
       peak_positive_error_db: Optional[float]
       peak_negative_error_db: Optional[float]
       spectral_tilt_db_per_oct: float
       passband_ripple_db: float
   ```
2. **`FractionalOctaveSmoothing`** (Enum / utility):
   `NONE`, `OCTAVE_1_3`, `OCTAVE_1_6`, `OCTAVE_1_12`, `OCTAVE_1_24`.

Zero modifications to existing frozen Phase 3B domain classes.

---

## 8. Numerical / Scientific Boundaries

| Operation | Input Units | Output Units | Interpolation Space | Numerical Tolerance | Mathematical Boundary |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Passband Sensitivity** | Frequency [Hz], SPL [dB] | SPL [dB] | $\log_{10}(f)$ linear power | $\pm 10^{-12}\text{ dB}$ | Energy average: $10 \log_{10}\left(\frac{1}{\Delta \log f}\int 10^{M(f)/10} d\log f\right)$ |
| **$F_3 / F_6 / F_{10}$ Cutoff** | Frequency [Hz], SPL [dB] | Frequency [Hz] | $\log_{10}(f)$ linear interpolation | $\pm 10^{-6}\text{ Hz}$ | Exact crossing point $M(f) = M_{\text{ref}} - \Delta\text{dB}$ |
| **RMS Target Error** | Frequency [Hz], SPL [dB] | Error [dB] | $\log_{10}(f)$ discrete grid | $\pm 10^{-12}\text{ dB}$ | $\sqrt{\frac{1}{N}\sum (M(f_i) - T(f_i))^2}$ |
| **Spectral Tilt** | Frequency [Hz], SPL [dB] | Slope [dB/oct] | $\log_2(f)$ linear regression | $\pm 10^{-12}\text{ dB/oct}$ | Ordinary least squares slope of $M(f)$ vs $\log_2(f)$ |
| **Bandpass Crossover** | Specification (LR/BW, order) | Cascaded BiquadCoefficients | Bilinear transform (pre-warped) | $\pm 10^{-14}$ | Poles on unit circle, stable $|z_p| < 1$ |

### Explicit Scientific Boundary Declaration:
- Computational metrics evaluate properties of the **measured data set**.
- They do **NOT** validate physical acoustic qualities (e.g. microphone acoustic shadow, room boundary boundary reflection interference, non-linear distortion, voice-coil thermal compression, or 3D polar radiation).
- All reports and documentation must maintain this clear boundary.

---

## 9. Runtime Boundary

- **Offline Control Plane:** All response metric calculations, fractional-octave smoothing, regression slopes, and crossover synthesis execute exclusively in the offline control plane before graph execution.
- **Realtime Compute Plane:** `ComputeGraph.process()` executes only static, pre-allocated DSP nodes (`BiquadNode`, `GainNode`, `DelayNode`) with $O(N)$ deterministic execution time per audio block.
- **Zero Realtime Allocations:** No analysis functions or memory allocations are invoked inside the audio processing loop.

---

## 10. Dependency Analysis

- **Normative Policy:** Python Standard Library + NumPy only.
- **Audit of Candidate Requirements:**
  - Response Analysis & Metrics: 100% achievable using standard Python + NumPy array operations (`np.interp`, `np.polyfit`, `np.trapz`/`np.trapezoid`, `np.sqrt`).
  - Multi-Way Graph Builder: 100% achievable using existing pure Python graph primitives.
  - Impulse Response WAV ingestion (future): achievable using standard library `wave` + `np.fft`.
- **Verdict:** **Zero new dependencies authorized.** `scipy`, `pandas`, `librosa`, `soundfile`, `sounddevice`, `pyaudio`, and `torch` remain strictly forbidden.

---

## 11. Hardware Boundary

- Hardware audio capture, soundcard playback, ALSA, ASIO, WASAPI, PortAudio, and Bluetooth/amplifier APIs remain **100% OUT OF SCOPE**.
- AcoustiForge provides the computational ACE kernel. Hardware audio adapters belong in separate external application wrappers.

---

## 12. Entity / Action / Agent Boundary

- **Finding:** No Agent, Entity, Action, Proposal, or Workflow classes are required or authorized.
- Standard functional composition ($f(\text{data}) \to \text{Result}$) is completely sufficient, deterministic, and verifiable.

---

## 13. Golden Data Strategy

Golden test data for Phase 4B must follow the **Golden Data Independence Rule** established in Phase 4A:
1. **Idealized Analytical Curves:**
   - Perfect Butterworth low-pass ($M(f) = -10\log_{10}(1 + (f/f_c)^{2N})$) with hand-calculated $F_3 = f_c$, exact $F_6$, exact $F_{10}$, and exact $-6N\text{ dB/octave}$ asymptote.
   - Idealized tilted responses ($+3.0\text{ dB/octave}$ linear spectral tilt) to verify linear regression without numerical artifacts.
   - Known sine-wave ripple profiles ($M(f) = M_0 + A\sin(\omega \log f)$) with known peak-to-peak ripple amplitude $2A$.
2. **Deterministic Multi-Way Topologies:**
   - 3-way crossover graph topologies with hand-derived topological schedules and node ID expectations.
   - Multi-block PCM pass-through and impulse tests with mathematically proven output vectors.
3. **Zero Self-Referential Assertions:** Expected outputs must never be generated by calling production analysis code.

---

## 14. Candidate Sequencing & Phase Roadmap

```
Phase 4A (FROZEN):
  Measurement Ingestion (.frd/.csv/.txt/.cal) + Mic Calibration + 2-Way EQ Graph Insertion
        │
        ▼
Phase 4B (RECOMMENDED NEXT):
  Acoustic Response Analysis & Quantitative Metrics (Candidate B)
  + 3-Way System Graph Synthesis (Candidate C)
        │
        ▼
Phase 4C (FUTURE):
  Impulse Response & Time-Domain Gated Ingestion (Candidate A)
  + Measurement Quality Diagnostics (Candidate E)
        │
        ▼
Phase 4D (FUTURE):
  Measurement-Driven Multi-Way Deterministic System Optimization (Candidate D)
```

---

## 15. Recommended Phase 4B Vertical Slice

### **Acoustic Response Analysis & Multi-Way System Synthesis**

This vertical slice connects the existing measurement ingestion and calibration pipeline with:
1. **Objective Quantitative Analysis:** Extracting sensitivity, $F_3/F_6/F_{10}$ bandwidth, passband ripple, spectral slope, and target tracking error from calibrated measurements.
2. **3-Way Loudspeaker System Construction:** Expanding graph builders to 3-way systems (Woofer, Midrange, Tweeter) where the midrange driver incorporates bandpass crossover biquads, dedicated EQ cascades, alignment delay, gain, and protection.
3. **End-to-End Computational Verification:** Raw measurement files $\to$ Calibration $\to$ Acoustic Analysis $\to$ 3-Way Crossover Synthesis $\to$ 3-Way `ComputeGraph` $\to$ Multi-Block PCM execution.

---

## 16. Proposed Scope for Phase 4B Implementation

### In Scope:
- `acoustiforge.acoustic_math.metrics` (`calculate_response_metrics`, `calculate_bandwidth_cutoffs`, `calculate_passband_sensitivity`, `calculate_spectral_tilt`, `calculate_passband_ripple`, `smooth_frequency_response`).
- `acoustiforge.domain.metrics` or `acoustiforge.acoustic_math` result dataclass `AcousticMetricsResult`.
- `acoustiforge.builders.multiway_builder` (`ThreeWayGraphBuilder` or extending `SystemTopologyBuilder` for 3-way and 2.1 systems with bandpass midrange branches).
- Independent golden analytical test suites.
- 100% backward compatibility with Phase 3D and Phase 4A graphs.

---

## 17. Deferred Scope

The following capabilities are explicitly deferred from Phase 4B:
- Time-domain Impulse Response / WAV file ingestion (Candidate A $\to$ Phase 4C).
- Multi-parameter numerical multi-way optimizer (Candidate D $\to$ Phase 4D).
- Room acoustic simulation and modal calculation (Candidate F).
- Hardware audio I/O, PortAudio, sounddevice, ASIO, WASAPI (Candidate G).
- Graphical User Interface (GUI).
- Database persistence, ORM, and Entity/Action frameworks.
- AI/ML optimization frameworks.

---

## 18. Entry Criteria for Phase 4B Implementation

1. Phase 4A fully frozen and committed (`a4fafa3`).
2. Repository working tree 100% clean.
3. Full regression suite passing: 301 passed, 0 failures, 0 errors, 0 warnings under `pytest -q -W error`.
4. Normative contracts (`ACOUSTIC_METRICS_CONTRACT.md`, `MULTIWAY_GRAPH_BUILDER_CONTRACT.md`) drafted and approved before implementation.
5. Independent golden analytical vectors established.

---

## 19. Exit Criteria for Phase 4B Implementation

1. 100% pass rate under `pytest -q -W error` with zero warnings.
2. All baseline 301 tests pass without regression.
3. Frozen layers (`domain/`, `graph/`, `nodes/`, `PCM_CONTRACT`) remain untouched.
4. Backward compatibility verified: 2-way graph builders produce bit-exact identical DAGs and PCM outputs.
5. Golden data independence verified for all metric and 3-way graph calculations.
6. Dependency audit confirms standard library + NumPy only.
7. Verification document `docs/phases/PHASE_4B_IMPLEMENTATION_AND_VERIFICATION.md` completed.

---

## 20. Risks and Open Questions

1. **Midrange Bandpass Crossover Ordering:** When cascading HP and LP biquad filters for a bandpass midrange branch, should HP precede LP or vice versa? (Mathematically linear time-invariant, but standard practice is HP first to reject low-frequency energy before high-frequency shaping; contract will standardize this).
2. **Cutoff Interpolation in Noisy Data:** When measurement data crosses the $-3.0\text{ dB}$ threshold multiple times due to narrow dips, what is the deterministic tie-breaking rule? (Contract must standardize: outermost crossing vs first crossing from passband center).
3. **Fractional-Octave Smoothing Kernel:** Standardizing exact log-Gaussian weighting window implementation to ensure bit-exact reproducibility across platforms.

---

## 21. Discovery Verdict

```
PHASE 4B DISCOVERY: COMPLETE
RECOMMENDATION: ADOPT CANDIDATE B (ACOUSTIC METRICS) + CANDIDATE C (3-WAY SYNTHESIS)
IMPLEMENTATION: NOT STARTED — AWAITING PHASE 4B CONTRACT RECONCILIATION & IMPLEMENTATION GATE
```
