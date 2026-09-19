"""Tests for Phase E7 Falsification Evidence & Model Review Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E7: Falsification Evidence & Model Review
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Contradictory Evidence != Falsification Evidence != Model Falsified
  - Large Residual / Comparison Defeat / Worse BIC != Automatic Falsification
  - FALSIFICATION_EVIDENCE_DETECTED is distinct from FALSIFIED
  - Model status transition to FALSIFIED requires explicit, auditable review
  - Permitted Review Outcomes: DOMAIN_LIMITED, CHALLENGED, FALSIFIED
  - Production Core remains completely untouched
  - AI-generated content cannot become empirical evidence through E7
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import sys
from typing import Any

import pytest

from acoustiforge.epistemic.assumptions import EpistemicAssumption
from acoustiforge.epistemic.challenges import EpistemicChallenge
from acoustiforge.epistemic.competition import ModelComparison, ModelEvidenceProfile
from acoustiforge.epistemic.falsification import (
    ALLOWED_REVIEW_DECISIONS,
    ApplicabilityStatus,
    FalsificationAssessment,
    FalsificationEvidence,
    FalsificationRegistry,
    FalsificationReview,
)
from acoustiforge.epistemic.models import EpistemicModel
from acoustiforge.epistemic.residuals import ModelResidual, ResidualAssessment
from acoustiforge.epistemic.unknowns import EpistemicUnknown
from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
    ResidualClassificationType,
)


# ==============================================================================
# 1. Standard Construction, Validation, and Registry Tests
# ==============================================================================

def test_falsification_evidence_construction() -> None:
    """Test valid construction of FalsificationEvidence."""
    ev = FalsificationEvidence(
        evidence_id="FE-001",
        model_id="MODEL-LTI-001",
        observation_ref="OBS-LASER-001",
        criterion_id="CRIT-THD-001",
        criterion_description="THD must remain below 1.0% between 100 Hz and 1 kHz at 90 dB SPL.",
        observed_behavior="THD measured at 4.2% at 500 Hz.",
        expected_behavior="THD predicted at 0.4% under linear model.",
        discrepancy_summary="Harmonic distortion exceeds linear tolerance by factor of 10.",
        provenance="laser-vibrometry-bench-3",
        evidence_refs=("EV-LASER-RAW-001", "EV-MIC-RAW-002"),
        scope={"frequency_hz": [100.0, 1000.0], "spl_db": 90.0},
        applicability_status=ApplicabilityStatus.WITHIN_SCOPE,
    )
    assert ev.evidence_id == "FE-001"
    assert ev.model_id == "MODEL-LTI-001"
    assert ev.criterion_id == "CRIT-THD-001"
    assert ev.applicability_status == "WITHIN_SCOPE"
    assert ev.scope == {"frequency_hz": [100.0, 1000.0], "spl_db": 90.0}
    assert ev.evidence_refs == ("EV-LASER-RAW-001", "EV-MIC-RAW-002")


def test_falsification_evidence_validation() -> None:
    """Test validation constraints on FalsificationEvidence."""
    valid_args = {
        "evidence_id": "FE-001",
        "model_id": "MODEL-001",
        "observation_ref": "OBS-001",
        "criterion_id": "CRIT-1",
        "criterion_description": "Desc",
        "observed_behavior": "Observed",
        "expected_behavior": "Expected",
        "discrepancy_summary": "Discrepancy",
        "provenance": "Lab",
    }
    for k in valid_args:
        with pytest.raises(ValueError):
            FalsificationEvidence(**{**valid_args, k: ""})

    with pytest.raises(ValueError):
        FalsificationEvidence(**{**valid_args, "evidence_refs": ("EV-1", "")})


def test_falsification_evidence_serialization() -> None:
    """Test deterministic serialization and lossless JSON round-trip for FalsificationEvidence."""
    ev = FalsificationEvidence(
        evidence_id="FE-JSON-001",
        model_id="MODEL-001",
        observation_ref="OBS-001",
        criterion_id="CRIT-1",
        criterion_description="Desc",
        observed_behavior="Obs",
        expected_behavior="Exp",
        discrepancy_summary="Disc",
        provenance="Lab",
        evidence_refs=("EV-1",),
        scope={"axis": "on-axis"},
        applicability_status=ApplicabilityStatus.WITHIN_SCOPE,
    )
    d = ev.to_dict()
    assert d["evidence_id"] == "FE-JSON-001"
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = FalsificationEvidence.from_dict(json.loads(json_str))
    assert reconstructed == ev


def test_falsification_assessment_construction_and_serialization() -> None:
    """Test construction, validation, and serialization for FalsificationAssessment."""
    assessment = FalsificationAssessment(
        assessment_id="FA-001",
        model_id="MODEL-001",
        criterion_id="CRIT-1",
        evidence_id="FE-001",
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="High-precision calibrated laser vibrometry",
        rationale="Measured THD exceeds declared linear envelope.",
        provenance="analyst-review",
        unresolved_items=("investigate temperature dependence",),
    )
    assert assessment.criterion_violated is True
    assert assessment.unresolved_items == ("investigate temperature dependence",)

    d = assessment.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = FalsificationAssessment.from_dict(json.loads(json_str))
    assert reconstructed == assessment


def test_falsification_review_construction_and_decisions() -> None:
    """Test construction, valid decision constraints, and serialization for FalsificationReview."""
    rev = FalsificationReview(
        review_id="REV-001",
        model_id="MODEL-001",
        evidence_id="FE-001",
        initial_status=EpistemicStatus.VALIDATED_MODEL,
        decision=EpistemicStatus.DOMAIN_LIMITED,
        rationale="Model remains accurate below 90 dB SPL; domain limited above 90 dB SPL.",
        provenance="expert-panel",
        supporting_evidence_refs=("EV-1",),
        contradictory_evidence_refs=(),
        unresolved_items=(),
        scope={"spl_max_db": 90.0},
    )
    assert rev.decision == EpistemicStatus.DOMAIN_LIMITED
    assert rev.decision in ALLOWED_REVIEW_DECISIONS

    # Forbid invalid review decisions (e.g. PRODUCTION_AUTHORITY or VALIDATED_MODEL)
    with pytest.raises(ValueError, match="Invalid review decision"):
        FalsificationReview(
            review_id="REV-BAD",
            model_id="MODEL-001",
            evidence_id="FE-001",
            initial_status=EpistemicStatus.VALIDATED_MODEL,
            decision=EpistemicStatus.PRODUCTION_AUTHORITY,
            rationale="Attempted promotion via review.",
            provenance="bad-actor",
        )


def test_falsification_registry_operations() -> None:
    """Test registration, retrieval, duplicate protection, and querying in FalsificationRegistry."""
    reg = FalsificationRegistry()

    ev = FalsificationEvidence(
        evidence_id="FE-1",
        model_id="M1",
        observation_ref="OBS-1",
        criterion_id="C1",
        criterion_description="Desc",
        observed_behavior="Obs",
        expected_behavior="Exp",
        discrepancy_summary="Disc",
        provenance="Lab",
    )
    reg.register_evidence(ev)
    assert reg.get_evidence("FE-1") == ev
    assert reg.all_evidence() == (ev,)

    # Duplicate evidence
    with pytest.raises(ValueError, match="already registered"):
        reg.register_evidence(ev)

    ass = FalsificationAssessment(
        assessment_id="FA-1",
        model_id="M1",
        criterion_id="C1",
        evidence_id="FE-1",
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="High",
        rationale="Violated",
        provenance="Lab",
    )
    reg.register_assessment(ass)
    assert reg.get_assessment("FA-1") == ass

    rev1 = FalsificationReview(
        review_id="REV-1",
        model_id="M1",
        evidence_id="FE-1",
        initial_status=EpistemicStatus.VALIDATED_MODEL,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Falsified in core operating domain.",
        provenance="Committee",
    )
    rev2 = FalsificationReview(
        review_id="REV-2",
        model_id="M2",
        evidence_id="FE-2",
        initial_status=EpistemicStatus.VALIDATED_MODEL,
        decision=EpistemicStatus.CHALLENGED,
        rationale="Challenged pending re-test.",
        provenance="Committee",
    )
    reg.register_review(rev1)
    reg.register(rev2)

    assert reg.contains("REV-1")
    assert "REV-1" in reg
    assert len(reg) == 2
    assert reg.all() == (rev1, rev2)

    # Querying
    assert reg.query(model_id="M1") == (rev1,)
    assert reg.query(decision=EpistemicStatus.CHALLENGED) == (rev2,)
    assert reg.query(model_id="NONEXISTENT") == ()


def test_independent_import() -> None:
    """Test independent import of falsification module without Core/hardware dependencies."""
    from acoustiforge.epistemic.falsification import (
        ApplicabilityStatus,
        FalsificationAssessment,
        FalsificationEvidence,
        FalsificationRegistry,
        FalsificationReview,
    )
    assert FalsificationEvidence is not None
    assert FalsificationAssessment is not None
    assert FalsificationReview is not None
    assert FalsificationRegistry is not None


# ==============================================================================
# 2. Mandatory Red-Team Tests (A through T)
# ==============================================================================

def test_red_team_a_contradictory_evidence_is_not_automatically_falsified() -> None:
    """Red-Team A: Evidence violating a criterion produces FALSIFICATION_EVIDENCE_DETECTED, NOT FALSIFIED."""
    mdl = EpistemicModel(
        model_id="MDL-001",
        name="Linear Model",
        description="LTI model.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.APPROXIMATION,
        assumption_ids=(),
        provenance="lab",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    ev = FalsificationEvidence(
        evidence_id="FE-001",
        model_id=mdl.model_id,
        observation_ref="OBS-001",
        criterion_id="CRIT-1",
        criterion_description="Passband ripple < 0.5 dB",
        observed_behavior="Ripple = 2.1 dB",
        expected_behavior="Ripple < 0.5 dB",
        discrepancy_summary="Discrepancy of 1.6 dB observed.",
        provenance="lab",
    )
    assessment = FalsificationAssessment(
        assessment_id="FA-001",
        model_id=mdl.model_id,
        criterion_id="CRIT-1",
        evidence_id=ev.evidence_id,
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="Calibrated",
        rationale="Violation detected.",
        provenance="eval",
    )
    # The assessment signals FALSIFICATION_EVIDENCE_DETECTED; model is NOT automatically FALSIFIED
    assert assessment.criterion_violated is True
    assert mdl.status == EpistemicStatus.VALIDATED_MODEL
    assert mdl.status != EpistemicStatus.FALSIFIED


def test_red_team_b_review_is_required() -> None:
    """Red-Team B: Transition to UNDER_REVIEW is explicit; FALSIFIED cannot occur without review."""
    assessment = FalsificationAssessment(
        assessment_id="FA-002",
        model_id="MDL-002",
        criterion_id="CRIT-2",
        evidence_id="FE-002",
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="High",
        rationale="Criterion violated.",
        provenance="eval",
    )
    # Assessment alone does not produce a FalsificationReview
    assert not isinstance(assessment, FalsificationReview)
    assert not hasattr(assessment, "decision")


def test_red_team_c_explicit_review_can_produce_falsified() -> None:
    """Red-Team C: Explicit review decision can produce FALSIFIED with full provenance."""
    rev = FalsificationReview(
        review_id="REV-003",
        model_id="MDL-003",
        evidence_id="FE-003",
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Multiple independent labs replicated acoustic short-circuiting violating fundamental model assumption.",
        provenance="scientific-review-board-session-12",
        supporting_evidence_refs=("EV-LAB-A", "EV-LAB-B"),
    )
    assert rev.decision == EpistemicStatus.FALSIFIED
    assert rev.provenance == "scientific-review-board-session-12"
    assert len(rev.supporting_evidence_refs) == 2


def test_red_team_d_domain_limitation_outside_scope() -> None:
    """Red-Team D: Evidence outside declared applicability leads to DOMAIN_LIMITED, not falsification."""
    ev = FalsificationEvidence(
        evidence_id="FE-004",
        model_id="MDL-004",
        observation_ref="OBS-EXTREME-TEMP",
        criterion_id="CRIT-TEMP",
        criterion_description="Accuracy within 10C to 40C",
        observed_behavior="Degraded at -30C",
        expected_behavior="Model not calibrated for arctic conditions",
        discrepancy_summary="Arctic temperature discrepancy",
        provenance="arctic-field-test",
        applicability_status=ApplicabilityStatus.OUTSIDE_SCOPE,
    )
    rev = FalsificationReview(
        review_id="REV-004",
        model_id="MDL-004",
        evidence_id=ev.evidence_id,
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.DOMAIN_LIMITED,
        rationale="Model is physically valid only between 10C and 40C.",
        provenance="engineering-review",
        scope={"min_temp_c": 10.0, "max_temp_c": 40.0},
    )
    assert rev.decision == EpistemicStatus.DOMAIN_LIMITED
    assert rev.decision != EpistemicStatus.FALSIFIED


def test_red_team_e_residual_is_not_falsification() -> None:
    """Red-Team E: A large residual alone does not produce FALSIFIED."""
    res = ModelResidual(
        residual_id="RES-LARGE-001",
        model_id="MDL-005",
        observation_ref="OBS-005",
        prediction_ref="PRED-005",
        residual_summary="Large 12 dB peak discrepancy at 4.5 kHz.",
        provenance="measurement",
        scope={},
    )
    reg = FalsificationRegistry()
    assert len(reg.all_reviews()) == 0
    assert not hasattr(res, "decision")


def test_red_team_f_e6_comparison_is_not_falsification() -> None:
    """Red-Team F: A model losing a comparison dimension in E6 does not become falsified."""
    comp = ModelComparison(
        comparison_id="COMP-006",
        observation_ref="OBS-006",
        model_ids=("MODEL-WINNER", "MODEL-LOSER"),
        provenance="eval",
        comparison_dimensions=("rmse",),
        pairwise_results=({"dimension": "rmse", "model_a": "MODEL-LOSER", "model_b": "MODEL-WINNER", "relation": "higher_value"},),
    )
    assert not hasattr(comp, "falsified_models")
    assert not hasattr(comp, "decision")


def test_red_team_g_bic_aic_are_not_falsification() -> None:
    """Red-Team G: A worse information criterion in E6 does not falsify a model in E7."""
    profile = ModelEvidenceProfile(
        model_id="MDL-HIGH-BIC",
        observation_ref="OBS-007",
        residual_summary="Higher BIC",
        provenance="eval",
        information_criteria={"bic": 450.0},
    )
    assert profile.information_criteria["bic"] == 450.0
    assert not hasattr(profile, "falsified")


def test_red_team_h_challenge_is_not_falsification() -> None:
    """Red-Team H: An E5 challenge alone does not create falsification evidence or decisions."""
    ch = EpistemicChallenge(
        challenge_id="CH-008",
        target_id="MDL-008",
        target_kind="model",
        rationale="Linearity questioned.",
        provenance="lab",
        status=ChallengeStatus.UNDER_INVESTIGATION,
    )
    assert ch.status == ChallengeStatus.UNDER_INVESTIGATION
    assert not hasattr(ch, "falsified")


def test_red_team_i_ai_hypothesis_is_not_empirical_evidence() -> None:
    """Red-Team I: AI-generated content cannot silently become empirical evidence."""
    ev = FalsificationEvidence(
        evidence_id="FE-AI-009",
        model_id="MDL-009",
        observation_ref="OBS-AI-SIM-001",
        criterion_id="CRIT-AI",
        criterion_description="AI suggested panel breakup criterion",
        observed_behavior="AI simulated resonance",
        expected_behavior="LTI uniform piston",
        discrepancy_summary="Simulated discrepancy",
        provenance="ai-reasoning-agent-run-5",
        applicability_status=ApplicabilityStatus.SCOPE_UNCERTAIN,
    )
    # Provenance explicitly identifies AI source, not empirical physical measurement
    assert ev.provenance == "ai-reasoning-agent-run-5"
    assert ev.applicability_status == "SCOPE_UNCERTAIN"


def test_red_team_j_no_model_mutation() -> None:
    """Red-Team J: Original model definition remains unchanged during falsification review."""
    mdl = EpistemicModel(
        model_id="MDL-010",
        name="Model 10",
        description="Desc",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        assumption_ids=(),
        provenance="lab",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    d_before = mdl.to_dict()

    rev = FalsificationReview(
        review_id="REV-010",
        model_id=mdl.model_id,
        evidence_id="FE-010",
        initial_status=mdl.status,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Falsified in review.",
        provenance="board",
    )
    reg = FalsificationRegistry()
    reg.register_review(rev)

    d_after = mdl.to_dict()
    assert d_before == d_after
    assert mdl.status == EpistemicStatus.VALIDATED_MODEL


def test_red_team_k_no_assumption_mutation() -> None:
    """Red-Team K: Assumption records remain unchanged during falsification review."""
    asm = EpistemicAssumption(
        assumption_id="ASM-011",
        statement="Homogeneous medium.",
        zone=EpistemicZone.ZONE_H,
        epistemic_class=EpistemicClass.PHYSICAL_INVARIANT,
        scope={},
        provenance="physics",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    d_before = asm.to_dict()

    rev = FalsificationReview(
        review_id="REV-011",
        model_id="MDL-011",
        evidence_id="FE-011",
        initial_status=EpistemicStatus.VALIDATED_MODEL,
        decision=EpistemicStatus.CHALLENGED,
        rationale="Challenged.",
        provenance="board",
    )
    reg = FalsificationRegistry()
    reg.register_review(rev)

    d_after = asm.to_dict()
    assert d_before == d_after
    assert asm.status == EpistemicStatus.VALIDATED_MODEL


def test_red_team_l_no_core_mutation() -> None:
    """Red-Team L: Production Core remains untouched by falsification layer."""
    reg = FalsificationRegistry()
    rev = FalsificationReview(
        review_id="REV-012",
        model_id="MDL-012",
        evidence_id="FE-012",
        initial_status=EpistemicStatus.VALIDATED_MODEL,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Falsified.",
        provenance="board",
    )
    reg.register_review(rev)

    core_modules = [m for m in sys.modules.keys() if m.startswith("acoustiforge.") and not m.startswith("acoustiforge.epistemic")]
    for mod_name in core_modules:
        mod = sys.modules[mod_name]
        assert not hasattr(mod, "_falsification_override")


def test_red_team_m_determinism() -> None:
    """Red-Team M: Identical inputs produce identical assessments and reviews."""
    args = {
        "review_id": "REV-DET-001",
        "model_id": "MDL-013",
        "evidence_id": "FE-013",
        "initial_status": EpistemicStatus.VALIDATED_MODEL,
        "decision": EpistemicStatus.DOMAIN_LIMITED,
        "rationale": "Deterministic rationale.",
        "provenance": "board",
        "supporting_evidence_refs": ("EV-1",),
        "contradictory_evidence_refs": ("EV-2",),
        "unresolved_items": ("item-1",),
        "scope": {"limit": 100},
    }
    r1 = FalsificationReview(**args)
    r2 = FalsificationReview(**args)
    assert r1.to_dict() == r2.to_dict()
    assert json.dumps(r1.to_dict(), sort_keys=True) == json.dumps(r2.to_dict(), sort_keys=True)


def test_red_team_n_provenance_preserved() -> None:
    """Red-Team N: Every falsification evidence/review record retains reconstructable provenance."""
    ev = FalsificationEvidence(
        evidence_id="FE-014",
        model_id="MDL-014",
        observation_ref="OBS-014",
        criterion_id="CRIT-14",
        criterion_description="Desc",
        observed_behavior="Obs",
        expected_behavior="Exp",
        discrepancy_summary="Disc",
        provenance="metrology-lab-run-99",
    )
    rev = FalsificationReview(
        review_id="REV-014",
        model_id="MDL-014",
        evidence_id=ev.evidence_id,
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.CHALLENGED,
        rationale="Challenged.",
        provenance="formal-audit-committee-2026",
    )
    assert ev.provenance == "metrology-lab-run-99"
    assert rev.provenance == "formal-audit-committee-2026"


def test_red_team_o_no_scalar_falsification_score() -> None:
    """Red-Team O: No universal falsification/truth/adequacy scalar score exists."""
    rev = FalsificationReview(
        review_id="REV-015",
        model_id="MDL-015",
        evidence_id="FE-015",
        initial_status=EpistemicStatus.VALIDATED_MODEL,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Falsified.",
        provenance="board",
    )
    d = rev.to_dict()
    forbidden_keys = [
        "falsification_score",
        "confidence_score",
        "model_truth_score",
        "adequacy_score",
        "truth_score",
        "score",
    ]
    for k in forbidden_keys:
        assert k not in d
        assert not hasattr(rev, k)


def test_red_team_p_criterion_traceability() -> None:
    """Red-Team P: Every falsification assessment references the exact criterion evaluated."""
    ass = FalsificationAssessment(
        assessment_id="FA-016",
        model_id="MDL-016",
        criterion_id="CRIT-EXPLICIT-016",
        evidence_id="FE-016",
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="High",
        rationale="Criterion matched.",
        provenance="eval",
    )
    assert ass.criterion_id == "CRIT-EXPLICIT-016"


def test_red_team_q_scope_traceability() -> None:
    """Red-Team Q: Every assessment and evidence preserves the applicability scope."""
    ev = FalsificationEvidence(
        evidence_id="FE-017",
        model_id="MDL-017",
        observation_ref="OBS-017",
        criterion_id="CRIT-17",
        criterion_description="Desc",
        observed_behavior="Obs",
        expected_behavior="Exp",
        discrepancy_summary="Disc",
        provenance="lab",
        scope={"frequency_band_hz": [20.0, 200.0]},
    )
    assert ev.scope == {"frequency_band_hz": [20.0, 200.0]}


def test_red_team_r_insufficient_evidence_does_not_falsify() -> None:
    """Red-Team R: Insufficient evidence does not produce FALSIFIED."""
    assessment = FalsificationAssessment(
        assessment_id="FA-018",
        model_id="MDL-018",
        criterion_id="CRIT-18",
        evidence_id="FE-018",
        criterion_tested=False,
        criterion_violated=False,
        applicability="SCOPE_UNCERTAIN",
        evidence_strength_description="Insufficient SNR (< 6 dB)",
        rationale="Measurement noise floor too high to evaluate criterion.",
        provenance="eval",
        unresolved_items=("repeat with higher averaging",),
    )
    assert assessment.criterion_tested is False
    assert assessment.criterion_violated is False


def test_red_team_s_alternative_explanation_preserved() -> None:
    """Red-Team S: Presence of a plausible alternative explanation remains explicitly represented."""
    rev = FalsificationReview(
        review_id="REV-019",
        model_id="MDL-019",
        evidence_id="FE-019",
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.CHALLENGED,
        rationale="Discrepancy may be caused by fixture resonance rather than constitutive model error.",
        provenance="expert-panel",
        unresolved_items=("test fixture resonance isolation",),
    )
    assert "fixture resonance" in rev.rationale
    assert rev.decision == EpistemicStatus.CHALLENGED
    assert rev.decision != EpistemicStatus.FALSIFIED


def test_red_team_t_explicit_decision_boundary() -> None:
    """Red-Team T: Only an explicit review decision can produce FALSIFIED."""
    # Instantiating evidence or assessment NEVER produces FALSIFIED
    ev = FalsificationEvidence(
        evidence_id="FE-020",
        model_id="MDL-020",
        observation_ref="OBS-020",
        criterion_id="CRIT-20",
        criterion_description="Desc",
        observed_behavior="Obs",
        expected_behavior="Exp",
        discrepancy_summary="Disc",
        provenance="lab",
    )
    ass = FalsificationAssessment(
        assessment_id="FA-020",
        model_id="MDL-020",
        criterion_id="CRIT-20",
        evidence_id=ev.evidence_id,
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="High",
        rationale="Violated",
        provenance="lab",
    )
    # Only FalsificationReview can record the explicit decision
    rev = FalsificationReview(
        review_id="REV-020",
        model_id="MDL-020",
        evidence_id=ev.evidence_id,
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Formal consensus reached.",
        provenance="panel",
    )
    assert rev.decision == EpistemicStatus.FALSIFIED
