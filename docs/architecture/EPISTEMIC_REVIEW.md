# AcoustiForge — Epistemic Review (Stage 1 Forensic Assessment)

**Document ID:** `DOC-EPISTEMIC-REV-01`  
**Evaluation Target:** `AcoustiForge` Core & Extension Architecture  
**Date:** 2026-09-19  
**Status:** Completed Forensic Audit (No Code Modified)

---

## 1. Executive Summary

AcoustiForge has achieved production-grade engineering excellence as a **deterministic computational acoustics optimizer and digital signal processing (DSP) execution engine**. Across 552 unit, property, and golden tests, the system demonstrates bitwise numerical determinism, strict memory safety, frozen directed acyclic graph (DAG) state machines, and a hardened validation firewall protecting the acoustic Core from untrusted AI intent.

However, from an **epistemic and scientific discovery standpoint**, the current architecture is strictly an **interpolative parameter optimizer operating within a fixed lumped-parameter LTI paradigm**. It lacks the ontological and structural capacity to:
1. Distinguish physical laws from engineering heuristics and modeling approximations.
2. Detect when an empirical residual is caused by structural model failure rather than parameter mistuning.
3. Represent unexplained observations or unknown physical variables without rejecting them as invalid.
4. Host competing scientific hypotheses ($T_0, T_1, \dots$) or record theory transition lineage.
5. Challenge its hardcoded scalar objective function ($L = E_{\text{rms}} + w_r R + w_\tau P_\tau$).

This review documents the exact state of all 14 subsystem areas, classifies all foundational constraints into epistemic categories, audits the objective and unknown-state representations, and establishes the forensic basis for the Epistemic Architecture.

---

## 2. Section A: Current Architecture Forensic Mapping

| Subsystem | Implemented Component / File | Current Epistemic Reality & Limitations |
| :--- | :--- | :--- |
| **1. Core Math Models** | `src/acoustiforge/acoustic_math/` (`crossover.py`, `alignment.py`, `target_curve.py`, `metrics.py`) | Classical Linkwitz-Riley and Butterworth biquad filter synthesis, fractional-delay sinc/linear interpolation, minimum-phase Hilbert transform. Models are frozen in code; no dynamic or alternative mathematical representations exist. |
| **2. Optimization** | `src/acoustiforge/acoustic_math/optimization.py` | Bounded coordinate descent combined with 1D golden-section line search and lexicographical tie-breaking. Strictly deterministic. Optimized purely over scalar parameter space $(\mathbf{f}_c, \mathbf{g}, \boldsymbol{\tau})$. |
| **3. Constraints** | `src/acoustiforge/domain/specifications.py`, `protection.py` | Hard scalar bounds: $0 < f_{\min} < f_{\max}$, $f_{\text{high}} \ge 1.5 f_{\text{low}}$, $X_{\text{max}}$, $P_{\text{max}}$, $|z_{\text{pole}}| < 1.0$. No representation of uncertainty or domain of validity. |
| **4. Validation** | `src/acoustiforge/domain/validation.py`, `contracts/validation.py` | Strict `__post_init__` validation raising `InvalidSpecificationError`, `UnstableFilterError`, `InvalidParameterError`. All violations abort execution. |
| **5. DesignIntent** | `src/acoustiforge/intent/contracts.py` | High-level dataclasses (`TargetCurveIntent`, `TonalBalanceIntent`, `CrossoverIntent`, `SpatialIntent`, `ConstraintIntent`). Captures user/AI desires prior to validation. |
| **6. AI Boundary** | `src/acoustiforge/intent/adapter.py` (`DesignIntentAdapter`) | 4-stage validation firewall (Schema $\to$ Semantic $\to$ Acoustic Bounds $\to$ Presets). AI has zero execution authority and zero direct Core write access. |
| **7. ExperienceStore** | `src/acoustiforge/experience/store.py`, `collector.py` | Append-only JSONL event/episode log (`ExperienceRecord`). Preserves complete intent $\to$ spec $\to$ optimization $\to$ graph $\to$ execution $\to$ feedback trajectories. |
| **8. Provenance** | `src/acoustiforge/experience/contracts.py`, `retrieval.py` | Structured provenance capturing `experience_id`, `timestamp_iso`, `runtime_version`, `schema_version`, and execution summaries. Provenance is descriptive/historical, not epistemic. |
| **9. Measurement Handling** | `src/acoustiforge/domain/measurements.py`, `acoustic_math/sweep.py`, `gating.py` | `FrequencyResponseData`, `ImpulseResponseData`, Farina log-sine sweep deconvolution, time-window gating, mic calibration subtraction. Strictly LTI-focused. |
| **10. Model Selection** | `src/acoustiforge/intent/adapter.py`, `engine/pipeline.py` | Manual selection of discrete presets (`CrossoverFamily.LINKWITZ_RILEY` vs `BUTTERWORTH`). No automated multi-model comparison, ranking, or hypothesis tournament. |
| **11. Objective Functions** | `src/acoustiforge/acoustic_math/optimization.py` (`evaluate_weighted_acoustic_loss`) | Hardcoded scalar objective: $L = E_{\text{rms}} + w_r R + w_\tau P_\tau$. Fixed in source code; cannot be challenged, replaced, or evaluated as a Pareto front. |
| **12. Representations** | `src/acoustiforge/nodes/biquad.py`, `graph/compute_graph.py` | Frequency-domain complex phasors ($H(f) \in \mathbb{C}$) and Direct Form II Transposed biquad cascades. Alternative formalisms (state-space, PDE, modal) are not representable. |
| **13. Spatial Extensions** | `src/acoustiforge/extensions/spatial_optimization.py` | Multi-position normalized weighted sum ($\sum w_i L_i$) across `SpatialMeasurementPosition` coordinates. Unprivileged extension layer. |
| **14. Hardware Execution** | `src/acoustiforge/execution/` (`alsa_backend.py`, `alsa_capture.py`, `offline_backend.py`) | Native Linux ALSA `ctypes` bindings (`snd_pcm_writei`, `snd_pcm_readi`) and synchronous offline simulation backend. |

---

## 3. Section B: Epistemic Classification Audit of Existing Invariants & Assumptions

To eliminate the conflation of engineering heuristics with universal physical laws, all foundational invariants, assumptions, and constraints in the codebase are classified into the 9 epistemic categories:

```
MATHEMATICAL_THEOREM
PHYSICAL_INVARIANT
CONSTITUTIVE_MODEL
APPROXIMATION
EMPIRICAL_REGULARITY
ENGINEERING_HEURISTIC
OBJECTIVE_ASSUMPTION
ONTOLOGICAL_ASSUMPTION
UNKNOWN
```

### Forensic Invariant & Assumption Audit Table

| Component / Invariant | Current Location | Epistemic Classification | Architectural Reality & Hidden Assumption |
| :--- | :--- | :--- | :--- |
| **Nyquist Sampling Limit** ($f \le f_s/2$) | `optimization.py:L70`, `sweep.py` | `MATHEMATICAL_THEOREM` | Exact mathematical identity for band-limited discrete sampling. True invariant within discrete-time domain. |
| **Filter Stability** ($|z_{\text{pole}}| < 1.0$) | `nodes/biquad.py:L56`, `contracts/validation.py` | `MATHEMATICAL_THEOREM` | Realizability and bounded-input bounded-output (BIBO) stability for discrete linear IIR systems. |
| **Time Non-Negativity** ($\tau \ge 0$) | `domain/specifications.py:L218` | `PHYSICAL_INVARIANT` | Causality in physical acoustic wave propagation. Negative delay cannot be realized without lookahead. |
| **Transducer Thermal/Excursion Limits** | `domain/specifications.py:L122`, `protection.py` | `PHYSICAL_INVARIANT` | First-law thermodynamic voice-coil heating ($P_{\text{max}}$) and mechanical suspension clearance limit ($X_{\text{max}}$). |
| **Linkwitz-Riley Acoustic Summing** | `acoustic_math/crossover.py`, `optimization.py` | `CONSTITUTIVE_MODEL` | Assumes coincident driver acoustic centers radiating into $4\pi$ free space without mutual radiation loading. |
| **Linear Time-Invariance (LTI)** | Entire `acoustic_math/` and `graph/` | `APPROXIMATION` | **Incorrectly treated as hard law.** Assumes loudspeaker drivers do not exhibit large-signal $BL(x)$ modulation, suspension softening, or port turbulence. |
| **Minimum-Phase Driver Behavior** | `domain/measurements.py` (Hilbert Phase) | `APPROXIMATION` | **Incorrectly treated as universal.** Loudspeaker drivers exhibit non-minimum phase behavior due to cone break-up modes and cabinet edge reflections. |
| **Far-Field / Plane-Wave Propagation** | `extensions/spatial_optimization.py` | `APPROXIMATION` | Assumes spherical $1/r$ far-field attenuation with zero room modal coupling or boundary scattering. |
| **Microphone Calibration File Subtraction** | `acoustic_math/calibration.py` | `EMPIRICAL_REGULARITY` | Interpolated 1D magnitude/phase correction curve measured under specific laboratory conditions (diffuse vs free field). |
| **3-Way Crossover Spacing** ($f_{\text{high}} \ge 1.5 f_{\text{low}}$) | `domain/specifications.py:L280` | `ENGINEERING_HEURISTIC` | **Incorrectly enforced as a hard specification error.** Prevents filter interaction, but is an engineering rule-of-thumb, not a physical impossibility. |
| **Filter Q Bounds** ($0.5 \le Q \le 10.0$) | `domain/specifications.py:L97` | `ENGINEERING_HEURISTIC` | Prevents ringing and narrow-band phase distortion, but is a design convention, not a physical law. |
| **Flat Frequency Response as Quality Proxy** | `acoustic_math/optimization.py:L450`, `intent/contracts.py` | `OBJECTIVE_ASSUMPTION` | Assumes that minimizing RMS dB deviation against a flat/target SPL curve constitutes acoustic excellence. |
| **Scalar Objective Summation** | `acoustic_math/optimization.py:L472` | `OBJECTIVE_ASSUMPTION` | Assumes multi-dimensional acoustic criteria (tracking, ripple, delay) collapse into a single scalar loss. |
| **Transfer-Function Phasor Ontology** | `domain/measurements.py` (`FrequencyResponseData`) | `ONTOLOGICAL_ASSUMPTION` | Assumes an acoustic system is fundamentally defined by complex scalar ratios $H(f) \in \mathbb{C}$ at discrete frequency points. |
| **Direct Form II Biquad Topology** | `nodes/biquad.py`, `builders/` | `ONTOLOGICAL_ASSUMPTION` | Assumes DSP signal processing is exhausted by cascades of 2nd-order transposed direct-form sections. |

---

## 4. Section C: Objective Audit

### 1. Classification of the Current Objective
The current objective function in [optimization.py](file:///e:/AcoustiForge/src/acoustiforge/acoustic_math/optimization.py#L420-L478) is:
$$L(\mathbf{f}_c, \mathbf{g}, \boldsymbol{\tau}) = E_{\text{rms}} + w_r \cdot R + w_\tau \cdot P_\tau$$
* **Classification:** **`OBJECTIVE_ASSUMPTION` & `PROXY`**.
* **Epistemic Finding:** The objective is hardcoded as an immutable Python function. The system conflates **minimizing $L$** with **achieving acoustic fidelity**.
* **Goodhart's Law Vulnerability:** If a driver has narrow acoustic cancellations (e.g. boundary notches), the optimizer may push filter gains or crossover frequencies into unnatural regions to flatten the curve, degrading temporal response while numerically minimizing $L$.

### 2. Distinguishing Loss from Engineering & Scientific Success
* **Low Optimization Loss ($\Delta L \to 0$):** Currently the *sole* stopping criterion and success indicator.
* **Actual Engineering Success:** Requires verifying that distortion, thermal margin, spatial directivity, and subjective listening feedback are satisfied.
* **Scientific Explanatory Adequacy:** Requires determining *why* a particular crossover alignment works (e.g., phase alignment across the spatial dispersion envelope vs coincidental on-axis cancellation).
* **Verdict:** The current architecture **cannot distinguish** these three concepts; it treats numerical loss as both necessary and sufficient.

---

## 5. Section D: Unknown-State Audit

| Target Unknown State | Current Architectural Capability | Failure Point & Restrictive Ontology |
| :--- | :---: | :--- |
| **1. Unexplained Residuals** | **GAP** | Residuals are calculated as scalar differences $e(f) = |H_{\text{pred}}| - |H_{\text{target}}|$. If residuals persist, the optimizer reports `converged = False` or returns a high loss; it cannot tag the residual as an unmodelled acoustic anomaly. |
| **2. Unknown Variables** | **GAP** | Dataclasses enforce strict type annotations with `__slots__`. An input containing an untyped or unknown physical variable (e.g., cabinet surface vibration velocity, ambient humidity) is immediately rejected with `TypeError` or `InvalidParameterError`. |
| **3. Missing Mechanisms** | **GAP** | Core assumes all acoustic loss is captured by the 3 parameter coordinates. A missing physical mechanism (e.g., baffle diffraction step, port turbulence) cannot be flagged or isolated. |
| **4. Structural Model Failure** | **GAP** | The optimizer cannot differentiate between a parameter search that terminated prematurely and a model structure that is mathematically incapable of fitting the data. |
| **5. Unsupported Representations** | **GAP** | Representations outside `FrequencyResponseData` / `BiquadFilterNode` cannot enter the system; the validation firewall rejects them. |
| **6. Competing Explanations** | **GAP** | There is no entity in the codebase representing two different physical hypotheses explaining the same dip at $350\text{ Hz}$ (e.g., floor bounce reflection vs driver cone surround resonance). |
| **7. Unresolved Contradictions** | **GAP** | When physical measurements conflict with model predictions, the measurement is either forced through calibration or execution fails. Contradictions cannot remain open as active scientific questions. |

---

## 6. Section E: Theory Transition Audit

1. **$T_0 \to T_1$ (Parametric / Structural Evolution):**
   * Currently, transitions are represented implicitly through Git commits or isolated `ExperienceRecord` session logs.
   * There is no first-class `Theory` or `Model` object in the runtime.
   * Historical models are not queryable as scientific theories with linked evidence.
2. **$T_0 \to \text{New Conceptual Framework} \to T_1$ (Paradigm Shift):**
   * The architecture assumes the lumped-parameter transfer-function paradigm is immutable.
   * A transition to a state-space formulation or wave-based acoustic boundary model cannot be expressed within Core contracts.

---

## 7. Section F: Evidence Audit

AcoustiForge has already laid valuable groundwork in [experience/contracts.py](file:///e:/AcoustiForge/src/acoustiforge/experience/contracts.py) by creating `EvidenceType` (`SOFTWARE_OFFLINE`, `PHYSICAL_HARDWARE`, `HYBRID_SIMULATION`).

However, the complete scientific taxonomy must be expanded to:
```
MATHEMATICAL_PROOF
PHYSICAL_MEASUREMENT
EXPERIMENTAL_RESULT
SIMULATION
OBSERVATIONAL_DATA
ENGINEERING_TEST
HUMAN_FEEDBACK
AI_GENERATED_HYPOTHESIS
```

* **CRITICAL INVARIANT:** AI-generated text, chain-of-thought, or intent objects are categorized strictly as `AI_GENERATED_HYPOTHESIS` and are **never** treated as empirical evidence.

---

## 8. Section G: Falsification Audit

Every scientific model must answer the 6 Popperian questions. Currently:
1. *What does this model predict?* **PARTIAL** (Predicts on-axis SPL magnitude/phase via `OptimizationResult.predicted_response`).
2. *What assumptions does it require?* **GAP** (Assumptions are implicit in code).
3. *Within what domain is it valid?* **GAP** (Frequency bounds exist, but SPL linearity / temperature / room volume domains are unrepresented).
4. *What evidence supports it?* **PARTIAL** (Referenced in docs, not linked in data structures).
5. *What evidence contradicts it?* **GAP** (Contradictory evidence is logged as failed episodes, not linked to model entities).
6. *What observation would falsify it?* **GAP** (No model carries an explicit `FalsificationCriterion` contract).

---

## 9. Section H: Premature-Stopping Audit

* **Current Stopping Condition:**
  $$\Delta L = |L_{k} - L_{k-1}| < 10^{-5}\text{ dB} \quad \lor \quad k \ge 50$$
* **Epistemic Defect:** The optimizer terminates and reports `converged = True` even if the final residual $e_{\text{rms}} = 6.5\text{ dB}$ (a massive structural failure). Conversely, if the optimizer runs out of iterations while making $10^{-6}\text{ dB}$ improvements, it reports `converged = False` (treated as failure) even if the model fits the data with $0.1\text{ dB}$ error.
* **Required Epistemic Capability:** The system must be able to report:
  $$\boxed{\text{Status: } \text{OPTIMIZATION\_CONVERGED\_MODEL\_INADEQUATE}}$$
  where parameter optimization has succeeded, but model uncertainty dominates parameter uncertainty.

---
*End of Document DOC-EPISTEMIC-REV-01.*
