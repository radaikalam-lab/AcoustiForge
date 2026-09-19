# AcoustiForge — Epistemic Semantic Amendment & E0.5 Freeze

**Document ID:** `DOC-EPISTEMIC-AMEND-01`  
**Base Documents:** `DOC-EPISTEMIC-REV-01`, `DOC-EPISTEMIC-ARCH-01`, `DOC-EPISTEMIC-GAPS-01`, `DOC-EPISTEMIC-PLAN-01`  
**Phase:** E0.5 (Epistemic Semantics Freeze)  
**Date:** 2026-09-19  
**Status:** Frozen & Approved Semantic Contract

---

## 1. Foundational Epistemic Law & Invariants

The foundational law is absolute and immutable:

$$\boxed{\text{Epistemic Novelty} \neq \text{Production Authority}}$$

1. **Epistemic Layer Authority:** May observe, classify, question, hypothesize, construct alternative models, evaluate competing models in shadow execution, identify contradictions, identify unexplained residuals, challenge assumptions, challenge objectives, challenge representations, and propose theory transitions.
2. **Production Core Inviolability:** May **never** silently modify production mathematics, modify production constraints, modify DSP compilation, modify execution graphs, modify hardware execution handles, or promote an epistemic hypothesis into production authority.
3. **Deterministic Authority:** The production Core remains authoritative and deterministic for all executable DSP, physical protection limits, and validation contracts.

---

## 2. Epistemic Vocabulary Semantic Freeze

The following concepts are strictly defined as distinct machine-readable categories and must **never** be conflated:

```text
MATHEMATICAL_THEOREM      : Formal mathematical identity valid within its analytical domain.
PHYSICAL_INVARIANT        : Validated physical conservation law or hardware protection limit.
CONSTITUTIVE_MODEL        : Idealized physical relationship (e.g. acoustic summing, crossover alignment).
APPROXIMATION             : Deliberate simplification of physical reality (e.g. LTI, minimum-phase, far-field).
EMPIRICAL_REGULARITY      : Observed statistical or calibrated curve (e.g. microphone calibration file).
ENGINEERING_HEURISTIC     : Pragmatic rule-of-thumb (e.g. 3-way crossover spacing >= 1.5x, filter Q bounds).
OBJECTIVE_ASSUMPTION      : Assumption regarding quality proxy (e.g. flat on-axis SPL as fidelity proxy).
ONTOLOGICAL_ASSUMPTION    : Choice of primitive entities/representations (e.g. transfer-function phasors).
HYPOTHESIS                : Candidate explanation, parameter set, or model structure proposed for evaluation.
UNKNOWN                   : Unexplained residual, unmeasured physical variable, or unrepresented phenomenon.
EVIDENCE                  : Empirical, mathematical, or experimental observation with explicit provenance.
CHALLENGE                 : Formal, auditable claim questioning an invariant, model, objective, or assumption.
FALSIFICATION_EVIDENCE    : Observation demonstrating model prediction failure beyond defined bounds.
EPISTEMIC_ACCEPTANCE      : Scientific consensus status within the Epistemic Layer based on evidence profiles.
PRODUCTION_CANDIDATE      : Epistemically accepted model packaged and queued for deterministic Core review.
PRODUCTION_AUTHORITY      : Authoritative model compiled and frozen in the production execution Core.
```

### Invariant Semantic Non-Equivalences

$$\begin{aligned}
\text{MODEL} &\neq \text{LAW} \\
\text{APPROXIMATION} &\neq \text{LAW} \\
\text{HEURISTIC} &\neq \text{LAW} \\
\text{HYPOTHESIS} &\neq \text{EVIDENCE} \\
\text{EVIDENCE} &\neq \text{TRUTH} \\
\text{FALSIFICATION\_EVIDENCE} &\neq \text{FALSIFIED} \\
\text{EPISTEMIC\_ACCEPTANCE} &\neq \text{PRODUCTION\_AUTHORITY} \\
\text{UNKNOWN} &\neq \text{INVALID} \\
\text{NOT\_REPRESENTABLE} &\neq \text{PHYSICALLY\_IMPOSSIBLE}
\end{aligned}$$

---

## 3. Zone H Challenge Semantics

Zone H represents authoritative mathematical and physical constraints within an explicitly declared domain and scope. It is not an unchallengeable dogma.

A Zone H challenge must explicitly declare its challenge category:

1. **`H_APPLICABILITY_CHALLENGE`:** Challenges whether the invariant applies to the specific operating domain, representation, or boundary condition (e.g. Does a free-field assumption apply in an enclosed cabin?).
2. **`H_CLASSIFICATION_CHALLENGE`:** Challenges whether a rule was incorrectly classified as a hard invariant (e.g. Demonstrating that a $1.5\times$ crossover spacing rule is an engineering heuristic, not a physical law).
3. **`H_FUNDAMENTAL_CHALLENGE`:** Claims that the underlying physical or mathematical identity itself is invalid.

### Invariant: No Automatic Zone H Invalidation
* There is **no automatic transition** $\text{ZONE\_H} \to \text{FALSE}$.
* A fundamental Zone H challenge remains an open research state requiring explicit human review, empirical replication, and formal scientific evidence before any system modification.

---

## 4. Residual Assessment Semantics (Assessment vs Truth)

A residual classifier must never claim ontological truth. A low SNR does not prove measurement error; high residual autocorrelation does not prove model failure.

The classifier outputs a `ResidualAssessment`, not a factual verdict:

$$\boxed{\text{Residual} \longrightarrow \text{Candidate Explanations (Assessment)}} \quad \neq \quad \boxed{\text{Residual} \longrightarrow \text{Truth}}$$

```python
@dataclass(frozen=True, slots=True)
class ResidualAssessment:
    """Diagnostic assessment of residual characteristics providing candidate hypotheses without asserting truth."""
    assessment_id: str
    residual_id: str
    candidate_classes: tuple[ResidualClassificationType, ...]  # e.g. (MODEL_ERROR, MISSING_VARIABLE)
    evidence: dict[str, Any]  # e.g. {"autocorrelation_r1": 0.81, "snr_db": 34.5, "converged": True}
    tests_run: tuple[str, ...]  # Diagnostic test identifiers executed
    confidence: float  # Deterministic heuristic diagnostic confidence (0.0 to 1.0)
    unresolved: bool  # True if residual could not be conclusively isolated
    rationale: str
```

---

## 5. Falsification Semantics (Review Trigger vs Immediate Refutation)

Exceeding a falsification threshold is **evidence for review**, not an immediate automated annihilation of the model.

Contradictory observations may arise from sensor calibration drift, boundary reflections, out-of-domain operation, or unmodelled physical variables.

### State Machine for Falsification:

$$\text{VALIDATED\_MODEL} \longrightarrow \text{FALSIFICATION\_EVIDENCE\_DETECTED} \longrightarrow \text{UNDER\_REVIEW} \longrightarrow \begin{cases} \text{DOMAIN\_LIMITED} \\ \text{CHALLENGED} \\ \text{FALSIFIED} \end{cases}$$

---

## 6. Multi-Model Competition & Evidence Profiles (No Single "Winner")

The Epistemic Layer does not produce a simplistic `ModelWinner`, `BestModel`, or `TruthModel`.

Instead, shadow tournaments evaluate candidate models across multi-dimensional criteria and produce a `ModelComparison`:

1. **`ModelEvidenceProfile` Dimensions:**
   * Empirical Fit: RMS tracking error ($E_{\text{rms}}$), passband ripple ($R$).
   * Structural Parsimony: Parameter count ($k$), Akaike Information Criterion ($\text{AIC}$), Bayesian Information Criterion ($\text{BIC}$).
   * Residual Structure: Autocorrelation coefficient ($r_1$), runs test.
   * Robustness: Parameter sensitivity under perturbation.
   * Domain Coverage: Fraction of operational frequency/SPL envelope valid.
   * Falsification Margin: Proximity to refutation bounds.
2. **`ModelComparison` Output:**
   * Contains comparative evidence profiles, trade-offs, discriminating predictions, and unresolved uncertainties.
   * A lower BIC indicates greater statistical parsimony, **not** that the model is universal physical truth.

---

## 7. Structured Mechanistic Assessment

The arbitrary scalar `mechanistic_adequacy_score: float` is formally replaced with the structured contract `MechanisticAssessment`:

```python
@dataclass(frozen=True, slots=True)
class MechanisticAssessment:
    """Structured audit of physical mechanisms represented vs omitted."""
    assessment_id: str
    model_id: str
    mechanisms_represented: tuple[str, ...]  # e.g. ("acoustic_wave_delay", "biquad_resonance")
    mechanisms_omitted: tuple[str, ...]      # e.g. ("baffle_diffraction", "driver_thermal_compression")
    supporting_evidence_ids: tuple[str, ...]
    contradictory_evidence_ids: tuple[str, ...]
    explanatory_predictions: tuple[str, ...]
    causal_assumptions: tuple[str, ...]
    domain_limitations: tuple[str, ...]
```

---

## 8. Epistemic Acceptance vs Production Authority

The life cycle from hypothesis to production authority is strictly staged and decoupled:

```text
       AI / Untrusted Observation
                   ↓
               HYPOTHESIS
                   ↓
            CANDIDATE MODEL
                   ↓
        SHADOW TOURNAMENT RUNNER
                   ↓
      MODEL EVIDENCE PROFILES (AIC/BIC/r1)
                   ↓
          EPISTEMIC ACCEPTANCE
                   ↓
          PRODUCTION CANDIDATE
                   ↓
     EXPLICIT AUTHORIZATION (Human / Gate)
                   ↓
     DETERMINISTIC CORE VALIDATION
                   ↓
          PRODUCTION AUTHORITY
```

* **API Constraint:** There is **no programmatic path** for an `AI_GENERATED_HYPOTHESIS` or an `EPISTEMIC_ACCEPTED` model to directly mutate Core contracts, compiled graphs, or hardware backends.

---

## 9. Evidence Relationship Semantics

Evidence is not merely a list of strings; it participates in explicit semantic relationships:

```python
class EvidenceRelation(str, Enum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CHALLENGES = "CHALLENGES"
    LOCALIZES = "LOCALIZES"
    DISCRIMINATES = "DISCRIMINATES"
    DOES_NOT_TEST = "DOES_NOT_TEST"

@dataclass(frozen=True, slots=True)
class EpistemicEvidenceLink:
    """Explicit relational link between an evidence item and a model, assumption, or unknown."""
    evidence_id: str
    target_id: str  # Model ID, Assumption ID, or Unknown ID
    relation: EvidenceRelation
    confidence: float
    notes: Optional[str] = None
```

---

## 10. Dynamic Baseline Test Methodology

* Test counts must **never be hardcoded** (e.g. 552 or 554).
* At the start of Phase E1, `pytest` establishes the dynamic baseline:
  $$\text{Baseline} = (\text{collected}, \text{passed}, \text{failed}, \text{errors}, \text{skipped}, \text{warnings})$$
* All future verification runs compare against the dynamically established baseline.
* The core invariant is: **Existing Core behavior must not regress, and existing tests must remain 100% green**.

---

## 11. Expanded 20-Point Red-Team Verification Suite

The red-team test suite in `tests/epistemic/test_epistemic_red_team.py` contains all 20 required verification tests:

| Test ID | Name | Verification Requirement |
| :--- | :--- | :--- |
| **Test 1** | `test_model_challenge_on_residual` | Persistent systematic residual triggers a model challenge rather than endless parameter optimization. |
| **Test 2** | `test_unknown_representation` | Unexplained phenomenon in Zone U is represented without raising validation exceptions. |
| **Test 3** | `test_alternative_model_competition` | Competing models $T_0, T_1$ evaluate against identical evidence in shadow mode. |
| **Test 4** | `test_objective_challenge_shadow` | Candidate alternative objective evaluates in shadow mode without altering production loss. |
| **Test 5** | `test_representation_challenge` | Non-standard representation (state-space, modal) exists in shadow layer. |
| **Test 6** | `test_model_falsification_criteria` | Explicit falsification criterion flags refuting evidence for review. |
| **Test 7** | `test_theory_transition_lineage` | Reconstructs full lineage $T_0 \to T_1$ with rationale and evidence hash. |
| **Test 8** | `test_no_silent_promotion` | AI hypothesis cannot bypass validation or promote itself to production authority. |
| **Test 9** | `test_tournament_reproducibility` | Shadow tournaments produce identical bitwise results on identical inputs. |
| **Test 10** | `test_historical_preservation` | Rejecting a hypothesis preserves its historical record and evidence intact. |
| **Test 11** | `test_production_core_immutability` | Epistemic operations cannot mutate Core modules, dispatchers, or ALSA handles. |
| **Test 12** | `test_epistemic_downgrade` | Trusted model can be demoted to domain-limited without erasing history. |
| **Test 13** | `test_zone_h_applicability_challenge` | Invariant applicability can be challenged without deleting or mutating the invariant. |
| **Test 14** | `test_residual_assessment_uncertainty` | Residual produces multiple candidate explanations without asserting truth. |
| **Test 15** | `test_falsification_evidence_triggers_review` | Triggering a falsification threshold enters `UNDER_REVIEW` without immediate deletion. |
| **Test 16** | `test_evidence_does_not_create_truth` | Lower AIC/BIC does not automatically grant `PRODUCTION_AUTHORITY`. |
| **Test 17** | `test_mechanistic_assessment_auditable` | Mechanistic assessment requires structured represented/omitted lists. |
| **Test 18** | `test_epistemic_acceptance_isolated` | `EPISTEMIC_ACCEPTED` status cannot mutate the production Core. |
| **Test 19** | `test_unknown_survives_model_failure` | Failed candidate explanation preserves the underlying Zone U observation. |
| **Test 20** | `test_production_authority_structural_separation` | Passing epistemic candidate directly into production raises validation error. |

---

## 12. E0.5 Semantics Freeze Acceptance Checklist

- [x] Epistemic vocabulary frozen with all 16 distinct categories.
- [x] Legal state transitions defined from Hypothesis to Production Authority.
- [x] Zone H challenge semantics defined (`H_APPLICABILITY`, `H_CLASSIFICATION`, `H_FUNDAMENTAL`).
- [x] Residual assessment semantics defined (`ResidualAssessment`, assessment vs truth).
- [x] Falsification evidence separated from immediate model refutation.
- [x] Model comparison separated from model truth (`ModelComparison`, no `ModelWinner`).
- [x] Mechanistic adequacy scalar resolved into structured `MechanisticAssessment`.
- [x] Epistemic acceptance separated from production authority.
- [x] Evidence relationship semantics defined (`EvidenceRelation`, `EpistemicEvidenceLink`).
- [x] Unknown semantics preserved (`UNKNOWN != INVALID`, `NOT_REPRESENTABLE != IMPOSSIBLE`).
- [x] Production mutation boundary formally specified ($\text{Epistemic Novelty} \neq \text{Production Authority}$).
- [x] Baseline test methodology corrected to dynamic pytest collection.
- [x] Amendment document created (`EPISTEMIC_SEMANTIC_AMENDMENT.md`).
- [x] Zero production Core source files modified.

---
*End of Document DOC-EPISTEMIC-AMEND-01. Phase E0.5 Complete.*
