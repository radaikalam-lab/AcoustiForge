"""AcoustiForge Acoustic Domain Models and Value Types Test Suite.

Verifies Phase 3B domain specifications, profiles, and measurement containers.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import numpy as np
import pytest

from acoustiforge.domain.measurements import (
    FrequencyResponseData,
    ImpulseResponseData,
)
from acoustiforge.domain.profiles import (
    DriverProfile,
    DriverRole,
    EnclosureProfile,
    EnclosureType,
)
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    CrossoverSpecification,
    EqualizerBudget,
    TransducerLimits,
)
from acoustiforge.domain.validation import (
    DomainError,
    InvalidMeasurementError,
    InvalidProfileError,
    InvalidSpecificationError,
)


# --- 1. CrossoverSpecification Tests ---

class TestCrossoverSpecification:
    def test_valid_linkwitz_riley_spec(self) -> None:
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2400.0,
        )
        assert spec.family == CrossoverFamily.LINKWITZ_RILEY
        assert spec.order == 4
        assert spec.frequency_hz == 2400.0

    def test_string_family_parsing(self) -> None:
        spec = CrossoverSpecification(
            family="butterworth",  # type: ignore[arg-type]
            order=2,
            frequency_hz=1000.0,
        )
        assert spec.family == CrossoverFamily.BUTTERWORTH

    def test_invalid_order_rejected(self) -> None:
        with pytest.raises(InvalidSpecificationError, match="Unsupported crossover order"):
            CrossoverSpecification(family=CrossoverFamily.BUTTERWORTH, order=3, frequency_hz=1000.0)

        with pytest.raises(InvalidSpecificationError, match="Unsupported crossover order"):
            CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=6, frequency_hz=1000.0)

    def test_invalid_frequency_rejected(self) -> None:
        with pytest.raises(InvalidSpecificationError, match="positive finite number"):
            CrossoverSpecification(family=CrossoverFamily.BUTTERWORTH, order=2, frequency_hz=-500.0)

        with pytest.raises(InvalidSpecificationError, match="positive finite number"):
            CrossoverSpecification(family=CrossoverFamily.BUTTERWORTH, order=2, frequency_hz=float("nan"))

    def test_immutability(self) -> None:
        spec = CrossoverSpecification(family=CrossoverFamily.LINKWITZ_RILEY, order=4, frequency_hz=2000.0)
        with pytest.raises(FrozenInstanceError):
            spec.order = 2  # type: ignore[misc]


# --- 2. AcousticTargetCurve Tests ---

class TestAcousticTargetCurve:
    def test_valid_target_curve(self) -> None:
        pts = ((20.0, 4.0), (100.0, 2.0), (1000.0, 0.0), (10000.0, -2.0), (20000.0, -4.0))
        target = AcousticTargetCurve(name="HarmanInRoom", points=pts)

        assert target.name == "HarmanInRoom"
        assert len(target.points) == 5
        assert target.frequencies == (20.0, 100.0, 1000.0, 10000.0, 20000.0)
        assert target.magnitudes_db == (4.0, 2.0, 0.0, -2.0, -4.0)

    def test_target_curve_properties_and_equality(self) -> None:
        pts = ((100.0, 0.0), (1000.0, 6.0))
        target1 = AcousticTargetCurve(name="SimpleSlope", points=pts)
        target2 = AcousticTargetCurve(name="SimpleSlope", points=((100.0, 0.0), (1000.0, 6.0)))

        assert target1.num_points == 2
        assert target1.frequencies == (100.0, 1000.0)
        assert target1.magnitudes_db == (0.0, 6.0)
        assert target1 == target2
        assert not hasattr(target1, "evaluate_at")

    def test_non_monotonic_points_rejected(self) -> None:
        pts = ((100.0, 0.0), (50.0, 2.0))
        with pytest.raises(InvalidSpecificationError, match="strictly monotonically increasing"):
            AcousticTargetCurve(name="BadTarget", points=pts)

    def test_immutability(self) -> None:
        target = AcousticTargetCurve(name="Target", points=((20.0, 0.0), (20000.0, 0.0)))
        with pytest.raises(FrozenInstanceError):
            target.name = "Mutated"  # type: ignore[misc]


# --- 3. EqualizerBudget Tests ---

class TestEqualizerBudget:
    def test_valid_budget(self) -> None:
        budget = EqualizerBudget(max_bands=5, max_boost_db=4.0, max_cut_db=10.0, min_q=0.7, max_q=8.0)
        assert budget.max_bands == 5
        assert budget.max_boost_db == 4.0
        assert budget.max_cut_db == 10.0
        assert budget.min_q == 0.7
        assert budget.max_q == 8.0

    def test_invalid_bounds_rejected(self) -> None:
        with pytest.raises(InvalidSpecificationError, match="max_bands"):
            EqualizerBudget(max_bands=0)

        with pytest.raises(InvalidSpecificationError, match="max_boost_db"):
            EqualizerBudget(max_bands=4, max_boost_db=-2.0)

        with pytest.raises(InvalidSpecificationError, match="max_q"):
            EqualizerBudget(max_bands=4, min_q=5.0, max_q=2.0)

    def test_immutability(self) -> None:
        budget = EqualizerBudget(max_bands=6)
        with pytest.raises(FrozenInstanceError):
            budget.max_bands = 8  # type: ignore[misc]


# --- 4. TransducerLimits Tests ---

class TestTransducerLimits:
    def test_valid_limits(self) -> None:
        limits = TransducerLimits(x_max_mm=5.5, p_max_rms_watts=60.0, f_s_hz=42.0, r_e_ohms=6.2)
        assert limits.x_max_mm == 5.5
        assert limits.p_max_rms_watts == 60.0
        assert limits.f_s_hz == 42.0
        assert limits.r_e_ohms == 6.2

    def test_non_positive_limit_rejected(self) -> None:
        with pytest.raises(InvalidSpecificationError, match="x_max_mm"):
            TransducerLimits(x_max_mm=0.0, p_max_rms_watts=60.0, f_s_hz=42.0, r_e_ohms=6.2)

    def test_immutability(self) -> None:
        limits = TransducerLimits(x_max_mm=4.0, p_max_rms_watts=50.0, f_s_hz=40.0, r_e_ohms=6.0)
        with pytest.raises(FrozenInstanceError):
            limits.p_max_rms_watts = 100.0  # type: ignore[misc]


# --- 5. DriverProfile Tests ---

class TestDriverProfile:
    def test_valid_driver_profile(self) -> None:
        limits = TransducerLimits(x_max_mm=6.0, p_max_rms_watts=80.0, f_s_hz=35.0, r_e_ohms=5.8)
        driver = DriverProfile(
            name="ScanSpeak_18W",
            role=DriverRole.WOOFER,
            sensitivity_db=87.5,
            depth_offset_mm=22.0,
            polarity_inverted=False,
            nominal_impedance_ohms=8.0,
            limits=limits,
        )
        assert driver.name == "ScanSpeak_18W"
        assert driver.role == DriverRole.WOOFER
        assert driver.sensitivity_db == 87.5
        assert driver.depth_offset_mm == 22.0
        assert not driver.polarity_inverted
        assert driver.nominal_impedance_ohms == 8.0
        assert driver.limits == limits

    def test_driver_role_string_parsing(self) -> None:
        driver = DriverProfile(name="Tweeter", role="tweeter", sensitivity_db=91.0)  # type: ignore[arg-type]
        assert driver.role == DriverRole.TWEETER

    def test_invalid_driver_name_rejected(self) -> None:
        with pytest.raises(InvalidProfileError, match="non-empty string"):
            DriverProfile(name="", role=DriverRole.MIDRANGE, sensitivity_db=88.0)

    def test_immutability(self) -> None:
        driver = DriverProfile(name="Woofer", role=DriverRole.WOOFER, sensitivity_db=88.0)
        with pytest.raises(FrozenInstanceError):
            driver.sensitivity_db = 90.0  # type: ignore[misc]


# --- 6. EnclosureProfile Tests ---

class TestEnclosureProfile:
    def test_valid_sealed_enclosure(self) -> None:
        enc = EnclosureProfile(enclosure_type=EnclosureType.SEALED, volume_liters=25.0)
        assert enc.enclosure_type == EnclosureType.SEALED
        assert enc.volume_liters == 25.0
        assert enc.tuning_frequency_hz is None

    def test_valid_vented_enclosure(self) -> None:
        enc = EnclosureProfile(
            enclosure_type=EnclosureType.VENTED,
            volume_liters=45.0,
            tuning_frequency_hz=38.0,
        )
        assert enc.enclosure_type == EnclosureType.VENTED
        assert enc.volume_liters == 45.0
        assert enc.tuning_frequency_hz == 38.0

    def test_vented_without_tuning_rejected(self) -> None:
        with pytest.raises(InvalidProfileError, match="tuning_frequency_hz is required"):
            EnclosureProfile(enclosure_type=EnclosureType.VENTED, volume_liters=45.0)

    def test_invalid_volume_rejected(self) -> None:
        with pytest.raises(InvalidProfileError, match="volume_liters"):
            EnclosureProfile(enclosure_type=EnclosureType.SEALED, volume_liters=-10.0)

    def test_immutability(self) -> None:
        enc = EnclosureProfile(enclosure_type=EnclosureType.SEALED, volume_liters=15.0)
        with pytest.raises(FrozenInstanceError):
            enc.volume_liters = 20.0  # type: ignore[misc]


# --- 7. FrequencyResponseData & Array Ownership Tests ---

class TestFrequencyResponseData:
    def test_valid_frequency_response(self) -> None:
        freqs = np.array([20.0, 100.0, 1000.0, 10000.0, 20000.0], dtype=np.float64)
        mags = np.array([75.0, 82.0, 86.5, 85.0, 81.0], dtype=np.float64)
        phases = np.array([0.0, -0.2, -1.1, -2.4, -3.1], dtype=np.float64)

        frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags, phase_rad=phases)

        assert frd.num_points == 5
        assert frd.frequency_range == (20.0, 20000.0)
        np.testing.assert_array_equal(frd.frequencies_hz, freqs)
        np.testing.assert_array_equal(frd.magnitude_db, mags)
        assert frd.phase_rad is not None
        np.testing.assert_array_equal(frd.phase_rad, phases)

    def test_defensive_copying_and_array_immutability(self) -> None:
        source_freqs = np.array([100.0, 200.0, 500.0], dtype=np.float64)
        source_mags = np.array([80.0, 82.0, 84.0], dtype=np.float64)

        frd = FrequencyResponseData(frequencies_hz=source_freqs, magnitude_db=source_mags)

        # 1. Mutating source array must NOT affect frd
        source_freqs[0] = 9999.0
        source_mags[0] = -999.0
        assert frd.frequencies_hz[0] == 100.0
        assert frd.magnitude_db[0] == 80.0

        # 2. Mutating frd internal array must fail because array flags are write=False
        with pytest.raises(ValueError, match="read-only"):
            frd.frequencies_hz[0] = 50.0

        with pytest.raises(ValueError, match="read-only"):
            frd.magnitude_db[0] = 50.0

        # 3. Mutating frd dataclass field must fail
        with pytest.raises(FrozenInstanceError):
            frd.magnitude_db = np.array([1.0, 2.0, 3.0])  # type: ignore[misc]

    def test_length_mismatch_rejected(self) -> None:
        freqs = np.array([100.0, 200.0, 500.0])
        mags = np.array([80.0, 82.0])  # Only 2 points
        with pytest.raises(InvalidMeasurementError, match="length"):
            FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

    def test_non_monotonic_frequency_rejected(self) -> None:
        freqs = np.array([100.0, 50.0, 500.0])
        mags = np.array([80.0, 82.0, 84.0])
        with pytest.raises(InvalidMeasurementError, match="strictly monotonically increasing"):
            FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)


# --- 8. ImpulseResponseData & Array Ownership Tests ---

class TestImpulseResponseData:
    def test_valid_impulse_response_automatic_peak(self) -> None:
        # Construct synthetic impulse with peak at index 10
        samples = np.zeros(64, dtype=np.float32)
        samples[10] = 0.95
        samples[11] = -0.4
        samples[12] = 0.1

        ir = ImpulseResponseData(samples=samples, sample_rate=48000)

        assert ir.num_samples == 64
        assert ir.sample_rate == 48000
        assert ir.peak_index == 10
        assert pytest.approx(ir.duration_seconds) == 64 / 48000
        assert pytest.approx(ir.time_to_peak_seconds) == 10 / 48000

    def test_explicit_peak_index(self) -> None:
        samples = np.ones(32, dtype=np.float32)
        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=5)
        assert ir.peak_index == 5

    def test_out_of_bounds_peak_rejected(self) -> None:
        samples = np.ones(16, dtype=np.float32)
        with pytest.raises(InvalidMeasurementError, match="out of bounds"):
            ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=20)

    def test_defensive_copying_and_array_immutability(self) -> None:
        source_samples = np.array([0.1, 0.9, -0.2], dtype=np.float32)
        ir = ImpulseResponseData(samples=source_samples, sample_rate=48000)

        # 1. Mutating source does not affect object
        source_samples[0] = 55.0
        assert ir.samples[0] == pytest.approx(0.1, rel=1e-5)

        # 2. Mutating internal array fails (read-only)
        with pytest.raises(ValueError, match="read-only"):
            ir.samples[0] = 0.0

        # 3. Mutating dataclass attribute fails
        with pytest.raises(FrozenInstanceError):
            ir.sample_rate = 96000  # type: ignore[misc]
