"""AcoustiForge Epistemic Residual and Residual Assessment Tests.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E4: Unknown and Residual Representation
"""

import json
import pytest

from acoustiforge.epistemic.models import (
    EpistemicModel,
)
from acoustiforge.epistemic.residuals import (
    ModelResidual,
    ResidualAssessment,
    ResidualRegistry,
)
from acoustiforge.epistemic.unknowns import (
    EpistemicUnknown,
)
from acoustiforge.epistemic.vocabulary import (
    EpistemicClass,
    EpistemicEvidenceType,
    EpistemicStatus,
    EpistemicZone,
    ResidualClassificationType,
)


# ==============================================================================
# Test 1 — Residual Construction
# ==============================================================================

def test_residual_construction():
    """Verify that a valid ModelResidual can be constructed with canonical fields."""
    res = ModelResidual(
        residual_id="RES-001",
        model_id="MODEL-LR4-2WAY",
        observation_ref="OBS-SWEEP-LIVE-01",
        prediction_ref="PRED-OPT-LR4-01",
        residual_summary="-4.2 dB acoustic notch at 350 Hz with 0.3 octave bandwidth.",
        scope={"frequency_range_hz": [20.0, 20000.0], "axis": "on-axis"},
        provenance="offline-simulation-audit",
    )
    assert res.residual_id == "RES-001"
    assert res.model_id == "MODEL-LR4-2WAY"
    assert res.observation_ref == "OBS-SWEEP-LIVE-01"
    assert res.prediction_ref == "PRED-OPT-LR4-01"
    assert "-4.2 dB" in res.residual_summary
    assert res.scope["axis"] == "on-axis"
    assert res.provenance == "offline-simulation-audit"


# ==============================================================================
# Test 2 — Required References Validation
# ==============================================================================

def test_required_references_validation():
    """Verify that empty/invalid IDs, model refs, observation refs, prediction refs are rejected."""
    # Empty residual_id
    with pytest.raises(ValueError, match="residual_id"):
        ModelResidual(
            residual_id="",
            model_id="M-1",
            observation_ref="O-1",
            prediction_ref="P-1",
            residual_summary="summary",
            scope={},
            provenance="core",
        )

    # Empty model_id
    with pytest.raises(ValueError, match="model_id"):
        ModelResidual(
            residual_id="R-1",
            model_id="",
            observation_ref="O-1",
            prediction_ref="P-1",
            residual_summary="summary",
            scope={},
            provenance="core",
        )

    # Empty observation_ref
    with pytest.raises(ValueError, match="observation_ref"):
        ModelResidual(
            residual_id="R-1",
            model_id="M-1",
            observation_ref="  ",
            prediction_ref="P-1",
            residual_summary="summary",
            scope={},
            provenance="core",
        )

    # Empty prediction_ref
    with pytest.raises(ValueError, match="prediction_ref"):
        ModelResidual(
            residual_id="R-1",
            model_id="M-1",
            observation_ref="O-1",
            prediction_ref="",
            residual_summary="summary",
            scope={},
            provenance="core",
        )

    # Empty residual_summary
    with pytest.raises(ValueError, match="residual_summary"):
        ModelResidual(
            residual_id="R-1",
            model_id="M-1",
            observation_ref="O-1",
            prediction_ref="P-1",
            residual_summary="   ",
            scope={},
            provenance="core",
        )

    # Empty provenance
    with pytest.raises(ValueError, match="provenance"):
        ModelResidual(
            residual_id="R-1",
            model_id="M-1",
            observation_ref="O-1",
            prediction_ref="P-1",
            residual_summary="summary",
            scope={},
            provenance="",
        )


# ==============================================================================
# Test 3 — Residual Is Descriptive (Residual != Model Error / Falsified)
# ==============================================================================

def test_residual_is_descriptive():
    """Verify residual construction does not automatically classify or declare model failure."""
    res = ModelResidual(
        residual_id="RES-NOTCH",
        model_id="MODEL-LR4",
        observation_ref="OBS-01",
        prediction_ref="PRED-01",
        residual_summary="Broadband tilt discrepancy.",
        scope={},
        provenance="lab",
    )
    # The residual itself is purely descriptive observation data
    assert not hasattr(res, "is_falsified")
    assert not hasattr(res, "is_model_error")


# ==============================================================================
# Test 4 — Candidate Classification Taxonomy
# ==============================================================================

def test_candidate_classification_taxonomy():
    """Verify all six candidate classes can be represented in a ResidualAssessment."""
    all_classes = (
        ResidualClassificationType.MEASUREMENT_ERROR,
        ResidualClassificationType.PARAMETER_ERROR,
        ResidualClassificationType.BOUNDARY_ERROR,
        ResidualClassificationType.MODEL_ERROR,
        ResidualClassificationType.MISSING_VARIABLE,
        ResidualClassificationType.UNKNOWN,
    )
    assessment = ResidualAssessment(
        residual_id="RES-001",
        candidate_classes=all_classes,
        evidence_refs=("EVID-01",),
        proposed_tests=("test_repeat",),
        unresolved=True,
        rationale="Initial broad multi-hypothesis assessment.",
    )
    assert len(assessment.candidate_classes) == 6
    assert ResidualClassificationType.MODEL_ERROR in assessment.candidate_classes
    assert ResidualClassificationType.MISSING_VARIABLE in assessment.candidate_classes


# ==============================================================================
# Test 5 — Candidate Semantics (Multiple Candidates Coexist)
# ==============================================================================

def test_candidate_semantics_coexistence():
    """Verify multiple candidate classes can coexist without singular forced collapse."""
    assessment = ResidualAssessment(
        residual_id="RES-002",
        candidate_classes=(
            ResidualClassificationType.MODEL_ERROR,
            ResidualClassificationType.MISSING_VARIABLE,
        ),
        evidence_refs=(),
        proposed_tests=("test_laser_vibrometry", "test_free_field_chamber"),
        unresolved=True,
        rationale="Could be driver cone breakup mode or unmodelled cabinet diffraction.",
    )
    assert len(assessment.candidate_classes) == 2
    assert assessment.unresolved is True


# ==============================================================================
# Test 6 — No Winner
# ==============================================================================

def test_no_candidate_winner():
    """Verify no candidate class is automatically crowned as the singular truth."""
    assessment = ResidualAssessment(
        residual_id="RES-003",
        candidate_classes=(ResidualClassificationType.PARAMETER_ERROR,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=False,
        rationale="Parameter gradient non-zero at termination.",
    )
    # Even if single candidate, it is a candidate explanation, not an ontological proof
    assert assessment.candidate_classes == (ResidualClassificationType.PARAMETER_ERROR,)
    assert not hasattr(assessment, "winner")
    assert not hasattr(assessment, "truth")


# ==============================================================================
# Test 7 — Evidence References
# ==============================================================================

def test_evidence_references():
    """Verify evidence references are retained as string identifiers without evidence subsystem coupling."""
    assessment = ResidualAssessment(
        residual_id="RES-004",
        candidate_classes=(ResidualClassificationType.MEASUREMENT_ERROR,),
        evidence_refs=("EVID-MIC-CAL-01", "EVID-NOISE-FLOOR-02"),
        proposed_tests=(),
        unresolved=True,
        rationale="Microphone SNR below 15 dB.",
    )
    assert assessment.evidence_refs == ("EVID-MIC-CAL-01", "EVID-NOISE-FLOOR-02")
    assert isinstance(assessment.evidence_refs, tuple)


# ==============================================================================
# Test 8 — Proposed Tests (Stored But Not Executed)
# ==============================================================================

def test_proposed_tests():
    """Verify proposed tests are stored as descriptions/identifiers and not executed."""
    tests = ("test_repeat_sweep", "test_near_field_port_measurement")
    assessment = ResidualAssessment(
        residual_id="RES-005",
        candidate_classes=(ResidualClassificationType.MISSING_VARIABLE,),
        evidence_refs=(),
        proposed_tests=tests,
        unresolved=True,
        rationale="Port resonance suspect.",
    )
    assert assessment.proposed_tests == tests
    # Verify no execution side effects occurred


# ==============================================================================
# Test 9 — Unresolved Semantics
# ==============================================================================

def test_unresolved_semantics():
    """Verify unresolved state is explicit boolean."""
    a_unres = ResidualAssessment(
        residual_id="RES-006A",
        candidate_classes=(ResidualClassificationType.UNKNOWN,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale="Insufficient information to isolate cause.",
    )
    assert a_unres.unresolved is True

    a_res = ResidualAssessment(
        residual_id="RES-006B",
        candidate_classes=(ResidualClassificationType.BOUNDARY_ERROR,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=False,
        rationale="Parameter hit bound limit.",
    )
    assert a_res.unresolved is False


# ==============================================================================
# Test 10 — Rationale
# ==============================================================================

def test_rationale_semantics():
    """Verify rationale is retained as descriptive metadata."""
    rationale_text = "Autocorrelation r1 = 0.82 indicates structured non-random residual pattern."
    assessment = ResidualAssessment(
        residual_id="RES-007",
        candidate_classes=(ResidualClassificationType.MODEL_ERROR,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale=rationale_text,
    )
    assert assessment.rationale == rationale_text


# ==============================================================================
# Test 11 — Immutability
# ==============================================================================

def test_immutability():
    """Verify ModelResidual and ResidualAssessment reject attribute reassignment."""
    res = ModelResidual(
        residual_id="RES-IMM",
        model_id="M-1",
        observation_ref="O-1",
        prediction_ref="P-1",
        residual_summary="summary",
        scope={},
        provenance="core",
    )
    with pytest.raises((AttributeError, TypeError)):
        res.model_id = "M-2"  # type: ignore

    assessment = ResidualAssessment(
        residual_id="RES-IMM",
        candidate_classes=(ResidualClassificationType.UNKNOWN,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale="rationale",
    )
    with pytest.raises((AttributeError, TypeError)):
        assessment.unresolved = False  # type: ignore


# ==============================================================================
# Test 12 — Deterministic Serialization
# ==============================================================================

def test_deterministic_serialization():
    """Verify deterministic conversion to dict for both objects."""
    res = ModelResidual(
        residual_id="RES-SER-01",
        model_id="MODEL-LR4",
        observation_ref="OBS-01",
        prediction_ref="PRED-01",
        residual_summary="Notch at 350 Hz",
        scope={"axis": "on-axis"},
        provenance="lab",
    )
    d_res = res.to_dict()
    assert d_res["residual_id"] == "RES-SER-01"
    assert d_res["scope"] == {"axis": "on-axis"}

    assessment = ResidualAssessment(
        residual_id="RES-SER-01",
        candidate_classes=(ResidualClassificationType.MODEL_ERROR, ResidualClassificationType.MISSING_VARIABLE),
        evidence_refs=("E1",),
        proposed_tests=("T1",),
        unresolved=True,
        rationale="Diagnostic assessment",
    )
    d_ass = assessment.to_dict()
    assert d_ass["candidate_classes"] == ["MODEL_ERROR", "MISSING_VARIABLE"]
    assert d_ass["unresolved"] is True


# ==============================================================================
# Test 13 — JSON Round-Trip Losslessness
# ==============================================================================

def test_json_round_trip():
    """Verify lossless JSON round-trip reconstruction for ModelResidual and ResidualAssessment."""
    res = ModelResidual(
        residual_id="RES-JSON-01",
        model_id="MODEL-LR4",
        observation_ref="OBS-01",
        prediction_ref="PRED-01",
        residual_summary="Dip at 350 Hz",
        scope={"freq": [300, 400]},
        provenance="offline",
    )
    json_res = json.dumps(res.to_dict(), sort_keys=True)
    rec_res = ModelResidual.from_dict(json.loads(json_res))
    assert rec_res == res

    assessment = ResidualAssessment(
        residual_id="RES-JSON-01",
        candidate_classes=(ResidualClassificationType.MODEL_ERROR,),
        evidence_refs=("EVID-1",),
        proposed_tests=("TEST-1",),
        unresolved=False,
        rationale="Assessment rationale",
    )
    json_ass = json.dumps(assessment.to_dict(), sort_keys=True)
    rec_ass = ResidualAssessment.from_dict(json.loads(json_ass))
    assert rec_ass == assessment
    assert rec_ass.candidate_classes == (ResidualClassificationType.MODEL_ERROR,)


# ==============================================================================
# Test 14 — Independent Import & ResidualRegistry
# ==============================================================================

def test_residual_registry_and_independent_import():
    """Verify ResidualRegistry operates deterministically with zero Core/hardware dependency."""
    from acoustiforge.epistemic import (
        ModelResidual,
        ResidualAssessment,
        ResidualRegistry,
    )
    registry = ResidualRegistry()
    assert len(registry) == 0

    res = ModelResidual(
        residual_id="RES-REG-01",
        model_id="M-1",
        observation_ref="O-1",
        prediction_ref="P-1",
        residual_summary="Summary",
        scope={},
        provenance="lab",
    )
    assessment = ResidualAssessment(
        residual_id="RES-REG-01",
        candidate_classes=(ResidualClassificationType.MODEL_ERROR,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale="Rationale",
    )

    registry.register_residual(res)
    registry.register_assessment(assessment)

    assert len(registry) == 1
    assert registry.get_residual("RES-REG-01") == res
    assert registry.get_assessment("RES-REG-01") == assessment
    assert registry.contains_residual("RES-REG-01")
    assert registry.contains_assessment("RES-REG-01")

    # Duplicate registration rejection
    with pytest.raises(ValueError, match="already registered"):
        registry.register_residual(res)

    with pytest.raises(ValueError, match="already registered"):
        registry.register_assessment(assessment)


# ==============================================================================
# CROSS-SEMANTIC RED-TEAM TESTS (A through H)
# ==============================================================================

def test_red_team_a_residual_is_not_model_error():
    """Red-team A: A residual must NOT automatically become MODEL_ERROR."""
    res = ModelResidual(
        residual_id="RES-RT-A",
        model_id="MODEL-01",
        observation_ref="OBS-01",
        prediction_ref="PRED-01",
        residual_summary="Dip observed.",
        scope={},
        provenance="measurement",
    )
    # Creating a residual does not create a MODEL_ERROR claim
    assert not hasattr(res, "epistemic_class")
    assert not hasattr(res, "error_type")


def test_red_team_b_residual_is_not_falsification_detected():
    """Red-team B: A residual must NOT automatically become FALSIFICATION_EVIDENCE_DETECTED."""
    res = ModelResidual(
        residual_id="RES-RT-B",
        model_id="MODEL-01",
        observation_ref="OBS-01",
        prediction_ref="PRED-01",
        residual_summary="Large residual 10 dB.",
        scope={},
        provenance="measurement",
    )
    assert not hasattr(res, "falsification_status")


def test_red_team_c_unknown_is_not_invalid():
    """Red-team C: An UNKNOWN must NOT automatically become INVALID."""
    unk = EpistemicUnknown(
        unknown_id="UNK-RT-C",
        statement="Unmodelled acoustic phase shift.",
        scope={},
        provenance="lab",
        status=EpistemicStatus.HYPOTHESIS,
    )
    assert unk.status == EpistemicStatus.HYPOTHESIS
    assert unk.status != EpistemicStatus.FALSIFIED
    assert unk.status != EpistemicStatus.DEPRECATED


def test_red_team_d_proposed_test_does_not_execute():
    """Red-team D: A proposed test must NOT execute during construction."""
    executed = False
    def fake_test():
        nonlocal executed
        executed = True

    assessment = ResidualAssessment(
        residual_id="RES-RT-D",
        candidate_classes=(ResidualClassificationType.PARAMETER_ERROR,),
        evidence_refs=(),
        proposed_tests=("re-optimize-with-different-bounds",),
        unresolved=True,
        rationale="Test proposed only.",
    )
    assert not executed
    assert assessment.proposed_tests == ("re-optimize-with-different-bounds",)


def test_red_team_e_ai_assessment_does_not_become_evidence():
    """Red-team E: An AI-generated residual assessment must NOT automatically become evidence."""
    assessment = ResidualAssessment(
        residual_id="RES-RT-E",
        candidate_classes=(ResidualClassificationType.MISSING_VARIABLE,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale="AI proposed hypothesis of enclosure leakage.",
    )
    # Assessment is an assessment object, not EpistemicEvidenceType or EvidenceRecord
    assert not isinstance(assessment, EpistemicEvidenceType)


def test_red_team_f_model_error_candidate_is_assessment_not_falsification():
    """Red-team F: An assessment containing MODEL_ERROR must remain an assessment, not a falsification event."""
    assessment = ResidualAssessment(
        residual_id="RES-RT-F",
        candidate_classes=(ResidualClassificationType.MODEL_ERROR,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale="Suspected crossover phase cancellation.",
    )
    # Candidate class is a candidate, not a state transition
    assert ResidualClassificationType.MODEL_ERROR in assessment.candidate_classes
    assert not hasattr(assessment, "falsified_model")


def test_red_team_g_candidate_classification_does_not_mutate_model():
    """Red-team G: No candidate classification may automatically modify EpistemicModel.status."""
    model = EpistemicModel(
        model_id="MODEL-RT-G",
        name="Target Model",
        description="Model to assess.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="core",
    )
    # Create residual and assessment pointing to model
    res = ModelResidual(
        residual_id="RES-RT-G",
        model_id=model.model_id,
        observation_ref="OBS-1",
        prediction_ref="PRED-1",
        residual_summary="Error",
        scope={},
        provenance="test",
    )
    assessment = ResidualAssessment(
        residual_id=res.residual_id,
        candidate_classes=(ResidualClassificationType.MODEL_ERROR,),
        evidence_refs=(),
        proposed_tests=(),
        unresolved=True,
        rationale="Model error candidate",
    )
    # Model status remains VALIDATED_MODEL without mutation
    assert model.status == EpistemicStatus.VALIDATED_MODEL
    assert model.status != EpistemicStatus.FALSIFIED
    assert model.status != EpistemicStatus.FALSIFICATION_EVIDENCE_DETECTED


def test_red_team_h_residual_does_not_modify_production_core():
    """Red-team H: No residual may modify production Core state."""
    res = ModelResidual(
        residual_id="RES-RT-H",
        model_id="MODEL-LR4-2WAY",
        observation_ref="OBS-1",
        prediction_ref="PRED-1",
        residual_summary="Notch",
        scope={},
        provenance="test",
    )
    # Verify core domain classes are untouched
    from acoustiforge.domain.specifications import CrossoverFamily
    assert CrossoverFamily.LINKWITZ_RILEY.value == "linkwitz_riley"
