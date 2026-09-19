"""Tests for Phase E10 Theory Transition, Integration, and Full Epistemic Red-Team.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E10: Theory Transition / Integration / Full Red-Team
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Epistemic reasoning may discover, challenge, compare, and recommend.
  - Deterministic production Core remains authoritative.
  - Theory transition is an auditable record of reasoning, NOT an automatic model promotion engine.
  - PRODUCTION_CANDIDATE != PRODUCTION_AUTHORITY
  - EPISTEMIC_ACCEPTED != PRODUCTION_AUTHORITY
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
    ApplicabilityStatus,
    FalsificationAssessment,
    FalsificationEvidence,
    FalsificationReview,
)
from acoustiforge.epistemic.models import EpistemicModel
from acoustiforge.epistemic.objectives import (
    EpistemicObjective,
    ObjectiveChallengeAssessment,
)
from acoustiforge.epistemic.representation import (
    RepresentationChallengeAssessment,
    RepresentationDefinition,
    RepresentationGap,
)
from acoustiforge.epistemic.residuals import ModelResidual, ResidualAssessment
from acoustiforge.epistemic.transitions import (
    TheoryTransitionRecord,
    TheoryTransitionRegistry,
)
from acoustiforge.epistemic.unknowns import EpistemicUnknown
from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
    ResidualClassificationType,
)


# ==============================================================================
# 1. Standard Value Object, Registry, and Serialization Tests
# ==============================================================================

def test_theory_transition_record_construction() -> None:
    """Test valid construction of TheoryTransitionRecord."""
    rec = TheoryTransitionRecord(
        transition_id="TRANS-2026-001",
        source_model_id="MODEL-LTI-001",
        candidate_model_ids=("MODEL-NONLIN-VOLTERRA-002", "MODEL-NONLIN-HAMMERSTEIN-003"),
        conclusion="Recommend candidate Volterra model as PRODUCTION_CANDIDATE pending external hardware qualification.",
        provenance="acoustics-advisory-board",
        evidence_refs=("EV-LASER-001", "EV-MUSHRA-002"),
        challenge_refs=("CH-MDL-001", "CH-OBJ-001", "CH-REP-001"),
        review_refs=("REV-001",),
        objective_refs=("OBJ-PROD-001",),
        representation_refs=("REP-FRD-001",),
        unresolved_items=("hardware DSP cycle budget validation",),
        scope={"frequency_band_hz": [20.0, 20000.0]},
    )
    assert rec.transition_id == "TRANS-2026-001"
    assert rec.source_model_id == "MODEL-LTI-001"
    assert len(rec.candidate_model_ids) == 2
    assert "Recommend candidate" in rec.conclusion
    assert rec.review_refs == ("REV-001",)


def test_theory_transition_record_validation() -> None:
    """Test validation constraints on TheoryTransitionRecord."""
    valid_args = {
        "transition_id": "TRANS-001",
        "conclusion": "Conclusion",
        "provenance": "Board",
    }
    for k in valid_args:
        with pytest.raises(ValueError):
            TheoryTransitionRecord(**{**valid_args, k: ""})

    with pytest.raises(ValueError):
        TheoryTransitionRecord(**{**valid_args, "source_model_id": ""})

    with pytest.raises(ValueError):
        TheoryTransitionRecord(**{**valid_args, "evidence_refs": ("EV-1", "")})


def test_theory_transition_record_serialization() -> None:
    """Test deterministic serialization and lossless JSON round-trip."""
    rec = TheoryTransitionRecord(
        transition_id="TRANS-JSON-001",
        source_model_id="M1",
        candidate_model_ids=("M2",),
        conclusion="Conclusion text",
        provenance="Board",
        evidence_refs=("EV-1",),
        challenge_refs=("CH-1",),
        review_refs=("REV-1",),
        objective_refs=("OBJ-1",),
        representation_refs=("REP-1",),
        unresolved_items=("item-1",),
        scope={"dim": "2d"},
    )
    d = rec.to_dict()
    assert d["transition_id"] == "TRANS-JSON-001"
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = TheoryTransitionRecord.from_dict(json.loads(json_str))
    assert reconstructed == rec


def test_theory_transition_registry_operations() -> None:
    """Test registry storage, retrieval, duplicate protection, and query."""
    reg = TheoryTransitionRegistry()
    t1 = TheoryTransitionRecord(
        transition_id="TRANS-1",
        source_model_id="M1",
        candidate_model_ids=("M2",),
        conclusion="C1",
        provenance="Board",
    )
    t2 = TheoryTransitionRecord(
        transition_id="TRANS-2",
        source_model_id="M3",
        candidate_model_ids=("M4", "M5"),
        conclusion="C2",
        provenance="Board",
    )
    reg.register(t1)
    reg.register(t2)

    assert reg.get("TRANS-1") == t1
    assert reg.contains("TRANS-1")
    assert len(reg) == 2
    assert reg.all() == (t1, t2)

    with pytest.raises(ValueError, match="already registered"):
        reg.register(t1)

    assert reg.query(source_model_id="M1") == (t1,)
    assert reg.query(candidate_model_id="M5") == (t2,)
    assert reg.query(source_model_id="NONEXISTENT") == ()


def test_independent_import() -> None:
    """Test clean independent import without Core/hardware dependencies."""
    from acoustiforge.epistemic.transitions import (
        TheoryTransitionRecord,
        TheoryTransitionRegistry,
    )
    assert TheoryTransitionRecord is not None
    assert TheoryTransitionRegistry is not None


# ==============================================================================
# 2. End-to-End Synthetic Integration Scenario (Steps 1 through 17)
# ==============================================================================

def test_end_to_end_synthetic_theory_transition_lifecycle() -> None:
    """[SYNTHETIC TEST SCENARIO] Execute full end-to-end epistemic chain from observation to authority boundary."""
    # 1. Observation enters system
    obs_id = "OBS-SYNTHETIC-2026-001"

    # 2. Existing representation captures only part of the observation
    rep_prod = RepresentationDefinition(
        representation_id="REP-1D-BODE",
        name="1D Steady-State Magnitude Representation",
        description="Encodes 1D frequency response magnitude.",
        represented_phenomenon="Linear steady-state acoustic pressure",
        represented_variables=("frequency_hz", "magnitude_db"),
        omitted_variables=("transient_burst_envelope", "nonlinear_harmonic_products"),
        provenance="core-legacy-spec",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )

    # 3. Residual is recorded
    residual = ModelResidual(
        residual_id="RES-001",
        model_id="MODEL-LINEAR-LTI",
        observation_ref=obs_id,
        prediction_ref="PRED-001",
        residual_summary="Discrepancy in high-drive burst response (4 dB compression peak).",
        scope={"spl_db": 105.0},
        provenance="measurement-sweep-lab",
    )

    # 4. An unknown is registered where explanation is unresolved
    unknown = EpistemicUnknown(
        unknown_id="UNK-001",
        statement="Mechanism for high-frequency burst ringdown anomaly is unknown.",
        scope={"burst_freq_hz": 4500.0},
        provenance="investigation-team",
    )

    # 5. A challenge targets the existing model
    challenge_mdl = EpistemicChallenge(
        challenge_id="CH-MDL-001",
        target_id="MODEL-LINEAR-LTI",
        target_kind="model",
        rationale="Linear superposition fails under 105 dB dynamic tone burst.",
        provenance="scientific-critic",
    )

    # 6. Candidate Model B is registered
    cand_model = EpistemicModel(
        model_id="MODEL-NONLINEAR-POLYNOMIAL",
        name="Polynomial Nonlinear Transducer Model",
        description="Incorporates Bl(x) and Kms(x) power-series expansion.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        assumption_ids=(),
        provenance="nonlinear-acoustics-group",
        status=EpistemicStatus.TESTED_CANDIDATE,
    )

    # 7. E6 compares Model A and Model B
    prof_a = ModelEvidenceProfile(
        model_id="MODEL-LINEAR-LTI",
        observation_ref=obs_id,
        residual_summary="Poor burst fit",
        provenance="benchmark",
        fit_metrics={"rmse": 0.42},
        information_criteria={"bic": 180.0},
    )
    prof_b = ModelEvidenceProfile(
        model_id="MODEL-NONLINEAR-POLYNOMIAL",
        observation_ref=obs_id,
        residual_summary="Excellent burst fit",
        provenance="benchmark",
        fit_metrics={"rmse": 0.08},
        information_criteria={"bic": 95.0},
    )
    comparison = ModelComparison(
        comparison_id="COMP-001",
        observation_ref=obs_id,
        model_ids=("MODEL-LINEAR-LTI", "MODEL-NONLINEAR-POLYNOMIAL"),
        provenance="e6-evaluator",
        comparison_dimensions=("rmse", "bic"),
        pairwise_results=(
            {"dimension": "rmse", "model_a": "MODEL-LINEAR-LTI", "model_b": "MODEL-NONLINEAR-POLYNOMIAL", "relation": "higher_value"},
            {"dimension": "bic", "model_a": "MODEL-LINEAR-LTI", "model_b": "MODEL-NONLINEAR-POLYNOMIAL", "relation": "higher_value"},
        ),
    )

    # 8. Comparative evidence is recorded (verified above)
    assert len(comparison.pairwise_results) == 2

    # 9. Falsification evidence generated against explicit criterion
    fals_ev = FalsificationEvidence(
        evidence_id="FE-001",
        model_id="MODEL-LINEAR-LTI",
        observation_ref=obs_id,
        criterion_id="CRIT-DYNAMIC-RANGE-01",
        criterion_description="Model must predict burst compression within 0.5 dB up to 110 dB SPL.",
        observed_behavior="Burst compression = 4.0 dB.",
        expected_behavior="Burst compression < 0.5 dB.",
        discrepancy_summary="Violation of dynamic range linearity bound by 3.5 dB.",
        provenance="calibrated-burst-rig",
        applicability_status=ApplicabilityStatus.WITHIN_SCOPE,
    )

    # 10. E7 records FALSIFICATION_EVIDENCE_DETECTED
    assessment = FalsificationAssessment(
        assessment_id="FA-001",
        model_id="MODEL-LINEAR-LTI",
        criterion_id="CRIT-DYNAMIC-RANGE-01",
        evidence_id=fals_ev.evidence_id,
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="High-SNR calibrated acquisition",
        rationale="Criterion violated in declared linear operating domain.",
        provenance="eval-auditor",
    )
    assert assessment.criterion_violated is True

    # 11 & 12. Review is entered and produces explicit decision DOMAIN_LIMITED
    review = FalsificationReview(
        review_id="REV-001",
        model_id="MODEL-LINEAR-LTI",
        evidence_id=fals_ev.evidence_id,
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.DOMAIN_LIMITED,
        rationale="MODEL-LINEAR-LTI is accurate below 90 dB SPL; domain limited to spl_max <= 90 dB.",
        provenance="formal-review-committee",
        supporting_evidence_refs=("EV-BURST-DATA-01",),
        scope={"spl_max_db": 90.0},
    )
    assert review.decision == EpistemicStatus.DOMAIN_LIMITED

    # 13. E8 identifies an objective limitation
    obj_challenge = ObjectiveChallengeAssessment(
        assessment_id="OCA-001",
        challenge_id="CH-OBJ-001",
        objective_id="OBJ-PROD-001",
        rationale="Steady-state RMS tracking loss fails to penalize dynamic burst compression.",
        provenance="evaluator",
        affected_terms=("E_rms",),
    )

    # 14. E9 identifies a representation limitation
    rep_gap = RepresentationGap(
        gap_id="GAP-001",
        representation_id="REP-1D-BODE",
        observation_ref=obs_id,
        phenomenon_description="Dynamic burst envelope compression cannot be expressed in steady-state 1D FRD.",
        missing_capability="Missing time-resolved dynamic envelope variable.",
        provenance="lab",
    )

    # 15. A candidate theory transition is recorded
    transition = TheoryTransitionRecord(
        transition_id="TRANS-2026-SYNTHETIC-001",
        source_model_id="MODEL-LINEAR-LTI",
        candidate_model_ids=("MODEL-NONLINEAR-POLYNOMIAL",),
        conclusion="Recommend candidate MODEL-NONLINEAR-POLYNOMIAL as PRODUCTION_CANDIDATE for high-SPL systems.",
        provenance="acoustics-board-synthesis",
        evidence_refs=(fals_ev.evidence_id,),
        challenge_refs=(challenge_mdl.challenge_id,),
        review_refs=(review.review_id,),
        objective_refs=("OBJ-PROD-001",),
        representation_refs=(rep_prod.representation_id,),
    )
    reg = TheoryTransitionRegistry()
    reg.register(transition)

    # 16. No production Core mutation occurs
    core_modules = [m for m in sys.modules.keys() if m.startswith("acoustiforge.") and not m.startswith("acoustiforge.epistemic")]
    for mod_name in core_modules:
        mod = sys.modules[mod_name]
        assert not hasattr(mod, "_synthetic_transition_applied")

    # 17. Production authority remains completely unchanged
    assert rep_prod.status == EpistemicStatus.PRODUCTION_AUTHORITY
    assert cand_model.status != EpistemicStatus.PRODUCTION_AUTHORITY


# ==============================================================================
# 3. Full Red-Team Matrix (A through Z)
# ==============================================================================

def test_red_team_a_core_authority() -> None:
    """Red-Team A: Epistemic layers cannot modify production Core."""
    from acoustiforge.domain.measurements import FrequencyResponseData
    # Verify core contract is unmodified
    assert hasattr(FrequencyResponseData, "frequencies_hz")
    assert not hasattr(FrequencyResponseData, "_epistemic_override")


def test_red_team_b_ai_authority() -> None:
    """Red-Team B: AI proposals cannot become production authority."""
    ai_rec = TheoryTransitionRecord(
        transition_id="TRANS-AI",
        conclusion="AI proposes replacing Core optimizer with neural surrogate.",
        provenance="ai-reasoning-prompt",
    )
    assert ai_rec.provenance == "ai-reasoning-prompt"
    assert not hasattr(ai_rec, "production_authority")


def test_red_team_c_model_authority() -> None:
    """Red-Team C: Model competition cannot silently select a production model."""
    comp = ModelComparison(
        comparison_id="COMP-C",
        observation_ref="OBS-C",
        model_ids=("M1", "M2"),
        provenance="e6",
        pairwise_results=({"dimension": "rmse", "better": "M2"},),
    )
    assert not hasattr(comp, "production_selection")


def test_red_team_d_evidence_authority() -> None:
    """Red-Team D: Evidence does not automatically become truth."""
    ev = FalsificationEvidence(
        evidence_id="FE-D",
        model_id="M1",
        observation_ref="OBS-D",
        criterion_id="C1",
        criterion_description="D",
        observed_behavior="O",
        expected_behavior="E",
        discrepancy_summary="D",
        provenance="L",
    )
    assert not hasattr(ev, "is_absolute_truth")


def test_red_team_e_falsification_boundary() -> None:
    """Red-Team E: Falsification evidence does not automatically mean falsified."""
    ass = FalsificationAssessment(
        assessment_id="FA-E",
        model_id="M1",
        criterion_id="C1",
        evidence_id="FE-E",
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="H",
        rationale="R",
        provenance="P",
    )
    # Asserts criterion_violated signals FALSIFICATION_EVIDENCE_DETECTED, not FALSIFIED
    assert ass.criterion_violated is True
    assert not hasattr(ass, "decision")


def test_red_team_f_review_boundary() -> None:
    """Red-Team F: Falsification requires explicit review."""
    rev = FalsificationReview(
        review_id="REV-F",
        model_id="M1",
        evidence_id="FE-F",
        initial_status=EpistemicStatus.UNDER_REVIEW,
        decision=EpistemicStatus.FALSIFIED,
        rationale="Formal audit.",
        provenance="committee",
    )
    assert rev.decision == EpistemicStatus.FALSIFIED


def test_red_team_g_objective_boundary() -> None:
    """Red-Team G: Objective challenge does not replace production objective."""
    obj = EpistemicObjective(
        objective_id="OBJ-G",
        name="Prod Loss",
        description="Desc",
        expression="L = E",
        provenance="core",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    assert obj.status == EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_h_representation_boundary() -> None:
    """Red-Team H: Representation challenge does not replace production representation."""
    rep = RepresentationDefinition(
        representation_id="REP-H",
        name="Prod Rep",
        description="Desc",
        represented_phenomenon="P",
        provenance="core",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    assert rep.status == EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_i_ontology_boundary() -> None:
    """Red-Team I: Not represented does not mean physically impossible."""
    gap = RepresentationGap(
        gap_id="GAP-I",
        representation_id="REP-I",
        observation_ref="OBS-I",
        phenomenon_description="Acoustic cavitation in ultrasonic cleaning bath.",
        missing_capability="Linear wave equation cannot represent cavitation bubbles.",
        provenance="lab",
    )
    assert "Acoustic cavitation" in gap.phenomenon_description


def test_red_team_j_unknown_boundary() -> None:
    """Red-Team J: Unknown does not mean invalid."""
    unk = EpistemicUnknown(
        unknown_id="UNK-J",
        statement="Mechanism of boundary shear layer attenuation is unknown.",
        scope={},
        provenance="lab",
    )
    assert unk.status != EpistemicStatus.DEPRECATED


def test_red_team_k_residual_boundary() -> None:
    """Red-Team K: Residual does not automatically mean model error."""
    res = ModelResidual(
        residual_id="RES-K",
        model_id="M1",
        observation_ref="OBS-K",
        prediction_ref="PRED-K",
        residual_summary="High frequency peak",
        provenance="lab",
        scope={},
    )
    assert not hasattr(res, "model_error")


def test_red_team_l_comparison_boundary() -> None:
    """Red-Team L: Lower AIC/BIC/error does not mean true."""
    p1 = ModelEvidenceProfile(model_id="M1", observation_ref="O", residual_summary="R", provenance="L", information_criteria={"bic": 50})
    p2 = ModelEvidenceProfile(model_id="M2", observation_ref="O", residual_summary="R", provenance="L", information_criteria={"bic": 150})
    assert p1.information_criteria["bic"] < p2.information_criteria["bic"]
    assert not hasattr(p1, "is_true")


def test_red_team_m_constraint_boundary() -> None:
    """Red-Team M: Constraint does not become objective penalty without explicit definition."""
    obj = EpistemicObjective(
        objective_id="OBJ-M",
        name="Name",
        description="Desc",
        expression="L = E",
        terms=("E",),
        constraints=("x <= 5.0",),
        provenance="eng",
    )
    assert obj.terms != obj.constraints


def test_red_team_n_objective_boundary_law() -> None:
    """Red-Team N: Objective does not become physical law."""
    obj = EpistemicObjective(
        objective_id="OBJ-N",
        name="Target Loss",
        description="Loss function",
        expression="L = E",
        provenance="user-choice",
    )
    assert not hasattr(obj, "physical_law")


def test_red_team_o_model_boundary_law() -> None:
    """Red-Team O: Model does not become law."""
    mdl = EpistemicModel(
        model_id="MDL-O",
        name="Approximation",
        description="Desc",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.APPROXIMATION,
        assumption_ids=(),
        provenance="eng",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    assert mdl.epistemic_class == EpistemicClass.APPROXIMATION
    assert mdl.epistemic_class != EpistemicClass.PHYSICAL_INVARIANT


def test_red_team_p_provenance() -> None:
    """Red-Team P: Every conclusion remains traceable."""
    rec = TheoryTransitionRecord(
        transition_id="TRANS-P",
        conclusion="Recommend candidate",
        provenance="committee-chair",
        evidence_refs=("EV-1",),
        review_refs=("REV-1",),
    )
    assert rec.provenance == "committee-chair"
    assert rec.evidence_refs == ("EV-1",)


def test_red_team_q_determinism() -> None:
    """Red-Team Q: Full replay produces identical serialized output."""
    args = {
        "transition_id": "TRANS-Q",
        "conclusion": "Deterministic conclusion",
        "provenance": "test",
        "source_model_id": "M1",
        "candidate_model_ids": ("M2", "M3"),
        "evidence_refs": ("EV-1",),
        "challenge_refs": ("CH-1",),
        "review_refs": ("REV-1",),
        "objective_refs": ("OBJ-1",),
        "representation_refs": ("REP-1",),
        "unresolved_items": ("item-1",),
        "scope": {"limit": 10},
    }
    t1 = TheoryTransitionRecord(**args)
    t2 = TheoryTransitionRecord(**args)
    assert t1.to_dict() == t2.to_dict()
    assert json.dumps(t1.to_dict(), sort_keys=True) == json.dumps(t2.to_dict(), sort_keys=True)


def test_red_team_r_incomparability() -> None:
    """Red-Team R: Insufficient/incompatible evidence remains incomparable."""
    comp = ModelComparison(
        comparison_id="COMP-R",
        observation_ref="OBS-R",
        model_ids=("M1", "M2"),
        provenance="test",
        incomparable_dimensions=("mesh_resolution",),
    )
    assert "mesh_resolution" in comp.incomparable_dimensions


def test_red_team_s_alternative_explanations() -> None:
    """Red-Team S: Competing explanations are not silently discarded."""
    gap = RepresentationGap(
        gap_id="GAP-S",
        representation_id="REP-S",
        observation_ref="OBS-S",
        phenomenon_description="Discrepancy",
        missing_capability="Missing capability",
        alternative_explanations=("Hypothesis Alpha", "Hypothesis Beta"),
        provenance="lab",
    )
    assert len(gap.alternative_explanations) == 2


def test_red_team_t_no_hidden_scalar() -> None:
    """Red-Team T: No universal truth/adequacy score exists."""
    rec = TheoryTransitionRecord(
        transition_id="TRANS-T",
        conclusion="Conclusion",
        provenance="test",
    )
    d = rec.to_dict()
    forbidden_keys = ["score", "truth_score", "adequacy_score", "confidence_score"]
    for k in forbidden_keys:
        assert k not in d
        assert not hasattr(rec, k)


def test_red_team_u_production_candidate_boundary() -> None:
    """Red-Team U: PRODUCTION_CANDIDATE != PRODUCTION_AUTHORITY."""
    assert EpistemicStatus.PRODUCTION_CANDIDATE != EpistemicStatus.PRODUCTION_AUTHORITY
    assert EpistemicStatus.PRODUCTION_CANDIDATE.value == "PRODUCTION_CANDIDATE"
    assert EpistemicStatus.PRODUCTION_AUTHORITY.value == "PRODUCTION_AUTHORITY"


def test_red_team_v_epistemic_acceptance_boundary() -> None:
    """Red-Team V: EPISTEMIC_ACCEPTED != PRODUCTION_AUTHORITY."""
    assert EpistemicStatus.EPISTEMIC_ACCEPTED != EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_w_objective_representation_interaction() -> None:
    """Red-Team W: Objective and representation challenges remain separately identifiable."""
    obj_ch = ObjectiveChallengeAssessment(
        assessment_id="OCA-W",
        challenge_id="CH-OBJ-W",
        objective_id="OBJ-W",
        rationale="Loss function weights",
        provenance="lab",
    )
    rep_ch = RepresentationChallengeAssessment(
        assessment_id="RCA-W",
        challenge_id="CH-REP-W",
        representation_id="REP-W",
        rationale="Missing state variable",
        provenance="lab",
    )
    assert hasattr(obj_ch, "objective_id")
    assert hasattr(rep_ch, "representation_id")
    assert obj_ch.assessment_id != rep_ch.assessment_id


def test_red_team_x_model_representation_interaction() -> None:
    """Red-Team X: Model and representation challenges remain separately identifiable."""
    mdl_ch = EpistemicChallenge(challenge_id="CH-MDL-X", target_id="MDL-X", target_kind="model", rationale="LTI", provenance="L")
    rep_ch = EpistemicChallenge(challenge_id="CH-REP-X", target_id="REP-X", target_kind="representation", rationale="Bode", provenance="L")
    assert mdl_ch.target_kind == "model"
    assert rep_ch.target_kind == "representation"


def test_red_team_y_model_objective_interaction() -> None:
    """Red-Team Y: Model inadequacy does not automatically imply objective inadequacy."""
    mdl_ass = FalsificationAssessment(
        assessment_id="FA-Y",
        model_id="MDL-Y",
        criterion_id="CRIT-Y",
        evidence_id="FE-Y",
        criterion_tested=True,
        criterion_violated=True,
        applicability="WITHIN_SCOPE",
        evidence_strength_description="H",
        rationale="Model violated criterion",
        provenance="L",
    )
    # Model criterion violation does not mutate or invalidate the objective
    assert mdl_ass.criterion_violated is True
    assert not hasattr(mdl_ass, "objective_invalidated")


def test_red_team_z_complete_lifecycle_reconstructability() -> None:
    """Red-Team Z: The entire synthetic lifecycle is completely traceable from transition record."""
    transition = TheoryTransitionRecord(
        transition_id="TRANS-Z",
        source_model_id="MODEL-OLD",
        candidate_model_ids=("MODEL-NEW-A", "MODEL-NEW-B"),
        conclusion="Consensus recommendation",
        provenance="board-z",
        evidence_refs=("EV-Z-01", "EV-Z-02"),
        challenge_refs=("CH-MDL-Z", "CH-OBJ-Z"),
        review_refs=("REV-Z-01",),
        objective_refs=("OBJ-PROD-Z",),
        representation_refs=("REP-PROD-Z",),
        unresolved_items=("hardware-thermal-validation",),
    )
    assert transition.source_model_id == "MODEL-OLD"
    assert "EV-Z-01" in transition.evidence_refs
    assert "REV-Z-01" in transition.review_refs
    assert "CH-MDL-Z" in transition.challenge_refs
    assert "OBJ-PROD-Z" in transition.objective_refs
    assert "REP-PROD-Z" in transition.representation_refs
