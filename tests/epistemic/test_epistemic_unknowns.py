"""AcoustiForge Epistemic Unknown Value Object and Registry Tests.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E4: Unknown and Residual Representation
"""

import json
import pytest

from acoustiforge.epistemic.unknowns import (
    EpistemicUnknown,
    UnknownRegistry,
)
from acoustiforge.epistemic.vocabulary import (
    EpistemicEvidenceType,
    EpistemicStatus,
)


# ==============================================================================
# Test 1 — Unknown Construction
# ==============================================================================

def test_unknown_construction():
    """Verify that a valid EpistemicUnknown can be constructed with canonical fields."""
    unk = EpistemicUnknown(
        unknown_id="UNK-RESONANCE-350HZ",
        statement="Unexplained narrow-band acoustic notch observed at 350 Hz in physical measurement.",
        scope={"frequency_hz": [300.0, 400.0], "microphone_position": "spatial-pos-1"},
        provenance="physical-measurement-lab",
        status=EpistemicStatus.HYPOTHESIS,
    )
    assert unk.unknown_id == "UNK-RESONANCE-350HZ"
    assert "350 Hz" in unk.statement
    assert unk.scope["frequency_hz"] == [300.0, 400.0]
    assert unk.provenance == "physical-measurement-lab"
    assert unk.status == EpistemicStatus.HYPOTHESIS


# ==============================================================================
# Test 2 — Required Field Validation
# ==============================================================================

def test_required_field_validation():
    """Verify that empty/invalid IDs, statements, provenance, scope, and status are rejected."""
    # Empty unknown_id
    with pytest.raises(ValueError, match="unknown_id"):
        EpistemicUnknown(
            unknown_id="",
            statement="Valid statement",
            scope={},
            provenance="lab",
        )

    # Empty statement
    with pytest.raises(ValueError, match="statement"):
        EpistemicUnknown(
            unknown_id="UNK-01",
            statement="   ",
            scope={},
            provenance="lab",
        )

    # Empty provenance
    with pytest.raises(ValueError, match="provenance"):
        EpistemicUnknown(
            unknown_id="UNK-01",
            statement="Valid statement",
            scope={},
            provenance="",
        )

    # Invalid scope type
    with pytest.raises(ValueError, match="scope"):
        EpistemicUnknown(
            unknown_id="UNK-01",
            statement="Valid statement",
            scope="invalid-scope",  # type: ignore
            provenance="lab",
        )

    # Invalid status
    with pytest.raises(ValueError):
        EpistemicUnknown(
            unknown_id="UNK-01",
            statement="Valid statement",
            scope={},
            provenance="lab",
            status="INVALID_STATUS",  # type: ignore
        )


# ==============================================================================
# Test 3 — E1 Vocabulary Reuse
# ==============================================================================

def test_vocabulary_reuse():
    """Verify that EpistemicUnknown reuses frozen EpistemicStatus enum."""
    unk = EpistemicUnknown(
        unknown_id="UNK-01",
        statement="Unknown physical mechanism in driver suspension.",
        scope={},
        provenance="measurement",
        status=EpistemicStatus.UNDER_REVIEW,
    )
    assert isinstance(unk.status, EpistemicStatus)
    assert unk.status is EpistemicStatus.UNDER_REVIEW


# ==============================================================================
# Test 4 — UNKNOWN Semantics (Unknown != Invalid / Model Error / Falsified)
# ==============================================================================

def test_unknown_semantics():
    """Verify that an UNKNOWN state does not imply invalidity, falsehood, or model failure."""
    unk = EpistemicUnknown(
        unknown_id="UNK-SURROUND-MODES",
        statement="Acoustic radiation dip above 8 kHz without known structural explanation.",
        scope={"frequency_hz": [8000.0, 12000.0]},
        provenance="laser-scan",
        status=EpistemicStatus.HYPOTHESIS,
    )
    # Status remains an open hypothesis / under-investigation entity
    assert unk.status == EpistemicStatus.HYPOTHESIS
    assert unk.status != EpistemicStatus.FALSIFIED
    assert unk.status != EpistemicStatus.PRODUCTION_AUTHORITY


# ==============================================================================
# Test 5 — Scope Preservation
# ==============================================================================

def test_scope_preservation():
    """Verify scope remains descriptive and survives dict conversion without data corruption."""
    scope_data = {"operating_spl": 90.0, "ambient_temp_c": 22.5}
    unk = EpistemicUnknown(
        unknown_id="UNK-TEMP-DRIFT",
        statement="High-frequency attenuation under thermal heating.",
        scope=scope_data,
        provenance="stress-test",
    )
    assert unk.scope["ambient_temp_c"] == 22.5
    d = unk.to_dict()
    assert d["scope"]["operating_spl"] == 90.0


# ==============================================================================
# Test 6 — Provenance Separation
# ==============================================================================

def test_provenance_separation():
    """Verify provenance remains descriptive provenance and does not become evidence."""
    unk = EpistemicUnknown(
        unknown_id="UNK-MEAS-01",
        statement="Room corner boundary reflection cancellation.",
        scope={},
        provenance="in-situ-measurement",
    )
    assert unk.provenance == "in-situ-measurement"
    assert not isinstance(unk.provenance, EpistemicEvidenceType)


# ==============================================================================
# Test 7 — Immutability
# ==============================================================================

def test_unknown_immutability():
    """Verify that EpistemicUnknown rejects attribute reassignment."""
    unk = EpistemicUnknown(
        unknown_id="UNK-IMMUTABLE",
        statement="Immutable unknown",
        scope={},
        provenance="test",
    )
    with pytest.raises((AttributeError, TypeError)):
        unk.statement = "Modified statement"  # type: ignore

    with pytest.raises((AttributeError, TypeError)):
        unk.status = EpistemicStatus.PRODUCTION_AUTHORITY  # type: ignore


# ==============================================================================
# Test 8 — Deterministic Serialization
# ==============================================================================

def test_deterministic_serialization():
    """Verify deterministic conversion to dict."""
    unk = EpistemicUnknown(
        unknown_id="UNK-SERIAL",
        statement="Serialization test unknown",
        scope={"band": "low-frequency"},
        provenance="unit-test",
        status=EpistemicStatus.HYPOTHESIS,
    )
    d = unk.to_dict()
    assert d == {
        "unknown_id": "UNK-SERIAL",
        "statement": "Serialization test unknown",
        "scope": {"band": "low-frequency"},
        "provenance": "unit-test",
        "status": "HYPOTHESIS",
    }


# ==============================================================================
# Test 9 — JSON Round-Trip Losslessness
# ==============================================================================

def test_json_round_trip():
    """Verify that EpistemicUnknown supports lossless JSON round-trip reconstruction."""
    unk = EpistemicUnknown(
        unknown_id="UNK-JSON-RT",
        statement="JSON round trip unknown",
        scope={"axis": "off-axis-30deg"},
        provenance="measurement-run-5",
        status=EpistemicStatus.UNDER_REVIEW,
    )
    json_str = json.dumps(unk.to_dict(), sort_keys=True)
    loaded_dict = json.loads(json_str)
    reconstructed = EpistemicUnknown.from_dict(loaded_dict)
    assert reconstructed == unk
    assert reconstructed.unknown_id == unk.unknown_id
    assert reconstructed.status is EpistemicStatus.UNDER_REVIEW


# ==============================================================================
# Test 10 — Independent Import & Registry Functionality
# ==============================================================================

def test_unknown_registry_and_independent_import():
    """Verify UnknownRegistry operates deterministically with zero Core/hardware dependency."""
    from acoustiforge.epistemic import (
        EpistemicUnknown,
        UnknownRegistry,
    )
    registry = UnknownRegistry()
    assert len(registry) == 0

    unk1 = EpistemicUnknown(
        unknown_id="UNK-01",
        statement="Unknown 1",
        scope={},
        provenance="p1",
        status=EpistemicStatus.HYPOTHESIS,
    )
    unk2 = EpistemicUnknown(
        unknown_id="UNK-02",
        statement="Unknown 2",
        scope={},
        provenance="p2",
        status=EpistemicStatus.UNDER_REVIEW,
    )

    registry.register(unk1)
    registry.register(unk2)
    assert len(registry) == 2
    assert registry.get("UNK-01") == unk1
    assert registry.contains("UNK-02")
    assert "UNK-01" in registry

    # Duplicate rejection
    with pytest.raises(ValueError, match="already registered"):
        registry.register(unk1)

    # Missing ID
    with pytest.raises(KeyError, match="not found"):
        registry.get("UNK-NONEXISTENT")

    # Deterministic enumeration
    all_unks = registry.all()
    assert len(all_unks) == 2
    assert all_unks[0].unknown_id == "UNK-01"
    assert all_unks[1].unknown_id == "UNK-02"

    # Query filtering
    under_rev = registry.query(status=EpistemicStatus.UNDER_REVIEW)
    assert len(under_rev) == 1
    assert under_rev[0].unknown_id == "UNK-02"
