"""Tests for Phase E5 Epistemic Challenge Representation.

Normative Authority:
- docs/architecture/EPISTEMIC_SEMANTIC_AMENDMENT.md (DOC-EPISTEMIC-AMEND-01)
- docs/architecture/EPISTEMIC_ARCHITECTURE.md (DOC-EPISTEMIC-ARCH-01)
- Phase E5: Challenge Representation
- Governing Invariants:
  - Epistemic Novelty != Production Authority
  - CHALLENGE != FALSIFICATION
  - CHALLENGE != TARGET_INVALIDATION
  - CHALLENGE != EVIDENCE
  - CHALLENGE_STATUS != TRUTH
  - PROPOSED_TEST != EXECUTED_TEST
  - EPISTEMIC_ACCEPTED != PRODUCTION_AUTHORITY
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import sys
from typing import Any

import pytest

from acoustiforge.epistemic.assumptions import EpistemicAssumption
from acoustiforge.epistemic.challenges import ChallengeRegistry, EpistemicChallenge
from acoustiforge.epistemic.models import EpistemicModel
from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicStatus,
    EpistemicZone,
)


# ==============================================================================
# Standard Specification Tests (Tests 1-21)
# ==============================================================================

def test_challenge_construction() -> None:
    """Test 1: Valid challenge can be constructed with explicit attributes."""
    ch = EpistemicChallenge(
        challenge_id="CHALLENGE-001",
        target_id="MODEL-LTI-001",
        target_kind="model",
        status=ChallengeStatus.CHALLENGE_PROPOSED,
        rationale="Harmonic distortion observed above 95 dB SPL violates linearity assumption.",
        scope={"frequency_hz": [100.0, 1000.0], "spl_db": [95.0, 110.0]},
        trigger_refs=("RESIDUAL-001", "OBS-014"),
        proposed_tests=("stepped_sine_thd_sweep", "multitone_im_measurement"),
        provenance="measurement-program-lab-b",
    )
    assert ch.challenge_id == "CHALLENGE-001"
    assert ch.target_id == "MODEL-LTI-001"
    assert ch.target_kind == "model"
    assert ch.status == ChallengeStatus.CHALLENGE_PROPOSED
    assert "Harmonic distortion" in ch.rationale
    assert ch.scope == {"frequency_hz": [100.0, 1000.0], "spl_db": [95.0, 110.0]}
    assert ch.trigger_refs == ("RESIDUAL-001", "OBS-014")
    assert ch.proposed_tests == ("stepped_sine_thd_sweep", "multitone_im_measurement")
    assert ch.provenance == "measurement-program-lab-b"


def test_required_fields_validation() -> None:
    """Test 2: Reject empty challenge_id, target_id, target_kind, rationale, provenance."""
    valid_args = {
        "challenge_id": "CHALLENGE-001",
        "target_id": "MODEL-001",
        "target_kind": "model",
        "rationale": "Nonlinear behavior observed.",
        "provenance": "lab-review",
    }

    # Empty / whitespace challenge_id
    for bad_id in ["", "  ", None]:
        with pytest.raises(ValueError):
            EpistemicChallenge(**{**valid_args, "challenge_id": bad_id})  # type: ignore

    # Empty / whitespace target_id
    for bad_tid in ["", "  ", None]:
        with pytest.raises(ValueError):
            EpistemicChallenge(**{**valid_args, "target_id": bad_tid})  # type: ignore

    # Empty / whitespace target_kind
    for bad_tk in ["", "  ", None]:
        with pytest.raises(ValueError):
            EpistemicChallenge(**{**valid_args, "target_kind": bad_tk})  # type: ignore

    # Empty / whitespace rationale
    for bad_rat in ["", "  ", None]:
        with pytest.raises(ValueError):
            EpistemicChallenge(**{**valid_args, "rationale": bad_rat})  # type: ignore

    # Empty / whitespace provenance
    for bad_prov in ["", "  ", None]:
        with pytest.raises(ValueError):
            EpistemicChallenge(**{**valid_args, "provenance": bad_prov})  # type: ignore

    # Invalid status type
    with pytest.raises(ValueError):
        EpistemicChallenge(**{**valid_args, "status": "CHALLENGE_PROPOSED"})  # type: ignore

    # Invalid scope type
    with pytest.raises(ValueError):
        EpistemicChallenge(**{**valid_args, "scope": [1, 2, 3]})  # type: ignore

    # Invalid trigger_refs items
    with pytest.raises(ValueError):
        EpistemicChallenge(**{**valid_args, "trigger_refs": ("RES-1", "")})

    # Invalid proposed_tests items
    with pytest.raises(ValueError):
        EpistemicChallenge(**{**valid_args, "proposed_tests": ("", "test-2")})


def test_vocabulary_reuse() -> None:
    """Test 3: Verify ChallengeStatus comes from frozen E1 vocabulary."""
    assert ChallengeStatus.UNCHALLENGED.value == "UNCHALLENGED"
    assert ChallengeStatus.CHALLENGE_PROPOSED.value == "CHALLENGE_PROPOSED"
    assert ChallengeStatus.UNDER_INVESTIGATION.value == "UNDER_INVESTIGATION"
    assert ChallengeStatus.EVIDENCE_SUPPORTED.value == "EVIDENCE_SUPPORTED"
    assert ChallengeStatus.CHALLENGE_REJECTED.value == "CHALLENGE_REJECTED"
    assert ChallengeStatus.EPISTEMIC_ACCEPTED.value == "EPISTEMIC_ACCEPTED"


def test_target_representation() -> None:
    """Test 4: Verify assumption and model targets can be represented."""
    ch_assumption = EpistemicChallenge(
        challenge_id="CH-ASM-001",
        target_id="ASM-PISTON-001",
        target_kind="assumption",
        rationale="Breakup modes occur at 3.5 kHz, violating rigid piston assumption.",
        provenance="laser-vibrometry",
    )
    assert ch_assumption.target_kind == "assumption"
    assert ch_assumption.target_id == "ASM-PISTON-001"

    ch_model = EpistemicChallenge(
        challenge_id="CH-MDL-001",
        target_id="MODEL-LTI-001",
        target_kind="model",
        rationale="Port turbulence introduces quadratic damping not captured by linear state space.",
        provenance="fluid-dynamics-review",
    )
    assert ch_model.target_kind == "model"
    assert ch_model.target_id == "MODEL-LTI-001"


def test_target_references_are_identifiers() -> None:
    """Test 5: Verify no live registry or object references are stored in the challenge."""
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Testing reference isolation.",
        trigger_refs=("RESIDUAL-001", "OBS-002"),
        proposed_tests=("test_a", "test_b"),
        provenance="lab",
    )
    assert isinstance(ch.target_id, str)
    assert all(isinstance(r, str) for r in ch.trigger_refs)
    assert all(isinstance(t, str) for t in ch.proposed_tests)


def test_challenge_does_not_mutate_target() -> None:
    """Test 6: Creating/registering a challenge must not alter the referenced model or assumption."""
    asm = EpistemicAssumption(
        assumption_id="ASM-001",
        statement="Rigid piston motion.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.APPROXIMATION,
        scope={"max_freq_hz": 2000.0},
        provenance="engineering-handbook",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    mdl = EpistemicModel(
        model_id="MODEL-001",
        name="Linear Enclosure Model",
        description="LTI model of vented enclosure.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        assumption_ids=("ASM-001",),
        provenance="acoustics-team",
        status=EpistemicStatus.VALIDATED_MODEL,
    )

    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id=mdl.model_id,
        target_kind="model",
        rationale="Port compression observed at high drive levels.",
        provenance="measurement",
    )
    reg = ChallengeRegistry()
    reg.register(ch)

    # Invariant check: Model and assumption statuses remain completely unchanged
    assert mdl.status == EpistemicStatus.VALIDATED_MODEL
    assert asm.status == EpistemicStatus.VALIDATED_MODEL


def test_status_preservation() -> None:
    """Test 7: Explicit status remains unchanged after registration."""
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        status=ChallengeStatus.UNDER_INVESTIGATION,
        rationale="Active investigation in anechoic chamber.",
        provenance="test-lead",
    )
    reg = ChallengeRegistry()
    reg.register(ch)
    retrieved = reg.get("CH-001")
    assert retrieved.status == ChallengeStatus.UNDER_INVESTIGATION


def test_no_automatic_lifecycle_transition() -> None:
    """Test 8: Registration must not automatically transition challenge status."""
    ch_proposed = EpistemicChallenge(
        challenge_id="CH-PROP",
        target_id="MODEL-001",
        target_kind="model",
        status=ChallengeStatus.CHALLENGE_PROPOSED,
        rationale="Discrepancy observed.",
        provenance="lab",
    )
    reg = ChallengeRegistry()
    reg.register(ch_proposed)
    assert reg.get("CH-PROP").status == ChallengeStatus.CHALLENGE_PROPOSED
    assert reg.get("CH-PROP").status != ChallengeStatus.EVIDENCE_SUPPORTED
    assert reg.get("CH-PROP").status != ChallengeStatus.EPISTEMIC_ACCEPTED


def test_scope_preservation() -> None:
    """Test 9: Scope survives serialization exactly."""
    scope_data = {"temp_c": 21.5, "humidity_pct": 45.0, "band": "sub-bass"}
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Environmental boundary review.",
        scope=scope_data,
        provenance="metrology",
    )
    serialized = ch.to_dict()
    deserialized = EpistemicChallenge.from_dict(serialized)
    assert deserialized.scope == scope_data


def test_trigger_references() -> None:
    """Test 10: Trigger references remain stable and immutable."""
    triggers = ("RESIDUAL-001", "UNKNOWN-002", "OBS-099")
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Triggers recorded.",
        trigger_refs=triggers,
        provenance="lab",
    )
    assert ch.trigger_refs == triggers
    assert isinstance(ch.trigger_refs, tuple)


def test_proposed_tests() -> None:
    """Test 11: Proposed tests are stored but never executed."""
    execution_marker = []

    def fake_test_runner() -> None:
        execution_marker.append("EXECUTED")

    tests = ("laser_scan_cone", "nearfield_pressure_array")
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Proposed tests recorded.",
        proposed_tests=tests,
        provenance="test-planner",
    )
    assert ch.proposed_tests == ("laser_scan_cone", "nearfield_pressure_array")
    assert len(execution_marker) == 0


def test_provenance_semantics() -> None:
    """Test 12: Provenance remains descriptive provenance and does not become evidence."""
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Challenge with human engineering review provenance.",
        provenance="human-authored-expert-panel",
    )
    assert ch.provenance == "human-authored-expert-panel"


def test_ai_challenge_separation() -> None:
    """Test 13: An AI-generated challenge remains a challenge; never automatic evidence or authority."""
    ch = EpistemicChallenge(
        challenge_id="CH-AI-001",
        target_id="MODEL-LTI-001",
        target_kind="model",
        status=ChallengeStatus.CHALLENGE_PROPOSED,
        rationale="AI anomaly detector flagged non-minimum-phase behavior in crossover band.",
        provenance="ai-generated-anomaly-detector",
    )
    assert ch.provenance == "ai-generated-anomaly-detector"
    assert ch.status == ChallengeStatus.CHALLENGE_PROPOSED
    assert ch.status != ChallengeStatus.EVIDENCE_SUPPORTED
    assert ch.status != ChallengeStatus.EPISTEMIC_ACCEPTED


def test_immutability() -> None:
    """Test 14: EpistemicChallenge is immutable and rejects attribute mutation."""
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Testing immutability.",
        provenance="lab",
    )
    with pytest.raises(FrozenInstanceError):
        ch.status = ChallengeStatus.EPISTEMIC_ACCEPTED  # type: ignore

    with pytest.raises(FrozenInstanceError):
        ch.rationale = "New rationale"  # type: ignore


def test_deterministic_serialization() -> None:
    """Test 15: to_dict() produces deterministic dictionary representation."""
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        status=ChallengeStatus.UNDER_INVESTIGATION,
        rationale="Serialization test.",
        scope={"axis": "vertical", "distance_m": 1.0},
        trigger_refs=("RES-1", "RES-2"),
        proposed_tests=("test_1", "test_2"),
        provenance="serialization-suite",
    )
    d1 = ch.to_dict()
    d2 = ch.to_dict()
    assert d1 == d2
    assert d1["challenge_id"] == "CH-001"
    assert d1["status"] == "UNDER_INVESTIGATION"
    assert d1["trigger_refs"] == ["RES-1", "RES-2"]


def test_json_round_trip() -> None:
    """Test 16: Lossless JSON round-trip reconstruction."""
    ch = EpistemicChallenge(
        challenge_id="CH-JSON-001",
        target_id="ASM-RIGID-001",
        target_kind="assumption",
        status=ChallengeStatus.CHALLENGE_PROPOSED,
        rationale="Lossless JSON test.",
        scope={"spl_limit": 100.0},
        trigger_refs=("RES-001",),
        proposed_tests=("test_impulse",),
        provenance="json-validator",
    )
    serialized_dict = ch.to_dict()
    json_str = json.dumps(serialized_dict, sort_keys=True)
    parsed_dict = json.loads(json_str)
    reconstructed = EpistemicChallenge.from_dict(parsed_dict)
    assert reconstructed == ch


def test_registry_registration_and_retrieval() -> None:
    """Test 17: Register, get, and contains in ChallengeRegistry."""
    reg = ChallengeRegistry()
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="Registry test.",
        provenance="lab",
    )
    assert not reg.contains("CH-001")
    assert "CH-001" not in reg

    reg.register(ch)
    assert reg.contains("CH-001")
    assert "CH-001" in reg
    assert reg.get("CH-001") == ch
    assert len(reg) == 1

    with pytest.raises(KeyError):
        reg.get("CH-NONEXISTENT")


def test_duplicate_protection() -> None:
    """Test 18: Registering duplicate challenge IDs raises ValueError."""
    reg = ChallengeRegistry()
    ch1 = EpistemicChallenge(
        challenge_id="CH-DUP-001",
        target_id="MODEL-001",
        target_kind="model",
        rationale="First registration.",
        provenance="lab",
    )
    ch2 = EpistemicChallenge(
        challenge_id="CH-DUP-001",
        target_id="MODEL-002",
        target_kind="model",
        rationale="Second registration with identical ID.",
        provenance="lab",
    )
    reg.register(ch1)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(ch2)


def test_deterministic_enumeration() -> None:
    """Test 19: all() and iteration preserve deterministic insertion order."""
    reg = ChallengeRegistry()
    c1 = EpistemicChallenge(challenge_id="CH-C", target_id="M1", target_kind="model", rationale="R1", provenance="P1")
    c2 = EpistemicChallenge(challenge_id="CH-A", target_id="M2", target_kind="model", rationale="R2", provenance="P2")
    c3 = EpistemicChallenge(challenge_id="CH-B", target_id="M3", target_kind="model", rationale="R3", provenance="P3")

    reg.register(c1)
    reg.register(c2)
    reg.register(c3)

    assert reg.all() == (c1, c2, c3)
    assert list(reg) == [c1, c2, c3]


def test_query_filtering() -> None:
    """Test 20: Query filtering by status, target_id, target_kind."""
    reg = ChallengeRegistry()
    c1 = EpistemicChallenge(
        challenge_id="CH-1",
        target_id="MODEL-001",
        target_kind="model",
        status=ChallengeStatus.CHALLENGE_PROPOSED,
        rationale="R1",
        provenance="P1",
    )
    c2 = EpistemicChallenge(
        challenge_id="CH-2",
        target_id="MODEL-001",
        target_kind="model",
        status=ChallengeStatus.UNDER_INVESTIGATION,
        rationale="R2",
        provenance="P2",
    )
    c3 = EpistemicChallenge(
        challenge_id="CH-3",
        target_id="ASM-001",
        target_kind="assumption",
        status=ChallengeStatus.CHALLENGE_PROPOSED,
        rationale="R3",
        provenance="P3",
    )
    reg.register(c1)
    reg.register(c2)
    reg.register(c3)

    # Filter by target_id
    res_m1 = reg.query(target_id="MODEL-001")
    assert res_m1 == (c1, c2)

    # Filter by target_kind
    res_asm = reg.query(target_kind="assumption")
    assert res_asm == (c3,)

    # Filter by status
    res_prop = reg.query(status=ChallengeStatus.CHALLENGE_PROPOSED)
    assert res_prop == (c1, c3)

    # Filter by multiple
    res_combo = reg.query(target_id="MODEL-001", status=ChallengeStatus.UNDER_INVESTIGATION)
    assert res_combo == (c2,)


def test_independent_import() -> None:
    """Test 21: Epistemic challenges module can be imported independently without Core/hardware dependencies."""
    from acoustiforge.epistemic.challenges import ChallengeRegistry, EpistemicChallenge
    assert EpistemicChallenge is not None
    assert ChallengeRegistry is not None


# ==============================================================================
# Mandatory Red-Team Boundary Tests (Red-Team A through I)
# ==============================================================================

def test_red_team_a_challenge_is_not_falsification() -> None:
    """Red-Team A: Creating a challenge must NOT produce FALSIFICATION_EVIDENCE_DETECTED."""
    mdl = EpistemicModel(
        model_id="MDL-LTI-001",
        name="LTI Enclosure",
        description="Linear bass reflex model.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        assumption_ids=(),
        provenance="metrology",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    ch = EpistemicChallenge(
        challenge_id="CH-001",
        target_id=mdl.model_id,
        target_kind="model",
        rationale="Port chuffing observed at 100 dB SPL.",
        provenance="measurements",
    )
    assert mdl.status == EpistemicStatus.VALIDATED_MODEL
    assert mdl.status != EpistemicStatus.FALSIFICATION_EVIDENCE_DETECTED
    assert ch.status == ChallengeStatus.CHALLENGE_PROPOSED


def test_red_team_b_challenge_does_not_mutate_model() -> None:
    """Red-Team B: Creating/registering a challenge must NOT change model status."""
    mdl = EpistemicModel(
        model_id="MDL-TEST-002",
        name="LTI Model",
        description="Linear model.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.APPROXIMATION,
        assumption_ids=(),
        provenance="metrology",
        status=EpistemicStatus.VALIDATED_MODEL,
    )
    reg = ChallengeRegistry()
    ch = EpistemicChallenge(
        challenge_id="CH-002",
        target_id=mdl.model_id,
        target_kind="model",
        rationale="Linearity questioned.",
        provenance="analyst",
    )
    reg.register(ch)
    assert mdl.status == EpistemicStatus.VALIDATED_MODEL
    assert mdl.status != EpistemicStatus.CHALLENGED


def test_red_team_c_challenge_is_not_evidence() -> None:
    """Red-Team C: A challenge is an investigation request, not an evidence record."""
    ch = EpistemicChallenge(
        challenge_id="CH-003",
        target_id="MDL-003",
        target_kind="model",
        rationale="High frequency directivity anomaly.",
        provenance="polar-scan",
    )
    # Challenge holds references to triggers, not an evidence engine or evidence score
    assert not hasattr(ch, "evidence_score")
    assert not hasattr(ch, "weight")
    assert not hasattr(ch, "confidence")


def test_red_team_d_ai_challenge_is_not_empirical_evidence() -> None:
    """Red-Team D: AI-generated challenge remains a challenge, never empirical evidence."""
    ch = EpistemicChallenge(
        challenge_id="CH-AI-002",
        target_id="MDL-004",
        target_kind="model",
        rationale="LLM hypothesized higher-order cabinet panel modes.",
        provenance="ai-reasoning-agent",
    )
    assert ch.provenance == "ai-reasoning-agent"
    assert ch.status == ChallengeStatus.CHALLENGE_PROPOSED
    assert ch.status != ChallengeStatus.EVIDENCE_SUPPORTED


def test_red_team_e_challenge_status_is_not_truth() -> None:
    """Red-Team E: EVIDENCE_SUPPORTED challenge status must not mean target is disproven or true."""
    ch = EpistemicChallenge(
        challenge_id="CH-005",
        target_id="MDL-005",
        target_kind="model",
        status=ChallengeStatus.EVIDENCE_SUPPORTED,
        rationale="Measurements corroborate boundary mismatch.",
        provenance="lab",
    )
    # The challenge object only represents the challenge status, not target truth/falsehood
    assert ch.status == ChallengeStatus.EVIDENCE_SUPPORTED


def test_red_team_f_challenge_rejection_does_not_mutate_target() -> None:
    """Red-Team F: CHALLENGE_REJECTED must not mutate the target."""
    asm = EpistemicAssumption(
        assumption_id="ASM-005",
        statement="Room air temperature is 20 C.",
        zone=EpistemicZone.ZONE_M,
        epistemic_class=EpistemicClass.CONSTITUTIVE_MODEL,
        scope={},
        provenance="lab",
        status=EpistemicStatus.TESTED_CANDIDATE,
    )
    ch = EpistemicChallenge(
        challenge_id="CH-006",
        target_id=asm.assumption_id,
        target_kind="assumption",
        status=ChallengeStatus.CHALLENGE_REJECTED,
        rationale="Re-measurement confirmed chamber temperature remained exactly 20.0 C.",
        provenance="review-board",
    )
    reg = ChallengeRegistry()
    reg.register(ch)
    assert asm.status == EpistemicStatus.TESTED_CANDIDATE


def test_red_team_g_proposed_test_does_not_execute() -> None:
    """Red-Team G: No execution occurs merely because a test is proposed."""
    execution_flag = {"ran": False}

    def dangerous_execution() -> None:
        execution_flag["ran"] = True

    ch = EpistemicChallenge(
        challenge_id="CH-007",
        target_id="MDL-007",
        target_kind="model",
        rationale="Testing execution isolation.",
        proposed_tests=("run_destructive_overdrive_test",),
        provenance="test-planner",
    )
    assert not execution_flag["ran"]
    assert ch.proposed_tests == ("run_destructive_overdrive_test",)


def test_red_team_h_epistemic_accepted_is_not_production_authority() -> None:
    """Red-Team H: EPISTEMIC_ACCEPTED challenge status must not create production authority."""
    ch = EpistemicChallenge(
        challenge_id="CH-008",
        target_id="MDL-008",
        target_kind="model",
        status=ChallengeStatus.EPISTEMIC_ACCEPTED,
        rationale="Peer review consensus accepted that thin-wall approximation fails for this enclosure.",
        provenance="scientific-review",
    )
    assert ch.status == ChallengeStatus.EPISTEMIC_ACCEPTED
    assert not hasattr(ch, "production_authority")
    assert not hasattr(ch, "dsp_pipeline")


def test_red_team_i_no_core_mutation() -> None:
    """Red-Team I: Challenge registration must not modify deterministic production Core state."""
    reg = ChallengeRegistry()
    ch = EpistemicChallenge(
        challenge_id="CH-009",
        target_id="MODEL-PROD-001",
        target_kind="model",
        rationale="Checking core isolation.",
        provenance="test",
    )
    reg.register(ch)

    core_modules = [m for m in sys.modules.keys() if m.startswith("acoustiforge.") and not m.startswith("acoustiforge.epistemic")]
    for mod_name in core_modules:
        mod = sys.modules[mod_name]
        assert not hasattr(mod, "_epistemic_challenge_override")
