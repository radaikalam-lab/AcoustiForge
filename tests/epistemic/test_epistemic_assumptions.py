"""AcoustiForge Epistemic Assumption Registry Unit & Invariant Tests.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E2: Assumption Registry Implementation
"""

import json
import pytest

from acoustiforge.epistemic.assumptions import (
    AssumptionRegistry,
    EpistemicAssumption,
)
from acoustiforge.epistemic.vocabulary import (
    EpistemicClass,
    EpistemicEvidenceType,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# Test 1 — Assumption Construction
# ==============================================================================

def test_assumption_construction():
    """Verify that a valid EpistemicAssumption can be constructed with canonical fields."""
    asm = EpistemicAssumption(
        assumption_id="ASM-LTI-01",
        statement="Loudspeaker transducer operates as a linear time-invariant system within small-signal regime.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        scope={"spl_db_max": 85.0, "frequency_hz": [20.0, 20000.0]},
        provenance="engineering-acoustics-literature",
    )
    assert asm.assumption_id == "ASM-LTI-01"
    assert "linear time-invariant" in asm.statement
    assert asm.epistemic_class == EpistemicClass.APPROXIMATION
    assert asm.zone == EpistemicZone.ZONE_M
    assert asm.status == EpistemicStatus.VALIDATED_MODEL
    assert asm.scope == {"spl_db_max": 85.0, "frequency_hz": [20.0, 20000.0]}
    assert asm.provenance == "engineering-acoustics-literature"


# ==============================================================================
# Test 2 — Required Field Validation
# ==============================================================================

def test_required_field_validation():
    """Verify that empty/invalid IDs, statements, provenance, scope, and enums are rejected."""
    # Empty assumption_id
    with pytest.raises(ValueError, match="assumption_id"):
        EpistemicAssumption(
            assumption_id="",
            statement="Valid statement",
            epistemic_class=EpistemicClass.APPROXIMATION,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            scope={},
            provenance="core",
        )

    # Empty statement
    with pytest.raises(ValueError, match="statement"):
        EpistemicAssumption(
            assumption_id="ASM-01",
            statement="   ",
            epistemic_class=EpistemicClass.APPROXIMATION,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            scope={},
            provenance="core",
        )

    # Empty provenance
    with pytest.raises(ValueError, match="provenance"):
        EpistemicAssumption(
            assumption_id="ASM-01",
            statement="Valid statement",
            epistemic_class=EpistemicClass.APPROXIMATION,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            scope={},
            provenance="",
        )

    # Invalid scope type
    with pytest.raises(ValueError, match="scope"):
        EpistemicAssumption(
            assumption_id="ASM-01",
            statement="Valid statement",
            epistemic_class=EpistemicClass.APPROXIMATION,
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            scope=[20, 20000],  # type: ignore
            provenance="core",
        )

    # Invalid enum string
    with pytest.raises(ValueError):
        EpistemicAssumption(
            assumption_id="ASM-01",
            statement="Valid statement",
            epistemic_class="INVALID_CLASS",  # type: ignore
            zone=EpistemicZone.ZONE_M,
            status=EpistemicStatus.HYPOTHESIS,
            scope={},
            provenance="core",
        )


# ==============================================================================
# Test 3 — E1 Vocabulary Reuse
# ==============================================================================

def test_vocabulary_reuse():
    """Verify that E2 directly reuses frozen E1 enums without parallel definitions."""
    asm = EpistemicAssumption(
        assumption_id="ASM-NYQUIST-01",
        statement="Sampling frequency is strictly greater than twice the highest signal frequency component.",
        epistemic_class=EpistemicClass.MATHEMATICAL_THEOREM,
        zone=EpistemicZone.ZONE_H,
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
        scope={"sampling_regime": "discrete-time", "bandlimited": True},
        provenance="Nyquist-Shannon-Theorem-1949",
    )
    assert isinstance(asm.epistemic_class, EpistemicClass)
    assert isinstance(asm.zone, EpistemicZone)
    assert isinstance(asm.status, EpistemicStatus)
    assert asm.epistemic_class is EpistemicClass.MATHEMATICAL_THEOREM
    assert asm.zone is EpistemicZone.ZONE_H


# ==============================================================================
# Test 4 — Zone / Class Separation
# ==============================================================================

def test_zone_class_separation():
    """Verify that Zone and EpistemicClass remain independent semantic dimensions."""
    # Engineering heuristic in Zone H
    asm_heur = EpistemicAssumption(
        assumption_id="ASM-HEUR-3WAY",
        statement="3-way crossover upper frequency should be at least 1.5x the lower frequency.",
        epistemic_class=EpistemicClass.ENGINEERING_HEURISTIC,
        zone=EpistemicZone.ZONE_H,
        status=EpistemicStatus.VALIDATED_MODEL,
        scope={"crossover_order": [2, 4, 8]},
        provenance="engineering-guideline",
    )
    assert asm_heur.zone == EpistemicZone.ZONE_H
    assert asm_heur.epistemic_class == EpistemicClass.ENGINEERING_HEURISTIC
    assert asm_heur.epistemic_class != EpistemicClass.PHYSICAL_INVARIANT

    # Constitutive model in Zone M
    asm_model = EpistemicAssumption(
        assumption_id="ASM-LR4-SUM",
        statement="4th-order Linkwitz-Riley crossover produces flat acoustic magnitude summing under ideal acoustic alignment.",
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        scope={"filter_order": 4},
        provenance="Linkwitz-Riley-1976",
    )
    assert asm_model.zone == EpistemicZone.ZONE_M
    assert asm_model.epistemic_class == EpistemicClass.CONSTITUTIVE_MODEL


# ==============================================================================
# Test 5 — Status Separation (Acceptance != Authority)
# ==============================================================================

def test_status_separation():
    """Verify that EPISTEMIC_ACCEPTED is distinct from PRODUCTION_AUTHORITY."""
    asm_accepted = EpistemicAssumption(
        assumption_id="ASM-EXP-01",
        statement="High-frequency dome tweeter exhibits continuous piston motion below 18 kHz.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.EPISTEMIC_ACCEPTED,
        scope={"frequency_hz": [2000.0, 18000.0]},
        provenance="laser-vibrometry-study",
    )
    assert asm_accepted.status == EpistemicStatus.EPISTEMIC_ACCEPTED
    assert asm_accepted.status != EpistemicStatus.PRODUCTION_AUTHORITY
    assert asm_accepted.status != EpistemicStatus.PRODUCTION_CANDIDATE


# ==============================================================================
# Test 6 — Scope Semantics
# ==============================================================================

def test_scope_semantics():
    """Verify that scope is descriptive metadata and preserved faithfully without mutating data."""
    raw_scope = {
        "frequency_range_hz": (20.0, 20000.0),
        "temperature_celsius": (15.0, 30.0),
        "regime": "far-field-anechoic",
    }
    asm = EpistemicAssumption(
        assumption_id="ASM-FARFIELD-01",
        statement="Sound propagation obeys inverse-square spherical wave spreading.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        scope=raw_scope,
        provenance="standard-acoustics",
    )
    assert asm.scope["regime"] == "far-field-anechoic"
    assert asm.scope["frequency_range_hz"] == (20.0, 20000.0)


# ==============================================================================
# Test 7 — Provenance Semantics
# ==============================================================================

def test_provenance_semantics():
    """Verify provenance is retained and does not acquire evidence semantics."""
    asm = EpistemicAssumption(
        assumption_id="ASM-PROV-01",
        statement="Transducer voice-coil resistance Re remains constant across short signal bursts.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        scope={"burst_duration_seconds": 0.5},
        provenance="measurement-program-lab-bench",
    )
    assert asm.provenance == "measurement-program-lab-bench"
    # Ensure provenance is purely descriptive and not conflated with evidence types
    assert not isinstance(asm.provenance, EpistemicEvidenceType)


# ==============================================================================
# Test 8 — Immutability
# ==============================================================================

def test_assumption_immutability():
    """Verify that EpistemicAssumption instances reject attribute reassignment."""
    asm = EpistemicAssumption(
        assumption_id="ASM-IMMUTABLE",
        statement="Immutable statement",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        scope={},
        provenance="test",
    )
    with pytest.raises((AttributeError, TypeError)):
        asm.statement = "Modified statement"  # type: ignore

    with pytest.raises((AttributeError, TypeError)):
        asm.status = EpistemicStatus.PRODUCTION_AUTHORITY  # type: ignore


# ==============================================================================
# Test 9 — Deterministic Serialization & Round-Trip
# ==============================================================================

def test_deterministic_serialization():
    """Verify deterministic conversion to dict, JSON, and round-trip reconstruction."""
    asm = EpistemicAssumption(
        assumption_id="ASM-MINPHASE-01",
        statement="Transducer acoustic transfer function exhibits minimum-phase characteristics.",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        scope={"frequency_hz": [50.0, 15000.0], "measurement": "on-axis-gated"},
        provenance="hilbert-transform-theory",
    )
    data = asm.to_dict()
    assert data["assumption_id"] == "ASM-MINPHASE-01"
    assert data["epistemic_class"] == "APPROXIMATION"
    assert data["zone"] == "ZONE_M"
    assert data["status"] == "VALIDATED_MODEL"

    # JSON round-trip
    json_str = json.dumps(data, sort_keys=True)
    loaded_data = json.loads(json_str)
    reconstructed = EpistemicAssumption.from_dict(loaded_data)
    assert reconstructed == asm
    assert reconstructed.assumption_id == asm.assumption_id
    assert reconstructed.epistemic_class is EpistemicClass.APPROXIMATION


# ==============================================================================
# Test 10 — Registry Registration & Retrieval
# ==============================================================================

def test_registry_registration_and_retrieval():
    """Verify that valid assumptions can be registered and retrieved by ID."""
    registry = AssumptionRegistry()
    assert len(registry) == 0

    asm = EpistemicAssumption(
        assumption_id="ASM-01",
        statement="Statement 1",
        epistemic_class=EpistemicClass.PHYSICAL_INVARIANT,
        zone=EpistemicZone.ZONE_H,
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
        scope={},
        provenance="physics",
    )
    registry.register(asm)
    assert len(registry) == 1
    assert registry.contains("ASM-01")
    assert "ASM-01" in registry
    assert registry.get("ASM-01") == asm

    # Missing ID raises KeyError
    with pytest.raises(KeyError, match="not found"):
        registry.get("ASM-NONEXISTENT")


# ==============================================================================
# Test 11 — Duplicate Protection
# ==============================================================================

def test_registry_duplicate_protection():
    """Verify that attempting to register duplicate assumption IDs raises ValueError."""
    registry = AssumptionRegistry()
    asm1 = EpistemicAssumption(
        assumption_id="ASM-DUP",
        statement="First registration",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        scope={},
        provenance="source-1",
    )
    asm2 = EpistemicAssumption(
        assumption_id="ASM-DUP",
        statement="Second registration with different statement",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.VALIDATED_MODEL,
        scope={},
        provenance="source-2",
    )
    registry.register(asm1)

    # Duplicate must raise ValueError and not overwrite asm1
    with pytest.raises(ValueError, match="already registered"):
        registry.register(asm2)

    assert registry.get("ASM-DUP").statement == "First registration"
    assert len(registry) == 1


# ==============================================================================
# Test 12 — Deterministic Enumeration & Querying
# ==============================================================================

def test_registry_deterministic_enumeration_and_querying():
    """Verify all(), __iter__, and query() preserve deterministic order and filtering."""
    registry = AssumptionRegistry()
    asm_h = EpistemicAssumption(
        assumption_id="ASM-H1",
        statement="Invariant H1",
        epistemic_class=EpistemicClass.PHYSICAL_INVARIANT,
        zone=EpistemicZone.ZONE_H,
        status=EpistemicStatus.PRODUCTION_AUTHORITY,
        scope={},
        provenance="physics",
    )
    asm_m = EpistemicAssumption(
        assumption_id="ASM-M1",
        statement="Model M1",
        epistemic_class=EpistemicClass.APPROXIMATION,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        scope={},
        provenance="hypothesis",
    )
    asm_p = EpistemicAssumption(
        assumption_id="ASM-P1",
        statement="Problem P1",
        epistemic_class=EpistemicClass.OBJECTIVE_ASSUMPTION,
        zone=EpistemicZone.ZONE_P,
        status=EpistemicStatus.EPISTEMIC_ACCEPTED,
        scope={},
        provenance="intent",
    )

    registry.register(asm_h)
    registry.register(asm_m)
    registry.register(asm_p)

    assert len(registry) == 3
    all_asms = registry.all()
    assert len(all_asms) == 3
    assert all_asms[0].assumption_id == "ASM-H1"
    assert all_asms[1].assumption_id == "ASM-M1"
    assert all_asms[2].assumption_id == "ASM-P1"

    # Query by zone
    h_only = registry.query(zone=EpistemicZone.ZONE_H)
    assert len(h_only) == 1
    assert h_only[0].assumption_id == "ASM-H1"

    # Query by epistemic class
    appr_only = registry.query(epistemic_class=EpistemicClass.APPROXIMATION)
    assert len(appr_only) == 1
    assert appr_only[0].assumption_id == "ASM-M1"

    # Query by status
    accepted_only = registry.query(status=EpistemicStatus.EPISTEMIC_ACCEPTED)
    assert len(accepted_only) == 1
    assert accepted_only[0].assumption_id == "ASM-P1"


# ==============================================================================
# Test 13 — Independent Import & Zero Core Initialization
# ==============================================================================

def test_independent_import():
    """Verify that importing AssumptionRegistry has zero runtime hardware or Core initialization requirement."""
    from acoustiforge.epistemic import (
        AssumptionRegistry,
        EpistemicAssumption,
    )
    reg = AssumptionRegistry()
    assert len(reg) == 0


# ==============================================================================
# Test 14 — AI Provenance Separation
# ==============================================================================

def test_ai_provenance_separation():
    """Verify that an assumption with AI provenance remains an assumption and cannot become evidence or authority."""
    asm_ai = EpistemicAssumption(
        assumption_id="ASM-AI-PROPOSAL-01",
        statement="Acoustic radiation efficiency decreases nonlinearly above 10 kHz due to surround decoupling.",
        epistemic_class=EpistemicClass.HYPOTHESIS,
        zone=EpistemicZone.ZONE_M,
        status=EpistemicStatus.HYPOTHESIS,
        scope={"frequency_hz": [10000.0, 20000.0]},
        provenance="ai-generated",
    )
    assert asm_ai.provenance == "ai-generated"
    assert asm_ai.status == EpistemicStatus.HYPOTHESIS
    assert asm_ai.status != EpistemicStatus.PRODUCTION_AUTHORITY
    assert asm_ai.epistemic_class != EpistemicClass.PHYSICAL_INVARIANT
