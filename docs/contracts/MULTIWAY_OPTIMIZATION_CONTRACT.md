# AcoustiForge Normative Contract: Multi-Way System Optimization & Complex Acoustic Summation

**Contract Identifier:** `CONTRACT-MULTIWAY-OPT-01`  
**Phase:** 4D  
**Status:** NORMATIVE / FROZEN SPECIFICATION  
**Layer:** Control / Acoustic Intelligence Plane (`acoustiforge.domain`, `acoustiforge.acoustic_math.optimization`)  
**Target Dependencies:** Python Standard Library (`math`, `typing`, `dataclasses`, `enum`, `pathlib`) + `numpy`  
**Prohibited Dependencies:** `scipy` (`scipy.optimize`, `scipy.signal`), `sounddevice`, `pyaudio`, `torch`, `matplotlib`, `pandas`

---

## 1. Purpose & Scope

This contract defines the exact mathematical formulations, numerical invariants, parameter search procedures, error taxonomy, and deterministic guarantees for:
1. Frequency-domain complex transfer function evaluation of cascaded biquad digital filters ($H_{\text{filter}}(e^{j\omega})$).
2. Multi-transducer phase-accurate vector acoustic superposition ($H_{\text{total}}(f)$).
3. Deterministic bounded numerical optimization of multi-way loudspeaker parameters (crossover cutoff frequencies $f_c$, branch sensitivity balancing gains $G_k$, and acoustic center alignment delays $\tau_k$) against an `AcousticTargetCurve`.

### Scope Containment:
- **In Scope:**
  - Complex transfer function evaluation of `BiquadCoefficients` cascades.
  - Vector complex summation of $K$ acoustic branches with individual driver frequency responses, filter transfer functions, gains, and delays.
  - Piecewise-linear log-frequency target curve evaluation via existing `evaluate_target_curve`.
  - Pure-NumPy bounded coordinate descent and 1D golden-section line search.
  - Joint optimization of crossover frequencies $f_c \in [f_{\text{min}}, f_{\text{max}}]$, branch gains $G_k \in [G_{\text{min}}, G_{\text{max}}]$, and driver delays $\tau_k \in [\tau_{\text{min}}, \tau_{\text{max}}]$.
  - Generation of standard `CrossoverSynthesisResult`, `GainDesignResult`, and `DriverAlignmentResult` objects that interface directly with existing `ThreeWayGraphBuilder` and `CrossoverGraphBuilder`.
- **Explicitly Deferred / Out of Scope:**
  - Multi-branch automated parametric EQ band allocation (deferred to preserve normative determinism).
  - Continuous gradient backpropagation or non-deterministic heuristic search.
  - Third-party optimization libraries (`scipy.optimize`, `nlopt`, `cvxpy`, `torch`).
  - Hardware audio I/O, realtime streaming, GUI, and 3D room simulation.

---

## 2. Terminology & Mathematical Symbols

| Symbol | Description | Units / Range |
| :--- | :--- | :--- |
| $f$ | Frequency | $\text{Hz} > 0$ |
| $f_s$ | Sampling frequency | $\text{Hz} \in \mathbb{Z}^+$ |
| $\omega$ | Normalized angular frequency ($\omega = 2\pi f / f_s$) | $\text{rad} \in [0, \pi]$ |
| $z$ | Discrete complex variable ($z = e^{j\omega}$) | Dimensionless complex |
| $H_{\text{biquad}}(f)$ | Complex transfer function of a single biquad filter | Dimensionless complex |
| $H_{\text{filter}, k}(f)$ | Composite complex transfer function of branch $k$'s cascaded biquads | Dimensionless complex |
| $H_{\text{driver}, k}(f)$ | Complex acoustic response of driver $k$ from measurement | Dimensionless complex |
| $G_k$ | Branch $k$ sensitivity adjustment gain | $\text{dB}$ |
| $g_k$ | Linear branch gain ($g_k = 10^{G_k/20}$) | Dimensionless float $\ge 0$ |
| $\tau_k$ | Branch $k$ acoustic center alignment delay | $\text{seconds} \ge 0$ |
| $H_{\text{total}}(f)$ | Total complex acoustic output at the listening position | Dimensionless complex |
| $M_{\text{total}}(f)$ | Total acoustic sound pressure magnitude | $\text{dB}$ |
| $\phi_{\text{total}}(f)$ | Total acoustic phase | $\text{rad} \in [-\pi, \pi]$ |
| $T(f)$ | Target acoustic magnitude profile | $\text{dB}$ |
| $\mathcal{L}$ | Objective loss function (tracking error + penalties) | $\text{dB}$ |

---

## 3. Complex Response Definitions

### 3.1 Complex Driver Response
For a driver measurement represented by `FrequencyResponseData` with discrete frequency vector $\mathbf{f} = [f_1, f_2, \dots, f_N]$, magnitude vector $\mathbf{M} = [M_1, M_2, \dots, M_N]$ in dB, and phase vector $\boldsymbol{\phi} = [\phi_1, \phi_2, \dots, \phi_N]$ in radians:

$$H_{\text{driver}, k}(f_i) = 10^{M_{k, i}/20} \cdot \left(\cos(\phi_{k, i}) + j \sin(\phi_{k, i})\right) = 10^{M_{k, i}/20} \cdot e^{j \phi_{k, i}}$$

#### Normative Phase Policy:
1. If `phase_rad` is provided, it MUST be an owned contiguous float64 array of shape `(N,)` with valid finite values in $[-\pi, \pi]$.
2. If `phase_rad` is `None`, the driver response is treated as zero-phase ($\phi_{k, i} = 0.0\text{ rad}$ for all $i$), yielding $H_{\text{driver}, k}(f_i) = 10^{M_{k, i}/20} + j 0.0$.

### 3.2 Complex Biquad Filter Response
For a digital biquad filter with normalized coefficients `BiquadCoefficients(b0, b1, b2, a1, a2)` (with implicit $a_0 = 1.0$), the frequency response at frequency $f$ with sample rate $f_s$ is evaluated on the unit circle $z = e^{j 2\pi f / f_s}$:

$$z^{-1} = e^{-j 2\pi f / f_s} = \cos\left(\frac{2\pi f}{f_s}\right) - j \sin\left(\frac{2\pi f}{f_s}\right)$$
$$z^{-2} = e^{-j 4\pi f / f_s} = \cos\left(\frac{4\pi f}{f_s}\right) - j \sin\left(\frac{4\pi f}{f_s}\right)$$

$$N(f) = b_0 + b_1 z^{-1} + b_2 z^{-2}$$
$$D(f) = 1.0 + a_1 z^{-1} + a_2 z^{-2}$$

$$H_{\text{biquad}}(f) = \frac{N(f)}{D(f)}$$

#### Numerical Stability & Singularity Invariant:
For a stable biquad filter with poles strictly inside the unit circle ($|p_{1,2}| < 1$), $|D(f)| > 0$ for all $0 \le f \le f_s/2$.
If at any evaluated frequency $|D(f)| < 10^{-12}$, the implementation MUST raise `UnstableFilterError` or `NumericalEvaluationError`. The denominator MUST NOT be silently clamped or modified.

#### Biquad Cascade Composition:
For a cascade of $M$ biquad sections $\mathbf{B} = [B_1, B_2, \dots, B_M]$:
$$H_{\text{filter}}(f) = \prod_{m=1}^M H_{\text{biquad}, m}(f)$$
If $M = 0$, $H_{\text{filter}}(f) = 1.0 + j 0.0$.

---

## 4. Complex Acoustic Summation Contract

For a multi-way loudspeaker system with $K$ branches ($K \ge 1$), where each branch $k$ has:
1. Measured driver response $H_{\text{driver}, k}(f)$
2. Cascaded branch filter transfer function $H_{\text{filter}, k}(f)$
3. Branch sensitivity gain $G_k$ in dB (linear gain $g_k = 10^{G_k/20}$)
4. Acoustic time-alignment delay $\tau_k$ in seconds

The branch complex transfer function is:
$$H_{\text{branch}, k}(f) = H_{\text{driver}, k}(f) \cdot H_{\text{filter}, k}(f) \cdot 10^{G_k/20} \cdot e^{-j 2\pi f \tau_k}$$

The total complex acoustic output at the measurement position is:
$$H_{\text{total}}(f) = \sum_{k=1}^K H_{\text{branch}, k}(f)$$

### Output Magnitude & Phase Conversion:
The composite complex response $H_{\text{total}}(f)$ is converted to a canonical `FrequencyResponseData` instance:
1. **Magnitude (dB):**
   $$M_{\text{total}}(f) = 20 \log_{10}\left(\max\left(|H_{\text{total}}(f)|, 10^{-12}\right)\right)$$
   *(Floor of $10^{-12}$ enforces a strict lower bound of $-240.0\text{ dB}$ to prevent $-\infty$ singularities).*
2. **Phase (radians):**
   $$\phi_{\text{total}}(f) = \text{arctan2}\left(\text{Im}(H_{\text{total}}(f)), \text{Re}(H_{\text{total}}(f))\right) \in [-\pi, \pi]$$

### Analytical Phasor Goldens:
1. **In-Phase Summation ($0^\circ$):**
   $$H_1 = 1.0 + j 0.0,\quad H_2 = 1.0 + j 0.0 \implies H_{\text{total}} = 2.0 + j 0.0 \implies M_{\text{total}} = 20\log_{10}(2) \approx 6.0205999\text{ dB}$$
2. **Quadrature Summation ($90^\circ$):**
   $$H_1 = 1.0 + j 0.0,\quad H_2 = 0.0 + j 1.0 \implies H_{\text{total}} = 1.0 + j 1.0 \implies |H_{\text{total}}| = \sqrt{2} \implies M_{\text{total}} \approx 3.01029996\text{ dB}$$
3. **Out-of-Phase Cancellation ($180^\circ$):**
   $$H_1 = 1.0 + j 0.0,\quad H_2 = -1.0 + j 0.0 \implies H_{\text{total}} = 0.0 + j 0.0 \implies M_{\text{total}} = -240.0\text{ dB},\quad |H_{\text{total}}| \le 10^{-15}$$

---

## 5. Frequency Grid Requirements & Invariants

1. **Grid Uniformity Across Drivers:**
   In multi-driver summation and optimization, all $K$ driver `FrequencyResponseData` instances MUST share an identical discrete frequency vector $\mathbf{f}$:
   $$\mathbf{f}_1 \equiv \mathbf{f}_2 \equiv \dots \equiv \mathbf{f}_K$$
   If `driver_a.frequencies_hz` and `driver_b.frequencies_hz` differ in length, start frequency, end frequency, or point-by-point values by more than $10^{-6}\text{ Hz}$, the function MUST raise `InvalidParameterError` (or `FrequencyGridMismatchError`).
2. **No Silent Interpolation:**
   The summation engine and optimizer MUST NOT silently interpolate, extrapolate, or resample driver measurement grids. Resampling, if required, must be performed explicitly prior to calling the optimization engine.
3. **Frequency Bounds:**
   All frequencies in the grid must satisfy $0 < f_i \le f_s/2$ (strictly positive and within the Nyquist limit).

---

## 6. Objective Loss Function

The objective loss $\mathcal{L}$ evaluates the discrepancy between the synthesized total acoustic magnitude $M_{\text{total}}(f)$ and the target curve $T(f)$ across the active optimization band $[f_{\text{min}}, f_{\text{max}}]$:

$$\mathcal{L}(\mathbf{p}) = E_{\text{rms}}(\mathbf{p}) + w_r \cdot R(\mathbf{p}) + w_\tau \cdot P_\tau(\mathbf{p})$$

### 6.1 RMS Tracking Error ($E_{\text{rms}}$)
Let $\mathcal{I}_{\text{band}} = \{i \mid f_{\text{min}} \le f_i \le f_{\text{max}}\}$ be the indices of the discrete measurement frequencies lying within $[f_{\text{min}}, f_{\text{max}}]$. Let $N_{\text{band}} = |\mathcal{I}_{\text{band}}|$ ($N_{\text{band}} \ge 1$).

$$E_{\text{rms}} = \sqrt{\frac{1}{N_{\text{band}}} \sum_{i \in \mathcal{I}_{\text{band}}} \left(M_{\text{total}}(f_i) - T(f_i)\right)^2}$$

where $T(f_i) = \text{evaluate\_target\_curve}(\text{curve}, f_i)$ using the existing Phase 3C piecewise-linear log-frequency interpolation.

### 6.2 Crossover Passband Ripple Penalty ($R$)
To prevent solutions with high RMS flatness that exhibit localized sharp peaks/dips in crossover transition regions:
$$R = \max_{i \in \mathcal{I}_{\text{band}}} \left|M_{\text{total}}(f_i) - T(f_i)\right| - \min_{i \in \mathcal{I}_{\text{band}}} \left|M_{\text{total}}(f_i) - T(f_i)\right|$$
*(Default weight: $w_r = 0.0$. If enabled, $w_r \ge 0.0$).*

### 6.3 Alignment Delay Regularization Penalty ($P_\tau$)
To discourage unnecessarily large time delays:
$$P_\tau = \sum_{k=1}^K \left(\frac{\tau_k}{\tau_{\text{max}, k}}\right)^2$$
*(Default weight: $w_\tau = 0.0$. If enabled, $w_\tau \ge 0.0$).*

---

## 7. Optimization Search Procedure & Determinism

### 7.1 Parameter Space & Bounds
The parameter vector $\mathbf{p}$ comprises:
- **2-Way System:** $\mathbf{p} = [f_c, G_2, \tau_2]$ (with $G_1 = 0\text{ dB}, \tau_1 = 0\text{ s}$ as reference).
- **3-Way System:** $\mathbf{p} = [f_{\text{low}}, f_{\text{high}}, G_{\text{mid}}, G_{\text{tweet}}, \tau_{\text{mid}}, \tau_{\text{tweet}}]$ (with woofer as reference $G_{\text{woof}} = 0, \tau_{\text{woof}} = 0$).

Each parameter is constrained within strict physical bounds:
- $f_{c, 1} \in [f_{\text{crossover, min}}, f_{\text{crossover, max}}]$
- $f_{\text{crossover, min}} \le f_{\text{low}} \le f_{\text{high}} \le f_{\text{crossover, max}}$ with $f_{\text{high}} \ge 1.5 \cdot f_{\text{low}}$ (minimum 0.58-octave separation).
- $G_k \in [G_{\text{min}}, G_{\text{max}}]$ (typically $[-12.0\text{ dB}, +12.0\text{ dB}]$).
- $\tau_k \in [0.0, \tau_{\text{max}}]$ (typically $[0.0, 5.0\text{ ms}]$).

### 7.2 Search Procedure (Pure NumPy Coordinate Descent)
1. **Candidate Grid Initialization:**
   Generate a deterministic log-spaced grid of $N_f$ crossover frequency candidates and linear grid of $N_\tau$ delay candidates.
   Evaluate the baseline parameter candidate $\mathbf{p}_0$ (initial specification) and all initial grid points.
   Select the candidate with the lowest loss as $\mathbf{p}^{(0)}$.
2. **Iterative Coordinate Descent:**
   For iteration $t = 1, 2, \dots, N_{\text{max}}$:
   - For each parameter index $j$:
     - Perform a 1D bounded golden-section search over $[p_{j, \text{min}}, p_{j, \text{max}}]$ with fixed iteration budget $N_{\text{golden}} = 20$.
     - Update parameter $p_j^{(t)}$ if the candidate reduces loss.
   - Compute $\Delta \mathcal{L} = \mathcal{L}(\mathbf{p}^{(t-1)}) - \mathcal{L}(\mathbf{p}^{(t)})$.
   - If $\Delta \mathcal{L} < \epsilon_{\text{conv}}$ ($10^{-5}\text{ dB}$) or $\Delta \mathcal{L} / \mathcal{L}(\mathbf{p}^{(t-1)}) < 10^{-5}$, terminate search.
3. **Hard Monotonicity & Best-Candidate Selection:**
   $$\mathbf{p}^* = \arg\min_{\mathbf{p} \in \{\mathbf{p}_0, \mathbf{p}^{(1)}, \dots, \mathbf{p}^{(T)}\}} \mathcal{L}(\mathbf{p})$$
   The optimizer is mathematically guaranteed to return a solution with $\mathcal{L}(\mathbf{p}^*) \le \mathcal{L}(\mathbf{p}_0)$.

### 7.3 Determinism & Tie-Breaking
1. All calculations must use standard IEEE 754 float64 arithmetic.
2. Given identical inputs, bounds, and settings, the optimizer must produce bit-exact identical parameter outputs across runs.
3. **Tie-Breaking Rule:** If two evaluated parameter candidates $\mathbf{p}_a$ and $\mathbf{p}_b$ yield $|\mathcal{L}(\mathbf{p}_a) - \mathcal{L}(\mathbf{p}_b)| \le 10^{-12}$, the optimizer MUST deterministically select the candidate that is lexicographically smaller: $\mathbf{p}_a < \mathbf{p}_b$.

---

## 8. Domain Value Types

### 8.1 `OptimizationSpecification`
```python
@dataclass(frozen=True, slots=True)
class OptimizationSpecification:
    target_curve: AcousticTargetCurve
    crossover_family: CrossoverFamily
    crossover_order: int
    frequency_range_hz: tuple[float, float]
    crossover_bounds_hz: tuple[float, float]
    gain_bounds_db: tuple[float, float] = (-12.0, 12.0)
    delay_bounds_seconds: tuple[float, float] = (0.0, 0.005)
    ripple_weight: float = 0.0
    delay_weight: float = 0.0
    max_iterations: int = 50
    convergence_tolerance_db: float = 1e-5
```

### 8.2 `OptimizationResult`
```python
@dataclass(frozen=True, slots=True)
class OptimizationResult:
    crossover_result: CrossoverSynthesisResult  # (or tuple for 3-way)
    gain_results: dict[str, GainDesignResult]
    alignment_results: dict[str, DriverAlignmentResult]
    predicted_response: FrequencyResponseData
    initial_metrics: AcousticMetricsResult
    optimized_metrics: AcousticMetricsResult
    initial_loss_db: float
    final_loss_db: float
    converged: bool
    iterations_completed: int
```

---

## 9. Compatibility & Builder Integration

`OptimizationResult` generates standard, validated instances of:
- `CrossoverSynthesisResult`
- `GainDesignResult`
- `DriverAlignmentResult`

These results plug directly into:
1. `CrossoverGraphBuilder.build_2way_graph`
2. `ThreeWayGraphBuilder.build_3way_graph`

Zero changes to existing builder signatures or `ComputeGraph` contracts are permitted.

---

## 10. Error Taxonomy

| Exception | Condition |
| :--- | :--- |
| `InvalidParameterError` | Mismatched frequency grids across drivers, non-positive sample rate, or inverted parameter bounds ($f_{\text{max}} \le f_{\text{min}}$). |
| `InvalidSpecificationError` | Crossover order not in (2, 4, 8), or invalid target curve points. |
| `UnstableFilterError` | Biquad denominator magnitude $< 10^{-12}$ on the unit circle. |
| `NumericalEvaluationError` | Non-finite loss value (NaN / Inf) encountered during search evaluation. |

---

## 11. Acceptance Verification Criteria

```text
4D-A  Phase 4C frozen
4D-B  Complex biquad transfer function evaluation verified to machine precision (< 1e-12 error)
4D-C  Multi-transducer complex summation verified against analytical phasor goldens
4D-D  Strict frequency grid matching verified (mismatched grids raise InvalidParameterError)
4D-E  Pure-NumPy bounded optimizer verified (zero SciPy imports)
4D-F  Deterministic tie-breaking and bit-exact reproducibility across runs
4D-G  Hard loss monotonicity verified (final_loss_db <= initial_loss_db)
4D-H  Parameter bounds preservation verified (fc, G, tau strictly within bounds)
4D-I  Independent analytical 2-way and 3-way golden systems converge to known unique optima
4D-J  Output OptimizationResult integrates directly with ThreeWayGraphBuilder without builder modification
4D-K  Full regression baseline (>= 360 tests) passing with 0 failures, 0 errors, 0 warnings
```
