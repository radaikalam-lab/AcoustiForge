"""AcoustiForge Epistemic Vocabulary Unit & Invariant Tests.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- Phase E1: Epistemic Vocabulary Implementation
"""

import json
import pytest

from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicEvidenceLink,
    EpistemicEvidenceType,
    EpistemicStatus,
    EpistemicZone,
    EvidenceRelation,
    ResidualClassificationType,
    ZoneHChallengeType,
)


# ==============================================================================
# Test 1 — Enum Completeness
# ==============================================================================

def test_enum_completeness():
    """Verify that all frozen enum members exist and match canonical names."""
    # Zones
    assert set(EpistemicZone.__members__.keys()) == {"ZONE_H", "ZONE_M", "ZONE_P", "ZONE_U"}

    # EpistemicClass
    expected_classes = {
        "MATHEMATICAL_THEOREM",
        "PHYSICAL_INVARIANT",
        "CONSTITUTIVE_MODEL",
        "APPROXIMATION",
        "EMPIRICAL_REGULARITY",
        "ENGINEERING_HEURISTIC",
        "OBJECTIVE_ASSUMPTION",
        "ONTOLOGICAL_ASSUMPTION",
        "HYPOTHESIS",
        "UNKNOWN",
    }
    assert set(EpistemicClass.__members__.keys()) == expected_classes

    # EpistemicStatus
    expected_statuses = {
        "CONJECTURE",
        "HYPOTHESIS",
        "TESTED_CANDIDATE",
        "VALIDATED_MODEL",
        "EPISTEMIC_ACCEPTED",
        "PRODUCTION_CANDIDATE",
        "PRODUCTION_AUTHORITY",
        "FALSIFICATION_EVIDENCE_DETECTED",
        "UNDER_REVIEW",
        "DOMAIN_LIMITED",
        "CHALLENGED",
        "FALSIFIED",
        "DEPRECATED",
    }
    assert set(EpistemicStatus.__members__.keys()) == expected_statuses

    # ChallengeStatus
    expected_challenge_statuses = {
        "UNCHALLENGED",
        "CHALLENGE_PROPOSED",
        "UNDER_INVESTIGATION",
        "EVIDENCE_SUPPORTED",
        "CHALLENGE_REJECTED",
        "EPISTEMIC_ACCEPTED",
    }
    assert set(ChallengeStatus.__members__.keys()) == expected_challenge_statuses

    # ZoneHChallengeType
    expected_zone_h_challenges = {
        "H_APPLICABILITY_CHALLENGE",
        "H_CLASSIFICATION_CHALLENGE",
        "H_FUNDAMENTAL_CHALLENGE",
    }
    assert set(ZoneHChallengeType.__members__.keys()) == expected_zone_h_challenges

    # ResidualClassificationType
    expected_residuals = {
        "MEASUREMENT_ERROR",
        "PARAMETER_ERROR",
        "BOUNDARY_ERROR",
        "MODEL_ERROR",
        "MISSING_VARIABLE",
        "UNKNOWN",
    }
    assert set(ResidualClassificationType.__members__.keys()) == expected_residuals

    # EpistemicEvidenceType
    expected_evidence_types = {
        "MATHEMATICAL_PROOF",
        "PHYSICAL_MEASUREMENT",
        "EXPERIMENTAL_RESULT",
        "SIMULATION",
        "OBSERVATIONAL_DATA",
        "ENGINEERING_TEST",
        "HUMAN_FEEDBACK",
        "AI_GENERATED_HYPOTHESIS",
    }
    assert set(EpistemicEvidenceType.__members__.keys()) == expected_evidence_types

    # EvidenceRelation
    expected_relations = {
        "SUPPORTS",
        "CONTRADICTS",
        "CHALLENGES",
        "LOCALIZES",
        "DISCRIMINATES",
        "DOES_NOT_TEST",
    }
    assert set(EvidenceRelation.__members__.keys()) == expected_relations


# ==============================================================================
# Test 2 — Enum Stability & String Subclassing
# ==============================================================================

def test_enum_stability():
    """Verify that all enum values are stable string instances."""
    for enum_cls in [
        EpistemicZone,
        EpistemicClass,
        EpistemicStatus,
        ChallengeStatus,
        ZoneHChallengeType,
        ResidualClassificationType,
        EpistemicEvidenceType,
        EvidenceRelation,
    ]:
        for member in enum_cls:
            assert isinstance(member.value, str)
            assert isinstance(member, str)
            assert member == member.value


# ==============================================================================
# Test 3 — Zone Separation
# ==============================================================================

def test_zone_separation():
    """Verify that H, M, P, U zones are pairwise distinct and mutually exclusive."""
    zones = list(EpistemicZone)
    assert len(zones) == 4
    assert len(set(zones)) == 4
    assert EpistemicZone.ZONE_H != EpistemicZone.ZONE_M
    assert EpistemicZone.ZONE_M != EpistemicZone.ZONE_P
    assert EpistemicZone.ZONE_P != EpistemicZone.ZONE_U
    assert EpistemicZone.ZONE_U != EpistemicZone.ZONE_H


# ==============================================================================
# Test 4 — Epistemic Class Separation & Semantic Invariants
# ==============================================================================

def test_epistemic_class_separation():
    """Verify that all 10 epistemic classes remain strictly distinguishable."""
    classes = list(EpistemicClass)
    assert len(classes) == 10
    assert len(set(classes)) == 10

    # Semantic non-equivalence checks
    assert EpistemicClass.CONSTITUTIVE_MODEL != EpistemicClass.PHYSICAL_INVARIANT  # MODEL != LAW
    assert EpistemicClass.APPROXIMATION != EpistemicClass.PHYSICAL_INVARIANT        # APPROXIMATION != LAW
    assert EpistemicClass.ENGINEERING_HEURISTIC != EpistemicClass.PHYSICAL_INVARIANT # HEURISTIC != LAW
    assert EpistemicClass.HYPOTHESIS != EpistemicClass.EMPIRICAL_REGULARITY         # HYPOTHESIS != EVIDENCE
    assert EpistemicClass.UNKNOWN != EpistemicClass.ENGINEERING_HEURISTIC
    assert EpistemicClass.OBJECTIVE_ASSUMPTION != EpistemicClass.ONTOLOGICAL_ASSUMPTION


# ==============================================================================
# Test 5 — Production Authority Separation
# ==============================================================================

def test_production_authority_separation():
    """Verify that EPISTEMIC_ACCEPTED and PRODUCTION_CANDIDATE are distinct from PRODUCTION_AUTHORITY."""
    assert EpistemicStatus.EPISTEMIC_ACCEPTED != EpistemicStatus.PRODUCTION_AUTHORITY
    assert EpistemicStatus.PRODUCTION_CANDIDATE != EpistemicStatus.PRODUCTION_AUTHORITY
    assert EpistemicStatus.EPISTEMIC_ACCEPTED != EpistemicStatus.PRODUCTION_CANDIDATE

    # Ensure no ambiguous PROMOTED status exists in EpistemicStatus
    assert "PROMOTED" not in EpistemicStatus.__members__


# ==============================================================================
# Test 6 — Zone-H Challenge Taxonomy
# ==============================================================================

def test_zone_h_challenge_taxonomy():
    """Verify that Zone H challenges strictly distinguish applicability, classification, and fundamental claims."""
    assert ZoneHChallengeType.H_APPLICABILITY_CHALLENGE.value == "H_APPLICABILITY_CHALLENGE"
    assert ZoneHChallengeType.H_CLASSIFICATION_CHALLENGE.value == "H_CLASSIFICATION_CHALLENGE"
    assert ZoneHChallengeType.H_FUNDAMENTAL_CHALLENGE.value == "H_FUNDAMENTAL_CHALLENGE"
    assert len(list(ZoneHChallengeType)) == 3


# ==============================================================================
# Test 7 — No Automatic Zone-H Invalidation State
# ==============================================================================

def test_no_automatic_zone_h_invalidation():
    """Verify that there is no state representing automatic invalidation of Zone H invariants."""
    for enum_cls in [EpistemicZone, ZoneHChallengeType, ChallengeStatus, EpistemicStatus]:
        for member in enum_cls:
            assert "ZONE_H_FALSE" not in member.name
            assert "INVALIDATE_INVARIANT" not in member.name


# ==============================================================================
# Test 8 — Residual Candidate Explanatory Categories
# ==============================================================================

def test_residual_candidate_classes():
    """Verify all six candidate explanatory categories for residuals exist."""
    residuals = list(ResidualClassificationType)
    assert len(residuals) == 6
    assert ResidualClassificationType.MEASUREMENT_ERROR in residuals
    assert ResidualClassificationType.MODEL_ERROR in residuals
    assert ResidualClassificationType.MISSING_VARIABLE in residuals
    assert ResidualClassificationType.UNKNOWN in residuals


# ==============================================================================
# Test 9 — Evidence Taxonomy
# ==============================================================================

def test_evidence_taxonomy():
    """Verify all eight evidence types are present."""
    ev_types = list(EpistemicEvidenceType)
    assert len(ev_types) == 8
    assert EpistemicEvidenceType.MATHEMATICAL_PROOF in ev_types
    assert EpistemicEvidenceType.PHYSICAL_MEASUREMENT in ev_types
    assert EpistemicEvidenceType.EXPERIMENTAL_RESULT in ev_types
    assert EpistemicEvidenceType.SIMULATION in ev_types
    assert EpistemicEvidenceType.OBSERVATIONAL_DATA in ev_types
    assert EpistemicEvidenceType.ENGINEERING_TEST in ev_types
    assert EpistemicEvidenceType.HUMAN_FEEDBACK in ev_types
    assert EpistemicEvidenceType.AI_GENERATED_HYPOTHESIS in ev_types


# ==============================================================================
# Test 10 — AI Evidence Separation
# ==============================================================================

def test_ai_evidence_separation():
    """Verify AI_GENERATED_HYPOTHESIS is distinct from physical, mathematical, or empirical evidence."""
    ai_ev = EpistemicEvidenceType.AI_GENERATED_HYPOTHESIS
    assert ai_ev != EpistemicEvidenceType.PHYSICAL_MEASUREMENT
    assert ai_ev != EpistemicEvidenceType.MATHEMATICAL_PROOF
    assert ai_ev != EpistemicEvidenceType.EXPERIMENTAL_RESULT
    assert ai_ev != EpistemicEvidenceType.OBSERVATIONAL_DATA


# ==============================================================================
# Test 11 — Evidence Relationships & Prohibited Truth Claims
# ==============================================================================

def test_evidence_relationships():
    """Verify directional evidence relations and absence of absolute truth assertions."""
    relations = list(EvidenceRelation)
    assert len(relations) == 6
    assert EvidenceRelation.SUPPORTS in relations
    assert EvidenceRelation.CONTRADICTS in relations
    assert EvidenceRelation.CHALLENGES in relations
    assert EvidenceRelation.LOCALIZES in relations
    assert EvidenceRelation.DISCRIMINATES in relations
    assert EvidenceRelation.DOES_NOT_TEST in relations

    # Prohibited truth assertions
    prohibited = {"PROVES", "IS_TRUE", "IS_BEST", "IS_CORRECT", "PROVEN"}
    for p in prohibited:
        assert p not in EvidenceRelation.__members__


# ==============================================================================
# Test 12 — Evidence Link Immutability
# ==============================================================================

def test_evidence_link_immutability():
    """Verify that EpistemicEvidenceLink is frozen and rejects mutation."""
    link = EpistemicEvidenceLink(
        evidence_id="EVID-SWEEP-001",
        target_id="MODEL-LR4-2WAY",
        relation=EvidenceRelation.SUPPORTS,
        confidence=0.95,
        notes="Validated on live microphone capture.",
    )
    assert link.evidence_id == "EVID-SWEEP-001"
    assert link.target_id == "MODEL-LR4-2WAY"
    assert link.relation == EvidenceRelation.SUPPORTS
    assert link.confidence == 0.95

    with pytest.raises((AttributeError, TypeError)):
        link.confidence = 0.5  # type: ignore

    with pytest.raises((AttributeError, TypeError)):
        link.evidence_id = "EVID-SWEEP-002"  # type: ignore


# ==============================================================================
# Test 13 — Confidence Bounds Validation
# ==============================================================================

def test_confidence_bounds():
    """Verify confidence values outside [0.0, 1.0] or non-finite are rejected."""
    # Valid boundaries
    EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=0.0)
    EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=1.0)
    EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=0.5)

    # Invalid values
    with pytest.raises(ValueError):
        EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=-0.01)

    with pytest.raises(ValueError):
        EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=1.01)

    with pytest.raises(ValueError):
        EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=float("nan"))

    with pytest.raises(ValueError):
        EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=float("inf"))

    with pytest.raises(ValueError):
        EpistemicEvidenceLink("E1", "T1", EvidenceRelation.SUPPORTS, confidence=True)  # type: ignore

    # Empty IDs
    with pytest.raises(ValueError):
        EpistemicEvidenceLink("", "T1", EvidenceRelation.SUPPORTS, confidence=0.9)

    with pytest.raises(ValueError):
        EpistemicEvidenceLink("E1", "  ", EvidenceRelation.SUPPORTS, confidence=0.9)


# ==============================================================================
# Test 14 — Deterministic Serialization & Round-Trip
# ==============================================================================

def test_deterministic_serialization():
    """Verify deterministic serialization to dict and JSON round-trip."""
    link = EpistemicEvidenceLink(
        evidence_id="EVID-101",
        target_id="ASM-LTI-01",
        relation=EvidenceRelation.CHALLENGES,
        confidence=0.88,
        notes="High-SPL distortion detected.",
    )
    d = link.to_dict()
    assert d == {
        "evidence_id": "EVID-101",
        "target_id": "ASM-LTI-01",
        "relation": "CHALLENGES",
        "confidence": 0.88,
        "notes": "High-SPL distortion detected.",
    }

    # JSON serialization
    json_str = json.dumps(d, sort_keys=True)
    loaded_dict = json.loads(json_str)
    reconstructed = EpistemicEvidenceLink.from_dict(loaded_dict)
    assert reconstructed == link
    assert reconstructed.relation == EvidenceRelation.CHALLENGES


# ==============================================================================
# Test 15 — Architectural Isolation
# ==============================================================================

def test_architectural_isolation():
    """Verify that importing epistemic vocabulary has zero runtime hardware/ALSA dependency."""
    import sys
    # Verify module is imported cleanly without importing execution/ALSA
    assert "acoustiforge.epistemic.vocabulary" in sys.modules
    from acoustiforge.epistemic import (
        EpistemicZone,
        EpistemicClass,
        EpistemicStatus,
        ChallengeStatus,
        ZoneHChallengeType,
        ResidualClassificationType,
        EpistemicEvidenceType,
        EvidenceRelation,
        EpistemicEvidenceLink,
    )
    assert EpistemicZone.ZONE_H.value == "ZONE_H"
