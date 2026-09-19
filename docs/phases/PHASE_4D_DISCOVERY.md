# AcoustiForge — Phase 4D Architectural Discovery Report
## Measurement-Driven Multi-Way Deterministic System Optimization & Complex Acoustic Summation

---

## 1. Executive Summary

With Phase 4C (*Time-Domain Impulse Ingestion, Reflection Gating, FFT Spectral Transformation, and Measurement Diagnostics*) verified across the test suite (360 passed, 0 failures, 0 errors, 0 warnings under `pytest -q -W error`), AcoustiForge possesses a complete measurement acquisition, calibration, and analysis foundation.

Phase 4D discovery evaluates the natural, next additive milestone in the Acoustic Intelligence and Control Plane:
> *"What computational capability connects ingested, calibrated multi-driver measurements and acoustic metrics into an automated, deterministic multi-way system synthesis engine without introducing external optimization dependencies (such as SciPy) or violating runtime neutrality?"*

### Key Discovery Conclusions:
1. **Primary Capability — Measurement-Driven Multi-Way Deterministic System Optimization & Complex Acoustic Summation:**
   - Implement exact complex transfer function evaluation of biquad cascades in the frequency domain ($H_{\text{biquad}}(e^{j 2\pi f / f_s})$).
   - Implement multi-transducer acoustic complex superposition:
     $$H_{\text{total}}(f) = \sum_{k=1}^K H_{\text{driver}, k}(f) \cdot H_{\text{filter}, k}(f) \cdot e^{-j 2\pi f \tau_k}$$
     combining measured complex driver responses ($H_{\text{driver}, k}(f)$), branch filter transfer functions ($H_{\text{filter}, k}(f)$), relative driver sensitivity gains ($g_k = 10^{G_k/20}$), and time-of-flight acoustic alignment delays ($\tau_k$).
   - Implement deterministic, bounded multi-parameter optimization (crossover cutoff frequencies, branch sensitivity gains, driver alignment delays, and parametric EQ budget allocations) to minimize tracking error against an `AcousticTargetCurve` while preserving phase coherence across crossover transition bands.
2. **Zero Third-Party Solver Dependencies (Pure NumPy):**
   - Optimization algorithms are implemented strictly using vectorized NumPy (bounded grid search, golden-section 1D line search, and deterministic coordinate descent).
   - Zero SciPy (`scipy.optimize` strictly forbidden), zero PyTorch, zero external solvers.
3. **Strict Control-Plane Isolation:**
   - All optimization and summation calculations execute offline in `acoustiforge.acoustic_math.optimization`.
   - The output of optimization is a standard, immutable `OptimizationResult` containing discrete parameters that directly feed the existing `ThreeWayGraphBuilder` or `CrossoverGraphBuilder`.
   - The frozen ACE execution plane (`ComputeGraph`, DSP nodes, PCM contracts) remains 100% untouched.

---

## 2. Frozen Baseline Verification

The existing baseline is permanently frozen across all prior layers:
- **Phase 0 (PCM Contract):** `PCMBlock`, `AudioMetadata`, `ChannelLayout`, float32 planar buffers, and non-blocking multi-block stream execution.
- **Phase 1 (DSP Compute Plane):** `BiquadNode` (Direct Form II Transposed), `GainNode`, `DelayNode`, `PassThroughNode`, and sequential composition.
- **Phase 2B (Typed ComputeGraph):** Directed acyclic graph execution, typed single-producer ports (`PortDirection`, `PortShape`, `PortType`), cycle detection, static topological scheduling, fan-out, and latency tracking.
- **Phase 3B (Acoustic Domain Model):** Immutable domain value objects (`DriverProfile`, `EnclosureProfile`, `TransducerLimits`, `CrossoverSpecification`, `AcousticTargetCurve`, `EqualizerBudget`, `FrequencyResponseData`, `ImpulseResponseData`).
- **Phase 3C (Acoustic Mathematics):** Closed-form synthesis for Butterworth/Linkwitz-Riley crossovers, delay alignment, sensitivity matching, target curve evaluation, driver protection derivation, and greedy parametric EQ synthesis.
- **Phase 3D (Acoustic Graph Builders):** `CrossoverGraphBuilder` (2-way mono crossover graph) and `SystemTopologyBuilder` (stereo 2-way composition).
- **Phase 4A (Measurement Pipeline):** IO parser (`parse_measurement_file`, `parse_measurement_text`), `MeasurementImportResult`, microphone calibration math (`apply_microphone_calibration`), and additive EQ graph builder insertion.
- **Phase 4B (Acoustic Metrics & 3-Way Graph):** Acoustic metrics (`AcousticMetricsResult`, `calculate_response_metrics`, `smooth_frequency_response`), 3-way DAG builder (`ThreeWayGraphBuilder`), and end-to-end multi-block PCM execution.
- **Phase 4C (Impulse Ingestion, Gating & Diagnostics):** Time-domain impulse ingestion (`parse_impulse_file`, `parse_impulse_text`), windowing/reflection gating (`apply_reflection_gate`, `WindowSpecification`), FFT spectral transformation (`impulse_to_frequency_response`), and measurement quality diagnostics (`analyze_measurement_diagnostics`).
- **Committed Baseline:** Commit `a4fafa3` (Phase 4A freeze).
- **Verified Suite State:** 360 passed tests, 0 failures, 0 errors, 0 warnings under `pytest -q -W error`.
- **Baseline Classification:** `PHASE 4C IS VERIFIED BUT NOT FROZEN`.

---

## 3. Phase 4D Context & Evolutionary Flow

AcoustiForge has progressed along a disciplined control-plane and execution-plane trajectory:

```
Phase 4A: Ingestion (.frd, .cal) ──► Calibration ──► Greedy Single-Driver EQ ──► 2-Way Graph
                                                                                       │
Phase 4B: Acoustic Metrics (F3, Ripple, Tilt) ──► 3-Way Graph Builder ─────────────────┤
                                                                                       │
Phase 4C: Impulse (.wav, .txt) ──► Reflection Gating ──► FFT ──► Diagnostics ─────────┤
                                                                                       │
Phase 4D (PROPOSED): Multi-Transducer Acoustic Summation & Deterministic Optimization ◄┘
```

In Phases 3C, 3D, and 4B, system parameters (crossover cutoffs, driver gains, alignment delays) were specified a priori by the designer or calculated via isolated single-driver heuristics (e.g. geometric acoustic center offset, passband average sensitivity).

However, in physical multi-way loudspeaker systems:
1. Individual driver responses have complex natural rolloffs and phase rotations.
2. In the crossover overlap region, drivers sum vectorially (complex acoustic superposition). Unaligned phases cause destructive interference (notches), while unoptimized crossover slopes cause passband ripple or excessive driver excursion.
3. System voicing requires solving the multi-branch joint optimization problem: finding the optimal crossover frequencies $f_c$, branch gains $G_k$, delays $\tau_k$, and corrective EQ biquads such that the combined acoustic output $H_{\text{total}}(f)$ matches the system `AcousticTargetCurve` with minimal RMS error and maximal passband flatness.

Phase 4D delivers this automated, deterministic optimization capability to complete the acoustic intelligence control loop.

---

## 4. Evidence for the Objective

The selection of **Candidate D: Measurement-Driven Multi-Way Deterministic System Optimization** is directly backed by explicit roadmap documentation in the repository:
1. `docs/phases/PHASE_4B_DISCOVERY.md` (lines 171–198): Defines Candidate D (*Measurement-Driven Multi-Way System Optimization*), identifying its purpose, mathematical operations ($H_{\text{total}}(f)$ summation), pure-NumPy bounded search strategy, and sequencing immediately following 4B metrics and 4C impulse ingestion.
2. `docs/phases/PHASE_4B_DISCOVERY.md` (lines 448–450, 480): Sequences Phase 4D explicitly as:
   `Phase 4D: Measurement-Driven Multi-Way Deterministic System Optimization (Candidate D)`.
3. `docs/phases/PHASE_4B_CONTRACT_RECONCILIATION.md` (line 203): Explicitly defers automated multi-way numerical optimization to Phase 4D.
4. `docs/phases/PHASE_4C_DISCOVERY.md` (line 90): Explicitly notes:
   `Multi-Way Optimizer: Automated crossover/gain/delay parameter optimization is deferred to Phase 4D.`
5. `docs/phases/PHASE_4C_IMPLEMENTATION_AND_VERIFICATION.md` (line 120): Reaffirms Phase 4D as the destination for automated multi-way parameter optimization.

---

## 5. Current Architecture & Phase 4D Integration Point

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ CONTROL / ACOUSTIC INTELLIGENCE PLANE                                           │
│                                                                                 │
│  [WAV / Text Impulse Measurements] or [FRD Measurement Files]                   │
│          │                                                                      │
│          ▼ (Phase 4A / 4C Ingestion, Gating, Calibration)                       │
│  [Calibrated FrequencyResponseData for K Drivers]                               │
│          │                                                                      │
│          ├─────────────────────────┬────────────────────────────────────────────┤
│          ▼                         ▼                                            ▼
│  [DriverProfile K]       [AcousticTargetCurve]                        [EqualizerBudget]
│          │                         │                                            │
│          └─────────────────────────┼────────────────────────────────────────────┘
│                                    ▼
│    ┌───────────────────────────────────────────────────────────────────────┐
│    │ NEW Phase 4D: acoustiforge.acoustic_math.optimization                 │
│    │                                                                       │
│    │  1. Complex Transfer Function Evaluator:                              │
│    │     H_filter(f) for biquad cascades (crossover, EQ, protection)       │
│    │                                                                       │
│    │  2. Acoustic Complex Summation Engine:                                │
│    │     H_total(f) = sum_k [ H_driver,k(f) * H_filter,k(f) * exp(-j2πfτk) ]│
│    │                                                                       │
│    │  3. Deterministic Bounded Optimizer (Pure NumPy):                     │
│    │     - Optimize Crossover Frequencies {f_c,1, f_c,2}                   │
│    │     - Optimize Relative Driver Gains {G_k}                            │
│    │     - Optimize Fine Alignment Delays {τ_k}                            │
│    │     - Allocate Joint Parametric EQ across Branches                    │
│    │     - Minimize Cost: E_rms + w_ripple*R + w_excursion*P               │
│    └───────────────────────────────────┬───────────────────────────────────┘
│                                        │
│                                        ▼
│                             [OptimizationResult]
│                                        │
│                                        ▼ (Phase 3D / 4B Builders)
│                     [ThreeWayGraphBuilder / CrossoverGraphBuilder]
└────────────────────────────────────────┬────────────────────────────────────────┘
                                         │ produces frozen DAG
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ COMPUTE / REALTIME DATAFLOW PLANE (Frozen Phase 2B / 1 / 0)                     │
│  ComputeGraph.process(PCMBlock) ──► Deterministic Multi-Block Execution         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

The architectural layering remains strictly unidirectional:
`acoustiforge.io` $\to$ `acoustiforge.domain` $\to$ `acoustiforge.acoustic_math` $\to$ `acoustiforge.builders` $\to$ `acoustiforge.graph` $\to$ `acoustiforge.nodes` $\to$ `acoustiforge.engine`.

---

## 6. Phase 4D Capability Gap Matrix

| Capability | Exists | Reusable | Missing | Candidate Phase 4D Role |
| :--- | :---: | :---: | :---: | :--- |
| **Frequency Response Ingestion & Calibration** | EXISTS | `acoustiforge.io`, `acoustiforge.acoustic_math.calibration` | None | Input provider |
| **Impulse Ingestion & Gating** | EXISTS | `acoustiforge.io.impulse_parser`, `acoustiforge.acoustic_math.gating` | None | Input provider |
| **Acoustic Metric Evaluation** | EXISTS | `acoustiforge.acoustic_math.metrics` | None | Objective function evaluation component |
| **Crossover Biquad Synthesis** | EXISTS | `acoustiforge.acoustic_math.crossover` | None | Filter coefficient generation |
| **Parametric EQ Synthesis** | EXISTS | `acoustiforge.acoustic_math.equalizer` | None | Single-driver PEQ generation |
| **2-Way & 3-Way Graph Builders** | EXISTS | `acoustiforge.builders` | None | Final DAG assembly from optimized parameters |
| **Biquad Complex Frequency Response ($H(e^{j\omega})$)** | MISSING | — | Vectorized evaluation of biquad cascades | **Phase 4D Core (4D.1)** |
| **Multi-Driver Complex Acoustic Summation** | MISSING | — | Phase-accurate vector summation $H_{\text{total}}(f)$ | **Phase 4D Core (4D.1)** |
| **Pure-NumPy Bounded Optimizer** | MISSING | — | Coordinate descent & bounded grid search | **Phase 4D Core (4D.2)** |
| **Multi-Way Joint Parameter Optimization** | MISSING | — | Joint optimization of $f_c$, gains, delays, EQ | **Phase 4D Core (4D.3)** |
| **Optimization Domain Models** | MISSING | — | `OptimizationSpecification`, `OptimizationResult` | **Phase 4D Domain (4D.1)** |
| **Room Acoustic Simulation (BEM/FEM/Modes)** | OUT OF SCOPE | — | — | Explicitly excluded |
| **Hardware Audio I/O / Realtime Capture** | OUT OF SCOPE | — | — | Explicitly excluded |
| **AI / Neural Network Optimization** | OUT OF SCOPE | — | — | Explicitly excluded |

---

## 7. Reusable Components

Phase 4D reuses existing frozen abstractions without duplication:
- **`FrequencyResponseData`** (`domain.measurements`): Ingests driver measurements (frequencies, magnitude_db, phase_rad).
- **`AcousticTargetCurve`** (`domain.specifications`): Target magnitude profile across frequency.
- **`DriverProfile`** (`domain.profiles`): Driver nominal impedance, sensitivity, physical offset, limits.
- **`CrossoverSpecification`** (`domain.specifications`): Crossover filter types (Linkwitz-Riley, Butterworth), orders, and initial frequencies.
- **`EqualizerBudget`** (`domain.specifications`): Constraints on maximum filter count, max boost/cut, and Q ranges.
- **`synthesize_crossover_biquads`** (`acoustic_math.crossover`): Evaluates analog/digital s/z-domain biquad coefficients for crossover branches.
- **`synthesize_parametric_eq`** (`acoustic_math.equalizer`): Generates target-matching peaking/shelf filters.
- **`calculate_response_metrics`** (`acoustic_math.metrics`): Evaluates post-optimization metrics ($F_3, F_{10}$, ripple, RMS error).
- **`ThreeWayGraphBuilder`** & **`CrossoverGraphBuilder`** (`builders`): Consume `OptimizationResult` to produce executable `ComputeGraph` instances.

---

## 8. New Components Required for Phase 4D

### 8.1 Domain Layer (`acoustiforge.domain.specifications` or `acoustiforge.domain.optimization`)
1. **`OptimizationSpecification`:** Immutable configuration specifying:
   - Target curve (`AcousticTargetCurve`)
   - Driver profiles and measured responses (`tuple[tuple[DriverProfile, FrequencyResponseData], ...]`)
   - Parameter search bounds (min/max crossover frequencies, gain adjustment bounds $\pm \Delta G_{\text{max}}$, delay search window $[\tau_{\text{min}}, \tau_{\text{max}}]$)
   - Optimization weights (tracking error weight, passband ripple penalty, excursion penalty)
   - Convergence tolerances and max iterations
2. **`OptimizationResult`:** Immutable container storing:
   - Optimized crossover frequencies ($f_{c, 1}, f_{c, 2}$)
   - Optimized branch gains ($G_1, G_2, \dots$) in dB
   - Optimized branch delays ($\tau_1, \tau_2, \dots$) in milliseconds / seconds
   - Optimized parametric EQ filter cascade per branch
   - Predicted total complex response `FrequencyResponseData`
   - Pre- and post-optimization `AcousticMetricsResult`
   - Final objective loss and convergence status flag

### 8.2 Acoustic Math Layer (`acoustiforge.acoustic_math.optimization`)
1. **`evaluate_biquad_complex_response(biquads: Sequence[BiquadParameters], frequencies: np.ndarray, sample_rate: int) -> np.ndarray`:**
   - Computes exact complex frequency response $H(f) = \prod_{m} \frac{b_{0,m} + b_{1,m} e^{-j 2\pi f / f_s} + b_{2,m} e^{-j 4\pi f / f_s}}{a_{0,m} + a_{1,m} e^{-j 2\pi f / f_s} + a_{2,m} e^{-j 4\pi f / f_s}}$ using vectorized NumPy.
2. **`calculate_acoustic_complex_summation(...) -> FrequencyResponseData`:**
   - Evaluates vector acoustic summation of $K$ acoustic branches:
     $$H_{\text{total}}(f) = \sum_{k=1}^K 10^{M_k(f)/20} e^{j \phi_k(f)} \cdot H_{\text{filter}, k}(f) \cdot 10^{G_k/20} e^{-j 2\pi f \tau_k}$$
   - Returns consolidated `FrequencyResponseData` (frequencies, magnitude_db, phase_rad).
3. **`optimize_multiway_system(spec: OptimizationSpecification) -> OptimizationResult`:**
   - Executes deterministic coordinate descent / bounded line search over parameter bounds.
   - Evaluates composite loss:
     $$\mathcal{L} = \sqrt{\frac{1}{N}\sum_{i=1}^N (M_{\text{total}}(f_i) - T(f_i))^2} + w_r \cdot \text{Ripple} + w_p \cdot \text{Penalty}$$
   - Returns deterministic, mathematically verified global/local minimum within specified tolerances.

---

## 9. Proposed Normative Contract

### Contract Name: `MULTIWAY_OPTIMIZATION_CONTRACT.md` (`CONTRACT-MULTIWAY-OPT-01`)
- **Purpose:** Define exact mathematical equations, numerical tolerances, parameter search spaces, convergence criteria, and error semantics for multi-transducer acoustic complex summation and deterministic multi-way system parameter optimization.
- **Inputs:**
  - `OptimizationSpecification` containing driver measurements, driver profiles, crossover specifications, target curves, search bounds, and sample rate.
- **Outputs:**
  - `OptimizationResult` containing optimal crossover frequencies, branch gains, alignment delays, synthesized EQ filters, predicted summed response, and performance metrics.
- **Invariants:**
  1. *Determinism:* Given identical inputs, the optimizer must produce bit-exact identical floating-point parameter outputs across runs.
  2. *Frequency Ordering:* Optimized crossover cutoffs must strictly satisfy $f_{\text{min}} \le f_{c, 1} < f_{c, 2} < \dots < f_{\text{nyquist}}$.
  3. *Bound Preservation:* Optimal parameters ($f_c, G_k, \tau_k$) must strictly reside within the prescribed `OptimizationSpecification` bounds.
  4. *Loss Monotonicity:* Post-optimization target tracking error must be less than or equal to pre-optimization tracking error ($\mathcal{L}_{\text{post}} \le \mathcal{L}_{\text{pre}}$).
  5. *Zero Complex Phase Singularities:* Phase calculations must preserve principal argument conventions ($[-\pi, \pi]$) without undefined zero-division.
- **Error Semantics:**
  - Raise `AcousticValidationError` if driver measurements have mismatched frequency grids, if bounds are inverted ($f_{\text{max}} \le f_{\text{min}}$), if sample rates are non-positive, or if driver count does not match system branch count.
- **Dependency Constraints:**
  - Strictly Python standard library + NumPy. Zero SciPy, zero PyTorch, zero external solvers.

---

## 10. Numerical & Scientific Semantics

1. **Complex Transfer Function Evaluation:**
   - For a biquad with coefficients $[b_0, b_1, b_2, a_0, a_1, a_2]$, the complex frequency response at frequency $f$ with sample rate $f_s$ is:
     $$z = e^{j 2\pi f / f_s}$$
     $$H(f) = \frac{b_0 + b_1 z^{-1} + b_2 z^{-2}}{a_0 + a_1 z^{-1} + a_2 z^{-2}}$$
   - For a cascade of $M$ biquads, $H_{\text{cascade}}(f) = \prod_{m=1}^M H_m(f)$.
2. **Acoustic Complex Summation:**
   - Driver complex measurement: $H_{\text{driver}, k}(f) = 10^{M_k(f)/20} \cdot e^{j \phi_k(f)}$
   - Delay phase shift: $H_{\text{delay}, k}(f) = e^{-j 2\pi f \tau_k}$ (with $\tau_k$ in seconds)
   - Branch complex response: $H_{\text{branch}, k}(f) = H_{\text{driver}, k}(f) \cdot H_{\text{filter}, k}(f) \cdot 10^{G_k/20} \cdot H_{\text{delay}, k}(f)$
   - Total system acoustic response: $H_{\text{total}}(f) = \sum_{k=1}^K H_{\text{branch}, k}(f)$
   - Total magnitude (dB): $M_{\text{total}}(f) = 20 \log_{10} (|H_{\text{total}}(f)| + \epsilon)$ where $\epsilon = 10^{-12}$
   - Total phase (radians): $\phi_{\text{total}}(f) = \text{arctan2}(\text{Im}(H_{\text{total}}(f)), \text{Re}(H_{\text{total}}(f)))$
3. **Pure-NumPy Deterministic Optimization Strategy:**
   - **Step 1: Crossover & Delay Search (Bounded Grid / Coordinate Descent):**
     - Discrete evaluation over log-spaced crossover frequency candidates and fine linear delay steps.
     - Golden-section 1D line search for continuous refinement of individual scalar parameters.
   - **Step 2: Sensitivity Balancing:**
     - Closed-form weighted least-squares or bounded 1D search for branch gain offsets.
   - **Step 3: Joint Branch EQ Allocation:**
     - Evaluates residual error curve $E(f) = M_{\text{total}}(f) - T(f)$ and derives compensating peaking filters allocated to the driver branch with the highest sensitivity / authority in that frequency band.
4. **Convergence Criteria & Tolerances:**
   - Search iterations terminate when $\Delta \mathcal{L} < 10^{-6}$ or when maximum iteration count $N_{\text{iter}}$ is reached.
   - All intermediate and final calculations executed in standard IEEE 754 64-bit float (`np.float64`).

---

## 11. Dependency Boundary

- **Permitted Dependencies:** Python Standard Library (`math`, `typing`, `dataclasses`, `enum`, `pathlib`) + `numpy`.
- **Prohibited Dependencies:** `scipy` (e.g. `scipy.optimize`, `scipy.signal`), `sounddevice`, `pyaudio`, `torch`, `matplotlib`, `pandas`.
- **Dependency Audit Compliance:** Verified against `tests/test_dependency_isolation.py`.

---

## 12. Scope Firewall

| Domain / Feature | Classification | Rationale |
| :--- | :---: | :--- |
| **Measurement-Driven Multi-Way Optimization** | **IN SCOPE** | Core Phase 4D objective |
| **Biquad Complex Frequency Response Evaluation** | **IN SCOPE** | Mathematical necessity for acoustic summation |
| **Multi-Driver Complex Acoustic Summation** | **IN SCOPE** | Core physical-acoustic evaluation |
| **Pure-NumPy Bounded Optimizer** | **IN SCOPE** | Pure-NumPy implementation of coordinate descent |
| **Hardware Audio I/O / Soundcard Capture** | **OUT OF SCOPE** | ACE engine is strictly offline/headless |
| **Realtime Audio Streaming / PortAudio** | **OUT OF SCOPE** | Realtime stream drivers violate offline determinism |
| **Graphical User Interface (GUI) / Plots** | **OUT OF SCOPE** | AcoustiForge is an offline compute engine |
| **Database / ORM / Entity Frameworks** | **OUT OF SCOPE** | Out-of-scope enterprise software complexity |
| **AI / ML / Neural Network Parameter Fitters** | **OUT OF SCOPE** | Non-deterministic, unprovable black-box models |
| **3D Room Simulation / BEM / FEM / Ray Tracing** | **OUT OF SCOPE** | Room simulation is deferred to future major milestones |

---

## 13. Backward-Compatibility Analysis

Phase 4D is strictly additive:
- **Phase 0–3D:** No changes to `PCMBlock`, `BiquadNode`, `ComputeGraph`, domain models, or graph builders.
- **Phase 4A–4C:** `parse_measurement_file`, `apply_microphone_calibration`, `calculate_response_metrics`, `parse_impulse_file`, `apply_reflection_gate`, and `ThreeWayGraphBuilder` retain identical signatures and semantics.
- **Regression Target:** All 360 existing tests must pass with 0 failures, 0 errors, and 0 warnings under `pytest -q -W error`.

---

## 14. Golden-Test Strategy

To ensure independent verification without self-fulfilling test logic, Phase 4D will utilize analytical physical systems with mathematically closed-form known optima:

1. **Analytical 2-Way Coincident System (Known Gain & Delay Optima):**
   - Two synthetic flat drivers with deliberate sensitivity offset $\Delta G = 6.0\text{ dB}$ and physical time-offset $\Delta \tau = 0.5\text{ ms}$.
   - Analytical solution: Optimizer must converge to $G_2^* - G_1^* = -6.0\text{ dB}$ and $\tau^* = 0.5\text{ ms}$ within $\pm 0.05\text{ dB}$ and $\pm 0.005\text{ ms}$.
2. **Analytical Complementary Linkwitz-Riley 4th-Order System (Known Crossover Optimum):**
   - Low-frequency driver with natural 2nd-order low-pass rolloff at $f_1 = 3000\text{ Hz}$ and high-frequency driver with natural 2nd-order high-pass rolloff at $f_2 = 3000\text{ Hz}$.
   - Target curve: Perfectly flat $0\text{ dB}$.
   - Analytical solution: Crossover optimization must converge to $f_c^* = 3000\text{ Hz}$ to achieve minimum passband ripple ($< 0.1\text{ dB}$).
3. **Complex Summation Vector Goldens:**
   - Hand-calculated complex phasor additions at specific test frequencies (e.g. $+90^\circ$ phase difference yielding $+3.01\text{ dB}$ summation; $180^\circ$ out-of-phase yielding infinite notch cancellation $> 60\text{ dB}$ attenuation).
4. **End-to-End Vertical Slice:**
   - Raw IR / FRD measurements $\to$ Diagnostics $\to$ Optimization $\to$ `ThreeWayGraphBuilder` $\to$ `ComputeGraph` $\to$ Multi-block PCM processing.

---

## 15. Proposed Phase 4D Implementation Slices

### Slice 4D.1 — Domain Models & Complex Frequency Response Math
- **Objective:** Create `OptimizationSpecification`, `OptimizationResult` domain objects and `evaluate_biquad_complex_response` / `calculate_acoustic_complex_summation` functions.
- **Contract:** `MULTIWAY_OPTIMIZATION_CONTRACT.md` (Sections 1–4).
- **Tests:** Unit tests for complex biquad $H(f)$, vector summation, phase rotation, and phasor cancellations.

### Slice 4D.2 — Pure-NumPy Deterministic Optimization Primitives
- **Objective:** Implement 1D golden-section bounded search, 2D/ND grid evaluation, and coordinate descent in pure NumPy.
- **Contract:** `MULTIWAY_OPTIMIZATION_CONTRACT.md` (Section 5).
- **Tests:** Unit tests optimizing canonical convex test functions with known analytical minima.

### Slice 4D.3 — Multi-Way Joint Crossover, Gain & Delay Optimizer
- **Objective:** Implement `optimize_multiway_system` for 2-way and 3-way systems against `AcousticTargetCurve`.
- **Contract:** `MULTIWAY_OPTIMIZATION_CONTRACT.md` (Section 6).
- **Tests:** Optimization convergence tests, parameter bound enforcement, and error validation.

### Slice 4D.4 — Independent Analytical Golden Tests
- **Objective:** Verify optimization against closed-form 2-way and 3-way synthetic systems.
- **Tests:** `tests/test_multiway_optimization_golden.py`.

### Slice 4D.5 — End-to-End Measurement $\to$ Optimization $\to$ Graph Builder $\to$ PCM Slice
- **Objective:** Ingest real/synthetic multi-driver measurements, run diagnostics, optimize parameters, construct 3-way `ComputeGraph`, and execute multi-block PCM audio.
- **Tests:** `tests/test_phase_4d_end_to_end.py`.

---

## 16. Proposed Phase 4D Acceptance Gates

```text
4D-A  Frozen baseline preserved (360 tests pass)
4D-B  Domain models & specification validation
4D-C  Complex biquad transfer function calculation accuracy (< 1e-6 error)
4D-D  Acoustic complex summation accuracy & phase cancellation
4D-E  Pure-NumPy optimizer determinism & bit-exact reproducibility
4D-F  Parameter bound preservation (fc, G, delay within bounds)
4D-G  Target tracking error reduction (Loss_post <= Loss_pre)
4D-H  Independent analytical golden test suite PASS
4D-I  End-to-end measurement → optimizer → graph → PCM vertical slice PASS
4D-J  Backward compatibility with Phase 4A/4B/4C graphs PASS
4D-K  Zero third-party dependencies (strictly stdlib + NumPy, 0 SciPy)
4D-L  Layering and import direction audit PASS
4D-M  Scope firewall containment PASS
4D-N  Zero-warning test suite (pytest -q -W error)
```

---

## 17. Risk Register

| Risk | Likelihood | Impact | Detection Method | Mitigation | Blocks Impl? |
| :--- | :---: | :---: | :--- | :--- | :---: |
| **Local Minima in Crossover Search** | Low | Med | Multi-start grid initializations | Use coarse log-grid initial evaluation followed by fine coordinate descent | No |
| **Performance / Execution Time with Dense Grids** | Low | Low | Execution profiling tests | Vectorize all grid evaluations in NumPy across the frequency axis | No |
| **Numerical Instability in Complex Division** | Low | High | Edge-case tests with $a_0 \approx 0$ or extreme frequencies | Enforce denominator floor $\epsilon = 10^{-12}$ | No |
| **SciPy Leakage via Sub-dependencies** | Low | Critical | `tests/test_dependency_isolation.py` AST scan | Pure NumPy math; AST import checker in CI | No |
| **Keyword Filter Collision** | Low | Med | Scope test scan | Avoid forbidden keywords (`limiter`, `compressor`, etc.) in identifier names | No |

---

## 18. Open Questions & Contract Prerequisites

1. **Parameter Optimization Granularity:**
   - *Recommendation:* Support joint optimization of crossover frequencies ($f_c$), branch gains ($G_k$), and fine time-alignment delays ($\tau_k$), with optional per-branch parametric EQ allocation.
2. **Loss Function Weighting:**
   - *Recommendation:* Default to RMS target error in dB across active band ($f_{\text{min}}$ to $f_{\text{max}}$) with configurable penalty weights for passband ripple and driver excursion violations.

---

## 19. Final Decision

```text
GO — PHASE 4D READY FOR CONTRACT RECONCILIATION
```

### Rationale:
- Phase 4D objective is evidence-backed and follows directly from Phase 4B/4C sequencing roadmaps.
- Mathematical equations for complex transfer function evaluation and acoustic complex summation are closed-form and well-defined.
- Bounded optimization in pure NumPy without SciPy is technically straightforward, deterministic, and free of external dependency risks.
- Backward compatibility with Phase 0–4C is fully preserved.
