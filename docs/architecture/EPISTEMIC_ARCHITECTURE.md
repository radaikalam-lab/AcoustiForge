# AcoustiForge — Epistemic Architecture Specification

**Document ID:** `DOC-EPISTEMIC-ARCH-01`  
**Governing Authority:** AcoustiForge Epistemic Framework & Semantic Amendment (`DOC-EPISTEMIC-AMEND-01`)  
**Date:** 2026-09-19  
**Status:** Authoritative Epistemic Architecture (Phases E0.5–E10 Complete & Frozen)

---

## 1. Foundational Epistemic Safety Law

AcoustiForge enforces a strict and inviolable separation of concerns between **Deterministic Production Execution** and **Epistemic Scientific Reasoning**:

$$\boxed{
\text{Epistemic Novelty} \neq \text{Production Authority}
}$$

> **Architectural Law:**
> Epistemic reasoning may discover, challenge, compare, formulate candidate theories, and recommend.
> **Deterministic production Core remains authoritative.**
>
> The Epistemic Layer operates strictly beside and above the production Core. It may evaluate shadow tournaments, detect falsification criteria, and log auditable theory transitions; it cannot silently mutate or unilaterally promote any model, objective, or representation into the production execution plane.

---

## 2. The Four Epistemic Zones

All entities, assumptions, models, and empirical observations are partitioned into four explicit zones:

* **ZONE_H — Invariants / Bounded Hard Constraints:**
  Mathematical theorems, conservation laws, physical limits, hardware operating limits, and bounded identities.
  * Invariants must declare an explicit domain of validity.
  * Challenges to Zone H are strictly categorized (`H_APPLICABILITY_CHALLENGE`, `H_CLASSIFICATION_CHALLENGE`, `H_FUNDAMENTAL_CHALLENGE`).
  * Invariant: There is no automatic `ZONE_H -> FALSE` transition.

* **ZONE_M — Models / Explanatory Theories / Approximations:**
  Candidate mathematical and physical formulations ($T_0, T_1, T_2$).
  * Models capture mechanisms (e.g. transfer functions, lumped-parameter approximations, non-linear thermal models).
  * Competing models coexist simultaneously without any model being crowned universal ontological truth.
  * Models declare explicit falsification criteria triggering structured review rather than silent deletion.

* **ZONE_P — Problem Framing / Objectives / Ontology / Representations:**
  The formulation of what problem is being addressed, which variables are modeled, and how objectives are measured.
  * Formulates optimization objectives, primitive target dimensions, representation formalisms, and proxy losses.
  * Supports questioning: *"Is the problem formulation incomplete?"* and *"Does the representation omit critical physical variables?"*

* **ZONE_U — Unknowns / Anomalies / Unexplained Phenomena:**
  Mandatory holding area for phenomena that cannot be explained or represented within existing models.
  * Captures systematic residuals, unmodelled variables, and pre-ontological observations.
  * Core Invariant: `UNKNOWN != INVALID` and `NOT_REPRESENTABLE != PHYSICALLY_IMPOSSIBLE`.

---

## 3. Frozen Semantic Vocabulary & Invariant Distinctions

### 3.1 Epistemic Vocabulary
* **Epistemic Zones:** `ZONE_H`, `ZONE_M`, `ZONE_P`, `ZONE_U`
* **Epistemic Classes:** `MATHEMATICAL_THEOREM`, `PHYSICAL_INVARIANT`, `CONSTITUTIVE_MODEL`, `APPROXIMATION`, `EMPIRICAL_REGULARITY`, `ENGINEERING_HEURISTIC`, `OBJECTIVE_ASSUMPTION`, `ONTOLOGICAL_ASSUMPTION`, `UNKNOWN`
* **Epistemic Lifecycle States:** `HYPOTHESIS`, `TESTED_CANDIDATE`, `VALIDATED_MODEL`, `FALSIFICATION_EVIDENCE_DETECTED`, `UNDER_REVIEW`, `DOMAIN_LIMITED`, `CHALLENGED`, `FALSIFIED`, `DEPRECATED`
* **Challenge Lifecycle States:** `UNCHALLENGED`, `CHALLENGE_PROPOSED`, `UNDER_INVESTIGATION`, `EVIDENCE_SUPPORTED`, `CHALLENGE_REJECTED`, `EPISTEMIC_ACCEPTED`, `PRODUCTION_CANDIDATE`, `PRODUCTION_AUTHORITY`
* **Evidence Types:** `MATHEMATICAL_PROOF`, `PHYSICAL_MEASUREMENT`, `EXPERIMENTAL_RESULT`, `SIMULATION`, `OBSERVATIONAL_DATA`, `ENGINEERING_TEST`, `HUMAN_FEEDBACK`, `AI_GENERATED_HYPOTHESIS`
* **Evidence Relations:** `SUPPORTS`, `CONTRADICTS`, `CHALLENGES`, `LOCALIZES`, `DISCRIMINATES`, `DOES_NOT_TEST`

### 3.2 Semantic Invariants
The architecture enforces the following invariant distinctions across all epistemic and production layers:

* $\text{MODEL} \neq \text{LAW}$
* $\text{APPROXIMATION} \neq \text{LAW}$
* $\text{HEURISTIC} \neq \text{LAW}$
* $\text{HYPOTHESIS} \neq \text{EVIDENCE}$
* $\text{EVIDENCE} \neq \text{TRUTH}$
* $\text{FALSIFICATION\_EVIDENCE} \neq \text{FALSIFIED}$
* $\text{EPISTEMIC\_ACCEPTANCE} \neq \text{PRODUCTION\_AUTHORITY}$
* $\text{PRODUCTION\_CANDIDATE} \neq \text{PRODUCTION\_AUTHORITY}$
* $\text{UNKNOWN} \neq \text{INVALID}$
* $\text{NOT\_REPRESENTABLE} \neq \text{PHYSICALLY\_IMPOSSIBLE}$
* $\text{OBJECTIVE} \neq \text{CONSTRAINT}$
* $\text{OBJECTIVE} \neq \text{OPTIMIZER}$
* $\text{REPRESENTATION} \neq \text{PHENOMENON}$

---

## 4. End-to-End Architecture Diagram

```text
                         ┌─────────────────────────┐
                         │       OBSERVATION       │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   REPRESENTATION (E9)   │
                         └────────────┬────────────┘
                                      │
                      ┌───────────────┴───────────────┐
                      ▼                               ▼
             UNKNOWN / RESIDUAL (E4)            CHALLENGE (E5)
                      │                               │
                      └───────────────┬───────────────┘
                                      ▼
                                 MODEL (E3)
                                      │
                                      ▼
                           MODEL COMPETITION (E6)
                                      │
                                      ▼
                        FALSIFICATION / REVIEW (E7)
                                      │
                                      ▼
                             OBJECTIVE (E8)
                                      │
                                      ▼
                         EPISTEMIC CONCLUSION (E10)
                                      │
                                      ▼
                         PRODUCTION CANDIDATE (E10)
                                      │
══════════════════════════════════════╪══════════════════════════════════════
                            NON-AUTHORITY BOUNDARY
                          EXPLICIT AUTHORITY GATE
══════════════════════════════════════╪══════════════════════════════════════
                                      │ (Requires External Authorization)
                                      ▼
                         DETERMINISTIC CORE (PROD)
```

---

## 5. Incremental Contributions (Phases E1–E10)

* **Phase E0.5 — Semantic Freeze:**
  Established the foundational semantic amendments, four zones, and the non-authority invariant $\text{Epistemic Novelty} \neq \text{Production Authority}$.
* **Phase E1 — Epistemic Vocabulary:**
  Introduced typed enumerations and value objects for zones, epistemic classes, lifecycle states, evidence taxonomy, and Zone-H challenge classifications.
* **Phase E2 — Assumption Registry:**
  Created the immutable `AssumptionDescriptor` and `AssumptionRegistry` for making scientific assumptions explicit, bounded, and auditable without truth/confidence semantics.
* **Phase E3 — Model Registry:**
  Introduced `ModelDescriptor`, `FalsificationCriterion`, and `ModelRegistry` for cataloging mechanistic theories without declaring winners or computing adequacy scores.
* **Phase E4 — Unknowns & Residuals:**
  Implemented `UnknownDescriptor`, `ResidualDescriptor`, and `ResidualAssessment` to treat unexplained residuals and anomalies as observations rather than automatic model failures.
* **Phase E5 — Challenge Representation:**
  Established `EpistemicChallenge` and `ChallengeRegistry` to formalize questioning of models, assumptions, and scopes under explicit test conditions without automatic mutation.
* **Phase E6 — Model Competition:**
  Built multi-dimensional `ModelEvidenceProfile` and `ModelComparison` to compare candidate models across fit, complexity (AIC/BIC), and robustness without choosing a single winner.
* **Phase E7 — Falsification & Review:**
  Created `FalsificationEvidence` and `ModelReviewRecord` implementing the explicit state transition boundary $\text{VALIDATED\_MODEL} \to \text{FALSIFICATION\_EVIDENCE\_DETECTED} \to \text{UNDER\_REVIEW} \to \{\text{DOMAIN\_LIMITED}, \text{CHALLENGED}, \text{FALSIFIED}\}$.
* **Phase E8 — Objective Challenge:**
  Introduced `ObjectiveDescriptor`, `ObjectiveChallenge`, and `ObjectiveRegistry` to separate optimization criteria, proxy losses, and constraint boundaries from physics and models.
* **Phase E9 — Representation Challenge:**
  Built `RepresentationDescriptor`, `RepresentationGap`, and `RepresentationChallenge` enforcing the separation $\text{NOT\_REPRESENTABLE} \neq \text{PHYSICALLY\_IMPOSSIBLE}$.
* **Phase E10 — Theory Transition, Integration & Full Red-Team:**
  Introduced `TheoryTransitionRecord` and `TheoryTransitionRegistry` to synthesize the complete end-to-end lifecycle and validated all architectural invariants through a 26-point red-team suite (Matrix A–Z).

---

## 6. Theory Transition Semantics

A theory transition is an **audit record of scientific lineage**, not an automated model promoter.

```python
@dataclass(frozen=True, slots=True)
class TheoryTransitionRecord:
    transition_id: str
    source_model_id: Optional[str]
    candidate_model_ids: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    challenge_refs: tuple[str, ...]
    review_refs: tuple[str, ...]
    objective_refs: tuple[str, ...]
    representation_refs: tuple[str, ...]
    conclusion: str
    provenance: str
```

### Transition Semantics
1. **Lineage Preservation:** Explicitly records what model was questioned, what evidence motivated the transition, what alternatives were compared, and what remains provisional.
2. **No Implicit Truth:** A transition record does not assert that the candidate model is universal truth or that the source model is completely false.
3. **No Automatic Core Mutation:** Recording a theory transition creates an auditable candidate record; it never modifies the running deterministic production Core.

---

## 7. Phase Ledger

| Phase | Purpose | Status | Production Core Modified |
| :--- | :--- | :--- | :--- |
| **E0.5** | Semantic Freeze | FROZEN | No |
| **E1** | Epistemic Vocabulary | FROZEN | No |
| **E2** | Assumption Registry | FROZEN | No |
| **E3** | Model Registry | FROZEN | No |
| **E4** | Unknowns / Residuals | FROZEN | No |
| **E5** | Challenges | FROZEN | No |
| **E6** | Model Competition | FROZEN | No |
| **E7** | Falsification / Review | FROZEN | No |
| **E8** | Objective Challenge | FROZEN | No |
| **E9** | Representation Challenge | FROZEN | No |
| **E10** | Integration / Red-Team | COMPLETE / FROZEN | No |

---

## 8. Incremental Change History

* **E0.5 (2026-09-19):** Established semantic freeze amendment (`EPISTEMIC_SEMANTIC_AMENDMENT.md`). Defined 4 zones and core safety boundaries. Production Core: Unmodified.
* **E1 (2026-09-19):** Implemented core vocabulary (`vocabulary.py`). Established typed enums for zones, classes, states, and evidence taxonomy. Added `test_epistemic_vocabulary.py`. Production Core: Unmodified.
* **E2 (2026-09-19):** Implemented assumption registry (`assumptions.py`). Made domain assumptions explicit and immutable. Added `test_epistemic_assumptions.py`. Production Core: Unmodified.
* **E3 (2026-09-19):** Implemented model registry (`models.py`). Formalized candidate models and falsification criteria. Added `test_epistemic_models.py`. Production Core: Unmodified.
* **E4 (2026-09-19):** Implemented unknowns and residuals (`unknowns.py`, `residuals.py`). Added candidate explanation taxonomy without truth claims. Added `test_epistemic_unknowns.py`, `test_epistemic_residuals.py`. Production Core: Unmodified.
* **E5 (2026-09-19):** Implemented challenge representation (`challenges.py`). Supported scoped questioning and proposed test protocols. Added `test_epistemic_challenges.py`. Production Core: Unmodified.
* **E6 (2026-09-19):** Implemented model competition (`competition.py`). Multi-dimensional profiles with AIC/BIC dimensions and trade-off summaries without singular winners. Added `test_epistemic_competition.py`. Production Core: Unmodified.
* **E7 (2026-09-19):** Implemented falsification evidence and review state machine (`falsification.py`). Formalized `UNDER_REVIEW` workflow. Added `test_epistemic_falsification.py`. Production Core: Unmodified.
* **E8 (2026-09-19):** Implemented objective challenge (`objectives.py`). Separated optimization intent, proxies, and physics. Added `test_epistemic_objectives.py`. Production Core: Unmodified.
* **E9 (2026-09-19):** Implemented representation challenge (`representation.py`). Formalized representational limits and gaps. Added `test_epistemic_representation.py`. Production Core: Unmodified.
* **E10 (2026-09-19):** Implemented theory transitions (`transitions.py`), integrated synthetic lifecycle scenario, full Red-Team Matrix (A–Z), and consolidated epistemic architecture. Added `test_epistemic_transitions.py`. Production Core: Unmodified.

---

## 9. Architectural Decision Record (ADR)

### ADR-EPISTEMIC-01: Epistemic Layer Isolation & Explicit Production Authority Gate

#### Context
AcoustiForge provides high-performance, deterministic computational audio processing and hardware synthesis. As AI agents and automated reasoning systems explore alternative models, assumptions, and objectives, there is a fundamental risk that novel hypotheses or automated tournament winners could silently mutate production DSP pipelines.

#### Decision
1. **Strict Epistemic Isolation:** All epistemic reasoning modules (`src/acoustiforge/epistemic/`) are strictly read-only observers relative to Core.
2. **Explicit Authority Gate:** Epistemic acceptance (`EPISTEMIC_ACCEPTED`) and candidate designation (`PRODUCTION_CANDIDATE`) are advisory value objects. Promotion to `PRODUCTION_AUTHORITY` requires an explicit, audited external authorization gate.
3. **No Automatic Promotion:** Neither AIC/BIC superiority, falsification evidence detection, nor theory transition recording can automatically alter production behavior.

#### Consequences
* **Positive:** Complete protection of production safety, determinism, and hardware invariants against runaway AI hypothesis loops.
* **Positive:** Full auditability and scientific reproducibility across all candidate model transitions.
* **Trade-off:** Human/external authority confirmation is required to promote new models into production.
