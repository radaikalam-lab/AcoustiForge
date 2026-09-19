# AcoustiForge — Output Quality & Control-Edge Experimental Design

**Document Identifier:** `ARCH-EXP-2026-01`  
**Classification:** ARCHITECTURAL EXPERIMENTAL PROTOCOL  
**Target Repository:** `E:\AcoustiForge`  
**Baseline Commit:** `0ea8243 Freeze Phase 4C measurement ingestion and diagnostics`  
**Working State:** Phase 4D-3 Verified (`404 passed, 0 failures, 0 errors, 0 warnings`)  
**Governing Architecture Document:** [`ACOUSTIFORGE_OOTB_CAPABILITY_AUDIT.md`](file:///e:/AcoustiForge/docs/architecture/ACOUSTIFORGE_OOTB_CAPABILITY_AUDIT.md)

---

## 1. Objective

The strategic objective of this protocol is to test the core value proposition of AcoustiForge:

> **Does AcoustiForge's control over acoustic semantics, physical modelling, deterministic optimization, traceability, and executable DSP graph generation produce a measurable output-quality and engineering-control advantage over conventional Out-Of-The-Box (OOTB) acoustic workflows?**

### Crucial Distinction:
* **Architectural Control** is a property of the software design (e.g., typed contracts, immutable domain models, zero-dependency reference math, DAG topological execution).
* **Demonstrated Output Advantage** is an empirically verified engineering outcome (e.g., bit-exact reproducibility, error prevention, phase-accurate acoustic summation, end-to-end execution continuity from raw measurement to PCM samples).

Architectural control is not assumed to be an automatic advantage. This protocol establishes the rigorous, minimal, and falsifiable experimental program required to prove or disprove whether that control produces genuine engineering leverage.

---

## 2. The Control-Edge Hypothesis

### 2.1 Formal Hypothesis Statement
AcoustiForge provides a measurable engineering advantage over conventional acoustic tools not by inventing novel acoustic physics, but by **eliminating the semantic, numerical, and structural disconnects** that exist in fragmented OOTB workflows. 

Specifically:
1. **Physical Modeling Disconnect:** Many OOTB workflows optimize magnitude responses independently of complex phase interactions or rely on undocumented phase unwrapping heuristics. AcoustiForge enforces rigorous complex phasor superposition ($H_{\text{total}}(f) = \sum_k H_{\text{branch}, k}(f)$) with explicit acoustic delay modeling.
2. **Optimization Disconnect:** Standard numerical optimization algorithms (e.g., unconstrained BFGS, stochastic gradient descent, heuristic genetic algorithms) are non-deterministic, opaque in trajectory, and prone to physically unachievable filter gains or frequency crowding. AcoustiForge enforces deterministic coordinate descent and golden section line search bounded by physical acoustic constraints.
3. **Execution Disconnect:** Conventional workflows design filters in a CAD/simulation package, export text/biquad parameters, and manually re-enter them into DSP hardware/software, introducing quantization, topology, and sampling-rate drift. AcoustiForge compiles optimized crossover parameters directly into a validated, typed `ComputeGraph` DSP execution engine with zero semantic drift.
4. **Traceability Disconnect:** Conventional acoustic workflows lose provenance between raw microphone impulse responses, windowing gates, target curves, and DSP filters. AcoustiForge maintains an end-to-end immutable audit trail.

---

## 3. What is Already Demonstrated vs. What Remains Unverified

### 3.1 Ten Dimensions of Control Evaluation

| Dimension | Definition | Repository Status | Evidence / Location |
| :--- | :--- | :--- | :--- |
| **1. Semantic Control** | Formal domain value objects, immutable specifications, contract-enforced physical invariants. | **Demonstrated** | `src/acoustiforge/domain/`, `docs/contracts/` (11 contracts), 404 tests passing. |
| **2. Physical Model Transparency** | Multi-way complex phasor summation with explicit branch gain and phase-delay modeling. | **Demonstrated** | `src/acoustiforge/acoustic_math/optimization.py` (`calculate_branch_complex_response`, `calculate_multiway_complex_response`), [`test_acoustic_complex_summation.py`](file:///e:/AcoustiForge/tests/test_acoustic_complex_summation.py). |
| **3. Numerical Reproducibility** | Zero stochasticity; 100% deterministic results across runs, architectures, and environments. | **Demonstrated** | `tests/test_determinism.py`, `tests/test_optimization_math.py`. |
| **4. Optimization Transparency** | Complete inspection of candidate evaluations, error decomposition (RMS + ripple + delay), and deterministic tie-breaking. | **Demonstrated (Kernels)** | `src/acoustiforge/acoustic_math/optimization.py` (`evaluate_candidate_response`, `golden_section_search`, `coordinate_descent_1d`). |
| **5. Parameter Controllability** | Independent control of per-branch gain ($\text{dB}$), delay ($\text{s}$), biquad parameters ($f_0, Q, G$), and crossover order. | **Demonstrated** | `OptimizationSpecification`, `MultiWaySummationResult`. |
| **6. Intermediate-State Inspectability** | All intermediate phasors ($H_{\text{driver}}$, $H_{\text{filter}}$, $H_{\text{branch}}$, $H_{\text{total}}$), error curves, and diagnostic features are exposed as arrays. | **Demonstrated** | `MultiWaySummationResult` dataclass exposes per-branch and total complex responses. |
| **7. Measurement $\to$ Model Traceability** | Provenance from raw WAV/ASCII IR through windowing/gating to `FrequencyResponseData`. | **Demonstrated** | Phase 4C vertical slice (`tests/test_phase_4c_end_to_end.py`). |
| **8. Model $\to$ Executable DSP Continuity** | Direct compilation of crossover/filter specs into typed DSP DAG (`ComputeGraph`) processing PCM audio. | **Demonstrated (Manual/Builder)**; **Unverified (Auto-Optimizer $\to$ Graph)** | Phase 4B `MultiWayGraphBuilder` demonstrates manual spec $\to$ DSP. Auto-wiring optimizer output to graph is Phase 4D-4/4D-5. |
| **9. Composability** | Typed DAG execution with deterministic topological scheduling and zero-allocation block processing. | **Demonstrated** | Phase 1–3 `ComputeGraph` (`src/acoustiforge/graph/compute_graph.py`). |
| **10. Extensibility** | Pluggable backend architecture without mutating domain value objects or contracts. | **Plausible but Unverified** | Architecturally specified in `ACOUSTIFORGE_OOTB_CAPABILITY_AUDIT.md`; native reference backend exists. |

---

## 4. Experimental Program: Experiments A through E

### Experiment A — Forward-Model Transparency & Intermediate-State Inspectability

#### Goal:
Verify that AcoustiForge provides 100% mathematical transparency across all intermediate stages of multi-way acoustic superposition, where every intermediate transfer function is accessible, inspectable, and matches hand-derived complex arithmetic.

#### Experimental Setup:
* **System:** 2-Way System (Woofer $W$, Tweeter $T$).
* **Input Data:** Synthetic synthetic drivers with known analytical magnitude and phase:
  * Woofer: $H_W(f) = \frac{1}{1 + j(f / 2000)}$ (1st-order low-pass characteristic).
  * Tweeter: $H_T(f) = \frac{j(f / 2000)}{1 + j(f / 2000)}$ (1st-order high-pass characteristic).
* **Filters:** 
  * Branch 0: 2nd-order Butterworth Low-Pass at $2000\,\text{Hz}$, $Q = 1/\sqrt{2}$.
  * Branch 1: 2nd-order Butterworth High-Pass at $2000\,\text{Hz}$, $Q = 1/\sqrt{2}$, Inverted Phase ($G = 0\,\text{dB}$, Inverted = True).
* **Delays:** Tweeter delayed by $\tau = 50\,\mu\text{s}$ ($0.00005\,\text{s}$).

#### Inspection Verification Points:
Record and verify the exact numerical arrays for:
1. $H_{\text{driver}, k}(f)$ (Raw driver complex response)
2. $H_{\text{filter}, k}(f)$ (Cascaded biquad complex response)
3. $A_k(f) = 10^{G_k / 20}$ (Branch linear gain)
4. $D_k(f) = \exp(-j 2\pi f \tau_k)$ (Branch acoustic delay phasor)
5. $H_{\text{branch}, k}(f) = H_{\text{driver}, k}(f) \cdot H_{\text{filter}, k}(f) \cdot A_k(f) \cdot D_k(f)$
6. $H_{\text{total}}(f) = \sum_k H_{\text{branch}, k}(f)$
7. $\text{SPL}_{\text{total}}(f) = 20 \log_{10}(|H_{\text{total}}(f)|)$
8. $\Phi_{\text{total}}(f) = \text{unwrap}(\arg(H_{\text{total}}(f)))$
9. $\mathcal{E}(f) = \text{SPL}_{\text{total}}(f) - \text{SPL}_{\text{target}}(f)$

#### Measurable Edge Criteria:
* Maximum absolute discrepancy between AcoustiForge intermediate arrays and hand-calculated analytical equations must be $< 10^{-12}$ (floating-point epsilon).
* All 9 intermediate state arrays must be directly accessible via the public Python API without patching or debugging hooks.

---

### Experiment B — Deterministic Optimization & Search Trajectory Auditability

#### Goal:
Verify that AcoustiForge's optimization engine produces bit-exact identical trajectories, parameter convergence, and loss curves across repeated executions, and that the optimizer trajectory can be fully reconstructed.

#### Experimental Setup:
* **Problem:** 2-Way crossover frequency and gain alignment.
  * Parameter vector: $\mathbf{x} = [f_{\text{cross}}, G_{\text{tweeter}}, \tau_{\text{tweeter}}]$.
  * Search space: $f_{\text{cross}} \in [1500, 3500]\,\text{Hz}$, $G_T \in [-6.0, +6.0]\,\text{dB}$, $\tau_T \in [0.0, 200.0]\,\mu\text{s}$.
  * Target: Flat $85.0\,\text{dB}\,\text{SPL}$ from $100\,\text{Hz}$ to $20\,000\,\text{Hz}$.
* **Execution:**
  * Run the identical optimization problem 100 times consecutively on the same machine.
  * Run across different worker threads/processes.
  * Log every candidate parameter vector evaluated: $\{\mathbf{x}_i, \mathcal{L}(\mathbf{x}_i), \text{RMS}_i, \text{Ripple}_i, \text{DelayPenalty}_i\}$.

#### Measurable Edge Criteria:
* **Determinism:** Bit-exact reproducibility:
  $$\sigma^2(f_{\text{cross}}^*) = 0.0, \quad \sigma^2(G_T^*) = 0.0, \quad \sigma^2(\tau_T^*) = 0.0, \quad \sigma^2(\mathcal{L}^*) = 0.0$$
* **Convergence Auditability:** The exact evaluation count $N$, candidate evaluation history, and termination predicate must be identical across all 100 runs.
* **Loss Decomposition:** Total loss must exactly equal $\mathcal{L} = \text{RMS} + w_{\text{ripple}} \cdot \text{Ripple} + w_{\text{delay}} \cdot \text{Penalty}$ for every candidate point.

---

### Experiment C — Physical-Acoustic Phase Cancellation vs. Magnitude-Only Blindness

#### Goal:
Demonstrate the concrete engineering failure mode of magnitude-only acoustic workflows and prove that AcoustiForge's complex acoustic summation model correctly predicts and resolves destructive interference.

#### Physical Scenario:
* A 2-Way loudspeaker where the tweeter is physically offset from the woofer baffle plane by $\Delta d = 34.4\,\text{mm}$, introducing an acoustic time delay:
  $$\tau = \frac{\Delta d}{c} = \frac{0.0344\,\text{m}}{344\,\text{m/s}} = 100\,\mu\text{s}$$
* Crossover: 4th-order Linkwitz-Riley ($LR4$, $24\,\text{dB/oct}$) at $f_c = 2500\,\text{Hz}$.
* At $2500\,\text{Hz}$, a $100\,\mu\text{s}$ delay corresponds to a phase shift:
  $$\Delta \theta = 2\pi f_c \tau = 2\pi (2500)(0.0001) = 0.5\pi\,\text{rad} = 90^\circ$$
* With an additional polarity mismatch or improper crossover phase alignment, the phase difference at crossover approaches $180^\circ$ ($\pi\,\text{rad}$).

#### Comparison Cases:
1. **Magnitude-Only Summation (Naive Model):**
   $$|H_{\text{naive}}(f)| = \sqrt{|H_{\text{woofer}}(f)|^2 + |H_{\text{tweeter}}(f)|^2}$$
   *Predicts a smooth flat response ($0\,\text{dB}$ ripple).*
2. **AcoustiForge Complex Acoustic Summation:**
   $$H_{\text{complex}}(f) = H_{\text{woofer}}(f) + H_{\text{tweeter}}(f) \cdot e^{-j 2\pi f (0.0001)}$$
   *Correctly predicts a deep cancellation notch ($-15\,\text{dB}$ to $-30\,\text{dB}$) around $2500\,\text{Hz}$.*
3. **AcoustiForge Delay-Compensated Summation:**
   $$H_{\text{aligned}}(f) = H_{\text{woofer}}(f) + H_{\text{tweeter}}(f) \cdot e^{-j 2\pi f (0.0001)} \cdot e^{+j 2\pi f (0.0001)}$$
   *Restores perfect in-phase acoustic summation.*

#### Measurable Edge Criteria:
* Predicts the exact frequency and depth of the cancellation notch with zero error against closed-form analytical equations.
* Demonstrates that optimizing based on complex summation results in a system with $< 0.5\,\text{dB}$ real acoustic ripple, whereas magnitude-only optimization results in $> 12\,\text{dB}$ real acoustic notch error.

---

### Experiment D — Executable Continuity: From Optimization Model to DSP PCM Execution

#### Goal:
Verify that an optimized acoustic filter configuration remains semantically and numerically preserved when compiled into an executable `ComputeGraph` DSP engine operating on raw 32-bit floating point PCM audio samples.

#### Experimental Flow:
```text
Optimization Result (biquad f0, Q, gain, delay samples)
       ↓
MultiWayGraphBuilder.build()
       ↓
Typed ComputeGraph (BiquadFilterNodes, GainNodes, DelayNodes, SumNode)
       ↓
Inject Dirac Impulse δ[n] at 48 kHz
       ↓
PCM Sample Processing (compute_graph.process_block)
       ↓
FFT of Output PCM (numpy.fft.rfft)
       ↓
Compare FFT Frequency Response vs. Forward-Model Frequency Response
```

#### Measurable Edge Criteria:
* **Transfer Function Fidelity:** The frequency response extracted via FFT from the PCM time-domain output of the `ComputeGraph` must match the frequency response calculated by the analytical forward model `calculate_multiway_complex_response` within:
  * Magnitude error: $|\Delta \text{SPL}(f)| < 0.05\,\text{dB}$ across $20\,\text{Hz} - 20\,000\,\text{Hz}$.
  * Phase error: $|\Delta \Phi(f)| < 0.5^\circ$ across $20\,\text{Hz} - 20\,000\,\text{Hz}$.
* **Zero Parameter Drift:** Biquad coefficients $b_0, b_1, b_2, a_1, a_2$ in the DSP nodes must match the RBJ filter synthesis formulas exactly.

---

### Experiment E — OOTB Benchmarking & Control-Gap Matrix

#### Goal:
Execute the exact same mathematical 2-way acoustic optimization problem across:
1. **AcoustiForge Native Reference Engine** (Pure Python + NumPy, deterministic coordinate descent).
2. **General-Purpose Optimization Library (SciPy `minimize` SLSQP / Nelder-Mead).**
3. **Representative Acoustic CAD Workflow Reference (VituixCAD / REW simulation equations).**

#### Comparison Matrix:

| Capability / Dimension | AcoustiForge Reference Engine | SciPy `minimize` (SLSQP) | Conventional Acoustic CAD (e.g. VituixCAD) |
| :--- | :--- | :--- | :--- |
| **Mathematical Problem** | 2-Way Complex Acoustic Alignment ($H_{\text{total}} = \sum H_{\text{branch}}$). | Identical loss function passed to `scipy.optimize.minimize`. | Identical driver FRDs and filter topologies entered in CAD. |
| **Input Determinism** | 100% Bit-exact across runs. | Deterministic if seed/tolerances fixed, but dependent on external C-libraries (BLAS/LAPACK). | Highly dependent on GUI state, solver settings, and platform. |
| **Search Trajectory Inspectability** | **Complete:** Full candidate array, per-iteration parameter vector, and decomposed loss terms logged. | **Partial:** Callback provides current $\mathbf{x}$, but internal line-search evaluations and gradient steps are opaque. | **Zero:** Black-box solver; only initial and final states available. |
| **Physical Constraint Enforcement** | Native bounds, maximum $Q$ limits, monotonically increasing crossover frequencies. | Bounds supported via projection; constraint violation during intermediate steps common. | Manual GUI slider limits. |
| **Executable DSP Continuity** | **Direct:** Compiles natively to `ComputeGraph` for immediate PCM streaming. | **None:** Optimization output is a generic numpy array; requires external DSP implementation. | **Export-only:** Exports text biquad coefficients ($b_i, a_i$) requiring third-party DSP host. |
| **Dependency Burden** | `python` + `numpy` (Standard Library only for engine). | `scipy` + `numpy` + compiled C/Fortran binaries. | Proprietary binary, OS-specific GUI (Windows/Wine). |
| **Automated Headless CI/CD** | **Native:** Runs in headless CI test suites in $< 2\,\text{seconds}$. | Runs headless via Python scripts. | Cannot run headlessly in CI/CD build pipelines. |

---

## 5. Measurable Edge Criteria

To prevent vague or subjective assessments, all evaluations are tied to quantitative, falsifiable metrics:

| Metric Name | Mathematical Definition | Success Threshold (Edge Confirmed) | Failure Threshold (Edge Disproven) |
| :--- | :--- | :--- | :--- |
| **Numerical Determinism ($\Delta_{\text{rep}}$)** | $\max_{i,j} \|\mathbf{x}^*_i - \mathbf{x}^*_j\|_\infty$ across 100 runs | $\Delta_{\text{rep}} = 0.0$ (Bit-exact) | $\Delta_{\text{rep}} > 10^{-12}$ |
| **Forward Model Error ($\epsilon_{\text{model}}$)** | $\max_f |H_{\text{forge}}(f) - H_{\text{analytical}}(f)|$ | $\epsilon_{\text{model}} < 10^{-12}$ | $\epsilon_{\text{model}} > 10^{-6}$ |
| **DSP Continuity Error ($\epsilon_{\text{dsp}}$)** | $\max_f |20\log_{10}|\text{FFT}(\text{PCM})| - 20\log_{10}|H_{\text{model}}(f)||$ | $\epsilon_{\text{dsp}} < 0.05\,\text{dB}$ | $\epsilon_{\text{dsp}} > 0.5\,\text{dB}$ |
| **Intermediate State Access ($\mathcal{I}_{\text{state}}$)** | Number of intermediate phasors inspectable / Total intermediate states | $\mathcal{I}_{\text{state}} = 6 / 6 = 100\%$ | $\mathcal{I}_{\text{state}} < 100\%$ |
| **Causality Isolation ($\mathcal{C}_{\text{param}}$)** | Ability to isolate effect of single parameter change (e.g. $\Delta \tau$) on total response without recalculating unrelated branches | Supported natively in DAG and math kernels | Requires full black-box recomputation |

---

## 6. Independent Analytical Golden Strategy

To avoid circular reasoning (testing AcoustiForge against itself), all reference goldens must be derived independently:

```text
               ┌────────────────────────────────────────────────────────┐
               │         Independent Analytical Golden Source           │
               │   (Hand-derived equations, closed-form polynomials,    │
               │          evaluated in isolated test fixture)           │
               └───────────────────────────┬────────────────────────────┘
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                             │
                    ▼                                             ▼
     ┌─────────────────────────────┐               ┌─────────────────────────────┐
     │ AcoustiForge Implementation │               │  Analytical Golden Vector   │
     │      (Under Test)           │               │     (Isolated Reference)    │
     └──────────────┬──────────────┘               └──────────────┬──────────────┘
                    │                                             │
                    └──────────────────────┬──────────────────────┘
                                           │
                                           ▼
                            Compare: Error < Tolerance
```

### Golden Implementations:
1. **Linkwitz-Riley 4th-Order Analytical Formula:**
   $$H_{LR4, LP}(s) = \left(\frac{\omega_0^2}{s^2 + \sqrt{2}\omega_0 s + \omega_0^2}\right)^2$$
   $$H_{LR4, HP}(s) = \left(\frac{s^2}{s^2 + \sqrt{2}\omega_0 s + \omega_0^2}\right)^2$$
   *Evaluate analytically in continuous $s$-domain and discrete $z$-domain using bilinear transform without importing `acoustiforge.acoustic_math`.*
2. **Pure Phasor Delay Formula:**
   $$D(f) = \cos(2\pi f \tau) - j \sin(2\pi f \tau)$$
   *Computed directly via Python `math.cos` and `math.sin` on individual float scalar values.*

---

## 7. Falsification Criteria

The hypothesis that AcoustiForge provides an output-quality or engineering-control edge will be **falsified or significantly weakened** if any of the following occur:

1. **Equivalence of OOTB Inspectability:** An OOTB tool/library (e.g. standard SciPy or a free acoustic CAD tool) can provide identical intermediate phasor logging, provenance tracking, and headless CI automation with lower maintenance burden.
2. **Nondeterminism in Reference Solver:** AcoustiForge produces differing optimization solutions under identical input specifications due to floating-point reordering, unseeded operations, or thread scheduling.
3. **Semantic Drift in DSP Compilation:** Compiling an optimized filter specification into a `ComputeGraph` produces a PCM time-domain transfer function that deviates by $> 0.2\,\text{dB}$ or $> 2.0^\circ$ from the frequency-domain model.
4. **Computational Impracticability:** The deterministic reference implementation is too computationally slow to optimize a 2-way or 3-way system within acceptable engineering time ($< 5.0\,\text{seconds}$ for 2-way, $< 30.0\,\text{seconds}$ for 3-way).
5. **Lack of Physical Predictive Value:** Complex acoustic summation fails to predict experimental acoustic cancellation notches observed in physical measurements.

---

## 8. Edge Map

| Control Dimension | Current Repository Evidence | Test Experiment | Metric / Target | Expected Engineering Value | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Forward Model Transparency** | Phase 4D-2 summation formulas in `optimization.py` | Experiment A | Error $< 10^{-12}$, 100% intermediate state arrays available | Eliminates opaque simulation bugs; enables exact verification | **Ready to Test** |
| **Optimization Reproducibility** | Coordinate descent & golden section search in `optimization.py` | Experiment B | Repeatability variance $\sigma^2 = 0.0$ across 100 runs | Guaranteed repeatability in automated pipelines | **Ready to Test** |
| **Physical-Acoustic Fidelity** | Complex phasor summation tests in `test_acoustic_complex_summation.py` | Experiment C | Correctly predicts $\ge 15\,\text{dB}$ phase cancellation notch | Prevents magnitude-only acoustic design failures | **Ready to Test** |
| **DSP Executable Continuity** | `MultiWayGraphBuilder` and `ComputeGraph` | Experiment D | FFT(PCM) matches model within $0.05\,\text{dB}$ | Eliminates manual filter transcription errors between CAD & DSP | **Plausible; Needs E2E Test** |
| **OOTB Control Comparison** | Zero-dependency core architecture | Experiment E | Headless execution in $< 2\,\text{s}$ with standard library + NumPy | Enables version-controlled, automated CI acoustic testing | **Ready to Test** |

---

## 9. Recommended First Implementation Experiment

### Recommendation:
Implement **Experiment A + C Hybrid: The 2-Way Phase-Sensitive Forward Model & Inspectability Benchmark**.

### Rationale:
1. **Highest Scientific Leverage:** Validates both the complex physical modeling accuracy (Experiment C) and the complete intermediate state inspectability (Experiment A) in a single, clean test fixture.
2. **Zero Dependency on Future Phases:** Uses only frozen Phase 4C and verified Phase 4D-1/4D-2/4D-3 code already present in the repository. Does not require Phase 4D-4 (2-Way Optimizer) or Phase 5.
3. **Smallest Implementation Surface:** Can be implemented as a standalone verification suite (`tests/test_forward_model_transparency_benchmark.py`) with zero changes to production code.
4. **Direct Falsification Potential:** Immediately tests whether AcoustiForge's complex summation math matches hand-derived analytical goldens to machine precision ($10^{-12}$) and exposes all intermediate states.

### Exact Acceptance Criteria for First Experiment:
1. **Analytical Parity:** All 6 intermediate transfer functions ($H_{\text{driver}}$, $H_{\text{filter}}$, $A_{\text{gain}}$, $D_{\text{delay}}$, $H_{\text{branch}}$, $H_{\text{total}}$) match closed-form analytical equations within $\max |\Delta| < 10^{-12}$.
2. **Phase Cancellation Verification:** A $180^\circ$ acoustic phase mismatch at $2500\,\text{Hz}$ produces a destructive cancellation notch $\ge 20\,\text{dB}$ deep in complex summation, while magnitude-only summation incorrectly predicts a $0\,\text{dB}$ flat curve.
3. **Inspectability Guarantee:** All intermediate arrays are accessible via standard dataclass attributes of `MultiWaySummationResult` without inspecting private properties or modifying source code.
4. **Performance:** Computation of 1000-point complex summation across 2 branches executes in $< 1.0\,\text{millisecond}$.

---

## 10. Explicit Non-Goals

To maintain strict scientific and architectural discipline, the following are explicitly out of scope for this experimental program:
* **No GUI or Plotting Tool Development:** Experiments must run headlessly via automated test runners (`pytest`).
* **No Real-Time Audio Hardware Streaming:** PCM execution is tested via in-memory deterministic sample buffers, not hardware soundcards.
* **No Subjective Listening Tests:** Evaluation is strictly mathematical, physical, and architectural.
* **No Commercial Product Slandering / Marketing Rankings:** Focus is strictly on mathematical reproducibility, inspectability, and continuity.
* **No Production Source Code Modifications During Design:** Experimental test harnesses must test existing production APIs without modifying frozen baselines.
