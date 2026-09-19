# AcoustiForge — Epistemic Architecture Implementation Plan

**Document ID:** `DOC-EPISTEMIC-PLAN-01`  
**Target Module:** `src/acoustiforge/epistemic/`  
**Date:** 2026-09-19  
**Status:** Approved Phased Implementation Blueprint (Stage 1 Plan)

---

## 1. Architectural Guardrails & Invariants

1. **Zero Core Disruption:** No existing Core mathematical formulas, validation firewalls, compute graph compilers, or ALSA audio backends in `src/acoustiforge/domain/`, `acoustic_math/`, `graph/`, `nodes/`, or `execution/` will be modified or degraded.
2. **Dynamic Test Baseline:** At the start of implementation, `pytest` establishes the dynamic baseline test count. Existing tests must remain 100% green without regression after every implementation phase.
3. **Strict Epistemic Isolation:** All new epistemic data structures, registries, shadow executors, and tournament runners will reside in `src/acoustiforge/epistemic/` and `tests/epistemic/`.
4. **Safety Invariant:** $\text{Epistemic Novelty} \neq \text{Production Authority}$.

---

## 2. Phased Implementation Roadmap

```text
  Phase E0.5: Epistemic Semantics Freeze (Complete)
       │
       ▼
  Phase E1: Epistemic Vocabulary & Relations
       │
       ▼
  Phase E2: Assumption Registry
       │
       ▼
  Phase E3: Model Registry (T0, T1 Lineage & Falsification)
       │
       ▼
  Phase E4: Unknown Registry & Residual Assessment
       │
       ▼
  Phase E5: Model Challenge Framework
       │
       ▼
  Phase E6: Shadow Execution & Model Competition (ModelComparison)
       │
       ▼
  Phase E7: Falsification Engine (Review Trigger)
       │
       ▼
  Phase E8: Objective Challenge Framework
       │
       ▼
  Phase E9: Representation Challenge Framework
       │
       ▼
  Phase E10: Theory Transition Ledger & 20 Red-Team Tests
```

---

### Phase E0.5 — Epistemic Semantics Freeze (Complete)
* **Status:** **COMPLETE & FROZEN** (Governed by `DOC-EPISTEMIC-AMEND-01`).
* **Achievements:**
  * Freezes vocabulary into 16 non-collapsible categories.
  * Formulates invariant semantic non-equivalences (`MODEL != LAW`, `UNKNOWN != INVALID`).
  * Establishes Zone H challenge taxonomy (`H_APPLICABILITY`, `H_CLASSIFICATION`, `H_FUNDAMENTAL`).
  * Converts residual classification to `ResidualAssessment` (assessment vs truth).
  * Defines multi-model competition via `ModelEvidenceProfile` and `ModelComparison` (no single winner).
  * Replaces scalar adequacy with structured `MechanisticAssessment`.
  * Fully decouples `EPISTEMIC_ACCEPTED` from `PRODUCTION_AUTHORITY`.

---

### Phase E1 — Epistemic Vocabulary & Relational Types
* **Target Package:** `src/acoustiforge/epistemic/`
* **Target Files:**
  * `src/acoustiforge/epistemic/__init__.py`
  * `src/acoustiforge/epistemic/vocabulary.py`
* **Components:**
  * `EpistemicZone` (`ZONE_H`, `ZONE_M`, `ZONE_P`, `ZONE_U`)
  * `EpistemicClass` (9 standard classifications)
  * `EpistemicStatus` (`HYPOTHESIS`, `VALIDATED_MODEL`, `FALSIFICATION_EVIDENCE_DETECTED`, `UNDER_REVIEW`, `DOMAIN_LIMITED`, `FALSIFIED`, `DEPRECATED`)
  * `ChallengeStatus` (`UNCHALLENGED`, `UNDER_INVESTIGATION`, `EVIDENCE_SUPPORTED`, `EPISTEMIC_ACCEPTED`, `PRODUCTION_CANDIDATE`, `PRODUCTION_AUTHORITY`)
  * `ZoneHChallengeType` (3 challenge types)
  * `ResidualClassificationType` (6 classification types)
  * `EpistemicEvidenceType` (8 evidence types)
  * `EvidenceRelation` (6 relational types) and `EpistemicEvidenceLink`
* **Verification:** Unit tests verifying enum values, serialization, and immutability. Run full suite.

---

### Phase E2 — Assumption Registry
* **Target Files:**
  * `src/acoustiforge/epistemic/assumptions.py`
* **Components:**
  * `AssumptionDescriptor` dataclass (`frozen=True, slots=True`)
  * `AssumptionRegistry` with query by zone, epistemic class, and challenge status.
  * Canonical registration of existing AcoustiForge assumptions:
    * `ASM-NYQUIST-01` (Nyquist limit — `MATHEMATICAL_THEOREM`, `ZONE_H`)
    * `ASM-STABILITY-01` (Pole radius — `MATHEMATICAL_THEOREM`, `ZONE_H`)
    * `ASM-CAUSALITY-01` (Delay $\ge 0$ — `PHYSICAL_INVARIANT`, `ZONE_H`)
    * `ASM-THERMAL-01` ($P_{\text{max}}$ — `PHYSICAL_INVARIANT`, `ZONE_H`)
    * `ASM-EXCURSION-01` ($X_{\text{max}}$ — `PHYSICAL_INVARIANT`, `ZONE_H`)
    * `ASM-LTI-01` (Linear Time-Invariance — `APPROXIMATION`, `ZONE_M`)
    * `ASM-MINPHASE-01` (Hilbert Minimum Phase — `APPROXIMATION`, `ZONE_M`)
    * `ASM-SUM-01` (Uncoupled Acoustic Summing — `CONSTITUTIVE_MODEL`, `ZONE_M`)
    * `ASM-FARFIELD-01` (Spherical Spreading — `APPROXIMATION`, `ZONE_M`)
    * `ASM-LR-01` (Linkwitz-Riley Alignment — `CONSTITUTIVE_MODEL`, `ZONE_M`)
    * `ASM-HEUR-3WAY-01` ($f_{\text{high}} \ge 1.5 f_{\text{low}}$ — `ENGINEERING_HEURISTIC`, `ZONE_H`)
    * `ASM-OBJ-FLAT-01` (Flat Target SPL Quality — `OBJECTIVE_ASSUMPTION`, `ZONE_P`)
    * `ASM-ONT-PHASOR-01` (Complex Transfer Function — `ONTOLOGICAL_ASSUMPTION`, `ZONE_P`)
* **Verification:** Test all 13 canonical assumptions are registered, immutable, and queryable.

---

### Phase E3 — Model Registry, Lineage & Mechanistic Assessment
* **Target Files:**
  * `src/acoustiforge/epistemic/models.py`
* **Components:**
  * `FalsificationCriterion` value object
  * `MechanisticAssessment` structured audit contract
  * `ModelDescriptor` value object (`model_id`, `version`, `parent_model_id`, `assumptions`, `domain_of_validity`, `epistemic_status`, `falsification_criteria`)
  * `ModelRegistry` container
  * Register canonical baseline models:
    * `MODEL-LR4-2WAY` ($T_0$: 2-Way Linkwitz-Riley 4th Order LTI Model)
    * `MODEL-LR4-3WAY` ($T_0$: 3-Way Linkwitz-Riley 4th Order LTI Model)
    * `MODEL-BUTTERWORTH-2WAY` ($T_0$: Butterworth 2nd/4th Order Model)
    * `MODEL-SPATIAL-WEIGHTED` ($T_0$: Spatial Multi-Position Summing Model)
* **Verification:** Verify model retrieval, dependency resolution, assumption linking, and mechanistic audits.

---

### Phase E4 — Unknown Registry & Residual Assessment
* **Target Files:**
  * `src/acoustiforge/epistemic/unknowns.py`
  * `src/acoustiforge/epistemic/residuals.py`
* **Components:**
  * `UnknownDescriptor` value object
  * `UnknownRegistry` container
  * `ResidualAssessment` value object
  * `ResidualClassifier.assess_residual()` calculating deterministic autocorrelation ($r_1$) and outputting candidate explanatory classes with diagnostic confidence.
* **Verification:** Test synthetic residual vectors with known noise, parameter offsets, boundary limits, and systematic unmodelled resonance dips.

---

### Phase E5 — Model Challenge Framework
* **Target Files:**
  * `src/acoustiforge/epistemic/challenges.py`
* **Components:**
  * `ModelChallenge` contract (`challenge_id`, `target_model_id`, `challenged_assumption_ids`, `triggering_residual_id`, `competing_hypothesis_id`, `status`, `evidence_ids`)
  * `ChallengeRegistry` workflow manager
  * Challenge state transitions: `UNCHALLENGED` $\to$ `UNDER_INVESTIGATION` $\to$ `EVIDENCE_SUPPORTED` / `CHALLENGE_REJECTED` $\to$ `EPISTEMIC_ACCEPTED`.
* **Verification:** Lifecycle tests verifying challenge creation, state transitions, and immutable audit trails.

---

### Phase E6 — Shadow Model Competition & Evidence Profiles
* **Target Files:**
  * `src/acoustiforge/epistemic/competition.py`
  * `src/acoustiforge/epistemic/shadow/runner.py`
* **Components:**
  * `ModelEvidenceProfile` calculating:
    * RMS Fit ($E_{\text{rms}}$), Ripple ($R$)
    * Parameter Count ($k$), AIC, BIC
    * Residual Autocorrelation ($r_1$)
    * Robustness Score & Domain Coverage
  * `ModelComparison` aggregating comparative candidate profiles without declaring singular "winner".
  * `ShadowTournamentRunner` evaluating $T_0$ vs $T_1$ against identical `FrequencyResponseData` without touching Core production state.
* **Verification:** Multi-model benchmark test demonstrating $T_1$ outperforming $T_0$ under AIC/BIC on synthetic data with unmodelled driver resonance.

---

### Phase E7 — Falsification Engine (Review Trigger)
* **Target Files:**
  * `src/acoustiforge/epistemic/falsification.py`
* **Components:**
  * `FalsificationEngine` testing candidate models against their declared `FalsificationCriterion` thresholds.
  * Deterministic transition: `VALIDATED_MODEL` $\to$ `FALSIFICATION_EVIDENCE_DETECTED` $\to$ `UNDER_REVIEW`.
  * `DiscriminatingExperimentFinder` locating frequency bands $\arg\max_f |\hat{H}_{T_0}(f) - \hat{H}_{T_1}(f)|$.
* **Verification:** Refutation test case demonstrating automatic falsification review triggering.

---

### Phase E8 — Objective Challenge Framework
* **Target Files:**
  * `src/acoustiforge/epistemic/objectives.py`
* **Components:**
  * `ObjectiveDescriptor` (`objective_id`, `name`, `formula_description`, `proxy_for`, `assumptions`)
  * `ObjectiveChallenge` contract
  * Shadow evaluation of alternative objectives without altering Core optimizer loss.
* **Verification:** Verify candidate objective evaluation in shadow mode.

---

### Phase E9 — Representation Challenge Framework
* **Target Files:**
  * `src/acoustiforge/epistemic/representations.py`
* **Components:**
  * `RepresentationDescriptor` (`formalism_id`, `mathematical_domain`, `primitives`, `capabilities`, `limitations`)
  * Canonical representations:
    * `REP-PHASOR-FRD` (Frequency Response Phasors $\mathbb{C}^N$)
    * `REP-TIME-IR` (Discrete Time Impulse Responses $\mathbb{R}^N$)
    * `REP-STATE-SPACE` (Continuous/Discrete State Space $(\mathbf{A}, \mathbf{B}, \mathbf{C}, \mathbf{D})$)
    * `REP-MODAL` (Acoustic Cavity Modal Expansion)
* **Verification:** Representation registry queries and shadow mapping.

---

### Phase E10 — Theory Transition Ledger & 20-Point Red-Team Test Suite
* **Target Files:**
  * `src/acoustiforge/epistemic/transitions.py`
  * `src/acoustiforge/epistemic/store.py`
  * `tests/epistemic/test_epistemic_red_team.py`
* **Components:**
  * `TheoryTransition` value object and ledger
  * Append-only JSONL epistemic store (`epistemic_ledger.jsonl`)
  * Implementation of all **20 Required Red-Team Tests**:
    * **Test 1:** Model challenge triggered by persistent residual.
    * **Test 2:** Unknown phenomenon represented in Zone U without invalidation.
    * **Test 3:** Alternative model evaluated against identical evidence in shadow mode.
    * **Test 4:** Candidate alternative objective evaluated in shadow mode.
    * **Test 5:** Non-standard representation hosted in shadow layer.
    * **Test 6:** Model falsification criterion triggers `UNDER_REVIEW`.
    * **Test 7:** Full $T_0 \to T_1$ theory transition lineage reconstruction.
    * **Test 8:** AI-generated $T_1$ blocked from silent production promotion.
    * **Test 9:** Bitwise deterministic reproducibility of shadow tournaments.
    * **Test 10:** Historical preservation of rejected hypotheses and evidence.
    * **Test 11:** Production Core mutation resistance (authoritative Core immutable).
    * **Test 12:** Epistemic downgrade of trusted model to domain-limited without erasing history.
    * **Test 13:** Zone-H applicability challenge without deleting invariant.
    * **Test 14:** Residual assessment produces candidate explanations under uncertainty.
    * **Test 15:** Falsification evidence triggers review rather than immediate destruction.
    * **Test 16:** Lower AIC/BIC does not automatically grant `PRODUCTION_AUTHORITY`.
    * **Test 17:** Mechanistic assessment requires structured evidence.
    * **Test 18:** Epistemic acceptance is isolated from production Core.
    * **Test 19:** Unknown in Zone U survives model refutation.
    * **Test 20:** Production authority requires explicit structural promotion path.
* **Verification:** Execute all 20 red-team tests and full regression suite.

---
*End of Document DOC-EPISTEMIC-PLAN-01. Governed by DOC-EPISTEMIC-AMEND-01.*

