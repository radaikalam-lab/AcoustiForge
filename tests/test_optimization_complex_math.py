"""Unit tests for Phase 4D-1 Complex Response and Frequency Grid Validation Mathematics.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/phases/PHASE_4D_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.crossover import _synthesize_second_order_butterworth_section
from acoustiforge.acoustic_math.optimization import (
    driver_response_to_complex,
    evaluate_biquad_complex_response,
    validate_frequency_grid_matching,
)
from acoustiforge.contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
    UnstableFilterError,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    InvalidSpecificationError,
    OptimizationSpecification,
)
from acoustiforge.nodes.biquad import BiquadCoefficients


# ==============================================================================
# 1. OptimizationSpecification Domain Value Object Tests
# ==============================================================================

def test_optimization_specification_valid_construction() -> None:
    """Verify valid construction of OptimizationSpecification with default and custom arguments."""
    target = AcousticTargetCurve(
        name="FlatTarget",
        points=((20.0, 0.0), (1000.0, 0.0), (20000.0, 0.0)),
    )
    spec = OptimizationSpecification(
        target_curve=target,
        crossover_family=CrossoverFamily.LINKWITZ_RILEY,
        crossover_order=4,
        frequency_range_hz=(20.0, 20000.0),
        crossover_bounds_hz=(500.0, 5000.0),
    )

    assert spec.target_curve.name == "FlatTarget"
    assert spec.crossover_family == CrossoverFamily.LINKWITZ_RILEY
    assert spec.crossover_order == 4
    assert spec.frequency_range_hz == (20.0, 20000.0)
    assert spec.crossover_bounds_hz == (500.0, 5000.0)
    assert spec.gain_bounds_db == (-12.0, 12.0)
    assert spec.delay_bounds_seconds == (0.0, 0.005)
    assert spec.ripple_weight == 0.0
    assert spec.delay_weight == 0.0
    assert spec.max_iterations == 50
    assert spec.convergence_tolerance_db == 1e-5


def test_optimization_specification_validation_failures() -> None:
    """Verify that invalid parameters in OptimizationSpecification raise InvalidSpecificationError."""
    target = AcousticTargetCurve(name="T", points=((20.0, 0.0), (20000.0, 0.0)))

    # Invalid target_curve
    with pytest.raises(InvalidSpecificationError, match="target_curve"):
        OptimizationSpecification(
            target_curve="not_a_target_curve",  # type: ignore[arg-type]
            crossover_family=CrossoverFamily.BUTTERWORTH,
            crossover_order=2,
            frequency_range_hz=(20.0, 20000.0),
            crossover_bounds_hz=(500.0, 4000.0),
        )

    # Invalid crossover family
    with pytest.raises(InvalidSpecificationError, match="Unsupported crossover family"):
        OptimizationSpecification(
            target_curve=target,
            crossover_family="chebyshev",  # type: ignore[arg-type]
            crossover_order=2,
            frequency_range_hz=(20.0, 20000.0),
            crossover_bounds_hz=(500.0, 4000.0),
        )

    # Invalid order (must be 2, 4, 8)
    with pytest.raises(InvalidSpecificationError, match="Unsupported crossover order"):
        OptimizationSpecification(
            target_curve=target,
            crossover_family=CrossoverFamily.BUTTERWORTH,
            crossover_order=3,
            frequency_range_hz=(20.0, 20000.0),
            crossover_bounds_hz=(500.0, 4000.0),
        )

    # Inverted frequency range
    with pytest.raises(InvalidSpecificationError, match="frequency_range_hz"):
        OptimizationSpecification(
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(20000.0, 20.0),
            crossover_bounds_hz=(500.0, 4000.0),
        )

    # Inverted crossover bounds
    with pytest.raises(InvalidSpecificationError, match="crossover_bounds_hz"):
        OptimizationSpecification(
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(20.0, 20000.0),
            crossover_bounds_hz=(4000.0, 500.0),
        )

    # Negative delay bounds
    with pytest.raises(InvalidSpecificationError, match="delay_bounds_seconds"):
        OptimizationSpecification(
            target_curve=target,
            crossover_family=CrossoverFamily.LINKWITZ_RILEY,
            crossover_order=4,
            frequency_range_hz=(20.0, 20000.0),
            crossover_bounds_hz=(500.0, 4000.0),
            delay_bounds_seconds=(-0.001, 0.005),
        )


# ==============================================================================
# 2. Frequency Grid Validation Tests
# ==============================================================================

def test_validate_frequency_grid_matching_success() -> None:
    """Verify that identical frequency grids pass validation cleanly."""
    freqs = np.array([100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0], dtype=np.float64)
    r1 = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(7))
    r2 = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.ones(7), phase_rad=np.zeros(7))

    grid = validate_frequency_grid_matching([r1, r2], sample_rate=48000)
    assert np.array_equal(grid, freqs)


def test_validate_frequency_grid_matching_errors() -> None:
    """Verify that frequency grid mismatches and invalid inputs raise appropriate errors."""
    f1 = np.array([100.0, 200.0, 500.0], dtype=np.float64)
    f2 = np.array([100.0, 200.0, 500.0, 1000.0], dtype=np.float64)
    f3 = np.array([100.0, 200.0, 500.1], dtype=np.float64)

    r1 = FrequencyResponseData(frequencies_hz=f1, magnitude_db=np.zeros(3))
    r2 = FrequencyResponseData(frequencies_hz=f2, magnitude_db=np.zeros(4))
    r3 = FrequencyResponseData(frequencies_hz=f3, magnitude_db=np.zeros(3))

    # Empty list
    with pytest.raises(InvalidParameterError, match="non-empty Sequence"):
        validate_frequency_grid_matching([])

    # Length mismatch
    with pytest.raises(InvalidParameterError, match="point count mismatch"):
        validate_frequency_grid_matching([r1, r2])

    # Value mismatch
    with pytest.raises(InvalidParameterError, match="differ by more than 1e-6 Hz"):
        validate_frequency_grid_matching([r1, r3])

    # Invalid sample rate
    with pytest.raises(InvalidSampleRateError):
        validate_frequency_grid_matching([r1], sample_rate=0)

    # Exceeds Nyquist limit (sample_rate=800 -> Nyquist=400, f1 max is 500)
    with pytest.raises(InvalidParameterError, match="Nyquist limit"):
        validate_frequency_grid_matching([r1], sample_rate=800)


# ==============================================================================
# 3. Driver Response to Complex Tests
# ==============================================================================

def test_driver_response_to_complex_with_phase() -> None:
    """Verify exact complex phasor conversion for magnitude and phase."""
    freqs = np.array([100.0, 1000.0, 5000.0], dtype=np.float64)
    # Magnitudes: 0 dB (1.0), +6.020599913 dB (2.0), -6.020599913 dB (0.5)
    mag_db = np.array([0.0, 20.0 * math.log10(2.0), 20.0 * math.log10(0.5)], dtype=np.float64)
    # Phases: 0 rad, +pi/2 rad, +pi rad
    phase_rad = np.array([0.0, math.pi / 2.0, math.pi], dtype=np.float64)

    resp = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mag_db, phase_rad=phase_rad)
    complex_h = driver_response_to_complex(resp)

    # Point 0: 1.0 * e^(j*0) = 1.0 + 0j
    assert np.isclose(complex_h[0].real, 1.0, atol=1e-12)
    assert np.isclose(complex_h[0].imag, 0.0, atol=1e-12)

    # Point 1: 2.0 * e^(j*pi/2) = 0.0 + 2.0j
    assert np.isclose(complex_h[1].real, 0.0, atol=1e-12)
    assert np.isclose(complex_h[1].imag, 2.0, atol=1e-12)

    # Point 2: 0.5 * e^(j*pi) = -0.5 + 0j
    assert np.isclose(complex_h[2].real, -0.5, atol=1e-12)
    assert np.isclose(complex_h[2].imag, 0.0, atol=1e-12)


def test_driver_response_to_complex_without_phase() -> None:
    """Verify that None phase defaults to zero phase (purely real complex phasors)."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    mag_db = np.array([0.0, 6.0], dtype=np.float64)

    resp = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mag_db, phase_rad=None)
    complex_h = driver_response_to_complex(resp)

    assert complex_h.dtype == np.complex128
    assert np.all(complex_h.imag == 0.0)
    assert np.allclose(complex_h.real, 10.0 ** (mag_db / 20.0), atol=1e-12)


# ==============================================================================
# 4. Biquad Complex Frequency Response Tests
# ==============================================================================

def test_evaluate_biquad_complex_response_identities() -> None:
    """Verify analytical frequency response identities for standard biquads."""
    fs = 48000
    freqs = np.array([0.001, 1000.0, 12000.0, 24000.0], dtype=np.float64)

    # 1. Identity biquad: b0=1, all other coeffs 0 -> H(f) = 1 + 0j everywhere
    identity_bq = BiquadCoefficients(b0=1.0, b1=0.0, b2=0.0, a1=0.0, a2=0.0)
    h_ident = evaluate_biquad_complex_response([identity_bq], freqs, sample_rate=fs)
    assert np.allclose(h_ident, 1.0 + 0j, atol=1e-12)

    # 2. Pure gain biquad: b0=2.5 -> H(f) = 2.5 + 0j everywhere
    gain_bq = BiquadCoefficients(b0=2.5, b1=0.0, b2=0.0, a1=0.0, a2=0.0)
    h_gain = evaluate_biquad_complex_response([gain_bq], freqs, sample_rate=fs)
    assert np.allclose(h_gain, 2.5 + 0j, atol=1e-12)

    # 3. 1-sample delay biquad: b1=1 -> H(f) = e^(-j*omega)
    # At f = 12000 Hz (fs/4), omega = pi/2 -> H = -j
    # At f = 24000 Hz (fs/2), omega = pi -> H = -1
    delay1_bq = BiquadCoefficients(b0=0.0, b1=1.0, b2=0.0, a1=0.0, a2=0.0)
    h_del1 = evaluate_biquad_complex_response([delay1_bq], freqs, sample_rate=fs)
    assert np.isclose(h_del1[2], -1j, atol=1e-12)
    assert np.isclose(h_del1[3], -1.0 + 0j, atol=1e-12)

    # 4. 2-sample delay biquad: b2=1 -> H(f) = e^(-j*2*omega)
    # At f = 12000 Hz (fs/4), 2*omega = pi -> H = -1
    # At f = 24000 Hz (fs/2), 2*omega = 2*pi -> H = +1
    delay2_bq = BiquadCoefficients(b0=0.0, b1=0.0, b2=1.0, a1=0.0, a2=0.0)
    h_del2 = evaluate_biquad_complex_response([delay2_bq], freqs, sample_rate=fs)
    assert np.isclose(h_del2[2], -1.0 + 0j, atol=1e-12)
    assert np.isclose(h_del2[3], 1.0 + 0j, atol=1e-12)


def test_evaluate_biquad_complex_response_butterworth_cutoff() -> None:
    """Verify that a 2nd-order Butterworth LP biquad has exactly -3.0103 dB gain and -90 deg phase at fc."""
    fs = 48000
    fc = 1000.0
    k_tan = math.tan(math.pi * fc / fs)
    q = 1.0 / math.sqrt(2.0)  # Butterworth Q

    lp_bq, hp_bq = _synthesize_second_order_butterworth_section(k_tan, q)

    # Evaluate exactly at fc
    freqs = np.array([fc], dtype=np.float64)
    h_lp = evaluate_biquad_complex_response([lp_bq], freqs, sample_rate=fs)
    h_hp = evaluate_biquad_complex_response([hp_bq], freqs, sample_rate=fs)

    # At crossover frequency fc:
    # |H_lp| = 1/sqrt(2) ≈ 0.707106781
    # 20 log10(|H_lp|) = -3.0102999566 dB
    expected_mag = 1.0 / math.sqrt(2.0)
    assert np.isclose(np.abs(h_lp[0]), expected_mag, atol=1e-6)
    assert np.isclose(np.abs(h_hp[0]), expected_mag, atol=1e-6)

    # Phase at fc for 2nd order Butterworth LP is exactly -90 deg (-pi/2 rad)
    assert np.isclose(np.angle(h_lp[0]), -math.pi / 2.0, atol=1e-6)
    # Phase at fc for 2nd order Butterworth HP is exactly +90 deg (+pi/2 rad)
    assert np.isclose(np.angle(h_hp[0]), math.pi / 2.0, atol=1e-6)


def test_evaluate_biquad_complex_response_cascaded_sections() -> None:
    """Verify that cascaded biquads multiply their complex responses point-by-point."""
    fs = 48000
    freqs = np.array([100.0, 1000.0, 5000.0], dtype=np.float64)

    gain_bq = BiquadCoefficients(b0=2.0, b1=0.0, b2=0.0, a1=0.0, a2=0.0)
    delay_bq = BiquadCoefficients(b0=0.0, b1=1.0, b2=0.0, a1=0.0, a2=0.0)

    h_gain = evaluate_biquad_complex_response([gain_bq], freqs, sample_rate=fs)
    h_del = evaluate_biquad_complex_response([delay_bq], freqs, sample_rate=fs)
    h_cascade = evaluate_biquad_complex_response([gain_bq, delay_bq], freqs, sample_rate=fs)

    assert np.allclose(h_cascade, h_gain * h_del, atol=1e-12)


def test_evaluate_biquad_complex_response_empty_cascade() -> None:
    """Verify that an empty biquad sequence evaluates to unity complex response."""
    fs = 48000
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    h_empty = evaluate_biquad_complex_response([], freqs, sample_rate=fs)

    assert np.allclose(h_empty, 1.0 + 0j, atol=1e-12)


def test_evaluate_biquad_complex_response_unstable_filter() -> None:
    """Verify that a biquad with a pole on the unit circle raises UnstableFilterError."""
    fs = 48000
    # Pole at DC (z = 1): 1 + a1*z^-1 + a2*z^-2 = 0 -> a1 = -2, a2 = 1
    unstable_bq = BiquadCoefficients(b0=1.0, b1=0.0, b2=0.0, a1=-2.0, a2=1.0)
    freqs = np.array([0.0001, 1000.0], dtype=np.float64)

    with pytest.raises(UnstableFilterError, match="near-singular denominator"):
        evaluate_biquad_complex_response([unstable_bq], freqs, sample_rate=fs)


def test_evaluate_biquad_complex_response_invalid_inputs() -> None:
    """Verify error checking on sample rate and frequency inputs."""
    bq = BiquadCoefficients(b0=1.0, b1=0.0, b2=0.0, a1=0.0, a2=0.0)

    with pytest.raises(InvalidSampleRateError):
        evaluate_biquad_complex_response([bq], [100.0], sample_rate=-48000)

    with pytest.raises(InvalidParameterError, match="positive finite"):
        evaluate_biquad_complex_response([bq], [-100.0], sample_rate=48000)

    with pytest.raises(InvalidParameterError, match="Nyquist limit"):
        evaluate_biquad_complex_response([bq], [25000.0], sample_rate=48000)
