"""AcoustiForge Epistemic Model Registry Unit & Invariant Tests.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E3: Model Registry Implementation
"""

import json
import pytest

from acoustiforge.epistemic.models import (
    EpistemicModel,
    ModelRegistry,
)
from acoustiforge.epistemic.vocabulary import (
    EpistemicClass,
    EpistemicEvidenceType,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# Test 1 — Model Construction
# ==============================================================================

def test_model_construction():
    """Verify that a valid EpistemicModel can be constructed with canonical fields."""
    model = EpistemicModel(
        model_id="MODEL-LR4-2WAY",
        name="2-Way Linkwitz-Riley 4th-Order Acoustic Model",
        description="Classical 4th-order Linkwitz-Riley acoustic crossover summing model.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=("ASM-LTI-01", "ASM-MINPHASE-01", "ASM-LR4-SUM"),
        provenance="acoustiforge-core",
    )
    assert model.model_id == "MODEL-LR4-2WAY"
    assert model.name == "2-Way Linkwitz-Riley 4th-Order Acoustic Model"
    assert "crossover summing" in model.description
    assert model.epistemic_class == EpistemicClass.CONSTITUTIVE_MODEL
    assert model.zone == EpistemicZone.ZONE_M
    assert model.status == EpistemicStatus.VALIDATED_MODEL
    assert model.assumption_ids == ("ASM-LTI-01", "ASM-MINPHASE-01", "ASM-LR4-SUM")
    assert model.provenance == "acoustiforge-core"


# ==============================================================================
# Test 2 — Required Field Validation
# ==============================================================================

def test_required_field_validation():
    """Verify that empty/invalid IDs, names, descriptions, provenance, assumption IDs, and enums are rejected."""
    # Empty model_id
    with pytest.raises(ValueError, match="model_id"):
        EpistemicModel(
            model_id="",
            name="Valid Name",
            description="Valid Desc",
            epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids=(),
            provenance="core",
        )

    # Empty name
    with pytest.raises(ValueError, match="name"):
        EpistemicModel(
            model_id="MODEL-01",
            name="   ",
            description="Valid Desc",
            epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids=(),
            provenance="core",
        )

    # Empty description
    with pytest.raises(ValueError, match="description"):
        EpistemicModel(
            model_id="MODEL-01",
            name="Valid Name",
            description="",
            epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids=(),
            provenance="core",
        )

    # Empty provenance
    with pytest.raises(ValueError, match="provenance"):
        EpistemicModel(
            model_id="MODEL-01",
            name="Valid Name",
            description="Valid Desc",
            epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids=(),
            provenance="",
        )

    # Invalid assumption_ids type
    with pytest.raises(ValueError, match="assumption_ids"):
        EpistemicModel(
            model_id="MODEL-01",
            name="Valid Name",
            description="Valid Desc",
            epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids="ASM-01",  # type: ignore
            provenance="core",
        )

    # Invalid element in assumption_ids
    with pytest.raises(ValueError, match="assumption_ids"):
        EpistemicModel(
            model_id="MODEL-01",
            name="Valid Name",
            description="Valid Desc",
            epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids=("ASM-01", ""),
            provenance="core",
        )

    # Invalid enum string
    with pytest.raises(ValueError):
        EpistemicModel(
            model_id="MODEL-01",
            name="Valid Name",
            description="Valid Desc",
            epistemic_class="INVALID_CLASS",  # type: ignore
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            assumption_ids=(),
            provenance="core",
        )


# ==============================================================================
# Test 3 — E1 Vocabulary Reuse
# ==============================================================================

def test_vocabulary_reuse():
    """Verify that E3 directly reuses frozen E1 enums without parallel definitions."""
    model = EpistemicModel(
        model_id="MODEL-SPATIAL-WEIGHTED",
        name="Spatial Multi-Position Summing Model",
        description="Weighted multi-point acoustic response averaging model.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=("ASM-FARFIELD-01",),
        provenance="phase-5-track-c",
    )
    assert isinstance(model.epistemic_class, EpistemicClass)
    assert isinstance(model.zone, EpistemicZone)
    assert isinstance(model.status, EpistemicStatus)
    assert model.epistemic_class is EpistemicClass.CONSTITUTIVE_MODEL
    assert model.zone is EpistemicZone.ZONE_M


# ==============================================================================
# Test 4 — Zone / Class Separation
# ==============================================================================

def test_zone_class_separation():
    """Verify that Zone and EpistemicClass remain independent semantic dimensions for models."""
    # Approximation in Zone M
    m_appr = EpistemicModel(
        model_id="MODEL-LTI-APPROX",
        name="Small-Signal LTI Approximation Model",
        description="Treats transducer as linear time-invariant system.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=("ASM-LTI-01",),
        provenance="classical-acoustics",
    )
    assert m_appr.zone == EpistemicZone.ZONE_M
    assert m_appr.epistemic_class == EpistemicClass.APPROXIMATION
    assert m_appr.epistemic_class != EpistemicClass.PHYSICAL_INVARIANT

    # Objective assumption in Zone P
    m_obj = EpistemicModel(
        model_id="MODEL-FLAT-SPL-OBJ",
        name="Flat On-Axis Target SPL Quality Model",
        description="Treats flat on-axis frequency response as fidelity objective.",
        epistemic_class=EpistemicClass.OBJECTIVE_ASSUMPTION,
        zone=EpistemicZone.ZONE_P,
        status=EpistemicStatus.EPISTEMIC_ACCEPTED,
        assumption_ids=(),
        provenance="target-curve-intent",
    )
    assert m_obj.zone == EpistemicZone.ZONE_P
    assert m_obj.epistemic_class == EpistemicClass.OBJECTIVE_ASSUMPTION


# ==============================================================================
# Test 5 — Status Separation (Acceptance != Authority)
# ==============================================================================

def test_status_separation():
    """Verify that EPISTEMIC_ACCEPTED and PRODUCTION_CANDIDATE are distinct from PRODUCTION_AUTHORITY."""
    model_accepted = EpistemicModel(
        model_id="MODEL-NONLINEAR-VOLTERRA",
        name="Volterra Series 2nd-Order Nonlinear Driver Model",
        description="Models large-signal BL(x) magnetic flux modulation.",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.EPISTEMIC_ACCEPTED,
        assumption_ids=("ASM-VOLTERRA-01",),
        provenance="research-paper-2024",
    )
    assert model_accepted.status == EpistemicStatus.EPISTEMIC_ACCEPTED
    assert model_accepted.status != EpistemicStatus.PRODUCTION_AUTHORITY
    assert model_accepted.status != EpistemicStatus.PRODUCTION_CANDIDATE


# ==============================================================================
# Test 6 — Assumption Dependency Representation
# ==============================================================================

def test_assumption_dependency_representation():
    """Verify that declared assumption dependencies are preserved exactly as identifiers."""
    asms = ("ASM-NYQUIST-01", "ASM-STABILITY-01", "ASM-LR-01")
    model = EpistemicModel(
        model_id="MODEL-LR-CROSSOVER",
        name="Linkwitz-Riley Filter Model",
        description="Filter synthesis model.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
        assumption_ids=asms,
        provenance="core",
    )
    assert model.assumption_ids == asms
    assert len(model.assumption_ids) == 3
    assert "ASM-LR-01" in model.assumption_ids


# ==============================================================================
# Test 7 — Assumption Dependency Immutability
# ==============================================================================

def test_assumption_dependency_immutability():
    """Verify that the assumption_ids collection cannot be mutated through the model."""
    raw_list = ["ASM-01", "ASM-02"]
    model = EpistemicModel(
        model_id="MODEL-TEST",
        name="Test Model",
        description="Test Desc",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=raw_list,  # type: ignore
        provenance="test",
    )
    # Mutating raw_list must not affect model
    raw_list.append("ASM-03")
    assert model.assumption_ids == ("ASM-01", "ASM-02")
    assert isinstance(model.assumption_ids, tuple)


# ==============================================================================
# Test 8 — Provenance Semantics
# ==============================================================================

def test_provenance_semantics():
    """Verify provenance is retained as descriptive metadata and does not acquire evidence semantics."""
    model = EpistemicModel(
        model_id="MODEL-PROV",
        name="Literature Model",
        description="Model from academic literature.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="aes-convention-paper-8821",
    )
    assert model.provenance == "aes-convention-paper-8821"
    assert not isinstance(model.provenance, EpistemicEvidenceType)


# ==============================================================================
# Test 9 — AI Model Separation
# ==============================================================================

def test_ai_model_separation():
    """Verify that an AI-generated model remains a model and cannot become evidence or production authority."""
    model_ai = EpistemicModel(
        model_id="MODEL-AI-ACOUSTIC-PROPOSAL",
        name="AI Proposed Modal Damping Model",
        description="Heuristic cavity damping model generated by LLM.",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=("ASM-MODAL-DAMP-01",),
        provenance="ai-generated",
    )
    assert model_ai.provenance == "ai-generated"
    assert model_ai.status == EpistemicStatus.HYPOTHESIS
    assert model_ai.status != EpistemicStatus.PRODUCTION_AUTHORITY
    assert model_ai.epistemic_class != EpistemicClass.PHYSICAL_INVARIANT


# ==============================================================================
# Test 10 — Immutability
# ==============================================================================

def test_model_immutability():
    """Verify that EpistemicModel instances reject attribute reassignment."""
    model = EpistemicModel(
        model_id="MODEL-IMMUTABLE",
        name="Immutable Model",
        description="Immutable Description",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=(),
        provenance="test",
    )
    with pytest.raises((AttributeError, TypeError)):
        model.name = "Modified Name"  # type: ignore

    with pytest.raises((AttributeError, TypeError)):
        model.status = EpistemicStatus.PRODUCTION_AUTHORITY  # type: ignore


# ==============================================================================
# Test 11 — Serialization Behavior
# ==============================================================================

def test_deterministic_serialization():
    """Verify deterministic conversion to dict."""
    model = EpistemicModel(
        model_id="MODEL-SERIAL",
        name="Serialization Test Model",
        description="Testing dictionary serialization.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=("ASM-01", "ASM-02"),
        provenance="unit-test",
    )
    d = model.to_dict()
    assert d == {
        "model_id": "MODEL-SERIAL",
        "name": "Serialization Test Model",
        "description": "Testing dictionary serialization.",
        "epistemic_class": "CONSTITUTIVE_MODEL",
        "zone": "ZONE_M",
        "status": "VALIDATED_MODEL",
        "assumption_ids": ["ASM-01", "ASM-02"],
        "provenance": "unit-test",
    }


# ==============================================================================
# Test 12 — JSON Round-Trip Losslessness
# ==============================================================================

def test_json_round_trip():
    """Verify that EpistemicModel supports lossless JSON round-trip reconstruction."""
    model = EpistemicModel(
        model_id="MODEL-JSON-RT",
        name="JSON Round Trip Model",
        description="Verifying JSON round trip.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.TESTED_CANDIDATE,
        assumption_ids=("ASM-A", "ASM-B"),
        provenance="json-test",
    )
    json_str = json.dumps(model.to_dict(), sort_keys=True)
    loaded_dict = json.loads(json_str)
    reconstructed = EpistemicModel.from_dict(loaded_dict)
    assert reconstructed == model
    assert reconstructed.model_id == model.model_id
    assert reconstructed.assumption_ids == ("ASM-A", "ASM-B")
    assert reconstructed.epistemic_class is EpistemicClass.APPROXIMATION


# ==============================================================================
# Test 13 — Registry Registration & Retrieval
# ==============================================================================

def test_registry_registration_and_retrieval():
    """Verify that valid models can be registered and retrieved by ID."""
    registry = ModelRegistry()
    assert len(registry) == 0

    model = EpistemicModel(
        model_id="MODEL-REG-01",
        name="Registered Model 1",
        description="First model in registry.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="core",
    )
    registry.register(model)
    assert len(registry) == 1
    assert registry.contains("MODEL-REG-01")
    assert "MODEL-REG-01" in registry
    assert registry.get("MODEL-REG-01") == model

    # Missing ID raises KeyError
    with pytest.raises(KeyError, match="not found"):
        registry.get("MODEL-NONEXISTENT")


# ==============================================================================
# Test 14 — Duplicate Protection
# ==============================================================================

def test_registry_duplicate_protection():
    """Verify that attempting to register duplicate model IDs raises ValueError without silent overwrite."""
    registry = ModelRegistry()
    model1 = EpistemicModel(
        model_id="MODEL-DUP",
        name="Initial Model Registration",
        description="First registration.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=(),
        provenance="source-1",
    )
    model2 = EpistemicModel(
        model_id="MODEL-DUP",
        name="Second Model Registration",
        description="Second registration with different name.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="source-2",
    )
    registry.register(model1)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(model2)

    assert registry.get("MODEL-DUP").name == "Initial Model Registration"
    assert len(registry) == 1


# ==============================================================================
# Test 15 — Deterministic Enumeration & Ordering
# ==============================================================================

def test_registry_deterministic_enumeration():
    """Verify all() and iteration order match deterministic registration sequence."""
    registry = ModelRegistry()
    m1 = EpistemicModel(
        model_id="MODEL-01",
        name="Model 1",
        description="Desc 1",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="p1",
    )
    m2 = EpistemicModel(
        model_id="MODEL-02",
        name="Model 2",
        description="Desc 2",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=(),
        provenance="p2",
    )
    registry.register(m1)
    registry.register(m2)

    assert len(registry) == 2
    all_models = registry.all()
    assert len(all_models) == 2
    assert all_models[0].model_id == "MODEL-01"
    assert all_models[1].model_id == "MODEL-02"

    iterated = [m.model_id for m in registry]
    assert iterated == ["MODEL-01", "MODEL-02"]


# ==============================================================================
# Test 16 — Registry Filtering
# ==============================================================================

def test_registry_filtering():
    """Verify query() filters by zone, epistemic_class, and status without mutating registered models."""
    registry = ModelRegistry()
    m_m_val = EpistemicModel(
        model_id="M-1",
        name="Model 1",
        description="Desc",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="p",
    )
    m_m_hyp = EpistemicModel(
        model_id="M-2",
        name="Model 2",
        description="Desc",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=(),
        provenance="p",
    )
    m_p_val = EpistemicModel(
        model_id="M-3",
        name="Model 3",
        description="Desc",
        epistemic_class=EpistemicClass.OBJECTIVE_ASSUMPTION,
        zone=EpistemicZone.ZONE_P,
        status=EpistemicStatus.VALIDATED_MODEL,
        assumption_ids=(),
        provenance="p",
    )

    registry.register(m_m_val)
    registry.register(m_m_hyp)
    registry.register(m_p_val)

    # Filter by zone
    zone_p = registry.query(zone=EpistemicZone.ZONE_P)
    assert len(zone_p) == 1
    assert zone_p[0].model_id == "M-3"

    # Filter by class
    appr = registry.query(epistemic_class=EpistemicClass.APPROXIMATION)
    assert len(appr) == 1
    assert appr[0].model_id == "M-2"

    # Filter by status
    hyp = registry.query(status=EpistemicStatus.HYPOTHESIS)
    assert len(hyp) == 1
    assert hyp[0].model_id == "M-2"


# ==============================================================================
# Test 17 — Independent Import & Zero Core Initialization
# ==============================================================================

def test_independent_import():
    """Verify that importing ModelRegistry has zero runtime hardware or Core initialization requirement."""
    from acoustiforge.epistemic import (
        EpistemicModel,
        ModelRegistry,
    )
    reg = ModelRegistry()
    assert len(reg) == 0


# ==============================================================================
# Test 18 — No Implicit Validation upon Registration
# ==============================================================================

def test_no_implicit_validation():
    """Verify that registering a model does not change its status from HYPOTHESIS to VALIDATED_MODEL."""
    registry = ModelRegistry()
    m_hyp = EpistemicModel(
        model_id="MODEL-UNTESTED-HYPOTHESIS",
        name="Untested Hypothesis Model",
        description="A newly proposed candidate model.",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        assumption_ids=(),
        provenance="ai-proposal",
    )
    registry.register(m_hyp)
    retrieved = registry.get("MODEL-UNTESTED-HYPOTHESIS")
    assert retrieved.status == EpistemicStatus.HYPOTHESIS
    assert retrieved.status != EpistemicStatus.VALIDATED_MODEL
    assert retrieved.status != EpistemicStatus.PRODUCTION_AUTHORITY
