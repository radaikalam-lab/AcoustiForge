"""Tests for AcoustiForge Scientific Observation Envelope (Phase P1 & P1.1 Hardening)."""

import json
import pytest
import numpy as np

from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.validation import InvalidMeasurementError
from acoustiforge.science.observation import (
    EnvironmentalConditions,
    MeasurementTransform,
    MeasurementUncertainty,
    ObservationEnvelope,
    ObservationRegistry,
)


@pytest.fixture
def sample_freq_data() -> FrequencyResponseData:
    freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
    mags = np.array([85.0, 88.0, 84.0], dtype=np.float64)
    phases = np.array([0.0, -0.5, -1.2], dtype=np.float64)
    return FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags, phase_rad=phases)


def test_environmental_conditions_construction_and_validation() -> None:
    env = EnvironmentalConditions(
        temperature_c=21.5,
        relative_humidity_pct=45.0,
        ambient_pressure_kpa=101.3,
        ambient_noise_floor_db=28.0,
    )
    assert env.temperature_c == 21.5
    assert env.relative_humidity_pct == 45.0
    assert env.ambient_pressure_kpa == 101.3
    assert env.ambient_noise_floor_db == 28.0

    # Serialization
    d = env.to_dict()
    env2 = EnvironmentalConditions.from_dict(d)
    assert env == env2

    # Validation
    with pytest.raises(InvalidMeasurementError):
        EnvironmentalConditions(temperature_c=float("nan"))
    with pytest.raises(InvalidMeasurementError):
        EnvironmentalConditions(relative_humidity_pct=float("inf"))


def test_measurement_uncertainty_construction_and_validation() -> None:
    unc = MeasurementUncertainty(
        snr_db=35.0,
        repeatability_variance_db=0.2,
        calibration_uncertainty_db=0.5,
        frequency_range_hz=(20.0, 20000.0),
    )
    assert unc.snr_db == 35.0
    assert unc.repeatability_variance_db == 0.2
    assert unc.calibration_uncertainty_db == 0.5
    assert unc.frequency_range_hz == (20.0, 20000.0)

    # Serialization
    d = unc.to_dict()
    unc2 = MeasurementUncertainty.from_dict(d)
    assert unc == unc2

    # Validation
    with pytest.raises(InvalidMeasurementError):
        MeasurementUncertainty(snr_db=float("nan"))
    with pytest.raises(InvalidMeasurementError):
        MeasurementUncertainty(frequency_range_hz=(20000.0, 20.0))


def test_measurement_transform_tracking_and_immutability() -> None:
    input_params = {"window_type": "tukey", "gate_time_ms": 4.5}
    t1 = MeasurementTransform(
        transform_type="reflection_gating",
        parameters=input_params,
        rationale="Remove room reflections below 250 Hz",
    )
    assert t1.transform_type == "reflection_gating"
    assert t1.parameters["gate_time_ms"] == 4.5
    assert "reflections" in t1.rationale

    # Deep immutability: mutating parameter dictionary fails
    with pytest.raises(TypeError):
        t1.parameters["gate_time_ms"] = 10.0  # type: ignore[index]

    # Defensive copy: mutating input dictionary does not affect transform
    input_params["gate_time_ms"] = 99.0
    assert t1.parameters["gate_time_ms"] == 4.5

    d = t1.to_dict()
    t2 = MeasurementTransform.from_dict(d)
    assert t1 == t2

    with pytest.raises(InvalidMeasurementError):
        MeasurementTransform(transform_type="")


def test_observation_envelope_construction_and_deep_immutability(sample_freq_data: FrequencyResponseData) -> None:
    env = EnvironmentalConditions(temperature_c=20.0)
    unc = MeasurementUncertainty(snr_db=40.0)
    trans = (MeasurementTransform(transform_type="smoothing", parameters={"octave_fraction": 6}),)
    input_meta = {"gain_setting_db": 0.0, "nested": {"key": "val"}}

    obs = ObservationEnvelope(
        observation_id="OBS-TEST-001",
        data=sample_freq_data,
        source_reference="data/raw_sweeps/woofer_axis_0.frd",
        source_format="FRD",
        sensor_id="MIC-EARTHWORKS-M30-10492",
        calibration_id="CAL-M30-2026",
        operator="Acoustic Lab Tech A",
        microphone_distance_m=1.0,
        spl_calibration_offset_db=94.0,
        environmental_conditions=env,
        uncertainty=unc,
        transforms=trans,
        provenance="Anechoic Chamber 1 Sweep",
        metadata=input_meta,
    )

    assert obs.observation_id == "OBS-TEST-001"
    assert obs.source_format == "FRD"
    assert obs.microphone_distance_m == 1.0
    assert len(obs.transforms) == 1
    assert obs.transforms[0].transform_type == "smoothing"

    # Attribute reassignment fails
    with pytest.raises(Exception):
        obs.observation_id = "MUTATED"  # type: ignore[misc]

    # Nested dictionary mutation fails (deep immutability)
    with pytest.raises(TypeError):
        obs.metadata["gain_setting_db"] = 12.0  # type: ignore[index]

    with pytest.raises(TypeError):
        obs.metadata["nested"]["key"] = "tampered"  # type: ignore[index]

    # Defensive copy: mutating input dictionary does not affect envelope
    input_meta["gain_setting_db"] = 42.0
    input_meta["nested"]["key"] = "external_mutation"
    assert obs.metadata["gain_setting_db"] == 0.0
    assert obs.metadata["nested"]["key"] == "val"


def test_frequency_response_data_alias_isolation() -> None:
    raw_freqs = np.array([100.0, 1000.0], dtype=np.float64)
    raw_mags = np.array([80.0, 85.0], dtype=np.float64)
    freq_data = FrequencyResponseData(frequencies_hz=raw_freqs, magnitude_db=raw_mags)

    obs = ObservationEnvelope(
        observation_id="OBS-ALIAS-01",
        data=freq_data,
        source_reference="alias.frd",
        source_format="FRD",
    )

    # Mutating raw arrays used to construct FrequencyResponseData fails or does not affect data
    raw_freqs[0] = 999.0
    assert obs.data.frequencies_hz[0] == 100.0

    # Direct mutation of FrequencyResponseData array raises ValueError (read-only array)
    with pytest.raises(ValueError):
        obs.data.frequencies_hz[0] = 500.0


def test_observation_envelope_serialization_and_round_trip(sample_freq_data: FrequencyResponseData) -> None:
    obs = ObservationEnvelope(
        observation_id="OBS-ROUNDTRIP-01",
        data=sample_freq_data,
        source_reference="sweeps/tweeter.csv",
        source_format="CSV",
        sensor_id="MIC-001",
        environmental_conditions=EnvironmentalConditions(temperature_c=22.0, relative_humidity_pct=50.0),
        uncertainty=MeasurementUncertainty(snr_db=45.0, frequency_range_hz=(1000.0, 20000.0)),
        transforms=(MeasurementTransform(transform_type="calibration_compensation"),),
        provenance="Lab 2",
        metadata={"calibrated": True, "gain_steps": [0, 6, 12]},
    )

    d = obs.to_dict()
    json_str = json.dumps(d)
    d_loaded = json.loads(json_str)
    obs_recovered = ObservationEnvelope.from_dict(d_loaded)

    assert obs_recovered.observation_id == obs.observation_id
    assert obs_recovered.source_reference == obs.source_reference
    assert obs_recovered.sensor_id == obs.sensor_id
    assert np.allclose(obs_recovered.data.frequencies_hz, obs.data.frequencies_hz)
    assert np.allclose(obs_recovered.data.magnitude_db, obs.data.magnitude_db)
    assert np.allclose(obs_recovered.data.phase_rad, obs.data.phase_rad)
    assert obs_recovered.environmental_conditions == obs.environmental_conditions
    assert obs_recovered.uncertainty == obs.uncertainty
    assert obs_recovered.transforms == obs.transforms
    assert obs_recovered.metadata == obs.metadata


def test_observation_registry_operations(sample_freq_data: FrequencyResponseData) -> None:
    registry = ObservationRegistry()
    obs1 = ObservationEnvelope(
        observation_id="OBS-01",
        data=sample_freq_data,
        source_reference="file1.frd",
        source_format="FRD",
        sensor_id="MIC-A",
    )
    obs2 = ObservationEnvelope(
        observation_id="OBS-02",
        data=sample_freq_data,
        source_reference="file2.frd",
        source_format="FRD",
        sensor_id="MIC-B",
    )

    registry.register(obs1)
    registry.register(obs2)

    assert registry.get("OBS-01") == obs1
    assert registry.get("OBS-02") == obs2
    assert len(registry.list_all()) == 2
    assert len(registry.find_by_sensor("MIC-A")) == 1
    assert registry.find_by_sensor("MIC-A")[0] == obs1

    # Duplicate registration rejected
    with pytest.raises(InvalidMeasurementError):
        registry.register(obs1)

    registry.clear()
    assert len(registry.list_all()) == 0
