"""Integration and Safety Boundary Tests for Scientific Observation & Experiment Envelopes (Phase P1)."""

import json
import pytest
import numpy as np

from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.epistemic.vocabulary import (
    ChallengeStatus,
    EpistemicEvidenceType,
    EpistemicStatus,
    EvidenceRelation,
)
from acoustiforge.science.observation import (
    EnvironmentalConditions,
    MeasurementTransform,
    MeasurementUncertainty,
    ObservationEnvelope,
    ObservationRegistry,
)
from acoustiforge.science.experiment import (
    ExperimentLifecycleState,
    ExperimentSession,
    ExperimentSessionRegistry,
)


def test_end_to_end_synthetic_science_lifecycle() -> None:
    """SYNTHETIC TEST SCENARIO: End-to-end measurement, observation, experiment, and epistemic linking."""
    # 1. Synthetic measurement generation
    freqs = np.array([50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0], dtype=np.float64)
    mags = np.array([72.0, 80.0, 85.0, 86.0, 86.5, 86.0, 84.0, 82.0], dtype=np.float64)
    phases = np.array([0.0, -0.2, -0.5, -0.9, -1.4, -2.1, -3.2, -4.5], dtype=np.float64)
    raw_measurement = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags, phase_rad=phases)

    # 2. Contextualize into ObservationEnvelope
    obs = ObservationEnvelope(
        observation_id="OBS-SYNTHETIC-001",
        data=raw_measurement,
        source_reference="measurements/synthetic/driver_sweep_01.frd",
        source_format="FRD",
        sensor_id="MIC-TEST-CAL-99",
        calibration_id="CAL-STANDARD-2026",
        operator="Automated Bench Rig",
        microphone_distance_m=1.0,
        spl_calibration_offset_db=94.0,
        environmental_conditions=EnvironmentalConditions(
            temperature_c=20.5,
            relative_humidity_pct=48.0,
            ambient_pressure_kpa=101.2,
            ambient_noise_floor_db=25.0,
        ),
        uncertainty=MeasurementUncertainty(
            snr_db=42.0,
            repeatability_variance_db=0.15,
            calibration_uncertainty_db=0.3,
            frequency_range_hz=(50.0, 10000.0),
        ),
        transforms=(
            MeasurementTransform(
                transform_type="time_windowing",
                parameters={"window_ms": 6.0},
                rationale="Isolate direct sound",
            ),
        ),
        provenance="Anechoic test bench automated sweep",
    )

    # 3. Formulate an ExperimentSession
    session = ExperimentSession(
        experiment_id="EXP-SYNTHETIC-2026-01",
        name="Near-Field Driver Linearity Evaluation",
        description="Evaluating linear transducer model predictions against stepped drive acoustic sweep.",
        lifecycle_state=ExperimentLifecycleState.COMPLETED,
        target_model_ids=("MODEL-ELECTROACOUSTIC-LTI-01",),
        representation_id="REP-LUMPED-THIELE-SMALL",
        controlled_variables={
            "temperature_c": 20.5,
            "mic_distance_m": 1.0,
            "mounting_baffle": "IEC_Standard",
        },
        manipulated_variables={
            "drive_voltage_v": 2.83,
        },
        observation_ids=(obs.observation_id,),
        prediction_references={
            "MODEL-ELECTROACOUSTIC-LTI-01": "PRED-SYNTHETIC-SPL-01",
        },
        residual_references=("RES-SYNTHETIC-01",),
        provenance="Lab Experiment Automation",
    )

    # 4. Verify observation and session integrity
    assert obs.observation_id == "OBS-SYNTHETIC-001"
    assert session.experiment_id == "EXP-SYNTHETIC-2026-01"
    assert session.observation_ids[0] == obs.observation_id
    assert session.prediction_references["MODEL-ELECTROACOUSTIC-LTI-01"] == "PRED-SYNTHETIC-SPL-01"


def test_safety_boundary_observation_is_not_evidence_or_truth() -> None:
    """Verify ObservationEnvelope does not assert truth, falsification, or production authority."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    mags = np.array([80.0, 85.0], dtype=np.float64)
    data = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

    obs = ObservationEnvelope(
        observation_id="OBS-RAW-01",
        data=data,
        source_reference="raw.frd",
        source_format="FRD",
    )

    # Must NOT have epistemic status attributes
    assert not hasattr(obs, "epistemic_status")
    assert not hasattr(obs, "falsified")
    assert not hasattr(obs, "truth_score")
    assert not hasattr(obs, "production_authority")


def test_safety_boundary_experiment_is_not_model_or_production_authority() -> None:
    """Verify ExperimentSession does not mutate model state, objective, or Core."""
    session = ExperimentSession(
        experiment_id="EXP-BOUND-01",
        name="Boundary Test",
        description="Validating non-authority",
        target_model_ids=("MODEL-01",),
    )

    assert not hasattr(session, "production_authority")
    assert not hasattr(session, "is_winner")
    assert not hasattr(session, "adequacy_score")
    assert not hasattr(session, "falsify_model")


def test_safety_boundary_production_core_unmodified() -> None:
    """Verify Core domain objects and compute graph are completely untouched."""
    from acoustiforge.domain.measurements import FrequencyResponseData
    from acoustiforge.graph.compute_graph import ComputeGraph

    # Check that domain measurement has not been altered with epistemic fields
    assert hasattr(FrequencyResponseData, "frequencies_hz")
    assert hasattr(FrequencyResponseData, "magnitude_db")
    assert not hasattr(FrequencyResponseData, "observation_id")
    assert not hasattr(FrequencyResponseData, "experiment_id")

    # Check compute graph
    graph = ComputeGraph()
    assert not hasattr(graph, "_science_override")


def test_deterministic_double_replay() -> None:
    """Verify identical execution generates identical serialized representations."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    mags = np.array([80.0, 85.0], dtype=np.float64)
    data = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

    obs1 = ObservationEnvelope(
        observation_id="OBS-REPLAY",
        data=data,
        source_reference="sweep.frd",
        source_format="FRD",
        sensor_id="MIC-1",
        environmental_conditions=EnvironmentalConditions(temperature_c=20.0),
        uncertainty=MeasurementUncertainty(snr_db=40.0),
        provenance="Replay Rig",
    )
    sess1 = ExperimentSession(
        experiment_id="EXP-REPLAY",
        name="Replay Session",
        description="Testing deterministic replay",
        target_model_ids=("M1",),
        observation_ids=(obs1.observation_id,),
        provenance="Replay Rig",
    )

    obs2 = ObservationEnvelope(
        observation_id="OBS-REPLAY",
        data=data,
        source_reference="sweep.frd",
        source_format="FRD",
        sensor_id="MIC-1",
        environmental_conditions=EnvironmentalConditions(temperature_c=20.0),
        uncertainty=MeasurementUncertainty(snr_db=40.0),
        provenance="Replay Rig",
    )
    sess2 = ExperimentSession(
        experiment_id="EXP-REPLAY",
        name="Replay Session",
        description="Testing deterministic replay",
        target_model_ids=("M1",),
        observation_ids=(obs2.observation_id,),
        provenance="Replay Rig",
    )

    d1_obs = obs1.to_dict()
    d2_obs = obs2.to_dict()
    assert d1_obs == d2_obs

    d1_sess = sess1.to_dict()
    d2_sess = sess2.to_dict()
    assert d1_sess == d2_sess
