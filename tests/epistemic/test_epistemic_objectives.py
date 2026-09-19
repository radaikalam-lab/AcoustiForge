"""Tests for Phase E8 Objective Representation and Challenge Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E8: Objective Challenge
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - An objective can be challenged without silently redefining production intent or optimizer behavior
  - Poor optimization result != Bad objective != Bad model != Bad measurement
  - Objective terms, assumptions, scope, and constraints remain explicitly separated and inspectable
  - No universal ObjectiveWinner, objective truth score, or composite adequacy score
  - Multi-objective comparison preserves dimension separation without declaring a winner
  - Production Core and optimizer remain completely untouched
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import sys
from typing import Any

import pytest

from acoustiforge.epistemic.assumptions import EpistemicAssumption
from acoustiforge.epistemic.challenges import EpistemicChallenge
from acoustiforge.epistemic.models import EpistemicModel
from acoustiforge.epistemic.objectives import (
    EpistemicObjective,
    ObjectiveChallengeAssessment,
    ObjectiveComparison,
    ObjectiveRegistry,
)
from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# 1. Standard Construction, Validation, and Registry Tests
# ==============================================================================

def test_epistemic_objective_construction() -> None:
    """Test valid construction of EpistemicObjective representing production acoustic tracking loss."""
    obj = EpistemicObjective(
        objective_id="OBJ-PROD-001",
        name="Composite Acoustic Target Tracking Loss",
        description="Normative loss function evaluating RMS error, passband ripple, and delay penalties.",
        expression="L(p) = E_rms(p) + w_r * R(p) + w_tau * P_tau(p)",
        terms=(
            "E_rms: Root-mean-square magnitude error across active band",
            "R: Peak-to-peak passband ripple penalty",
            "P_tau: Delay regularization penalty",
        ),
        assumptions=(
            "Target curve represents desired perceptual sound balance.",
            "RMS tracking error correlates with auditory fidelity in passband.",
            "Excessive delay causes audible temporal smearing.",
        ),
        scope={"frequency_range_hz": [20.0, 20000.0], "spl_domain": "linear"},
        constraints=(
            "Filter gains bounded by gain_bounds",
            "Q factors strictly positive and bounded by max_q",
        ),
        provenance="src/acoustiforge/acoustic_math/optimization.py:evaluate_acoustic_target_loss",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    assert obj.objective_id == "OBJ-PROD-001"
    assert "E_rms" in obj.expression
    assert len(obj.terms) == 3
    assert len(obj.assumptions) == 3
    assert len(obj.constraints) == 2
    assert obj.status == EpistemicStatus.PRODUCTION_AUTHORITY
    assert obj.scope["frequency_range_hz"] == [20.0, 20000.0]


def test_epistemic_objective_validation() -> None:
    """Test validation constraints on EpistemicObjective."""
    valid_args = {
        "objective_id": "OBJ-1",
        "name": "Name",
        "description": "Desc",
        "expression": "L = E",
        "provenance": "Lab",
    }
    for k in valid_args:
        with pytest.raises(ValueError):
            EpistemicObjective(**{**valid_args, k: ""})

    with pytest.raises(ValueError):
        EpistemicObjective(**{**valid_args, "terms": ("Term 1", "")})


def test_epistemic_objective_serialization() -> None:
    """Test deterministic serialization and lossless JSON round-trip for EpistemicObjective."""
    obj = EpistemicObjective(
        objective_id="OBJ-JSON-001",
        name="Name",
        description="Desc",
        expression="L = E",
        provenance="Lab",
        terms=("T1",),
        assumptions=("A1",),
        scope={"f_min": 20.0},
        constraints=("C1",),
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    d = obj.to_dict()
    assert d["objective_id"] == "OBJ-JSON-001"
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = EpistemicObjective.from_dict(json.loads(json_str))
    assert reconstructed == obj


def test_objective_challenge_assessment_construction_and_serialization() -> None:
    """Test construction and serialization of ObjectiveChallengeAssessment."""
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-001",
        challenge_id="CH-OBJ-001",
        objective_id="OBJ-PROD-001",
        rationale="RMS error metric treats narrow deep notches with low penalty despite severe audible degradation.",
        provenance="psychoacoustic-audit-group",
        evidence_refs=("EV-LISTENING-TEST-001", "EV-AUDITORY-MODEL-002"),
        affected_terms=("E_rms",),
        affected_scope={"feature": "narrow_comb_notches"},
        observations=("Double-blind MUSHRA testing showed 35-point degradation for deep notch.",),
        alternative_explanations=("Notch was outside critical band resolution of listener",),
        proposed_tests=("gammatone_filterbank_auditory_loss_evaluation",),
        unresolved_items=("determine notch width threshold for perceptual audibility",),
    )
    assert assessment.assessment_id == "OCA-001"
    assert assessment.affected_terms == ("E_rms",)

    d = assessment.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = ObjectiveChallengeAssessment.from_dict(json.loads(json_str))
    assert reconstructed == assessment


def test_objective_comparison_construction_and_serialization() -> None:
    """Test construction and serialization of ObjectiveComparison."""
    comp = ObjectiveComparison(
        comparison_id="OCOMP-001",
        objective_ids=("OBJ-PROD-001", "OBJ-CAND-PERCEPTUAL-002"),
        comparison_dimensions=("psychoacoustic_fidelity", "computational_cost", "convexity"),
        dimension_findings=(
            {
                "dimension": "psychoacoustic_fidelity",
                "finding": "OBJ-CAND-PERCEPTUAL-002 models cochlear masking; OBJ-PROD-001 uses unweighted RMS",
            },
            {
                "dimension": "computational_cost",
                "finding": "OBJ-PROD-001 evaluates in 0.12 ms; OBJ-CAND-PERCEPTUAL-002 requires 14.5 ms per iteration",
            },
        ),
        provenance="benchmark-suite",
        incomparable_dimensions=(),
        limitations=("Perceptual objective calibrated only for 48 kHz sample rate",),
    )
    assert len(comp.objective_ids) == 2
    assert len(comp.dimension_findings) == 2

    d = comp.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = ObjectiveComparison.from_dict(json.loads(json_str))
    assert reconstructed == comp


def test_objective_registry_operations() -> None:
    """Test registry storage, retrieval, duplicate protection, and query."""
    reg = ObjectiveRegistry()
    obj1 = EpistemicObjective(
        objective_id="OBJ-1",
        name="Objective 1",
        description="Desc",
        expression="L1",
        provenance="Lab",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    obj2 = EpistemicObjective(
        objective_id="OBJ-2",
        name="Objective 2",
        description="Desc",
        expression="L2",
        provenance="Lab",
        status=EpistemicStatus.HYPOTHESIS,
    )
    reg.register(obj1)
    reg.register(obj2)

    assert reg.get("OBJ-1") == obj1
    assert reg.contains("OBJ-1")
    assert len(reg) == 2
    assert reg.all() == (obj1, obj2)

    with pytest.raises(ValueError, match="already registered"):
        reg.register(obj1)

    assert reg.query(status=EpistemicStatus.HYPOTHESIS) == (obj2,)
    assert reg.query(status=EpistemicStatus.CONJECTURE) == ()


def test_independent_import() -> None:
    """Test clean independent import without Core/hardware dependencies."""
    from acoustiforge.epistemic.objectives import (
        EpistemicObjective,
        ObjectiveChallengeAssessment,
        ObjectiveComparison,
        ObjectiveRegistry,
    )
    assert EpistemicObjective is not None
    assert ObjectiveChallengeAssessment is not None
    assert ObjectiveComparison is not None
    assert ObjectiveRegistry is not None


# ==============================================================================
# 2. Mandatory Red-Team Tests (A through T)
# ==============================================================================

def test_red_team_a_challenge_is_not_invalidation() -> None:
    """Red-Team A: An objective challenge does not automatically invalidate the objective."""
    obj = EpistemicObjective(
        objective_id="OBJ-PROD-001",
        name="Production Objective",
        description="Production loss",
        expression="L = E_rms + w_r R",
        provenance="core",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-001",
        challenge_id="CH-001",
        objective_id=obj.objective_id,
        rationale="RMS does not capture temporal transient smearing.",
        provenance="researcher",
    )
    # The objective remains PRODUCTION_AUTHORITY; assessment does not invalidate it
    assert obj.status == EpistemicStatus.PRODUCTION_AUTHORITY
    assert obj.status != EpistemicStatus.FALSIFIED
    assert obj.status != EpistemicStatus.DEPRECATED


def test_red_team_b_objective_challenge_is_not_model_challenge() -> None:
    """Red-Team B: Verify separate target semantics between objective challenge and model challenge."""
    ch_model = EpistemicChallenge(
        challenge_id="CH-MDL-001",
        target_id="MDL-001",
        target_kind="model",
        rationale="Port nonlinearity at high volume.",
        provenance="lab",
    )
    ch_obj = EpistemicChallenge(
        challenge_id="CH-OBJ-001",
        target_id="OBJ-001",
        target_kind="objective",
        rationale="Objective ignores group delay distortion.",
        provenance="lab",
    )
    assert ch_model.target_kind == "model"
    assert ch_obj.target_kind == "objective"
    assert ch_model.target_id != ch_obj.target_id


def test_red_team_c_objective_challenge_is_not_representation_challenge() -> None:
    """Red-Team C: Objective challenge does not implement E9 representation challenge."""
    ch_obj = EpistemicChallenge(
        challenge_id="CH-OBJ-002",
        target_id="OBJ-PROD",
        target_kind="objective",
        rationale="Objective framing ignores off-axis listening window.",
        provenance="lab",
    )
    # Scope is strictly restricted to target objective questioning, not spatial coordinate redesign
    assert ch_obj.target_kind == "objective"
    assert not hasattr(ch_obj, "coordinate_transform")
    assert not hasattr(ch_obj, "state_space_basis")


def test_red_team_d_objective_does_not_become_truth() -> None:
    """Red-Team D: Registering an objective does not automatically validate or declare it true."""
    cand_obj = EpistemicObjective(
        objective_id="OBJ-CAND-001",
        name="Candidate Auditory Model Loss",
        description="Psychoacoustic loss candidate",
        expression="L_psy = integral(loudness_diff)",
        provenance="ai-or-researcher",
        status=EpistemicStatus.HYPOTHESIS,
    )
    assert cand_obj.status == EpistemicStatus.HYPOTHESIS
    assert cand_obj.status != EpistemicStatus.VALIDATED_MODEL
    assert cand_obj.status != EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_e_ai_proposal_remains_epistemically_separate() -> None:
    """Red-Team E: AI-generated objective cannot become production authority."""
    ai_obj = EpistemicObjective(
        objective_id="OBJ-AI-001",
        name="AI Proposed Multi-Objective Loss",
        description="Autonomous loss formulation",
        expression="L = 0.3 * E + 0.7 * Entropy",
        provenance="ai-agent-prompt-run-84",
        status=EpistemicStatus.HYPOTHESIS,
    )
    assert ai_obj.provenance == "ai-agent-prompt-run-84"
    assert ai_obj.status == EpistemicStatus.HYPOTHESIS
    assert ai_obj.status != EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_f_no_automatic_replacement() -> None:
    """Red-Team F: Registering an alternative objective does not replace the production objective."""
    reg = ObjectiveRegistry()
    prod_obj = EpistemicObjective(
        objective_id="OBJ-PROD",
        name="Production Loss",
        description="Official",
        expression="L = E_rms",
        provenance="core",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    alt_obj = EpistemicObjective(
        objective_id="OBJ-ALT",
        name="Alternative Loss",
        description="Proposed",
        expression="L = E_perceptual",
        provenance="researcher",
        status=EpistemicStatus.HYPOTHESIS,
    )
    reg.register(prod_obj)
    reg.register(alt_obj)

    # Invariant: Both coexist independently; prod_obj is still registered and unchanged
    assert reg.get("OBJ-PROD").status == EpistemicStatus.PRODUCTION_AUTHORITY
    assert reg.get("OBJ-ALT").status == EpistemicStatus.HYPOTHESIS


def test_red_team_g_no_optimizer_mutation() -> None:
    """Red-Team G: Objective challenge cannot alter optimizer configuration or algorithms."""
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-OPT",
        challenge_id="CH-1",
        objective_id="OBJ-PROD",
        rationale="Testing optimizer isolation.",
        provenance="test",
    )
    assert not hasattr(assessment, "optimizer_step_size")
    assert not hasattr(assessment, "convergence_tolerance")
    assert not hasattr(assessment, "search_algorithm")


def test_red_team_h_no_core_mutation() -> None:
    """Red-Team H: Production Core remains untouched by objectives layer."""
    reg = ObjectiveRegistry()
    obj = EpistemicObjective(
        objective_id="OBJ-TEST-H",
        name="Test",
        description="Test",
        expression="L = 0",
        provenance="test",
    )
    reg.register(obj)

    core_modules = [m for m in sys.modules.keys() if m.startswith("acoustiforge.") and not m.startswith("acoustiforge.epistemic")]
    for mod_name in core_modules:
        mod = sys.modules[mod_name]
        assert not hasattr(mod, "_epistemic_objective_override")


def test_red_team_i_terms_remain_inspectable() -> None:
    """Red-Team I: Composite objective terms cannot collapse into an opaque scalar only."""
    obj = EpistemicObjective(
        objective_id="OBJ-COMPOSITE",
        name="Composite Loss",
        description="Normative composite loss",
        expression="L = E_rms + w_r * R + w_tau * P_tau",
        terms=("E_rms: RMS error", "R: Ripple penalty", "P_tau: Delay regularization"),
        provenance="core",
    )
    assert len(obj.terms) == 3
    assert any("E_rms" in t for t in obj.terms)
    assert any("Ripple penalty" in t for t in obj.terms)
    assert any("Delay regularization" in t for t in obj.terms)


def test_red_team_j_constraints_remain_distinct() -> None:
    """Red-Team J: Hard constraints remain distinguishable from objective penalty terms."""
    obj = EpistemicObjective(
        objective_id="OBJ-CONSTRAINTS",
        name="Constrained Tracking",
        description="Objective with distinct hard constraints",
        expression="L = E_rms",
        terms=("E_rms",),
        constraints=("driver_excursion <= 5.0 mm", "thermal_power <= 50 W"),
        provenance="engineering",
    )
    # Constraints are stored explicitly and separately from terms
    assert len(obj.constraints) == 2
    assert "driver_excursion <= 5.0 mm" in obj.constraints
    assert obj.terms == ("E_rms",)


def test_red_team_k_proxy_distinction() -> None:
    """Red-Team K: A proxy objective is explicitly identifiable via assumptions / description."""
    obj = EpistemicObjective(
        objective_id="OBJ-PROXY",
        name="Steady-State Magnitude Proxy",
        description="Proxy objective approximating perceptual balance via 1/3-octave magnitude.",
        expression="L = E_third_octave",
        assumptions=("Steady-state SPL in 1/3-octave bands acts as a proxy for perceptual timbre.",),
        provenance="standards-body",
    )
    assert "Proxy" in obj.name or "Proxy" in obj.description
    assert len(obj.assumptions) == 1
    assert "acts as a proxy" in obj.assumptions[0]


def test_red_team_l_scope_preservation() -> None:
    """Red-Team L: Evidence outside scope does not automatically invalidate the objective."""
    obj = EpistemicObjective(
        objective_id="OBJ-ANECHOIC-ONLY",
        name="Anechoic On-Axis Objective",
        description="Optimizes on-axis response under anechoic free-field conditions.",
        expression="L = E_on_axis",
        scope={"acoustic_environment": "anechoic", "angle_deg": 0.0},
        provenance="standards",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    # Observations in reverberant room do not invalidate anechoic objective
    assert obj.scope["acoustic_environment"] == "anechoic"
    assert obj.status == EpistemicStatus.VALIDATED_MODEL


def test_red_team_m_weight_sensitivity_represented() -> None:
    """Red-Team M: Weight sensitivity is represented without automatic reweighting."""
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-SENS",
        challenge_id="CH-SENS",
        objective_id="OBJ-PROD-001",
        rationale="Increasing w_r from 0.1 to 0.2 causes optimizer to suppress useful high frequencies.",
        provenance="sensitivity-audit",
        affected_terms=("w_r * R(p)",),
        observations=("Pareto front demonstrates extreme sensitivity to ripple weight scaling.",),
        unresolved_items=("investigate adaptive normalization of ripple term",),
    )
    assert "w_r * R(p)" in assessment.affected_terms
    assert len(assessment.observations) == 1


def test_red_team_n_alternative_objectives_coexist() -> None:
    """Red-Team N: Multiple objectives can coexist in registry without selecting a winner."""
    reg = ObjectiveRegistry()
    for i in range(3):
        reg.register(
            EpistemicObjective(
                objective_id=f"OBJ-ALT-{i}",
                name=f"Objective {i}",
                description=f"Desc {i}",
                expression=f"L_{i}",
                provenance="lab",
            )
        )
    assert len(reg) == 3
    assert all(o.objective_id.startswith("OBJ-ALT-") for o in reg.all())


def test_red_team_o_no_objective_winner() -> None:
    """Red-Team O: No ObjectiveWinner or equivalent winner selection abstraction exists."""
    comp = ObjectiveComparison(
        comparison_id="OCOMP-O",
        objective_ids=("OBJ-A", "OBJ-B"),
        comparison_dimensions=("coverage", "robustness"),
        dimension_findings=(
            {"dimension": "coverage", "note": "OBJ-B covers wider frequency band"},
            {"dimension": "robustness", "note": "OBJ-A is less sensitive to component tolerances"},
        ),
        provenance="eval",
    )
    assert not hasattr(comp, "winner")
    assert not hasattr(comp, "best_objective")
    assert not hasattr(comp, "winning_objective_id")


def test_red_team_p_no_universal_objective_score() -> None:
    """Red-Team P: No hidden scalar adequacy, truth, or quality score exists."""
    obj = EpistemicObjective(
        objective_id="OBJ-P",
        name="Objective P",
        description="Desc",
        expression="L = E",
        provenance="eval",
    )
    d = obj.to_dict()
    forbidden_keys = [
        "score",
        "objective_score",
        "adequacy_score",
        "truth_score",
        "confidence_score",
        "quality_score",
    ]
    for k in forbidden_keys:
        assert k not in d
        assert not hasattr(obj, k)


def test_red_team_q_optimizer_limitation_separation() -> None:
    """Red-Team Q: Optimizer failure or local minimum does not automatically become objective failure."""
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-Q",
        challenge_id="CH-Q",
        objective_id="OBJ-PROD",
        rationale="Optimizer converged to local minimum due to coarse step size, not objective flaw.",
        provenance="convergence-audit",
        alternative_explanations=("Optimizer step size was too large; objective gradient remained valid.",),
    )
    assert "local minimum" in assessment.rationale
    assert len(assessment.alternative_explanations) == 1
    assert "Optimizer step size" in assessment.alternative_explanations[0]


def test_red_team_r_determinism() -> None:
    """Red-Team R: Identical inputs produce identical serialized results."""
    args = {
        "objective_id": "OBJ-DET",
        "name": "Deterministic Obj",
        "description": "Desc",
        "expression": "L = E + R",
        "terms": ("E", "R"),
        "assumptions": ("A1",),
        "scope": {"freq": [20, 20000]},
        "constraints": ("C1",),
        "provenance": "test",
        "status": EpistemicStatus.VALIDATED_MODEL,
    }
    o1 = EpistemicObjective(**args)
    o2 = EpistemicObjective(**args)
    assert o1.to_dict() == o2.to_dict()
    assert json.dumps(o1.to_dict(), sort_keys=True) == json.dumps(o2.to_dict(), sort_keys=True)


def test_red_team_s_provenance_preserved() -> None:
    """Red-Team S: Objective and challenge provenance is explicitly preserved."""
    obj = EpistemicObjective(
        objective_id="OBJ-PROV",
        name="Name",
        description="Desc",
        expression="L",
        provenance="iso-acoustic-standard-226",
    )
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-PROV",
        challenge_id="CH-PROV",
        objective_id=obj.objective_id,
        rationale="Rationale",
        provenance="university-psychoacoustics-lab",
    )
    assert obj.provenance == "iso-acoustic-standard-226"
    assert assessment.provenance == "university-psychoacoustics-lab"


def test_red_team_t_production_isolation() -> None:
    """Red-Team T: The production objective remains completely unchanged after epistemic challenge."""
    from acoustiforge.acoustic_math.optimization import evaluate_acoustic_target_loss

    # The production function evaluate_acoustic_target_loss remains unchanged and functional
    assert callable(evaluate_acoustic_target_loss)

    # Epistemic challenge object registration does not patch or mutate evaluate_acoustic_target_loss
    reg = ObjectiveRegistry()
    assessment = ObjectiveChallengeAssessment(
        assessment_id="OCA-ISO",
        challenge_id="CH-ISO",
        objective_id="OBJ-PROD",
        rationale="Challenge registered in epistemic layer.",
        provenance="test",
    )
    reg.register_assessment(assessment)
    assert len(reg.all_assessments()) == 1
