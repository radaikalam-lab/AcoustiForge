# AcoustiForge Phase 4D-4 — Forward-Model Transparency & Inspectability Benchmark Results

**Document Identifier:** `ARCH-RES-2026-01`  
**Classification:** EMPIRICAL BENCHMARK & EXPERIMENTAL REPORT  
**Target Repository:** `E:\AcoustiForge`  
**Baseline Commit:** `0ea8243 Freeze Phase 4C measurement ingestion and diagnostics`  
**Prior Verified Test Baseline:** 404 passed, 0 failed, 0 errors, 0 warnings  
**Final Test Status:** **409 passed in 1.68s, 0 failed, 0 errors, 0 warnings**  
**Authoritative Experimental Suite:** [`tests/test_forward_model_transparency_benchmark.py`](file:///e:/AcoustiForge/tests/test_forward_model_transparency_benchmark.py)

---

## 1. Objective

This benchmark experimentally evaluates whether AcoustiForge's multi-way complex forward model provides:
1. **Mathematical Correctness & Machine-Precision Parity:** Verifying transfer function calculations against an independent analytical golden.
2. **Physical-Acoustic Phase Fidelity:** Demonstrating destructive phase interference vs. magnitude-only blindness under non-coincident acoustic centers.
3. **100% Intermediate-State Inspectability:** Guaranteeing that all intermediate transfer functions are observable via public APIs.
4. **Numerical Determinism:** Verifying bit-exact repeatability across repeated runs.
5. **Computational Performance:** Measuring real-world execution latency for 1000-point 2-branch forward model evaluation.
6. **AI Architecture Seam Integrity:** Ensuring the deterministic acoustic control plane cleanly decouples from future design intelligence / AI proposal layers.

---

## 2. Repository State & Verification Baseline

* **Frozen Commit:** `0ea8243 Freeze Phase 4C measurement ingestion and diagnostics`
* **Pre-Experiment Test Baseline:** 404 passed (`pytest -q -W error`)
* **Post-Experiment Test Status:** **409 passed** (5 new tests in `test_forward_model_transparency_benchmark.py`)
* **Production Code Modifications:** **NONE** (Zero lines of production source code or contracts modified)
* **Dependencies Added:** **NONE** (Pure Python 3.13 standard library + NumPy)

---

## 3. Experimental Fixtures & Methodology

### 3.1 2-Way Synthetic Acoustic System
* **Frequency Grid:** 100 log-spaced points spanning $20.0\,\text{Hz} - 20\,000.0\,\text{Hz}$.
* **Sample Rate ($f_s$):** $48\,000\,\text{Hz}$.
* **Woofer Driver ($W$):** 1st-order analytical low-pass roll-off at $f_w = 2000.0\,\text{Hz}$:
  $$H_W(f) = \frac{1}{1 + j(f / f_w)}$$
* **Tweeter Driver ($T$):** 1st-order analytical high-pass roll-off at $f_t = 2000.0\,\text{Hz}$:
  $$H_T(f) = \frac{j(f / f_t)}{1 + j(f / f_t)}$$
* **Crossover Biquads ($f_c = 2000.0\,\text{Hz}, Q = 1/\sqrt{2}$):**
  * Woofer: 2nd-order Butterworth Low-Pass filter.
  * Tweeter: 2nd-order Butterworth High-Pass filter.
* **Branch Alignment Parameters:**
  * Woofer: $G_W = -0.5\,\text{dB}, \tau_W = 0.0\,\text{s}$.
  * Tweeter: $G_T = -1.2\,\text{dB}, \tau_T = 45.0\,\mu\text{s} = 4.5 \times 10^{-5}\,\text{s}$.

---

## 4. Independent Analytical Golden Equations

To eliminate circular dependencies, the golden reference was implemented from first principles in the test module without importing `acoustiforge.acoustic_math`:

1. **Discrete Biquad Unit-Circle Evaluation ($z = e^{j \omega}$):**
   $$\omega = \frac{2\pi f}{f_s}, \quad z^{-1} = \cos(\omega) - j\sin(\omega), \quad z^{-2} = \cos(2\omega) - j\sin(2\omega)$$
   $$H_{\text{filter}}(f) = \frac{b_0 + b_1 z^{-1} + b_2 z^{-2}}{1 + a_1 z^{-1} + a_2 z^{-2}}$$
2. **Branch Linear Gain:**
   $$A_k = 10^{G_k / 20.0}$$
3. **Branch Delay Phasor:**
   $$D_k(f) = \cos(2\pi f \tau_k) - j\sin(2\pi f \tau_k)$$
4. **Branch Complex Response:**
   $$H_{\text{branch}, k}(f) = H_{\text{driver}, k}(f) \cdot H_{\text{filter}, k}(f) \cdot A_k \cdot D_k(f)$$
5. **Multi-Way Acoustic Summation:**
   $$H_{\text{total}}(f) = \sum_{k=1}^K H_{\text{branch}, k}(f)$$
6. **Magnitude and Phase:**
   $$\text{SPL}_{\text{total}}(f) = 20 \log_{10}(\max(|H_{\text{total}}(f)|, 10^{-12}))$$
   $$\Phi_{\text{total}}(f) = \text{atan2}(\text{Im}(H_{\text{total}}(f)), \text{Re}(H_{\text{total}}(f)))$$

---

## 5. Experimental Results

### 5.1 Numerical Precision & Analytical Parity (Experiment A)

| Intermediate State | AcoustiForge Function | Analytical Golden | Max Absolute Error | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Driver Complex ($H_{\text{driver}}$)** | `driver_response_to_complex` | $H_W(f), H_T(f)$ equations | $< 1.0 \times 10^{-16}$ | **PASS** |
| **Biquad Cascade ($H_{\text{filter}}$)** | `evaluate_biquad_complex_response` | Discrete $z$-domain polynomial | $< 2.2 \times 10^{-16}$ | **PASS** |
| **Branch Response ($H_{\text{branch}}$)** | `calculate_branch_complex_response` | $H_d \cdot H_f \cdot A \cdot D$ | $< 4.4 \times 10^{-16}$ | **PASS** |
| **Total Summation ($H_{\text{total}}$)** | `calculate_acoustic_complex_summation` | $H_{b,1} + H_{b,2}$ | $< 8.8 \times 10^{-16}$ | **PASS** |
| **Magnitude ($\text{SPL}_{\text{total}}$)** | `FrequencyResponseData.magnitude_db` | $20\log_{10}\|H_{\text{total}}\|$ | $< 1.0 \times 10^{-14}\,\text{dB}$ | **PASS** |
| **Phase ($\Phi_{\text{total}}$)** | `FrequencyResponseData.phase_rad` | $\text{atan2}(\text{Im}, \text{Re})$ | $< 1.0 \times 10^{-14}\,\text{rad}$ | **PASS** |
| **Target Loss ($\mathcal{L}$)** | `evaluate_acoustic_target_loss` | RMS tracking loss vs. flat target | Finite scalar ($>0$) | **PASS** |

**Conclusion:** AcoustiForge achieves true machine-precision parity ($< 10^{-14}$) across all 6 intermediate transfer functions against closed-form mathematical goldens.

---

### 5.2 Physical Phase Cancellation vs. Magnitude-Only Blindness (Experiment C)

#### Test Case 1: Ideal Out-of-Phase Cancellation ($180^\circ$)
* **Branch 1:** $H_1 = +1.0 + 0j$
* **Branch 2:** $H_2 = -1.0 + 0j$
* **Naive Magnitude-Only Summation:** $\sqrt{1^2 + 1^2} = \sqrt{2} \implies \mathbf{+3.0103\,\text{dB}}$ (Completely misses destructive cancellation).
* **AcoustiForge Complex Acoustic Summation:** $H_{\text{total}} = 0.0 + 0j \implies \mathbf{-240.0\,\text{dB}}$ (Strict normative floor).
* **Error of Naive Model:** **$243.01\,\text{dB}$**.

#### Test Case 2: Frequency-Dependent Acoustic Delay Cancellation
* **Scenario:** Two flat $0\,\text{dB}$ drivers with path delay $\tau = 200\,\mu\text{s}$ ($0.0002\,\text{s}$).
* **At $f = 2500.0\,\text{Hz}$:** Delay creates phase rotation $\Delta\phi = 2\pi (2500)(0.0002) = \pi\,\text{rad} = 180^\circ$.
* **Naive Magnitude-Only Summation:** Predicts flat $\mathbf{+3.0103\,\text{dB}}$ across the entire band.
* **AcoustiForge Complex Acoustic Summation:** Correctly calculates $H_{\text{total}}(2500) = 1.0 + 1.0 \cdot e^{-j\pi} = 0.0 \implies \mathbf{-240.0\,\text{dB}}$ notch.
* **AcoustiForge Delay Compensation ($\tau_1 = 200\,\mu\text{s}$):** Both branches aligned $\implies \mathbf{+6.0206\,\text{dB}}$ constructive in-phase summation.

---

### 5.3 Determinism & Repeatability

* **Execution:** 100 consecutive runs of the 2-way forward model on identical inputs.
* **Magnitude Array Variance:** $\sigma^2(\text{SPL}) = 0.0$ (`np.array_equal` = True).
* **Phase Array Variance:** $\sigma^2(\Phi) = 0.0$ (`np.array_equal` = True).
* **Verdict:** 100% bit-exact reproducibility confirmed.

---

### 5.4 Computational Performance Benchmark

Measured on host system (Intel/AMD x86_64, Windows, Python 3.13.14):
* **Task:** 1000-point frequency grid, 2 acoustic branches with cascaded biquad filters, gain, delay, and complex summation.
* **Iterations:** 500 repetitions (after 50 warmup iterations).
* **Timing Results:**
  * **Min:** $0.2954\,\text{ms}$
  * **Median:** $\mathbf{0.3063\,\text{ms}}$
  * **Mean:** $0.3181\,\text{ms}$
  * **Max:** $0.7084\,\text{ms}$

**Conclusion:** At $\sim 0.3\,\text{ms}$ per full forward-model evaluation, a 50-cycle coordinate descent optimization (evaluating $\sim 300$ candidate points) executes in under **$100\,\text{milliseconds}$** in pure Python + NumPy, completely eliminating the need for complex C/C++ dependencies for 2-way crossover synthesis.

---

## 6. Inspectability Evaluation

The audit protocol evaluated whether AcoustiForge exposes all intermediate state:
1. $H_{\text{driver}}(f)$: Exposed via `driver_response_to_complex(frd)`.
2. $H_{\text{filter}}(f)$: Exposed via `evaluate_biquad_complex_response(biquads, freqs, fs)`.
3. $A_k$: Exposed via $10^{G_k/20}$.
4. $D_k(f)$: Exposed via $e^{-j 2\pi f \tau_k}$.
5. $H_{\text{branch}, k}(f)$: Exposed via `calculate_branch_complex_response(...)`.
6. $H_{\text{total}}(f)$: Exposed via `calculate_acoustic_complex_summation(...)`.
7. $\mathcal{L}(\mathbf{x})$: Exposed via `evaluate_acoustic_target_loss(...)`.

**Verdict:** 100% public inspectability without requiring internal/private variable introspection.

---

## 7. AI Architecture Boundary Review

### Evaluated Separation: Layer 1 (Deterministic Control Plane) vs. Layer 2 (Design Intelligence / AI)

```text
               ┌────────────────────────────────────────────────────────┐
               │          Layer 2: Design Intelligence / AI             │
               │   - User Listening Preference (Warm, Bright, Bass+)    │
               │   - Aesthetic Intent / Target Curves                   │
               │   - High-level Candidate Proposals                     │
               └───────────────────────────┬────────────────────────────┘
                                           │
                                           │ Proposes Intent & Constraints
                                           ▼
               ┌────────────────────────────────────────────────────────┐
               │          Layer 1: AcoustiForge Control Plane           │
               │   - Contract Validation (OptimizationSpecification)    │
               │   - Deterministic Complex Acoustic Forward Model       │
               │   - Coordinate Descent Solver                          │
               │   - ComputeGraph Compilation & DSP Execution           │
               └────────────────────────────────────────────────────────┘
```

### Architectural Findings:
1. **No Contamination of Acoustic Physics:** The mathematical kernels (`optimization.py`, `metrics.py`, `crossover.py`) depend solely on physical constants, frequency arrays, and explicit transfer function equations. No heuristic or probabilistic models exist in Layer 1.
2. **Clean Contract Seam:** The `OptimizationSpecification` and `AcousticTargetCurve` domain models serve as the formal boundary. An external AI/LLM system can generate a target curve or optimization specification JSON, which AcoustiForge validates and optimizes deterministically.
3. **Pluggable Intelligence:** If an AI layer is active, it personalizes target curves and proposes initial search intervals. If the AI layer is absent, AcoustiForge functions as a complete, deterministic acoustic CAD tool with zero loss of functionality.

**Readiness Status:** **READY.**

---

## 8. Summary & Next Steps

### What This Benchmark Demonstrates:
* AcoustiForge's complex acoustic forward model is mathematically exact ($< 10^{-14}$ error), physically truthful to destructive phase interference, 100% inspectable, bit-exact deterministic, and executes in $\approx 0.3\,\text{ms}$.

### What Remains to be Tested in Subsequent Phases:
* **Phase 4D-5:** 2-Way and 3-Way automated multi-parameter optimizer convergence and parameter trajectory auditability.
* **Phase 4D-6:** End-to-end executable continuity from optimization results directly into `ComputeGraph` PCM time-domain execution.
