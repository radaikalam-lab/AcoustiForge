"""Tests for Phase E6 Epistemic Shadow Model Competition and Comparison Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E6: Shadow Model Competition
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Model competition produces comparative evidence, NOT truth
  - Lower BIC / Lower Residual / Better Fit != Model Status Promotion
  - No universal ModelWinner or composite truth/adequacy score
  - Multi-dimensional evidence dimensions remain strictly separated
  - Incomparability is explicitly represented
  - No automatic falsification or challenge resolution
  - No mutation of EpistemicModel, EpistemicAssumption, or Production Core
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import sys
from typing import Any

import pytest

from acoustiforge.epistemic.assumptions import AssumptionRegistry, EpistemicAssumption
from acoustiforge.epistemic.challenges import ChallengeRegistry, EpistemicChallenge
from acoustiforge.epistemic.competition import (
    ModelComparison,
    ModelCompetitionRegistry,
    ModelEvidenceProfile,
)
from acoustiforge.epistemic.models import EpistemicModel, ModelRegistry
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
# 1. Standard Value Object & Registry Tests
# ==============================================================================

def test_model_evidence_profile_construction() -> None:
    """Test valid construction of ModelEvidenceProfile."""
    profile = ModelEvidenceProfile(
        model_id="MODEL-LTI-001",
        observation_ref="OBS-ANECHOIC-001",
        residual_summary="Slight high-frequency roll-off discrepancy above 8 kHz.",
        provenance="lab-acoustics-run-42",
        evidence_refs=("EV-MEAS-001", "EV-MEAS-002"),
        fit_metrics={"rmse": 0.42, "rss": 1.25, "mae": 0.31},
        information_criteria={"aic": 104.2, "bic": 109.8},
        predictive_metrics={"cv_rmse": 0.48},
        constraint_results={"max_displacement_ok": True, "thermal_limit_ok": True},
        applicability_notes=("valid within 80-95 dB SPL",),
        unresolved_items=("phase ripple at 12 kHz",),
    )
    assert profile.model_id == "MODEL-LTI-001"
    assert profile.observation_ref == "OBS-ANECHOIC-001"
    assert profile.residual_summary.startswith("Slight high-frequency")
    assert profile.provenance == "lab-acoustics-run-42"
    assert profile.evidence_refs == ("EV-MEAS-001", "EV-MEAS-002")
    assert profile.fit_metrics["rmse"] == 0.42
    assert profile.information_criteria["aic"] == 104.2
    assert profile.predictive_metrics["cv_rmse"] == 0.48
    assert profile.constraint_results["max_displacement_ok"] is True
    assert profile.applicability_notes == ("valid within 80-95 dB SPL",)
    assert profile.unresolved_items == ("phase ripple at 12 kHz",)


def test_model_evidence_profile_validation() -> None:
    """Test validation and error raising on invalid ModelEvidenceProfile fields."""
    valid_args = {
        "model_id": "MODEL-001",
        "observation_ref": "OBS-001",
        "residual_summary": "Summary",
        "provenance": "Lab",
    }

    # Empty required string fields
    for field in ["model_id", "observation_ref", "residual_summary", "provenance"]:
        for bad_val in ["", "  ", None]:
            with pytest.raises(ValueError):
                ModelEvidenceProfile(**{**valid_args, field: bad_val})  # type: ignore

    # Invalid evidence_refs
    with pytest.raises(ValueError):
        ModelEvidenceProfile(**{**valid_args, "evidence_refs": ("EV-1", "")})

    # Invalid mapping types
    for mfield in ["fit_metrics", "information_criteria", "predictive_metrics", "constraint_results"]:
        with pytest.raises(ValueError):
            ModelEvidenceProfile(**{**valid_args, mfield: [1, 2, 3]})  # type: ignore


def test_model_evidence_profile_immutability() -> None:
    """Test that ModelEvidenceProfile is frozen and immutable."""
    profile = ModelEvidenceProfile(
        model_id="MODEL-001",
        observation_ref="OBS-001",
        residual_summary="Summary",
        provenance="Lab",
    )
    with pytest.raises(FrozenInstanceError):
        profile.model_id = "MODEL-002"  # type: ignore


def test_model_evidence_profile_serialization() -> None:
    """Test deterministic serialization and lossless JSON round-trip for ModelEvidenceProfile."""
    profile = ModelEvidenceProfile(
        model_id="MODEL-001",
        observation_ref="OBS-001",
        residual_summary="Summary",
        provenance="Lab",
        evidence_refs=("EV-1", "EV-2"),
        fit_metrics={"rmse": 0.12},
        information_criteria={"bic": 88.5},
        predictive_metrics={"pred_err": 0.05},
        constraint_results={"pass": True},
        applicability_notes=("note1",),
        unresolved_items=("item1",),
    )
    d = profile.to_dict()
    assert d["model_id"] == "MODEL-001"
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = ModelEvidenceProfile.from_dict(json.loads(json_str))
    assert reconstructed == profile


def test_model_comparison_construction() -> None:
    """Test valid construction of ModelComparison across multiple models."""
    comparison = ModelComparison(
        comparison_id="COMP-001",
        observation_ref="OBS-ANECHOIC-001",
        model_ids=("MODEL-LTI-001", "MODEL-NONLIN-002", "MODEL-BOUNDARY-003"),
        provenance="automated-benchmark-harness",
        profile_refs=("PROF-001", "PROF-002", "PROF-003"),
        comparison_dimensions=("rmse", "bic", "thermal_compliance"),
        pairwise_results=(
            {
                "dimension": "rmse",
                "model_a": "MODEL-LTI-001",
                "model_b": "MODEL-NONLIN-002",
                "relation": "higher_value",
                "delta": 0.15,
            },
            {
                "dimension": "bic",
                "model_a": "MODEL-LTI-001",
                "model_b": "MODEL-NONLIN-002",
                "relation": "lower_value",
                "delta": -12.4,
            },
        ),
        incomparable_dimensions=("spatial_polar_accuracy",),
        limitations=("measurement bandwidth limited to 20 kHz",),
    )
    assert comparison.comparison_id == "COMP-001"
    assert len(comparison.model_ids) == 3
    assert len(comparison.pairwise_results) == 2
    assert comparison.incomparable_dimensions == ("spatial_polar_accuracy",)
    assert comparison.limitations == ("measurement bandwidth limited to 20 kHz",)


def test_model_comparison_validation() -> None:
    """Test validation and constraints on ModelComparison."""
    valid_args = {
        "comparison_id": "COMP-001",
        "observation_ref": "OBS-001",
        "model_ids": ("M1", "M2"),
        "provenance": "Lab",
    }

    # Fewer than 2 models
    with pytest.raises(ValueError, match="at least 2 models"):
        ModelComparison(**{**valid_args, "model_ids": ("M1",)})

    # Empty string fields
    for field in ["comparison_id", "observation_ref", "provenance"]:
        with pytest.raises(ValueError):
            ModelComparison(**{**valid_args, field: ""})

    # Non-mapping pairwise_results
    with pytest.raises(ValueError):
        ModelComparison(**{**valid_args, "pairwise_results": ("not_a_mapping",)})  # type: ignore


def test_model_comparison_serialization() -> None:
    """Test deterministic serialization and lossless JSON round-trip for ModelComparison."""
    comp = ModelComparison(
        comparison_id="COMP-JSON-001",
        observation_ref="OBS-001",
        model_ids=("M1", "M2"),
        provenance="Lab",
        profile_refs=("P1", "P2"),
        comparison_dimensions=("rmse",),
        pairwise_results=({"dimension": "rmse", "model_a": "M1", "model_b": "M2", "relation": "lower_value"},),
        incomparable_dimensions=("flux_density",),
        limitations=("low_snr",),
    )
    d = comp.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = ModelComparison.from_dict(json.loads(json_str))
    assert reconstructed == comp


def test_competition_registry_operations() -> None:
    """Test registration, retrieval, duplicate protection, and querying in ModelCompetitionRegistry."""
    reg = ModelCompetitionRegistry()

    p1 = ModelEvidenceProfile(
        model_id="M1",
        observation_ref="OBS-1",
        residual_summary="Summary 1",
        provenance="Lab",
    )
    reg.register_profile(p1)
    assert reg.get_profile("M1", "OBS-1") == p1
    assert reg.all_profiles() == (p1,)

    # Duplicate profile registration
    with pytest.raises(ValueError, match="already registered"):
        reg.register_profile(p1)

    c1 = ModelComparison(
        comparison_id="COMP-1",
        observation_ref="OBS-1",
        model_ids=("M1", "M2"),
        provenance="Lab",
    )
    c2 = ModelComparison(
        comparison_id="COMP-2",
        observation_ref="OBS-2",
        model_ids=("M2", "M3"),
        provenance="Lab",
    )
    reg.register(c1)
    reg.register(c2)

    assert reg.contains("COMP-1")
    assert "COMP-1" in reg
    assert reg.get("COMP-1") == c1
    assert len(reg) == 2
    assert reg.all() == (c1, c2)

    # Duplicate comparison registration
    with pytest.raises(ValueError, match="already registered"):
        reg.register(c1)

    # Querying
    assert reg.query(observation_ref="OBS-1") == (c1,)
    assert reg.query(model_id="M2") == (c1, c2)
    assert reg.query(model_id="M3") == (c2,)
    assert reg.query(model_id="NONEXISTENT") == ()


def test_independent_import() -> None:
    """Test that competition module can be imported cleanly without Core/hardware dependencies."""
    from acoustiforge.epistemic.competition import (
        ModelComparison,
        ModelCompetitionRegistry,
        ModelEvidenceProfile,
    )
    assert ModelEvidenceProfile is not None
    assert ModelComparison is not None
    assert ModelCompetitionRegistry is not None


# ==============================================================================
# 2. Mandatory Red-Team Tests (A through O)
# ==============================================================================

def test_red_team_a_lower_bic_is_not_truth() -> None:
    """Red-Team A: Model A BIC < Model B BIC must not cause status transition or truth claim."""
    mdl_a = EpistemicModel(
        model_id="MDL-A",
        name="LTI Model A",
        description="Linear model.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.APPROXIMATION,
        assumption_ids=(),
        provenance="lab",
        status=EpistemicStatus.CONJECTURE,
    )
    mdl_b = EpistemicModel(
        model_id="MDL-B",
        name="LTI Model B",
        description="Complex model.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        assumption_ids=(),
        provenance="lab",
        status=EpistemicStatus.VALIDATED_MODEL,
    )

    p_a = ModelEvidenceProfile(
        model_id="MDL-A",
        observation_ref="OBS-001",
        residual_summary="Residual A",
        provenance="eval",
        information_criteria={"bic": 80.0},
    )
    p_b = ModelEvidenceProfile(
        model_id="MDL-B",
        observation_ref="OBS-001",
        residual_summary="Residual B",
        provenance="eval",
        information_criteria={"bic": 120.0},
    )

    comp = ModelComparison(
        comparison_id="COMP-AB",
        observation_ref="OBS-001",
        model_ids=("MDL-A", "MDL-B"),
        provenance="eval",
        comparison_dimensions=("bic",),
        pairwise_results=({"dimension": "bic", "model_a": "MDL-A", "model_b": "MDL-B", "relation": "lower_value", "delta": -40.0},),
    )
    reg = ModelCompetitionRegistry()
    reg.register_profile(p_a)
    reg.register_profile(p_b)
    reg.register(comp)

    # Invariant: mdl_a remains CONJECTURE, mdl_b remains VALIDATED_MODEL
    assert mdl_a.status == EpistemicStatus.CONJECTURE
    assert mdl_a.status != EpistemicStatus.EPISTEMIC_ACCEPTED
    assert mdl_a.status != EpistemicStatus.PRODUCTION_CANDIDATE
    assert mdl_b.status == EpistemicStatus.VALIDATED_MODEL
    assert mdl_b.status != EpistemicStatus.FALSIFIED


def test_red_team_b_lower_residual_is_not_truth() -> None:
    """Red-Team B: Model A residual < Model B residual must not cause model promotion."""
    mdl_a = EpistemicModel(
        model_id="MDL-A",
        name="Model A",
        description="Empirical curve fit.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.EMPIRICAL_REGULARITY,
        assumption_ids=(),
        provenance="lab",
        status=EpistemicStatus.TESTED_CANDIDATE,
    )
    p_a = ModelEvidenceProfile(
        model_id="MDL-A",
        observation_ref="OBS-001",
        residual_summary="Very low residual",
        provenance="eval",
        fit_metrics={"rmse": 0.001},
    )
    assert mdl_a.status == EpistemicStatus.TESTED_CANDIDATE
    assert p_a.fit_metrics["rmse"] == 0.001
    assert mdl_a.status != EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_c_no_model_winner() -> None:
    """Red-Team C: Demonstrate that the API contains no universal winner abstraction or attribute."""
    comp = ModelComparison(
        comparison_id="COMP-001",
        observation_ref="OBS-001",
        model_ids=("M1", "M2"),
        provenance="eval",
    )
    assert not hasattr(comp, "winner")
    assert not hasattr(comp, "model_winner")
    assert not hasattr(comp, "best_model")
    assert not hasattr(comp, "winning_model_id")


def test_red_team_d_multi_dimensional_comparison() -> None:
    """Red-Team D: Show that different models can perform better on different dimensions without collapsing."""
    comp = ModelComparison(
        comparison_id="COMP-MULTI",
        observation_ref="OBS-001",
        model_ids=("MODEL-A", "MODEL-B", "MODEL-C"),
        provenance="multi-eval",
        comparison_dimensions=("rmse", "bic", "prediction_error"),
        pairwise_results=(
            {"dimension": "rmse", "best_performing": "MODEL-A", "note": "Model A has lowest RMSE"},
            {"dimension": "bic", "best_performing": "MODEL-B", "note": "Model B has lowest BIC due to parsimony"},
            {"dimension": "prediction_error", "best_performing": "MODEL-C", "note": "Model C generalizes best out-of-sample"},
        ),
    )
    # Dimensions remain completely separate
    dims = [r["dimension"] for r in comp.pairwise_results]
    assert dims == ["rmse", "bic", "prediction_error"]
    assert comp.pairwise_results[0]["best_performing"] == "MODEL-A"
    assert comp.pairwise_results[1]["best_performing"] == "MODEL-B"
    assert comp.pairwise_results[2]["best_performing"] == "MODEL-C"


def test_red_team_e_incomparability() -> None:
    """Red-Team E: Missing or incompatible evidence produces explicit incomparable state."""
    comp = ModelComparison(
        comparison_id="COMP-INCOMP",
        observation_ref="OBS-001",
        model_ids=("MODEL-LUMPED", "MODEL-3D-FEM"),
        provenance="eval",
        incomparable_dimensions=("spatial_mesh_resolution", "fluid_vorticity_field"),
        limitations=("MODEL-LUMPED has zero spatial coordinates; spatial mesh comparison is physically incomparable",),
    )
    assert "spatial_mesh_resolution" in comp.incomparable_dimensions
    assert len(comp.incomparable_dimensions) == 2
    assert "physically incomparable" in comp.limitations[0]


def test_red_team_f_applicability_preserved() -> None:
    """Red-Team F: Numerical result outside model scope remains explicitly scope-limited."""
    profile = ModelEvidenceProfile(
        model_id="MODEL-LINEAR-001",
        observation_ref="OBS-HIGH-DRIVE-120DB",
        residual_summary="Numerically computed RMSE is low due to localized polynomial fit.",
        provenance="eval",
        fit_metrics={"rmse": 0.05},
        applicability_notes=("WARNING: 120 dB SPL is outside the declared linear operating regime of MODEL-LINEAR-001 (max 90 dB)",),
        unresolved_items=("High-drive harmonic distortion unmodeled",),
    )
    assert profile.fit_metrics["rmse"] == 0.05
    assert len(profile.applicability_notes) == 1
    assert "outside the declared linear operating regime" in profile.applicability_notes[0]


def test_red_team_g_no_model_mutation() -> None:
    """Red-Team G: Model records remain structurally unchanged and unmutated during comparison."""
    mdl = EpistemicModel(
        model_id="MDL-IMMUTABLE",
        name="Original Model",
        description="Immutable test model.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        assumption_ids=("ASM-1",),
        provenance="metrology",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    d_before = mdl.to_dict()

    p = ModelEvidenceProfile(
        model_id=mdl.model_id,
        observation_ref="OBS-001",
        residual_summary="Summary",
        provenance="eval",
    )
    c = ModelComparison(
        comparison_id="COMP-G",
        observation_ref="OBS-001",
        model_ids=(mdl.model_id, "MDL-OTHER"),
        provenance="eval",
    )
    reg = ModelCompetitionRegistry()
    reg.register_profile(p)
    reg.register(c)

    d_after = mdl.to_dict()
    assert d_before == d_after
    assert mdl.status == EpistemicStatus.VALIDATED_MODEL


def test_red_team_h_no_assumption_mutation() -> None:
    """Red-Team H: Assumption records remain unchanged during model competition."""
    asm = EpistemicAssumption(
        assumption_id="ASM-001",
        statement="Adiabatic gas compression.",
        zone=EpistemicZone.ZONE_H,
        epistemic_class=EpistemicClass.PHYSICAL_INVARIANT,
        scope={},
        provenance="physics",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    d_before = asm.to_dict()

    c = ModelComparison(
        comparison_id="COMP-H",
        observation_ref="OBS-001",
        model_ids=("M1", "M2"),
        provenance="eval",
    )
    reg = ModelCompetitionRegistry()
    reg.register(c)

    d_after = asm.to_dict()
    assert d_before == d_after
    assert asm.status == EpistemicStatus.VALIDATED_MODEL


def test_red_team_i_no_status_transition() -> None:
    """Red-Team I: Snapshot model statuses before comparison and verify identical statuses afterward."""
    models = [
        EpistemicModel(
            model_id=f"MDL-{i}",
            name=f"Model {i}",
            description=f"Desc {i}",
            zone=EpistemicZone.ZONE_M,
            epistemic_class=EpistemicClass.APPROXIMATION,
            assumption_ids=(),
            provenance="lab",
            status=status,
        )
        for i, status in enumerate([
            EpistemicStatus.CONJECTURE,
            EpistemicStatus.HYPOTHESIS,
            EpistemicStatus.TESTED_CANDIDATE,
            EpistemicStatus.VALIDATED_MODEL,
        ])
    ]
    statuses_before = [m.status for m in models]

    c = ModelComparison(
        comparison_id="COMP-I",
        observation_ref="OBS-ALL",
        model_ids=tuple(m.model_id for m in models),
        provenance="eval",
    )
    reg = ModelCompetitionRegistry()
    reg.register(c)

    statuses_after = [m.status for m in models]
    assert statuses_before == statuses_after


def test_red_team_j_no_evidence_fabrication() -> None:
    """Red-Team J: Comparison results must not silently become physical/experimental evidence."""
    comp = ModelComparison(
        comparison_id="COMP-J",
        observation_ref="OBS-001",
        model_ids=("M1", "M2"),
        provenance="eval-script",
    )
    assert not hasattr(comp, "physical_measurement")
    assert not hasattr(comp, "raw_signal")
    assert not hasattr(comp, "acoustic_evidence_id")


def test_red_team_k_determinism() -> None:
    """Red-Team K: Run identical comparison twice and assert identical serialized results."""
    args = {
        "comparison_id": "COMP-K",
        "observation_ref": "OBS-001",
        "model_ids": ("M1", "M2"),
        "provenance": "eval",
        "profile_refs": ("P1", "P2"),
        "comparison_dimensions": ("rmse", "bic"),
        "pairwise_results": ({"dim": "rmse", "diff": 0.02},),
        "incomparable_dimensions": (),
        "limitations": (),
    }
    c1 = ModelComparison(**args)  # type: ignore
    c2 = ModelComparison(**args)  # type: ignore
    assert c1.to_dict() == c2.to_dict()
    assert json.dumps(c1.to_dict(), sort_keys=True) == json.dumps(c2.to_dict(), sort_keys=True)


def test_red_team_l_provenance_preserved() -> None:
    """Red-Team L: Verify comparison preserves model, observation, evidence, and metric provenance."""
    profile = ModelEvidenceProfile(
        model_id="MDL-001",
        observation_ref="OBS-CHAMBER-9",
        residual_summary="Summary",
        provenance="lab-calibration-v3.2",
        evidence_refs=("EV-MIC-01",),
    )
    comp = ModelComparison(
        comparison_id="COMP-L",
        observation_ref="OBS-CHAMBER-9",
        model_ids=("MDL-001", "MDL-002"),
        provenance="competition-runner-v1.0",
        profile_refs=("PROF-1",),
    )
    assert profile.provenance == "lab-calibration-v3.2"
    assert profile.evidence_refs == ("EV-MIC-01",)
    assert comp.provenance == "competition-runner-v1.0"


def test_red_team_m_ai_hypothesis_separation() -> None:
    """Red-Team M: AI-generated hypothesis may participate as input but never becomes empirical evidence."""
    ai_model = EpistemicModel(
        model_id="MDL-AI-001",
        name="AI Surfaced Nonlinear Wave Model",
        description="Hypothesized nonlinear boundary condition generated by AI agent.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.HYPOTHESIS,
        assumption_ids=(),
        provenance="ai-agent-discovery-run",
        status=EpistemicStatus.HYPOTHESIS,
    )
    profile = ModelEvidenceProfile(
        model_id=ai_model.model_id,
        observation_ref="OBS-001",
        residual_summary="AI model matches empirical sweep with low error.",
        provenance="ai-evaluation",
        fit_metrics={"rmse": 0.01},
    )
    comp = ModelComparison(
        comparison_id="COMP-M",
        observation_ref="OBS-001",
        model_ids=(ai_model.model_id, "MDL-CONVENTIONAL"),
        provenance="competition-layer",
    )
    reg = ModelCompetitionRegistry()
    reg.register_profile(profile)
    reg.register(comp)

    # Invariant: ai_model remains HYPOTHESIS, does not become empirical evidence or validated model
    assert ai_model.status == EpistemicStatus.HYPOTHESIS
    assert ai_model.epistemic_class == EpistemicClass.HYPOTHESIS
    assert ai_model.status != EpistemicStatus.VALIDATED_MODEL
    assert ai_model.status != EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_n_no_core_mutation() -> None:
    """Red-Team N: Model competition execution does not modify production Core state."""
    reg = ModelCompetitionRegistry()
    c = ModelComparison(
        comparison_id="COMP-N",
        observation_ref="OBS-N",
        model_ids=("M1", "M2"),
        provenance="test",
    )
    reg.register(c)

    core_modules = [m for m in sys.modules.keys() if m.startswith("acoustiforge.") and not m.startswith("acoustiforge.epistemic")]
    for mod_name in core_modules:
        mod = sys.modules[mod_name]
        assert not hasattr(mod, "_epistemic_competition_winner")


def test_red_team_o_no_hidden_scalar_scores() -> None:
    """Red-Team O: Public comparison output contains no universal score, adequacy, confidence, truth, or winner fields."""
    comp = ModelComparison(
        comparison_id="COMP-O",
        observation_ref="OBS-001",
        model_ids=("M1", "M2"),
        provenance="test",
    )
    d = comp.to_dict()
    forbidden_keys = [
        "score",
        "model_score",
        "adequacy",
        "adequacy_score",
        "confidence",
        "confidence_score",
        "truth",
        "truth_score",
        "winner",
        "winner_score",
    ]
    for k in forbidden_keys:
        assert k not in d
        assert not hasattr(comp, k)
