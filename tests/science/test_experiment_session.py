"""Tests for AcoustiForge Scientific Experiment Session Protocol (Phase P1 & P1.1 Hardening)."""

import json
import pytest

from acoustiforge.domain.validation import InvalidSpecificationError
from acoustiforge.science.experiment import (
    ExperimentLifecycleState,
    ExperimentSession,
    ExperimentSessionRegistry,
)


def test_experiment_session_construction_and_validation() -> None:
    session = ExperimentSession(
        experiment_id="EXP-2026-PORT-01",
        name="Port Compression vs Drive Level",
        description="Investigating non-linear port air flow resistance under stepped sinusoidal drive levels.",
        lifecycle_state=ExperimentLifecycleState.ACQUIRING,
        target_model_ids=("MODEL-PORT-LINEAR-01", "MODEL-PORT-NONLINEAR-02"),
        representation_id="REP-LUMPED-ACOUSTIC",
        controlled_variables={"temperature_c": 20.0, "mic_distance_m": 0.5, "chamber_axis_deg": 0.0},
        manipulated_variables={"drive_voltage_v": [1.0, 2.83, 5.0, 10.0, 15.0]},
        observation_ids=("OBS-SWEEP-1V", "OBS-SWEEP-2.83V", "OBS-SWEEP-5V"),
        prediction_references={"MODEL-PORT-LINEAR-01": "PRED-LIN-01"},
        residual_references=("RES-PORT-10V",),
        provenance="Lab Experimenter A",
        metadata={"amplifier_gain": 26.0},
    )

    assert session.experiment_id == "EXP-2026-PORT-01"
    assert session.lifecycle_state == ExperimentLifecycleState.ACQUIRING
    assert len(session.target_model_ids) == 2
    assert session.controlled_variables["mic_distance_m"] == 0.5
    assert len(session.manipulated_variables["drive_voltage_v"]) == 5
    assert len(session.observation_ids) == 3

    # Attribute reassignment fails
    with pytest.raises(Exception):
        session.experiment_id = "MUTATED"  # type: ignore[misc]

    # Validation
    with pytest.raises(InvalidSpecificationError):
        ExperimentSession(experiment_id="", name="Valid", description="Valid")
    with pytest.raises(InvalidSpecificationError):
        ExperimentSession(experiment_id="EXP-01", name="", description="Valid")


def test_deep_immutability_and_defensive_copying() -> None:
    input_ctrl = {"ambient_temp_c": 20.0, "nested": {"sensor": "ch1"}}
    input_manip = {"voltage_v": [1.0, 2.0]}
    input_pred = {"MODEL-A": "PRED-A"}
    input_meta = {"operator": "Researcher A"}

    session = ExperimentSession(
        experiment_id="EXP-IMMUT-01",
        name="Deep Immutability Test",
        description="Testing that all nested mappings are read-only and defensively copied.",
        controlled_variables=input_ctrl,
        manipulated_variables=input_manip,
        prediction_references=input_pred,
        metadata=input_meta,
    )

    # 1. Direct mutation of nested mappings raises TypeError
    with pytest.raises(TypeError):
        session.controlled_variables["ambient_temp_c"] = 25.0  # type: ignore[index]

    with pytest.raises(TypeError):
        session.controlled_variables["nested"]["sensor"] = "ch2"  # type: ignore[index]

    with pytest.raises(TypeError):
        session.manipulated_variables["voltage_v"] = [5.0]  # type: ignore[index]

    with pytest.raises(TypeError):
        session.prediction_references["MODEL-A"] = "PRED-TAMPERED"  # type: ignore[index]

    with pytest.raises(TypeError):
        session.metadata["operator"] = "Impostor"  # type: ignore[index]

    # 2. Mutating original caller dictionaries has zero effect
    input_ctrl["ambient_temp_c"] = 99.0
    input_ctrl["nested"]["sensor"] = "mutated_externally"
    input_manip["voltage_v"].append(99.0)
    input_pred["MODEL-A"] = "external_tamper"
    input_meta["operator"] = "external_change"

    assert session.controlled_variables["ambient_temp_c"] == 20.0
    assert session.controlled_variables["nested"]["sensor"] == "ch1"
    assert session.manipulated_variables["voltage_v"] == (1.0, 2.0)
    assert session.prediction_references["MODEL-A"] == "PRED-A"
    assert session.metadata["operator"] == "Researcher A"


def test_controlled_vs_manipulated_variables_separation() -> None:
    session = ExperimentSession(
        experiment_id="EXP-SEP-01",
        name="Variable Separation Test",
        description="Verifying explicit variable partitioning.",
        controlled_variables={"ambient_temp_c": 21.0, "chamber_volume_m3": 85.0},
        manipulated_variables={"crossover_freq_hz": 2200.0, "filter_order": 4},
    )

    assert "ambient_temp_c" in session.controlled_variables
    assert "ambient_temp_c" not in session.manipulated_variables
    assert "crossover_freq_hz" in session.manipulated_variables
    assert "crossover_freq_hz" not in session.controlled_variables


def test_prediction_vs_observation_reference_separation() -> None:
    session = ExperimentSession(
        experiment_id="EXP-PRED-OBS-01",
        name="Prediction vs Observation Separation",
        description="Ensuring predictions and observations are not conflated.",
        target_model_ids=("MODEL-A",),
        prediction_references={"MODEL-A": "PRED-CURVE-A-SPL"},
        observation_ids=("OBS-MEASURED-SWEEP-01",),
        residual_references=("RES-DIFF-A-01",),
    )

    assert session.prediction_references["MODEL-A"] == "PRED-CURVE-A-SPL"
    assert "OBS-MEASURED-SWEEP-01" in session.observation_ids
    assert "RES-DIFF-A-01" in session.residual_references
    assert session.prediction_references["MODEL-A"] not in session.observation_ids


def test_experiment_session_serialization_and_round_trip() -> None:
    session = ExperimentSession(
        experiment_id="EXP-JSON-01",
        name="Round Trip Session",
        description="Testing JSON serialization",
        lifecycle_state=ExperimentLifecycleState.COMPLETED,
        target_model_ids=("M1", "M2"),
        representation_id="REP-01",
        controlled_variables={"v1": 10},
        manipulated_variables={"v2": 20},
        observation_ids=("O1", "O2"),
        prediction_references={"M1": "P1"},
        residual_references=("R1",),
        provenance="Operator B",
        metadata={"tag": "final"},
    )

    d = session.to_dict()
    json_str = json.dumps(d)
    d_loaded = json.loads(json_str)
    session_recovered = ExperimentSession.from_dict(d_loaded)

    assert session_recovered == session
    assert session_recovered.lifecycle_state == ExperimentLifecycleState.COMPLETED


def test_experiment_session_registry_operations() -> None:
    registry = ExperimentSessionRegistry()
    s1 = ExperimentSession(
        experiment_id="EXP-01",
        name="Session 1",
        description="First session",
        target_model_ids=("M1",),
        observation_ids=("OBS-A",),
    )
    s2 = ExperimentSession(
        experiment_id="EXP-02",
        name="Session 2",
        description="Second session",
        target_model_ids=("M2",),
        observation_ids=("OBS-B",),
    )

    registry.register(s1)
    registry.register(s2)

    assert registry.get("EXP-01") == s1
    assert registry.get("EXP-02") == s2
    assert len(registry.list_all()) == 2
    assert len(registry.find_by_model("M1")) == 1
    assert registry.find_by_model("M1")[0] == s1
    assert len(registry.find_by_observation("OBS-B")) == 1
    assert registry.find_by_observation("OBS-B")[0] == s2

    with pytest.raises(InvalidSpecificationError):
        registry.register(s1)

    registry.clear()
    assert len(registry.list_all()) == 0
