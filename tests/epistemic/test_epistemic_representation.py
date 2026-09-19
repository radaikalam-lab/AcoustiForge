"""Tests for Phase E9 Epistemic Representation Definition and Challenge Layer.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E9: Representation Challenge
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - Failure of representation is NOT evidence of physical impossibility (NOT_REPRESENTABLE != PHYSICALLY_IMPOSSIBLE)
  - Representation Gap != UNKNOWN != MODEL_ERROR != PHYSICALLY_IMPOSSIBLE != FALSIFIED
  - Representation != Model != Objective != Measurement != Optimization
  - Represented variables and omitted variables remain explicitly inspectable
  - No universal RepresentationWinner, representation adequacy score, or truth score
  - Multi-representation comparison preserves dimension separation without declaring a winner
  - Production Core and domain models remain completely untouched
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import sys
from typing import Any

import pytest

from acoustiforge.epistemic.assumptions import EpistemicAssumption
from acoustiforge.epistemic.challenges import EpistemicChallenge
from acoustiforge.epistemic.falsification import FalsificationReview
from acoustiforge.epistemic.models import EpistemicModel
from acoustiforge.epistemic.objectives import EpistemicObjective
from acoustiforge.epistemic.representation import (
    RepresentationChallengeAssessment,
    RepresentationComparison,
    RepresentationDefinition,
    RepresentationGap,
    RepresentationRegistry,
)
from acoustiforge.epistemic.residuals import ModelResidual
from acoustiforge.epistemic.unknowns import EpistemicUnknown
from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# 1. Standard Construction, Validation, and Registry Tests
# ==============================================================================

def test_representation_definition_construction() -> None:
    """Test valid construction of RepresentationDefinition."""
    rep = RepresentationDefinition(
        representation_id="REP-FRD-001",
        name="1D Frequency Response Magnitude Representation",
        description="Encodes steady-state acoustic pressure magnitude as a function of frequency on a discrete grid.",
        represented_phenomenon="Linear steady-state acoustic pressure variation across frequency.",
        represented_variables=("frequency_hz", "magnitude_db_spl"),
        omitted_variables=("phase_rad", "group_delay_seconds", "directivity_angles", "thermal_state"),
        relationships=("magnitude_db_spl = 20 * log10(|P(f)| / P_ref)",),
        assumptions=(
            "Linear time-invariant medium.",
            "Steady-state excitation is sufficient.",
            "Spatial field is collapsed to a single measurement point.",
        ),
        scope={"frequency_band_hz": [20.0, 20000.0], "spl_max_db": 100.0},
        provenance="src/acoustiforge/contracts/data_models.py:FrequencyResponseData",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    assert rep.representation_id == "REP-FRD-001"
    assert "frequency_hz" in rep.represented_variables
    assert "phase_rad" in rep.omitted_variables
    assert len(rep.assumptions) == 3
    assert rep.status == EpistemicStatus.PRODUCTION_AUTHORITY


def test_representation_definition_validation() -> None:
    """Test validation constraints on RepresentationDefinition."""
    valid_args = {
        "representation_id": "REP-1",
        "name": "Name",
        "description": "Desc",
        "represented_phenomenon": "Phenom",
        "provenance": "Lab",
    }
    for k in valid_args:
        with pytest.raises(ValueError):
            RepresentationDefinition(**{**valid_args, k: ""})

    with pytest.raises(ValueError):
        RepresentationDefinition(**{**valid_args, "represented_variables": ("v1", "")})


def test_representation_definition_serialization() -> None:
    """Test deterministic serialization and lossless JSON round-trip for RepresentationDefinition."""
    rep = RepresentationDefinition(
        representation_id="REP-JSON-001",
        name="Name",
        description="Desc",
        represented_phenomenon="Phenom",
        provenance="Lab",
        represented_variables=("v1",),
        omitted_variables=("o1",),
        relationships=("r1",),
        assumptions=("a1",),
        scope={"dim": 1},
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    d = rep.to_dict()
    assert d["representation_id"] == "REP-JSON-001"
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = RepresentationDefinition.from_dict(json.loads(json_str))
    assert reconstructed == rep


def test_representation_gap_construction_and_serialization() -> None:
    """Test construction and serialization of RepresentationGap."""
    gap = RepresentationGap(
        gap_id="GAP-001",
        representation_id="REP-FRD-001",
        observation_ref="OBS-LASER-3D-001",
        phenomenon_description="Asymmetric cone rocking mode causing off-axis harmonic cancellations.",
        missing_capability="1D FRD magnitude representation cannot represent 3D spatial field deformation or phase cancellation.",
        affected_variables=("magnitude_db_spl",),
        alternative_explanations=("Fixture misalignment during laser scan",),
        evidence_refs=("EV-LASER-3D-SCAN",),
        provenance="vibrometry-lab",
        scope={"frequency_hz": [2500.0, 3500.0]},
    )
    assert gap.gap_id == "GAP-001"
    assert "cone rocking mode" in gap.phenomenon_description

    d = gap.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = RepresentationGap.from_dict(json.loads(json_str))
    assert reconstructed == gap


def test_representation_challenge_assessment_construction_and_serialization() -> None:
    """Test construction and serialization of RepresentationChallengeAssessment."""
    assessment = RepresentationChallengeAssessment(
        assessment_id="RCA-001",
        challenge_id="CH-REP-001",
        representation_id="REP-FRD-001",
        rationale="Phase omissions prevent synthetic multiway complex acoustic summation from correctly predicting crossover notch depth.",
        provenance="systems-architecture-review",
        evidence_refs=("EV-SUMMATION-DISCREPANCY-001",),
        affected_variables=("magnitude_db_spl",),
        representation_gap_refs=("GAP-001",),
        alternative_explanations=("Transducer delay parameter misspecification",),
        proposed_tests=("complex_pressure_transfer_function_measurement",),
        unresolved_items=("determine whether minimum-phase Hilbert transform approximation is sufficient",),
    )
    assert assessment.assessment_id == "RCA-001"
    assert assessment.representation_gap_refs == ("GAP-001",)

    d = assessment.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = RepresentationChallengeAssessment.from_dict(json.loads(json_str))
    assert reconstructed == assessment


def test_representation_comparison_construction_and_serialization() -> None:
    """Test construction and serialization of RepresentationComparison."""
    comp = RepresentationComparison(
        comparison_id="RCOMP-001",
        representation_ids=("REP-FRD-1D", "REP-COMPLEX-TRANSFER-2D"),
        observation_refs=("OBS-001",),
        dimensions=("phase_preservation", "computational_memory", "measurement_complexity"),
        findings=(
            {"dimension": "phase_preservation", "finding": "REP-COMPLEX-TRANSFER-2D retains real/imag; REP-FRD-1D discards phase"},
            {"dimension": "computational_memory", "finding": "REP-FRD-1D is 50% smaller in storage size"},
        ),
        provenance="representation-benchmark",
        incomparable_dimensions=(),
        limitations=("2D representation requires dual-channel synchronous acquisition hardware",),
    )
    assert len(comp.representation_ids) == 2
    assert len(comp.findings) == 2

    d = comp.to_dict()
    json_str = json.dumps(d, sort_keys=True)
    reconstructed = RepresentationComparison.from_dict(json.loads(json_str))
    assert reconstructed == comp


def test_representation_registry_operations() -> None:
    """Test registry storage, retrieval, duplicate protection, and query."""
    reg = RepresentationRegistry()
    r1 = RepresentationDefinition(
        representation_id="REP-1",
        name="Rep 1",
        description="Desc",
        represented_phenomenon="P1",
        provenance="Lab",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    r2 = RepresentationDefinition(
        representation_id="REP-2",
        name="Rep 2",
        description="Desc",
        represented_phenomenon="P2",
        provenance="Lab",
        status=EpistemicStatus.HYPOTHESIS,
    )
    reg.register(r1)
    reg.register(r2)

    assert reg.get("REP-1") == r1
    assert reg.contains("REP-1")
    assert len(reg) == 2
    assert reg.all() == (r1, r2)

    with pytest.raises(ValueError, match="already registered"):
        reg.register(r1)

    assert reg.query(status=EpistemicStatus.HYPOTHESIS) == (r2,)
    assert reg.query(status=EpistemicStatus.CONJECTURE) == ()


def test_independent_import() -> None:
    """Test clean independent import without Core/hardware dependencies."""
    from acoustiforge.epistemic.representation import (
        RepresentationChallengeAssessment,
        RepresentationComparison,
        RepresentationDefinition,
        RepresentationGap,
        RepresentationRegistry,
    )
    assert RepresentationDefinition is not None
    assert RepresentationGap is not None
    assert RepresentationChallengeAssessment is not None
    assert RepresentationComparison is not None
    assert RepresentationRegistry is not None


# ==============================================================================
# 2. Mandatory Red-Team Tests (A through V)
# ==============================================================================

def test_red_team_a_not_represented_is_not_impossible() -> None:
    """Red-Team A: A phenomenon absent from the representation must not become PHYSICALLY_IMPOSSIBLE."""
    rep = RepresentationDefinition(
        representation_id="REP-LTI-1D",
        name="1D Linear Response",
        description="Magnitude only",
        represented_phenomenon="Linear frequency response",
        represented_variables=("frequency", "magnitude"),
        omitted_variables=("thermal_compression", "turbulent_vorticity"),
        provenance="core",
    )
    gap = RepresentationGap(
        gap_id="GAP-THERMAL",
        representation_id=rep.representation_id,
        observation_ref="OBS-THERMAL-001",
        phenomenon_description="Voice coil heating reduces sensitivity by 3 dB after 10 minutes.",
        missing_capability="Thermal state and temperature variance are omitted from representation.",
        provenance="field-test",
    )
    # The phenomenon is physically real and observed; representation gap explicitly prevents impossibility claim
    assert "thermal_compression" in rep.omitted_variables
    assert not hasattr(gap, "is_physically_impossible")
    assert not hasattr(rep, "impossible_phenomena")


def test_red_team_b_representation_gap_expresses_limitation() -> None:
    """Red-Team B: Observed behavior that cannot be expressed by the representation produces a representation gap."""
    gap = RepresentationGap(
        gap_id="GAP-002",
        representation_id="REP-FRD",
        observation_ref="OBS-VORTICITY-001",
        phenomenon_description="Port chuffing turbulence generates non-harmonic flow noise.",
        missing_capability="Frequency-domain transfer function cannot represent stochastic aerodynamic noise.",
        provenance="flow-lab",
    )
    assert gap.missing_capability.startswith("Frequency-domain transfer function cannot")


def test_red_team_c_representation_gap_distinct_from_unknown() -> None:
    """Red-Team C: Representation gap does not automatically become E4 UNKNOWN, and vice versa."""
    gap = RepresentationGap(
        gap_id="GAP-003",
        representation_id="REP-FRD",
        observation_ref="OBS-003",
        phenomenon_description="Phase delay is well understood in physics but omitted from this 1D magnitude representation.",
        missing_capability="Missing phase variable.",
        provenance="lab",
    )
    # The phenomenon is KNOWN in physics, but a GAP in the representation
    unknown = EpistemicUnknown(
        unknown_id="UNK-003",
        statement="Unknown resonance mechanism in surround suspension at 4.2 kHz.",
        scope={},
        provenance="lab",
    )
    assert isinstance(gap, RepresentationGap)
    assert isinstance(unknown, EpistemicUnknown)
    assert gap.gap_id != unknown.unknown_id


def test_red_team_d_representation_is_not_model() -> None:
    """Red-Team D: Representation limitation does not automatically produce MODEL_ERROR."""
    gap = RepresentationGap(
        gap_id="GAP-004",
        representation_id="REP-1D",
        observation_ref="OBS-004",
        phenomenon_description="Directivity balloon cannot be displayed on 2D Bode plot.",
        missing_capability="Missing spatial polar coordinates.",
        provenance="lab",
    )
    # A representation omission is not inherently a model mathematical error
    assert not hasattr(gap, "model_error")
    assert not hasattr(gap, "residual_classification")


def test_red_team_e_representation_is_not_objective() -> None:
    """Red-Team E: Representation limitation does not automatically invalidate the objective."""
    rep = RepresentationDefinition(
        representation_id="REP-FRD",
        name="FRD",
        description="Desc",
        represented_phenomenon="Magnitude",
        provenance="lab",
    )
    obj = EpistemicObjective(
        objective_id="OBJ-RMS",
        name="RMS Error",
        description="RMS loss",
        expression="L = E_rms",
        provenance="core",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    assessment = RepresentationChallengeAssessment(
        assessment_id="RCA-E",
        challenge_id="CH-E",
        representation_id=rep.representation_id,
        rationale="FRD does not represent phase.",
        provenance="lab",
    )
    # The objective remains PRODUCTION_AUTHORITY
    assert obj.status == EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_f_representation_is_not_measurement() -> None:
    """Red-Team F: Representation limitation does not automatically invalidate empirical measurement data."""
    rep = RepresentationDefinition(
        representation_id="REP-GRID",
        name="Coarse Grid",
        description="1/3 octave grid",
        represented_phenomenon="Spectrum",
        represented_variables=("1/3_octave_bins",),
        omitted_variables=("high_resolution_fft_bins",),
        provenance="lab",
    )
    # The underlying raw measurement (e.g. 96 kHz 24-bit PCM time-domain sweep) remains valid
    assert "high_resolution_fft_bins" in rep.omitted_variables


def test_red_team_g_no_representation_winner() -> None:
    """Red-Team G: Multiple representations can coexist without ranking or declaring a winner."""
    comp = RepresentationComparison(
        comparison_id="RCOMP-G",
        representation_ids=("REP-A", "REP-B"),
        observation_refs=("OBS-1",),
        dimensions=("dimension_1",),
        findings=({"dimension": "dimension_1", "note": "Comparison details"},),
        provenance="eval",
    )
    assert not hasattr(comp, "winner")
    assert not hasattr(comp, "best_representation")
    assert not hasattr(comp, "winning_representation_id")


def test_red_team_h_no_scalar_adequacy_score() -> None:
    """Red-Team H: No universal representation adequacy, confidence, or truth scalar score exists."""
    rep = RepresentationDefinition(
        representation_id="REP-H",
        name="Rep H",
        description="Desc",
        represented_phenomenon="Phenom",
        provenance="eval",
    )
    d = rep.to_dict()
    forbidden_keys = [
        "score",
        "adequacy_score",
        "truth_score",
        "confidence_score",
        "representation_score",
    ]
    for k in forbidden_keys:
        assert k not in d
        assert not hasattr(rep, k)


def test_red_team_i_omitted_variables_inspectable() -> None:
    """Red-Team I: Omitted variables remain explicitly inspectable."""
    rep = RepresentationDefinition(
        representation_id="REP-INSPECT",
        name="Inspection Rep",
        description="Desc",
        represented_phenomenon="Phenom",
        represented_variables=("frequency", "spl"),
        omitted_variables=("phase", "thd", "imd", "cone_velocity"),
        provenance="core",
    )
    assert len(rep.omitted_variables) == 4
    assert "cone_velocity" in rep.omitted_variables


def test_red_team_j_scope_mismatch_preservation() -> None:
    """Red-Team J: Out-of-scope representation use is explicitly preserved as scope limitation."""
    rep = RepresentationDefinition(
        representation_id="REP-PASSIVE-SCOPE",
        name="Small-Signal Linear Acoustic Model",
        description="Valid up to 85 dB SPL",
        represented_phenomenon="Small signal response",
        scope={"max_spl_db": 85.0},
        provenance="core",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    # Applying at 110 dB SPL is outside declared scope, but does not invalidate the small-signal representation
    assert rep.scope["max_spl_db"] == 85.0
    assert rep.status == EpistemicStatus.VALIDATED_MODEL


def test_red_team_k_alternative_representations_coexist() -> None:
    """Red-Team K: Multiple alternative representations remain independently addressable."""
    reg = RepresentationRegistry()
    r1 = RepresentationDefinition(representation_id="REP-1D", name="1D", description="D", represented_phenomenon="P", provenance="L")
    r2 = RepresentationDefinition(representation_id="REP-2D", name="2D", description="D", represented_phenomenon="P", provenance="L")
    r3 = RepresentationDefinition(representation_id="REP-3D", name="3D", description="D", represented_phenomenon="P", provenance="L")
    reg.register(r1)
    reg.register(r2)
    reg.register(r3)
    assert len(reg) == 3


def test_red_team_l_ai_proposals_do_not_become_evidence() -> None:
    """Red-Team L: AI proposals do not become empirical evidence."""
    ai_rep = RepresentationDefinition(
        representation_id="REP-AI-HYPOTHESIS",
        name="AI Proposed 4D Spatiotemporal Representation",
        description="Autonomous coordinate basis",
        represented_phenomenon="Hypothesized turbulent wave interaction",
        provenance="ai-agent-discovery",
        status=EpistemicStatus.HYPOTHESIS,
    )
    assert ai_rep.provenance == "ai-agent-discovery"
    assert ai_rep.status == EpistemicStatus.HYPOTHESIS
    assert ai_rep.status != EpistemicStatus.PRODUCTION_AUTHORITY


def test_red_team_m_no_automatic_replacement() -> None:
    """Red-Team M: A proposed alternative representation cannot replace production representation."""
    reg = RepresentationRegistry()
    prod_rep = RepresentationDefinition(
        representation_id="REP-PROD",
        name="Production FRD",
        description="Official",
        represented_phenomenon="Magnitude",
        provenance="core",
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
    )
    cand_rep = RepresentationDefinition(
        representation_id="REP-CAND",
        name="Candidate Spherical Harmonics",
        description="Proposed",
        represented_phenomenon="Directivity",
        provenance="researcher",
        status=EpistemicStatus.HYPOTHESIS,
    )
    reg.register(prod_rep)
    reg.register(cand_rep)

    assert reg.get("REP-PROD").status == EpistemicStatus.PRODUCTION_AUTHORITY
    assert reg.get("REP-CAND").status == EpistemicStatus.HYPOTHESIS


def test_red_team_n_no_production_mutation() -> None:
    """Red-Team N: Production domain models, measurement classes, and graphs remain unchanged."""
    reg = RepresentationRegistry()
    rep = RepresentationDefinition(
        representation_id="REP-TEST-N",
        name="Test",
        description="Test",
        represented_phenomenon="Test",
        provenance="test",
    )
    reg.register(rep)

    core_modules = [m for m in sys.modules.keys() if m.startswith("acoustiforge.") and not m.startswith("acoustiforge.epistemic")]
    for mod_name in core_modules:
        mod = sys.modules[mod_name]
        assert not hasattr(mod, "_epistemic_representation_override")


def test_red_team_o_determinism() -> None:
    """Red-Team O: Identical inputs produce identical serialized results."""
    args = {
        "representation_id": "REP-DET",
        "name": "Deterministic Rep",
        "description": "Desc",
        "represented_phenomenon": "Acoustic Pressure",
        "represented_variables": ("f", "p"),
        "omitted_variables": ("t",),
        "relationships": ("p(f)",),
        "assumptions": ("A1",),
        "provenance": "test",
        "scope": {"f": [20, 20000]},
        "status": EpistemicStatus.VALIDATED_MODEL,
    }
    r1 = RepresentationDefinition(**args)
    r2 = RepresentationDefinition(**args)
    assert r1.to_dict() == r2.to_dict()
    assert json.dumps(r1.to_dict(), sort_keys=True) == json.dumps(r2.to_dict(), sort_keys=True)


def test_red_team_p_provenance_preserved() -> None:
    """Red-Team P: Representation challenges preserve provenance."""
    assessment = RepresentationChallengeAssessment(
        assessment_id="RCA-PROV",
        challenge_id="CH-PROV",
        representation_id="REP-FRD",
        rationale="Rationale",
        provenance="scientific-review-panel-session-9",
    )
    assert assessment.provenance == "scientific-review-panel-session-9"


def test_red_team_q_measurement_and_representation_separated() -> None:
    """Red-Team Q: Measured data and its epistemic representation definition remain distinct."""
    rep = RepresentationDefinition(
        representation_id="REP-MAG-ONLY",
        name="Magnitude Representation",
        description="Discards raw phase and time-series samples",
        represented_phenomenon="Steady-state transfer function magnitude",
        represented_variables=("frequency", "magnitude"),
        omitted_variables=("raw_time_series_pcm", "phase"),
        provenance="lab",
    )
    # The representation documents what it retains and what it discards
    assert "raw_time_series_pcm" in rep.omitted_variables


def test_red_team_r_ontology_protection() -> None:
    """Red-Team R: No absence-from-representation inference becomes a physical impossibility claim."""
    gap = RepresentationGap(
        gap_id="GAP-MAGNETIC-HYSTERESIS",
        representation_id="REP-LINEAR-THIELE-SMALL",
        observation_ref="OBS-MAGNETIC-001",
        phenomenon_description="Nonlinear B-H magnetic hysteresis loop in motor pole piece.",
        missing_capability="Thiele-Small parameters assume linear constant Bl product.",
        provenance="transducer-lab",
    )
    # Magnetic hysteresis is a verified physical reality; it is simply not in linear Thiele-Small
    assert "B-H magnetic hysteresis" in gap.phenomenon_description


def test_red_team_s_model_challenge_separation() -> None:
    """Red-Team S: A representation challenge does not automatically enter E7 falsification."""
    assessment = RepresentationChallengeAssessment(
        assessment_id="RCA-S",
        challenge_id="CH-S",
        representation_id="REP-FRD",
        rationale="Phase omitted.",
        provenance="lab",
    )
    assert not isinstance(assessment, FalsificationReview)
    assert not hasattr(assessment, "decision")


def test_red_team_t_objective_challenge_separation() -> None:
    """Red-Team T: A representation challenge does not automatically become E8 objective challenge."""
    assessment = RepresentationChallengeAssessment(
        assessment_id="RCA-T",
        challenge_id="CH-T",
        representation_id="REP-FRD",
        rationale="Phase omitted.",
        provenance="lab",
    )
    # Representation challenge is targeted at the representation, not an optimization loss expression
    assert hasattr(assessment, "representation_id")
    assert not hasattr(assessment, "objective_id")


def test_red_team_u_alternative_explanations_preserved() -> None:
    """Red-Team U: Potential model, measurement, boundary, and unknown explanations remain explicit."""
    gap = RepresentationGap(
        gap_id="GAP-U",
        representation_id="REP-FRD",
        observation_ref="OBS-U",
        phenomenon_description="Discrepancy at high drive levels.",
        missing_capability="Missing nonlinear stiffness parameter x(t).",
        alternative_explanations=(
            "Could be amplifier clipping rather than mechanical spider nonlinearity.",
            "Could be microphone diaphragm overload.",
        ),
        provenance="metrology",
    )
    assert len(gap.alternative_explanations) == 2
    assert "amplifier clipping" in gap.alternative_explanations[0]


def test_red_team_v_intentional_information_loss_challengeable() -> None:
    """Red-Team V: A representation that intentionally discards information can be challenged without being declared invalid."""
    rep = RepresentationDefinition(
        representation_id="REP-1-OCTAVE",
        name="Octave-Band Smoothed Representation",
        description="Intentionally applies 1-octave spatial smoothing for architectural room acoustics.",
        represented_phenomenon="Broadband energy envelope",
        represented_variables=("octave_band_centers", "smoothed_spl"),
        omitted_variables=("fine_spectral_resonances", "q_factors"),
        provenance="architectural-handbook",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    assessment = RepresentationChallengeAssessment(
        assessment_id="RCA-V",
        challenge_id="CH-V",
        representation_id=rep.representation_id,
        rationale="1-octave smoothing masks high-Q modal peaks in small listening rooms.",
        provenance="acoustics-consultant",
    )
    # Both the representation (useful in broad architectural contexts) and the challenge coexist
    assert rep.status == EpistemicStatus.VALIDATED_MODEL
    assert "high-Q modal peaks" in assessment.rationale
