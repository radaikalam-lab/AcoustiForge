# AcoustiForge — Epistemic Gap Analysis & Risk Registry

**Document ID:** `DOC-EPISTEMIC-GAPS-01`  
**Evaluation Target:** AcoustiForge Core, Extensions, and Runtime Architecture  
**Date:** 2026-09-19  
**Status:** Approved Gap Registry

---

## 1. Gap Classification Framework

Gaps are categorized by their severity regarding scientific integrity, risk of epistemic lock-in, and safety guarantees:

* **CRITICAL:** Fundamental barriers preventing scientific model criticism, causing silent conflation of assumptions with physical laws, or risking unauthorized control plane mutation.
* **HIGH:** Absence of core registries (Models, Assumptions, Unknowns, Residuals) necessary to represent competing scientific hypotheses.
* **MEDIUM:** Missing multi-dimensional evaluation profiles (e.g. AIC/BIC, autocorrelation tests) or experimental discrimination generators.
* **LOW:** Documentation, schema metadata tagging, or fine-grained taxonomy extensions.
* **DEFERRED:** Advanced capabilities intentionally deferred to maintain focus and prevent overengineering (e.g., autonomous symbolic physics discovery).

---

## 2. Comprehensive Epistemic Gap Registry

| Gap ID | Severity | Category | Description & Current Architectural State | Smallest Architectural Remediation |
| :--- | :---: | :--- | :--- | :--- |
| **GAP-01** | **CRITICAL** | Model Criticism | **No Structural Model Defect Detection:** When optimization reaches its bound with high residual error, Core reports optimization failure rather than identifying structural model inadequacy. | Implement `ResidualClassifier` with residual autocorrelation and structural defect tagging. |
| **GAP-02** | **CRITICAL** | Epistemic Ontology | **Zone U (Unknown) Not Represented:** The system has no entity to represent unexplained residuals, unknown physical variables, or pre-ontological observations; unrecognised inputs are rejected as `InvalidParameterError`. | Implement `UnknownDescriptor` and `UnknownRegistry` in `src/acoustiforge/epistemic/`. |
| **GAP-03** | **CRITICAL** | Epistemic Separation | **Conflation of Heuristics with Hard Laws:** Engineering heuristics (e.g. $f_{\text{high}} \ge 1.5 f_{\text{low}}$, filter Q bounds) are hardcoded as immutable exceptions alongside true physical invariants. | Implement `EpistemicClass` and `AssumptionRegistry` explicitly distinguishing heuristics from physical laws. |
| **GAP-04** | **HIGH** | Theory Evolution | **No First-Class Model Lineage ($T_0 \to T_1$):** Models do not exist as identifiable, versioned scientific entities. Theory transitions cannot be tracked with rationale or evidence links. | Implement `ModelDescriptor`, `ModelRegistry`, and `TheoryTransitionLedger`. |
| **GAP-05** | **HIGH** | Shadow Execution | **No Isolated Multi-Model Competition:** Core only runs one specification at a time; competing candidate models cannot be benchmarked in parallel against identical empirical sweeps. | Build `ShadowExecutionEngine` and `ModelTournament` in `src/acoustiforge/epistemic/shadow/`. |
| **GAP-06** | **HIGH** | Falsification | **Absence of Falsification Criteria:** Models do not declare what empirical observation would refute them; models are implicitly treated as mature by default. | Add `FalsificationCriterion` to model descriptors and an automated falsification check. |
| **GAP-07** | **MEDIUM** | Objective Criticism | **Immutable Scalar Loss Assumption:** Objective function $L = E_{\text{rms}} + w_r R + w_\tau P_\tau$ is hardcoded; the system cannot evaluate whether the objective is a flawed proxy. | Define pluggable `ObjectiveDescriptor` protocol and support shadow objective evaluations. |
| **GAP-08** | **MEDIUM** | Model Evaluation | **Single Scalar Metric Stopping Criterion:** Optimizer stops solely on $\Delta L < 10^{-5}\text{ dB}$ without evaluating structural parsimony (AIC/BIC), domain coverage, or mechanistic depth. | Implement `ModelEvidenceProfile` calculating AIC, BIC, and residual autocorrelation. |
| **GAP-09** | **MEDIUM** | Representation | **Fixed Phasor Transfer-Function Ontology:** The architecture assumes all acoustic phenomena are reducible to frequency-domain complex phasors and Direct Form II biquads. | Define `RepresentationFormalism` interface supporting alternative formulations in shadow mode. |
| **GAP-10** | **LOW** | Evidence Provenance | **Coarse Evidence Categorization:** `EvidenceType` only distinguishes offline, hardware, and hybrid, missing mathematical proof, human feedback, and AI hypothesis classifications. | Expand `EpistemicEvidenceType` enum with all 8 standard evidence classes. |
| **GAP-11** | **DEFERRED** | Autonomous Physics | **Symbolic Equation & PDE Discovery:** Autonomous discovery of novel continuous partial differential equations without human validation. | **DEFERRED:** Intentionally outside scope to prevent ungrounded AI hallucinations and maintain deterministic safety. |
| **GAP-12** | **DEFERRED** | Unsupervised Promotion | **Autonomous Production Control Plane Mutation:** Allowing AI to directly rewrite production DSP coefficients or firmware without human review. | **DEFERRED / FORBIDDEN:** Strictly prohibited by foundational safety invariant $\text{Epistemic Novelty} \neq \text{Production Authority}$. |

---
*End of Document DOC-EPISTEMIC-GAPS-01.*
