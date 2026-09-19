"""Independent analytical tests for Phase 4D-2 Multi-Way Complex Acoustic Summation.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/phases/PHASE_4D_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    complex_response_to_frequency_response_data,
)
from acoustiforge.contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
)
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.nodes.biquad import BiquadCoefficients


# ==============================================================================
# 1. Independent Analytical Phasor Goldens (Goldens A, B, C)
# ==============================================================================

def test_golden_a_in_phase_summation_zero_degrees() -> None:
    """GOLDEN A: In-phase summation (0 deg) of two identical unit amplitude branches.

    Analytically:
        H1 = 1.0 + 0j
        H2 = 1.0 + 0j
        H_total = 2.0 + 0j
        |H_total| = 2.0
        M_total = 20 * log10(2.0) = 6.020599913279624... dB
        Phase = 0.0 rad
    """
    freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
    h1 = np.ones(3, dtype=np.complex128)
    h2 = np.ones(3, dtype=np.complex128)

    summed_frd = calculate_acoustic_complex_summation([h1, h2], freqs)

    expected_db = 20.0 * math.log10(2.0)  # 6.020599913279624...
    assert np.allclose(summed_frd.magnitude_db, expected_db, atol=1e-12)
    assert np.allclose(summed_frd.phase_rad, 0.0, atol=1e-12)


def test_golden_b_quadrature_summation_ninety_degrees() -> None:
    """GOLDEN B: Quadrature summation (90 deg) of two unit amplitude branches.

    Analytically:
        H1 = 1.0 + 0j
        H2 = 0.0 + 1.0j
        H_total = 1.0 + 1.0j
        |H_total| = sqrt(2) ≈ 1.4142135623730951
        M_total = 20 * log10(sqrt(2)) = 10 * log10(2) = 3.010299956639812... dB
        Phase = pi / 4 ≈ 0.7853981633974483 rad
    """
    freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
    h1 = np.ones(3, dtype=np.complex128)
    h2 = np.full(3, 1j, dtype=np.complex128)

    summed_frd = calculate_acoustic_complex_summation([h1, h2], freqs)

    expected_db = 10.0 * math.log10(2.0)  # 3.010299956639812...
    expected_phase = math.pi / 4.0        # 0.7853981633974483...
    assert np.allclose(summed_frd.magnitude_db, expected_db, atol=1e-12)
    assert np.allclose(summed_frd.phase_rad, expected_phase, atol=1e-12)


def test_golden_c_destructive_cancellation_one_eighty_degrees() -> None:
    """GOLDEN C: Destructive cancellation (180 deg) of two equal opposite branches.

    Analytically:
        H1 = 1.0 + 0j
        H2 = -1.0 + 0j
        H_total = 0.0 + 0j
        |H_total| = 0.0 (residual <= 1e-15)
        M_total = 20 * log10(1e-12) = -240.0 dB (floor)
    """
    freqs = np.array([100.0, 1000.0, 10000.0], dtype=np.float64)
    h1 = np.ones(3, dtype=np.complex128)
    h2 = np.full(3, -1.0 + 0j, dtype=np.complex128)

    summed_frd = calculate_acoustic_complex_summation([h1, h2], freqs)

    # Floor must be exactly -240.0 dB
    assert np.allclose(summed_frd.magnitude_db, -240.0, atol=1e-12)


# ==============================================================================
# 2. Branch Response: Gain, Delay, and Filtering
# ==============================================================================

def test_branch_response_positive_and_negative_gain() -> None:
    """Verify linear gain application across positive and negative dB gains."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    driver_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.array([0.0, 0.0]))

    # +6.020599913279624 dB -> linear gain 2.0
    g_pos_db = 20.0 * math.log10(2.0)
    h_pos = calculate_branch_complex_response(driver_frd, gain_db=g_pos_db)
    assert np.allclose(np.abs(h_pos), 2.0, atol=1e-12)

    # -6.020599913279624 dB -> linear gain 0.5
    g_neg_db = 20.0 * math.log10(0.5)
    h_neg = calculate_branch_complex_response(driver_frd, gain_db=g_neg_db)
    assert np.allclose(np.abs(h_neg), 0.5, atol=1e-12)


def test_branch_response_frequency_domain_delay() -> None:
    """Verify acoustic delay phase rotation exp(-j * 2*pi * f * tau)."""
    fs = 48000
    # Evaluate at f = fs/4 (12000 Hz) and f = fs/2 (24000 Hz)
    freqs = np.array([12000.0, 24000.0], dtype=np.float64)
    driver_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(2), phase_rad=np.zeros(2))

    # Delay tau = 1 sample = 1 / fs seconds
    tau_1sample = 1.0 / float(fs)
    h_branch = calculate_branch_complex_response(driver_frd, delay_seconds=tau_1sample)

    # At f = 12000 Hz: omega*tau = 2*pi*(fs/4)*(1/fs) = pi/2 -> exp(-j*pi/2) = -j
    assert np.isclose(h_branch[0].real, 0.0, atol=1e-12)
    assert np.isclose(h_branch[0].imag, -1.0, atol=1e-12)
    assert np.isclose(np.angle(h_branch[0]), -math.pi / 2.0, atol=1e-12)

    # At f = 24000 Hz: omega*tau = 2*pi*(fs/2)*(1/fs) = pi -> exp(-j*pi) = -1
    assert np.isclose(h_branch[1].real, -1.0, atol=1e-12)
    assert np.isclose(h_branch[1].imag, 0.0, atol=1e-12)
    assert np.isclose(abs(np.angle(h_branch[1])), math.pi, atol=1e-12)


def test_branch_response_composite_driver_filter_gain_delay() -> None:
    """Verify composite branch response H_driver * H_filter * gain * delay against hand calculation."""
    fs = 48000
    f0 = 6000.0  # fs / 8 -> omega = pi / 4
    freqs = np.array([f0, f0 * 2.0], dtype=np.float64)

    # Driver: magnitude = +6.0206 dB (linear 2.0), phase = +pi/4 rad -> H_driver = 2 * exp(j*pi/4) = sqrt(2) + j*sqrt(2)
    m_driver = 20.0 * math.log10(2.0)
    phi_driver = math.pi / 4.0
    driver_frd = FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=np.array([m_driver, m_driver]),
        phase_rad=np.array([phi_driver, phi_driver]),
    )

    # Filter: Gain biquad b0 = 1.5 -> H_filter = 1.5 + 0j
    filter_bq = BiquadCoefficients(b0=1.5, b1=0.0, b2=0.0, a1=0.0, a2=0.0)

    # Gain: +6.0206 dB -> g = 2.0
    gain_db = 20.0 * math.log10(2.0)

    # Delay: tau = 1 / (4 * f0) -> 2*pi*f0*tau = pi/2 -> exp(-j*pi/2) = -j
    delay_s = 1.0 / (4.0 * f0)

    h_branch = calculate_branch_complex_response(
        driver_response=driver_frd,
        biquads=[filter_bq],
        gain_db=gain_db,
        delay_seconds=delay_s,
        sample_rate=fs,
    )

    # Hand calculation:
    # H_branch = (2 * e^(j*pi/4)) * (1.5) * (2.0) * (e^(-j*pi/2))
    #          = 6.0 * e^(j*(pi/4 - pi/2)) = 6.0 * e^(-j*pi/4)
    #          = 6.0 * (cos(-pi/4) + j*sin(-pi/4)) = 6.0 * (sqrt(2)/2 - j*sqrt(2)/2)
    #          = 3*sqrt(2) - j*3*sqrt(2)
    expected_real = 3.0 * math.sqrt(2.0)
    expected_imag = -3.0 * math.sqrt(2.0)

    assert np.isclose(h_branch[0].real, expected_real, atol=1e-12)
    assert np.isclose(h_branch[0].imag, expected_imag, atol=1e-12)
    assert np.isclose(np.abs(h_branch[0]), 6.0, atol=1e-12)
    assert np.isclose(np.angle(h_branch[0]), -math.pi / 4.0, atol=1e-12)


# ==============================================================================
# 3. Phase Semantics & 4-Quadrant atan2 Testing
# ==============================================================================

@pytest.mark.parametrize(
    "real_val, imag_val, expected_phase_rad",
    [
        (1.0, 1.0, math.pi / 4.0),        # Q1: +45 deg
        (-1.0, 1.0, 3.0 * math.pi / 4.0), # Q2: +135 deg
        (-1.0, -1.0, -3.0 * math.pi / 4.0),# Q3: -135 deg
        (1.0, -1.0, -math.pi / 4.0),      # Q4: -45 deg
        (1.0, 0.0, 0.0),                  # +Real axis: 0 deg
        (0.0, 1.0, math.pi / 2.0),        # +Imag axis: +90 deg
        (-1.0, 0.0, math.pi),             # -Real axis: +180 deg
        (0.0, -1.0, -math.pi / 2.0),      # -Imag axis: -90 deg
    ],
)
def test_phase_quadrants_atan2(real_val: float, imag_val: float, expected_phase_rad: float) -> None:
    """Verify that phase calculation uses atan2(Im, Re) strictly mapping into [-pi, pi]."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    h_complex = np.array([complex(real_val, imag_val), complex(real_val, imag_val)], dtype=np.complex128)

    frd = complex_response_to_frequency_response_data(freqs, h_complex)
    assert frd.phase_rad is not None
    assert np.allclose(frd.phase_rad, expected_phase_rad, atol=1e-12)



# ==============================================================================
# 4. Multi-Branch 3-Way Vector Summation Test
# ==============================================================================

def test_three_branch_vector_summation() -> None:
    """Verify true vector complex summation across 3 branches against independent phasor calculation.

    Branches:
        H1 = 1.0 + 0j
        H2 = 0.0 + 2.0j
        H3 = -2.0 - 1.0j

    Vector Sum:
        H_total = (1 + 0 - 2) + j*(0 + 2 - 1) = -1.0 + 1.0j
        |H_total| = sqrt((-1)^2 + 1^2) = sqrt(2) ≈ 1.41421356
        M_total = 20 * log10(sqrt(2)) = 3.0102999566... dB
        Phase = atan2(1, -1) = 3*pi/4 rad (135 deg)
    """
    freqs = np.array([500.0, 1000.0], dtype=np.float64)
    h1 = np.full(2, 1.0 + 0j, dtype=np.complex128)
    h2 = np.full(2, 0.0 + 2.0j, dtype=np.complex128)
    h3 = np.full(2, -2.0 - 1.0j, dtype=np.complex128)

    summed_frd = calculate_acoustic_complex_summation([h1, h2, h3], freqs)

    expected_db = 10.0 * math.log10(2.0)
    expected_phase = 3.0 * math.pi / 4.0

    assert np.allclose(summed_frd.magnitude_db, expected_db, atol=1e-12)
    assert np.allclose(summed_frd.phase_rad, expected_phase, atol=1e-12)


# ==============================================================================
# 5. Input Validation & Error Handling
# ==============================================================================

def test_complex_summation_validation_errors() -> None:
    """Verify input validation and error raising for invalid summation inputs."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    h_valid = np.ones(2, dtype=np.complex128)
    h_wrong_len = np.ones(3, dtype=np.complex128)
    h_nan = np.array([1.0 + 0j, float("nan") + 1j], dtype=np.complex128)

    # Empty branch list
    with pytest.raises(InvalidParameterError, match="non-empty Sequence"):
        calculate_acoustic_complex_summation([], freqs)

    # Length mismatch between branch and frequencies
    with pytest.raises(InvalidParameterError, match="length"):
        calculate_acoustic_complex_summation([h_valid, h_wrong_len], freqs)

    # Non-finite complex values (NaN/Inf)
    with pytest.raises(InvalidParameterError, match="non-finite"):
        calculate_acoustic_complex_summation([h_valid, h_nan], freqs)

    # Invalid branch response type
    with pytest.raises(InvalidParameterError, match="np.ndarray"):
        calculate_acoustic_complex_summation(["not_an_array"], freqs)  # type: ignore[list-item]


def test_calculate_branch_complex_response_validation_errors() -> None:
    """Verify input validation for branch complex response calculation."""
    freqs = np.array([100.0, 1000.0], dtype=np.float64)
    driver_frd = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=np.zeros(2))
    bq = BiquadCoefficients(b0=1.0, b1=0.0, b2=0.0, a1=0.0, a2=0.0)

    # Missing sample_rate when biquads specified
    with pytest.raises(InvalidParameterError, match="sample_rate is required"):
        calculate_branch_complex_response(driver_frd, biquads=[bq], sample_rate=None)

    # Negative delay
    with pytest.raises(InvalidParameterError, match="delay_seconds"):
        calculate_branch_complex_response(driver_frd, delay_seconds=-0.001)

    # Non-finite gain
    with pytest.raises(InvalidParameterError, match="gain_db"):
        calculate_branch_complex_response(driver_frd, gain_db=float("nan"))
