# AcoustiForge — Phase 1B Biquad Filter Contract & Mathematical Foundation

**Project:** AcoustiForge  
**Architecture:** ACE — Acoustic Compute Engine  
**Phase:** 1B — Biquad Filter Contract & Mathematical Foundation (Corrected & Frozen in Phase 1B.1)  
**Status:** MATHEMATICAL CONTRACT SPECIFICATION (FROZEN — NO IMPLEMENTATION)  

---

## 1. Purpose

This document establishes the **normative mathematical and numerical contract** for the second-order Infinite Impulse Response (IIR) Biquad filter family in AcoustiForge.

It defines with absolute mathematical precision:
- The canonical discrete transfer function $H(z)$.
- Coefficient normalization and unambiguous sign conventions.
- Complete parameter domains for frequency $f_0$, quality factor $Q$, bandwidth $\text{BW}$, shelf slope $S$, and gain $G_{\text{dB}}$.
- Mathematical formulations for all seven canonical Audio EQ filter families.
- Discrete-time stability criteria and numerical stability test algorithms.
- Direct Form II Transposed (DF-II-T) reference difference and state equations.
- Multi-tier numerical conformance tolerances and golden reference vector strategies.
- Target-specific mapping considerations (including ARM CMSIS-DSP).

> [!NOTE]
> **Signal-Domain Agnostic Contract:** The Biquad mathematical contract is signal-domain agnostic. It operates on sampled numerical channels and does not encode audio-specific or other physical-domain semantics. Domain-specific meaning, units, calibration, provenance, and interpretation remain properties of the surrounding signal/object contract.

This specification serves as the authoritative mathematical foundation for the upcoming `BiquadNode` implementation (Phase 1C). **Zero production DSP code or filter loops are implemented during Phase 1B.**

---

## 2. Governing Authorities & Precedence

The authority hierarchy governing this phase is:

1. `prompts/MASTER_PROMPT.md` (Highest normative authority)
2. `docs/contracts/PCM_CONTRACT.md` (Canonical PCM representation & validation)
3. `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md` (Runtime neutrality & storage decoupling)
4. `docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md` (Frozen DSP node lifecycle, state separation, and parameter atomicity)
5. This specification document

---

## 3. Reference Sources

1. **Robert Bristow-Johnson (RBJ):** *"Cookbook formulae for audio equalizer biquad filter coefficients"*, Audio Engineering Society (AES) / Web Reference (Audio EQ Cookbook).
2. **Alan V. Oppenheim, Ronald W. Schafer:** *"Discrete-Time Signal Processing"*, 3rd Edition, Pearson (1999/2009).
3. **Udo Zölzer (Ed.):** *"DAFX: Digital Audio Effects"*, 2nd Edition, John Wiley & Sons (2011).
4. **IEEE 754-2019:** *"IEEE Standard for Floating-Point Arithmetic"*.

> [!IMPORTANT]
> **Reference vs. Normative Contract:** While RBJ's Audio EQ Cookbook serves as the primary mathematical reference source, this document constitutes the **ACE Normative Contract**. Where alternative implementation conventions exist in literature (e.g., coefficient sign inversions or bandwidth definitions), the explicit specifications in this document are binding.

---

## 4. ACE Canonical Transfer Function

The canonical transfer function for an AcoustiForge second-order IIR biquad section in the $z$-domain is defined as:

$$H(z) = \frac{Y(z)}{X(z)} = \frac{b_0 + b_1 z^{-1} + b_2 z^{-2}}{a_0 + a_1 z^{-1} + a_2 z^{-2}}$$

Where:
- $X(z)$ is the $z$-transform of the discrete-time input sequence $x[n]$.
- $Y(z)$ is the $z$-transform of the discrete-time output sequence $y[n]$.
- $\{b_0, b_1, b_2\}$ are the numerator (feedforward / zero) coefficients.
- $\{a_0, a_1, a_2\}$ are the denominator (feedback / pole) coefficients.
- $a_0 \neq 0$ (normalized to $a_0 \equiv 1.0$ at the contract boundary).

---

## 5. Coefficient Sign Convention & Difference Equation

To eliminate sign ambiguities across signal processing literature and hardware libraries, AcoustiForge normatively establishes:

### 5.1 Denominator Polynomial Sign Convention
The denominator polynomial $A(z)$ is written with positive summation signs:

$$A(z) = 1 + a_1 z^{-1} + a_2 z^{-2}$$

### 5.2 Discrete-Time Difference Equation
Transforming $H(z) = \frac{B(z)}{A(z)}$ into the time domain yields the canonical difference equation:

$$y[n] = b_0 x[n] + b_1 x[n-1] + b_2 x[n-2] - a_1 y[n-1] - a_2 y[n-2]$$

> [!CAUTION]
> **Sign Notice:** Denominator coefficients $a_1$ and $a_2$ are **subtracted** during time-domain sample synthesis. When coefficients are computed from the transfer function $A(z) = 1 + a_1 z^{-1} + a_2 z^{-2}$, $a_1$ and $a_2$ retain their algebraic signs as defined in Section 10.

---

## 6. Coefficient Normalization

All raw analog biquad prototypes mapped through the Bilinear Transform produce six raw coefficients: $\{b_0, b_1, b_2, a_0, a_1, a_2\}$.

### 6.1 Normalization Pre-Condition
$$a_0 \neq 0$$
If $a_0 = 0$ (or $|a_0| < 10^{-15}$), the filter is mathematically singular and MUST be rejected with `InvalidParameterError`.

### 6.2 Normalization Equations
Every coefficient is divided by $a_0$:

$$b_0' = \frac{b_0}{a_0}, \quad b_1' = \frac{b_1}{a_0}, \quad b_2' = \frac{b_2}{a_0}, \quad a_1' = \frac{a_1}{a_0}, \quad a_2' = \frac{a_2}{a_0}$$

### 6.3 Normalized Vector Representation
Within the ACE computational boundary, a normalized biquad coefficient set is represented as a 5-element tuple/vector:

$$\mathbf{w} = [b_0',\, b_1',\, b_2',\, a_1',\, a_2'] \quad \text{with implicit } a_0' \equiv 1.0$$

---

## 7. Parameter Model & Validation Domains

| Parameter | Symbol | Type | Mathematical Domain | AcoustiForge Valid Range | Units / Representation |
|---|---|---|---|---|---|
| **Sampling Frequency** | $f_s$ | Integer | $f_s > 0$ | Standard: $44100, 48000, 88200, 96000$ (any $f_s \ge 8000$) | Hertz ($\text{Hz}$) |
| **Corner / Center Frequency** | $f_0$ | Float | $0 < f_0 < \frac{f_s}{2}$ | $1.0 \le f_0 \le 0.499 \cdot f_s$ | Hertz ($\text{Hz}$) |
| **Quality Factor** | $Q$ | Float | $Q > 0$ | $0.05 \le Q \le 100.0$ | Dimensionless scalar |
| **Bandwidth** | $\text{BW}$ | Float | $\text{BW} > 0$ | $0.01 \le \text{BW} \le 10.0$ | Octaves |
| **Shelf Slope** | $S$ | Float | $S > 0$ | $0.1 \le S \le 2.0$ ($S=1$ is max monotonic) | Dimensionless scalar |
| **Filter Gain** | $G_{\text{dB}}$ | Float | $-\infty < G_{\text{dB}} < +\infty$ | $-80.0 \le G_{\text{dB}} \le +40.0$ | Decibels ($\text{dB}$) |

---

## 8. Frequency Semantics

### 8.1 Normalized Angular Frequency
$$\omega_0 = 2\pi \frac{f_0}{f_s}$$
- **Domain:** $\omega_0 \in (0, \pi)$ radians per sample.
- **$\omega_0 = 0$ (DC boundary):** Poles/zeros collapse onto $z = 1.0$; mathematical singularity. Parameter values $f_0 \le 0$ MUST be rejected.
- **$\omega_0 = \pi$ (Nyquist boundary):** $\tan\left(\frac{\omega_0}{2}\right) \to \infty$; Bilinear Transform singularity. Parameter values $f_0 \ge \frac{f_s}{2}$ MUST be rejected.

---

## 9. Q, Bandwidth, and Shelf Slope Semantics

The intermediate resonance/bandwidth parameter $\alpha$ determines the shape of the filter transitions:

### 9.1 Parameterization by Quality Factor ($Q$)
Used for standard parametric EQ, peaking, notch, and resonant lowpass/highpass filters:

$$\alpha = \frac{\sin\omega_0}{2Q}$$

### 9.2 Parameterization by Bandwidth in Octaves ($\text{BW}$)
Relates octave bandwidth $\text{BW}$ to $Q$:

$$\alpha = \sin\omega_0 \cdot \sinh\left( \frac{\ln 2}{2} \cdot \text{BW} \cdot \frac{\omega_0}{\sin\omega_0} \right)$$

### 9.3 Parameterization by Shelf Slope ($S$)
Used for LowShelf and HighShelf filters. $S = 1.0$ produces the steepest monotonic slope without shelf overshoot/undershoot:

$$\alpha = \frac{\sin\omega_0}{2} \sqrt{\left(A + \frac{1}{A}\right)\left(\frac{1}{S} - 1\right) + 2}$$

### 9.4 Linear Amplitude Parameter ($A$)
For peaking and shelf filters:

$$A = 10^{\frac{G_{\text{dB}}}{40}} = \sqrt{10^{\frac{G_{\text{dB}}}{20}}}$$

---

## 10. Filter Family Mathematical Formulations

All formulas compute raw coefficients $\{b_0, b_1, b_2, a_0, a_1, a_2\}$, which are subsequently normalized by dividing by $a_0$.

### 10.1 LowPass Filter (LPF)
- **Parameters:** $f_0, Q, f_s$
- **Transfer Function Characteristics:** Unity gain at DC ($H(1) = 1.0$), $-40\,\text{dB/decade}$ attenuation at high frequencies, gain $= Q$ at $f_0$.
- **Equations:**
  $$b_0 = \frac{1 - \cos\omega_0}{2}, \quad b_1 = 1 - \cos\omega_0, \quad b_2 = \frac{1 - \cos\omega_0}{2}$$
  $$a_0 = 1 + \alpha, \quad a_1 = -2\cos\omega_0, \quad a_2 = 1 - \alpha$$

### 10.2 HighPass Filter (HPF)
- **Parameters:** $f_0, Q, f_s$
- **Transfer Function Characteristics:** Total attenuation at DC ($H(1) = 0.0$), unity gain at Nyquist ($H(-1) = 1.0$), gain $= Q$ at $f_0$.
- **Equations:**
  $$b_0 = \frac{1 + \cos\omega_0}{2}, \quad b_1 = -(1 + \cos\omega_0), \quad b_2 = \frac{1 + \cos\omega_0}{2}$$
  $$a_0 = 1 + \alpha, \quad a_1 = -2\cos\omega_0, \quad a_2 = 1 - \alpha$$

### 10.3 BandPass Filter (BPF — Constant Skirt Gain, Peak Gain $= Q$)
- **Parameters:** $f_0, Q, f_s$
- **Transfer Function Characteristics:** Zero gain at DC and Nyquist; peak gain $= Q$ ($|H(e^{j\omega_0})| = Q$).
- **Equations:**
  $$b_0 = \frac{\sin\omega_0}{2} = Q\alpha, \quad b_1 = 0, \quad b_2 = -\frac{\sin\omega_0}{2} = -Q\alpha$$
  $$a_0 = 1 + \alpha, \quad a_1 = -2\cos\omega_0, \quad a_2 = 1 - \alpha$$

### 10.4 Notch Filter (BandStop / BRF)
- **Parameters:** $f_0, Q, f_s$
- **Transfer Function Characteristics:** Unity gain at DC and Nyquist; complete null ($H(e^{j\omega_0}) = 0$) at $f_0$.
- **Equations:**
  $$b_0 = 1, \quad b_1 = -2\cos\omega_0, \quad b_2 = 1$$
  $$a_0 = 1 + \alpha, \quad a_1 = -2\cos\omega_0, \quad a_2 = 1 - \alpha$$

### 10.5 Peaking Equalizer Filter (Peak / Bell)
- **Parameters:** $f_0, Q, G_{\text{dB}}, f_s$
- **Transfer Function Characteristics:** Unity gain ($0\,\text{dB}$) at DC and Nyquist; peak/cut gain $= 10^{G_{\text{dB}}/20}$ at $f_0$.
- **Equations:**
  $$b_0 = 1 + \alpha A, \quad b_1 = -2\cos\omega_0, \quad b_2 = 1 - \alpha A$$
  $$a_0 = 1 + \frac{\alpha}{A}, \quad a_1 = -2\cos\omega_0, \quad a_2 = 1 - \frac{\alpha}{A}$$

### 10.6 LowShelf Filter
- **Parameters:** $f_0, S, G_{\text{dB}}, f_s$
- **Transfer Function Characteristics:** Gain $= 10^{G_{\text{dB}}/20}$ at DC; unity gain ($0\,\text{dB}$) at Nyquist.
- **Equations:**
  $$b_0 = A \left[ (A+1) - (A-1)\cos\omega_0 + 2\sqrt{A}\alpha \right]$$
  $$b_1 = 2A \left[ (A-1) - (A+1)\cos\omega_0 \right]$$
  $$b_2 = A \left[ (A+1) - (A-1)\cos\omega_0 - 2\sqrt{A}\alpha \right]$$
  $$a_0 = (A+1) + (A-1)\cos\omega_0 + 2\sqrt{A}\alpha$$
  $$a_1 = -2 \left[ (A-1) + (A+1)\cos\omega_0 \right]$$
  $$a_2 = (A+1) + (A-1)\cos\omega_0 - 2\sqrt{A}\alpha$$

### 10.7 HighShelf Filter
- **Parameters:** $f_0, S, G_{\text{dB}}, f_s$
- **Transfer Function Characteristics:** Unity gain ($0\,\text{dB}$) at DC; gain $= 10^{G_{\text{dB}}/20}$ at Nyquist.
- **Equations:**
  $$b_0 = A \left[ (A+1) + (A-1)\cos\omega_0 + 2\sqrt{A}\alpha \right]$$
  $$b_1 = -2A \left[ (A-1) + (A+1)\cos\omega_0 \right]$$
  $$b_2 = A \left[ (A+1) + (A-1)\cos\omega_0 - 2\sqrt{A}\alpha \right]$$
  $$a_0 = (A+1) - (A-1)\cos\omega_0 + 2\sqrt{A}\alpha$$
  $$a_1 = 2 \left[ (A-1) - (A+1)\cos\omega_0 \right]$$
  $$a_2 = (A+1) - (A-1)\cos\omega_0 - 2\sqrt{A}\alpha$$

---

## 11. Stability Mathematics & Validation Algorithm

A discrete-time linear time-invariant system is Bounded-Input Bounded-Output (BIBO) stable if and only if all poles of $H(z)$ lie strictly inside the open unit disk in the complex plane ($|z_p| < 1.0$).

### 11.1 Pole Calculation
For normalized denominator $A(z) = 1 + a_1 z^{-1} + a_2 z^{-2}$, the poles are the roots of the quadratic equation $z^2 + a_1 z + a_2 = 0$:

$$z_{1,2} = \frac{-a_1 \pm \sqrt{a_1^2 - 4a_2}}{2}$$

- If $a_1^2 - 4a_2 \ge 0$: Poles are real.
- If $a_1^2 - 4a_2 < 0$: Poles are a complex-conjugate pair with magnitude $|z_p| = \sqrt{a_2}$.

### 11.2 Strict Mathematical Stability (Schur / Jury Criterion)
The mathematical stability definition is independent of any runtime, precision, compiler, processor, or epsilon.

Exact necessary and sufficient mathematical stability for a second-order discrete system is given by the strict Schur / Jury criteria:
1. Condition 1: $1 - a_2 > 0$  (or equivalently $|a_2| < 1.0$)
2. Condition 2: $1 + a_1 + a_2 > 0$
3. Condition 3: $1 - a_1 + a_2 > 0$

### 11.3 Numerical Implementation Stability Guard (Evaluation Policy)
In finite-precision floating-point implementations, evaluation near the stability boundary may employ an implementation-specific numerical guard $\epsilon_{\text{stab}}$:

$$\text{Implementation Guard} \iff (|a_2| \le 1.0 - \epsilon_{\text{stab}}) \land (1.0 + a_1 + a_2 > \epsilon_{\text{stab}}) \land (1.0 - a_1 + a_2 > \epsilon_{\text{stab}})$$

> [!IMPORTANT]
> **Classification:** The epsilon guard (e.g., $\epsilon_{\text{stab}} = 10^{-7}$) is strictly **numerical evaluation / implementation / test policy**, NOT part of the universal ACE mathematical stability definition. The mathematical stability contract is governed strictly by the Schur/Jury conditions in Section 11.2.

---

## 12. Direct Form II Transposed (DF-II-T) Reference Realization

In accordance with DEC-02, **Direct Form II Transposed (DF-II-T)** is selected as the canonical mathematical realization for the Phase 1B Python reference model.

```
       x[n] ─────────┬─────────────( b0 )─────────────(+)───────> y[n]
                     │                                 ▲
                     │                                 │
                    [z^-1] s1[n-1] ◄───────────────────┤
                     │                                 │
                     ├───( b1 )────────(+)─────────────┤
                     │                  ▲              │
                     │                  │             (-a1)
                    [z^-1] s2[n-1] ◄────┤              │
                     │                  │              │
                     └───( b2 )────────(+)─────────────┴──────── y[n]
                                        ▲
                                       (-a2)
```

### 12.1 State Variables per Channel
For channel $c$, the internal state consists of two scalar registers:

$$\mathbf{S}^{(c)} = [s_1^{(c)}, s_2^{(c)}]$$

### 12.2 Difference Equations (Executed per Sample $n$)
For input sample $x[n]$ on channel $c$:

$$y[n] = b_0 x[n] + s_1[n-1]$$
$$s_1[n] = b_1 x[n] - a_1 y[n] + s_2[n-1]$$
$$s_2[n] = b_2 x[n] - a_2 y[n]$$

### 12.3 Initial and Reset State
$$s_1^{(c)} = 0.0, \quad s_2^{(c)} = 0.0 \quad \forall c \in [0, C-1]$$

---

## 13. Numerical Precision Model

AcoustiForge strictly separates calculation precision from runtime storage precision:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Parameter & Coefficient Derivation (Host / Reference)               │
│    • Performed in double-precision IEEE 754 float64                    │
│    • Prevents trigonometric cancellation error near DC / Nyquist       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Quantized to
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. Runtime Coefficient Storage & In-Memory Execution                   │
│    • Stored as single-precision IEEE 754 float32                       │
│    • Matches canonical PCM block dtype (float32)                       │
│    • Native format for Cortex-M FPU and host SIMD                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 14. Conformance Model & Error Tolerances

In accordance with DEC-01 and Phase 1A.1, AcoustiForge distinguishes:
$$\text{Mathematical Contract} \longrightarrow \text{Reference Realization} \longrightarrow \text{Verification / Golden Vectors} \longrightarrow \text{Conformance Tolerance}$$

> [!IMPORTANT]
> **Verification Policy:** The tolerances below define criteria for accepting a runtime implementation relative to the contract. They are **conformance, verification, and test-policy thresholds**, NOT mathematical definitions of the biquad filter itself.

| Conformance Tier | Applied Artifact | Verification Metric & Permissible Tolerance Threshold |
|---|---|---|
| **`NUMERICALLY_EQUIVALENT`** | Normalized Coefficients $\mathbf{w}$ | $|w_{\text{runtime}} - w_{\text{ref}}| \le 1.0 \times 10^{-6}$ |
| **`NUMERICALLY_EQUIVALENT`** | Time-Domain Impulse Response $y[n]$ | $|y_{\text{runtime}}[n] - y_{\text{ref}}[n]| \le 1.0 \times 10^{-5}$ peak error |
| **`MEASUREMENT_EQUIVALENT`** | Frequency Magnitude Response $|H(f)|$ | $|\Delta |H(f)|_{\text{dB}}| \le 0.05\,\text{dB}$ across passband |
| **`MEASUREMENT_EQUIVALENT`** | Phase Response $\angle H(f)$ | $|\Delta \angle H(f)| \le 0.5^\circ$ across passband |

---

## 15. Golden Reference Vectors Strategy

Phase 1B resolves the **golden-vector strategy and specification**. Concrete executable generation of the golden vector dataset and numerical verification against implementations are formally deferred to **Phase 1C**.

The golden vector specification defines a compact 10-vector corpus covering standard filter families and edge conditions:

| Vector ID | Filter Family | $f_s$ ($\text{Hz}$) | $f_0$ ($\text{Hz}$) | $Q$ / $S$ / $\text{BW}$ | $G_{\text{dB}}$ | Target Evaluation |
|---|---|---|---|---|---|---|
| **GV-01** | LowPass | $48000$ | $1000.0$ | $Q = 0.707107$ | $0.0$ | Butterworth maximally-flat response |
| **GV-02** | HighPass | $48000$ | $100.0$ | $Q = 0.707107$ | $0.0$ | Sub-bass rumble filter |
| **GV-03** | Peaking | $48000$ | $1000.0$ | $Q = 2.0$ | $+6.0$ | Mid-band bell boost |
| **GV-04** | Peaking | $48000$ | $1000.0$ | $Q = 2.0$ | $-6.0$ | Mid-band bell cut |
| **GV-05** | Notch | $48000$ | $60.0$ | $Q = 10.0$ | $0.0$ | Mains hum rejection null |
| **GV-06** | BandPass | $48000$ | $2500.0$ | $Q = 1.414214$ | $0.0$ | Voice-band passband |
| **GV-07** | LowShelf | $48000$ | $200.0$ | $S = 1.0$ | $+9.0$ | Bass boost shelf |
| **GV-08** | HighShelf | $48000$ | $8000.0$ | $S = 1.0$ | $-9.0$ | High-frequency treble roll-off |
| **GV-09** | Peaking (Nyquist) | $44100$ | $20000.0$ | $Q = 1.0$ | $+3.0$ | High-frequency edge case |
| **GV-10** | Peaking (Sub-Bass) | $48000$ | $30.0$ | $Q = 0.5$ | $+6.0$ | Low-frequency edge case |

---

## 16. Edge Case Analysis & Rejection Matrix

| Parameter Condition | Classification | Expected Behavior / Rejection Class | Mathematical Rationale |
|---|---|---|---|
| $f_0 \le 0$ | **INVALID** | Reject with `InvalidParameterError` | Negative or zero frequency is physically and mathematically undefined. |
| $f_0 \ge \frac{f_s}{2}$ | **INVALID** | Reject with `InvalidParameterError` | Frequencies at or above Nyquist cause Bilinear Transform aliasing singularities. |
| $Q \le 0$ | **INVALID** | Reject with `InvalidParameterError` | Negative or zero $Q$ produces zero division in $\alpha$ and unstable left-plane poles. |
| $\text{BW} \le 0$ | **INVALID** | Reject with `InvalidParameterError` | Bandwidth must be strictly positive. |
| $S \le 0$ | **INVALID** | Reject with `InvalidParameterError` | Shelf slope must be strictly positive. |
| Parameter is `NaN` or `Inf` | **INVALID** | Reject with `NonFiniteValueError` | Non-finite parameter inputs corrupt coefficient calculations. |
| $|a_2| \ge 1.0$ | **UNSTABLE** | Reject with `UnstableFilterError` | Poles lie on or outside the unit circle; filter will oscillate or explode. |
| $a_0 = 0.0$ | **DEGENERATE** | Reject with `InvalidParameterError` | Division by zero during coefficient normalization. |
| $G_{\text{dB}} = 0.0$ (Peaking/Shelf)| **VALID** | Returns unity pass-through coefficients | Mathematically simplifies to identity filter ($H(z) = 1.0$). |

---

## 17. Parameter Update Transaction Semantics

Applying DEC-05 and DEC-06 to the Biquad filter lifecycle:

```
[Active Parameters θ_curr, Coefficients w_curr, State S]
                       │
                       │ User calls set_parameters(f0_new, Q_new, G_new)
                       ▼
[1. Validate Parameter Ranges] ──(Fails)──> Raise InvalidParameterError
                       │                     (θ_curr, w_curr, S UNCHANGED)
                       ▼ (Passes)
[2. Calculate Normalized Candidate Coefficients w_cand]
                       │
                       │ Using float64 RBJ Equations
                       ▼
[3. Validate Stability of w_cand] ──(Fails)──> Raise UnstableFilterError
                       │                        (θ_curr, w_curr, S UNCHANGED)
                       ▼ (Passes)
[4. Atomic Activation] ──> θ_curr = θ_new, w_curr = w_cand
                            State S is PRESERVED (no click or reset)
```

---

## 18. ARM CMSIS-DSP Mapping Considerations

AcoustiForge does not depend on CMSIS-DSP. The canonical ACE mathematical contract and coefficient representation $[b_0, b_1, b_2, a_1, a_2]$ under the canonical difference equation $y[n] = b_0 x[n] + b_1 x[n-1] + b_2 x[n-2] - a_1 y[n-1] - a_2 y[n-2]$ are authoritative.

### 18.1 Implementation Mapping for CMSIS-DSP Direct Form I (`arm_biquad_cascade_df1_f32`)
- **CMSIS Array Layout:** `float32_t pCoeffs[5] = {b0, b1, b2, -a1, -a2}`
- **Sign Difference:** CMSIS-DSP stores negated feedback coefficients $-a_1$ and $-a_2$ in memory so that its inner assembly kernel executes Multiply-Accumulate (`MAC`) rather than subtraction.
- **Implementation Mapping:**
  $$\mathbf{w}_{\text{CMSIS}} = [w_{\text{ACE}}[0],\, w_{\text{ACE}}[1],\, w_{\text{ACE}}[2],\, -w_{\text{ACE}}[3],\, -w_{\text{ACE}}[4]]$$

> [!NOTE]
> **Non-Normative Status:** ACE mathematical coefficients are authoritative. CMSIS-DSP coefficient layout is an implementation-specific runtime mapping and does NOT redefine the canonical ACE contract.

---

## 19. Deferred Implementation Decisions (Handoff to Phase 1C)

The following items are intentionally deferred to **Phase 1C (Biquad Node Implementation & Verification)**:
- ❌ Implementation of `BiquadNode` and `BiquadCoefficients` classes in `src/acoustiforge/`.
- ❌ Integration of the DF-II-T difference equations into active audio processing loops.
- ❌ Implementation of coefficient smoothing / parameter ramp interpolation.
- ❌ Concrete pytest test suites for `BiquadNode` execution.

---

## 20. Phase 1B Acceptance Checklist

- [x] Mathematical Jury stability ($1+a_1+a_2>0, 1-a_1+a_2>0, 1-a_2>0$) is separated from epsilon guards.
- [x] Floating-point epsilon is explicitly classified as implementation/test policy.
- [x] Numerical conformance tolerances are explicitly verification policies rather than mathematical definitions.
- [x] Golden-vector strategy is distinguished from actual generated verification corpus.
- [x] CMSIS-DSP mapping is explicitly non-normative.
- [x] Canonical ACE coefficient signs remain authoritative.
- [x] Biquad mathematical contract is explicitly signal-domain agnostic.
- [x] No generic GraphObject or SignalObject architecture is introduced.
- [x] No production DSP implementation exists.
- [x] Phase 0 source and tests are untouched.
- [x] Phase 1A frozen contract is untouched.
- [x] pytest remains 58/58 passing.
- [x] git diff contains only intended changes.

---

## 21. Final Decision & Status

### Decision
$$\mathbf{PHASE\ 1B\ BIQUAD\ MATHEMATICAL\ CONTRACT:\ FROZEN}$$

### Phase 0 Regression Baseline
- **Total Tests:** 58
- **Passed:** 58
- **Failed:** 0
- **Errors:** 0
- **Warnings:** 0

### Files Created
- `docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md`

### Files Protected / Not Modified
- `prompts/MASTER_PROMPT.md`
- `docs/contracts/PCM_CONTRACT.md`
- `docs/contracts/RUNTIME_ARCHITECTURE_AMENDMENT_0_1.md`
- `docs/phases/PHASE_1A_DSP_NODE_CONTRACT_DISCOVERY.md`
- `docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md`
- `src/acoustiforge/*` (All Phase 0 implementation files intact)
- `tests/*` (All Phase 0 test files intact)
- `docs/phases/PHASE_0_ACCEPTANCE_REPORT.md`

### Open Questions
- *None.* All mathematical formulas, parameter bounds, stability criteria, and sign conventions are resolved.

### Deferred Implementation (Handoff to Phase 1C)
Phase 1C will implement the executable `BiquadNode`, coefficient calculation functions, and comprehensive unit/conformance test suites in `src/acoustiforge/` and `tests/`.

---

PHASE 1B.1 BIQUAD MATHEMATICAL CORRECTION: COMPLETE  
PHASE 1B BIQUAD MATHEMATICAL CONTRACT: FROZEN  
PHASE 1B IMPLEMENTATION AUTHORIZATION: NOT REQUESTED
