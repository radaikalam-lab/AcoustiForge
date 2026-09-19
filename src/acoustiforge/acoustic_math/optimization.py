"""AcoustiForge Multi-Way Optimization and Complex Acoustic Mathematics.

Normative Authority:
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md (CONTRACT-MULTIWAY-OPT-01)
- docs/phases/PHASE_4D_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
from typing import Callable, Optional, Sequence, Union
import numpy as np

from ..contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
    NumericalEvaluationError,
    UnstableFilterError,
)
from ..domain.measurements import FrequencyResponseData
from ..domain.specifications import AcousticTargetCurve
from ..nodes.biquad import BiquadCoefficients
from .target_curve import evaluate_target_curve


def validate_frequency_grid_matching(
    responses: Sequence[FrequencyResponseData],
    sample_rate: Optional[int] = None,
) -> np.ndarray:
    """Validate that all frequency response measurements share an identical frequency grid.

    Normative Invariants:
    1. All elements must be FrequencyResponseData instances.
    2. At least one response must be provided.
    3. All responses must have identical point counts (num_points).
    4. Corresponding frequencies must match point-by-point within 1e-6 Hz tolerance.
    5. Frequencies must be strictly positive and, if sample_rate is provided, <= sample_rate / 2.

    Args:
        responses: Sequence of FrequencyResponseData objects.
        sample_rate: Optional sample rate in Hz to check Nyquist limit.

    Returns:
        The validated common frequency grid as a contiguous 1D float64 np.ndarray.

    Raises:
        InvalidParameterError: If responses are empty, contain invalid types, or have mismatched grids.
        InvalidSampleRateError: If sample_rate is non-positive.
    """
    if not isinstance(responses, (list, tuple)) or len(responses) == 0:
        raise InvalidParameterError("responses must be a non-empty Sequence of FrequencyResponseData.")

    if sample_rate is not None:
        if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    first_resp = responses[0]
    if not isinstance(first_resp, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData instance, got {type(first_resp)!r}.")

    grid = first_resp.frequencies_hz
    if grid.shape[0] == 0:
        raise InvalidParameterError("FrequencyResponseData must contain at least one frequency point.")

    if np.any(grid <= 0.0) or not np.all(np.isfinite(grid)):
        raise InvalidParameterError("All frequencies in grid must be strictly positive and finite.")

    if sample_rate is not None:
        nyquist = sample_rate / 2.0
        if np.any(grid > nyquist):
            raise InvalidParameterError(
                f"Frequencies exceed Nyquist limit ({nyquist:.1f} Hz) for sample rate {sample_rate} Hz."
            )

    for idx, resp in enumerate(responses[1:], start=1):
        if not isinstance(resp, FrequencyResponseData):
            raise InvalidParameterError(f"Expected FrequencyResponseData at index {idx}, got {type(resp)!r}.")
        if resp.num_points != grid.shape[0]:
            raise InvalidParameterError(
                f"Frequency grid point count mismatch at index {idx}: expected {grid.shape[0]}, got {resp.num_points}."
            )
        if not np.allclose(grid, resp.frequencies_hz, atol=1e-6, rtol=0.0):
            raise InvalidParameterError(
                f"Frequency grid values mismatch at index {idx}: frequencies differ by more than 1e-6 Hz."
            )

    return grid


def driver_response_to_complex(response: FrequencyResponseData) -> np.ndarray:
    """Convert a FrequencyResponseData measurement to an array of complex response phasors.

    Normative Equation:
        H(f_i) = 10^(M_i / 20) * exp(j * phi_i)

    If phase_rad is None, phase phi_i is treated as 0.0 radians (yielding real-only phasors).

    Args:
        response: FrequencyResponseData measurement container.

    Returns:
        1D complex128 np.ndarray of complex transfer function values.

    Raises:
        InvalidParameterError: If response is not a valid FrequencyResponseData instance.
    """
    if not isinstance(response, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData instance, got {type(response)!r}.")

    mag_linear = 10.0 ** (response.magnitude_db / 20.0)

    if response.phase_rad is None:
        return mag_linear.astype(np.complex128)

    cos_phi = np.cos(response.phase_rad)
    sin_phi = np.sin(response.phase_rad)
    return mag_linear * (cos_phi + 1j * sin_phi)


def evaluate_biquad_complex_response(
    biquads: Sequence[BiquadCoefficients],
    frequencies_hz: Union[Sequence[float], np.ndarray],
    sample_rate: int,
) -> np.ndarray:
    """Evaluate the exact complex frequency response of a biquad cascade in the frequency domain.

    Normative Equation for a single biquad:
        H(f) = (b0 + b1*z^-1 + b2*z^-2) / (1 + a1*z^-1 + a2*z^-2)
        where z = exp(j * 2*pi*f / fs)

    For a cascade of M biquad sections:
        H_cascade(f) = prod_{m=1}^M H_m(f)
        If M == 0, returns array of 1.0 + 0j.

    Numerical Singularity Protection:
        If denominator magnitude |D(f)| < 1e-12 at any evaluated frequency, raises UnstableFilterError.
        The denominator is NEVER silently clamped or altered.

    Args:
        biquads: Sequence of BiquadCoefficients normalized filter sections.
        frequencies_hz: Sequence or 1D array of evaluation frequencies in Hz.
        sample_rate: Audio sampling frequency in Hz.

    Returns:
        1D complex128 np.ndarray of cascaded complex frequency responses.

    Raises:
        InvalidSampleRateError: If sample_rate is non-positive.
        InvalidParameterError: If frequencies are non-positive, non-finite, or exceed Nyquist.
        UnstableFilterError: If a biquad denominator magnitude falls below 1e-12.
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    if isinstance(frequencies_hz, (list, tuple, np.ndarray)):
        freqs = np.asarray(frequencies_hz, dtype=np.float64)
    else:
        raise InvalidParameterError(f"frequencies_hz must be a Sequence or ndarray, got {type(frequencies_hz)!r}.")

    if freqs.ndim != 1 or freqs.shape[0] == 0:
        raise InvalidParameterError(f"frequencies_hz must be a non-empty 1D array, got shape {freqs.shape}.")

    if np.any(freqs <= 0.0) or not np.all(np.isfinite(freqs)):
        raise InvalidParameterError("All frequencies must be positive finite numbers.")

    nyquist = sample_rate / 2.0
    if np.any(freqs > nyquist):
        raise InvalidParameterError(f"All frequencies must be <= Nyquist limit ({nyquist:.1f} Hz).")

    if not isinstance(biquads, (list, tuple)):
        raise InvalidParameterError(f"biquads must be a Sequence of BiquadCoefficients, got {type(biquads)!r}.")

    num_pts = freqs.shape[0]
    total_h = np.ones(num_pts, dtype=np.complex128)

    if len(biquads) == 0:
        return total_h

    omega = 2.0 * math.pi * freqs / float(sample_rate)
    z_inv1 = np.cos(omega) - 1j * np.sin(omega)
    z_inv2 = np.cos(2.0 * omega) - 1j * np.sin(2.0 * omega)

    for idx, bq in enumerate(biquads):
        if not isinstance(bq, BiquadCoefficients):
            raise InvalidParameterError(f"Expected BiquadCoefficients at index {idx}, got {type(bq)!r}.")

        num = bq.b0 + bq.b1 * z_inv1 + bq.b2 * z_inv2
        den = 1.0 + bq.a1 * z_inv1 + bq.a2 * z_inv2

        min_den_mag = float(np.min(np.abs(den)))
        if min_den_mag < 1e-12:
            raise UnstableFilterError(
                f"Biquad section {idx} has near-singular denominator with minimum magnitude {min_den_mag:.2e} < 1e-12."
            )

        h_section = num / den
        total_h *= h_section

    return total_h


def calculate_branch_complex_response(
    driver_response: FrequencyResponseData,
    biquads: Optional[Sequence[BiquadCoefficients]] = None,
    gain_db: float = 0.0,
    delay_seconds: float = 0.0,
    sample_rate: Optional[int] = None,
) -> np.ndarray:
    """Evaluate the complete complex frequency response for an individual acoustic branch.

    Normative Equation:
        H_branch(f) = H_driver(f) * H_filter(f) * 10^(G / 20) * exp(-j * 2 * pi * f * tau)

    Args:
        driver_response: FrequencyResponseData measurement container.
        biquads: Optional sequence of BiquadCoefficients normalized filter stages.
        gain_db: Branch sensitivity adjustment gain in dB (default: 0.0).
        delay_seconds: Branch acoustic alignment delay in seconds (default: 0.0).
        sample_rate: Audio sample rate in Hz (required if biquads are specified).

    Returns:
        1D complex128 np.ndarray of branch complex frequency responses.

    Raises:
        InvalidParameterError: If inputs are invalid or non-finite.
        InvalidSampleRateError: If sample_rate is required but non-positive.
    """
    if not isinstance(driver_response, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData, got {type(driver_response)!r}.")

    if not isinstance(gain_db, (int, float)) or isinstance(gain_db, bool) or not math.isfinite(gain_db):
        raise InvalidParameterError(f"gain_db must be a finite float, got {gain_db!r}.")

    if (
        not isinstance(delay_seconds, (int, float))
        or isinstance(delay_seconds, bool)
        or not math.isfinite(delay_seconds)
        or delay_seconds < 0.0
    ):
        raise InvalidParameterError(f"delay_seconds must be a non-negative finite float, got {delay_seconds!r}.")

    h_driver = driver_response_to_complex(driver_response)
    freqs = driver_response.frequencies_hz

    if biquads is not None and len(biquads) > 0:
        if sample_rate is None:
            raise InvalidParameterError("sample_rate is required when biquads are specified.")
        h_filter = evaluate_biquad_complex_response(biquads, freqs, sample_rate)
    else:
        h_filter = np.ones(freqs.shape[0], dtype=np.complex128)

    # Linear gain
    g_linear = 10.0 ** (float(gain_db) / 20.0)

    # Delay phase rotation: exp(-j * 2 * pi * f * tau)
    if delay_seconds == 0.0:
        h_delay = 1.0 + 0j
    else:
        omega_tau = 2.0 * math.pi * freqs * float(delay_seconds)
        h_delay = np.cos(omega_tau) - 1j * np.sin(omega_tau)

    h_branch = h_driver * h_filter * g_linear * h_delay
    return h_branch


def complex_response_to_frequency_response_data(
    frequencies_hz: Union[Sequence[float], np.ndarray],
    complex_response: Union[Sequence[complex], np.ndarray],
) -> FrequencyResponseData:
    """Convert an array of complex response phasors to a canonical FrequencyResponseData container.

    Normative Conversion:
        M_total(f) = 20 * log10(max(|H_total(f)|, 1e-12))
        phase_rad(f) = atan2(Im(H_total(f)), Re(H_total(f))) in [-pi, pi]

    Floor Policy:
        The magnitude floor is strictly -240.0 dB (corresponding to 1e-12 magnitude).

    Args:
        frequencies_hz: 1D array or sequence of positive frequencies in Hz.
        complex_response: 1D array or sequence of complex128 response phasors.

    Returns:
        FrequencyResponseData with computed magnitude_db and phase_rad.

    Raises:
        InvalidParameterError: If shapes mismatch or arrays contain non-finite numbers.
    """
    if isinstance(frequencies_hz, (list, tuple, np.ndarray)):
        freqs = np.asarray(frequencies_hz, dtype=np.float64)
    else:
        raise InvalidParameterError(f"frequencies_hz must be a Sequence or ndarray, got {type(frequencies_hz)!r}.")

    if isinstance(complex_response, (list, tuple, np.ndarray)):
        h_arr = np.asarray(complex_response, dtype=np.complex128)
    else:
        raise InvalidParameterError(f"complex_response must be a Sequence or ndarray, got {type(complex_response)!r}.")

    if freqs.ndim != 1 or freqs.shape[0] == 0:
        raise InvalidParameterError("frequencies_hz must be a non-empty 1D array.")
    if h_arr.ndim != 1 or h_arr.shape[0] != freqs.shape[0]:
        raise InvalidParameterError(
            f"Shape mismatch: frequencies has {freqs.shape[0]} points, complex_response has {h_arr.shape[0]}."
        )
    if not np.all(np.isfinite(h_arr)):
        raise InvalidParameterError("complex_response must contain finite complex values.")

    # Magnitude in dB with 1e-12 floor (-240 dB)
    mag_abs = np.abs(h_arr)
    mag_clamped = np.maximum(mag_abs, 1e-12)
    mag_db = 20.0 * np.log10(mag_clamped)

    # Phase in radians via atan2 in [-pi, pi]
    phase_rad = np.arctan2(h_arr.imag, h_arr.real)

    return FrequencyResponseData(
        frequencies_hz=freqs,
        magnitude_db=mag_db,
        phase_rad=phase_rad,
    )


def calculate_acoustic_complex_summation(
    branch_responses: Sequence[np.ndarray],
    frequencies_hz: Union[Sequence[float], np.ndarray],
) -> FrequencyResponseData:
    """Calculate the vector complex acoustic summation of multiple acoustic branch responses.

    Normative Equation:
        H_total(f) = sum_{k=1}^K H_branch,k(f)

    Converts H_total(f) to canonical FrequencyResponseData using normative magnitude and phase rules.

    Args:
        branch_responses: Non-empty sequence of 1D complex128 branch responses.
        frequencies_hz: 1D array of frequencies matching the branch responses.

    Returns:
        FrequencyResponseData representing the summed acoustic output.

    Raises:
        InvalidParameterError: If branch_responses is empty or shapes/types mismatch.
    """
    if not isinstance(branch_responses, (list, tuple)) or len(branch_responses) == 0:
        raise InvalidParameterError("branch_responses must be a non-empty Sequence of complex arrays.")

    if isinstance(frequencies_hz, (list, tuple, np.ndarray)):
        freqs = np.asarray(frequencies_hz, dtype=np.float64)
    else:
        raise InvalidParameterError(f"frequencies_hz must be a Sequence or ndarray, got {type(frequencies_hz)!r}.")

    if freqs.ndim != 1 or freqs.shape[0] == 0:
        raise InvalidParameterError("frequencies_hz must be a non-empty 1D array.")

    expected_len = freqs.shape[0]
    h_total = np.zeros(expected_len, dtype=np.complex128)

    for idx, b_resp in enumerate(branch_responses):
        if not isinstance(b_resp, np.ndarray):
            raise InvalidParameterError(f"Expected np.ndarray for branch response at index {idx}, got {type(b_resp)!r}.")
        arr = b_resp.astype(np.complex128, copy=False)
        if arr.ndim != 1 or arr.shape[0] != expected_len:
            raise InvalidParameterError(
                f"Branch response {idx} length ({arr.shape[0]}) does not match frequency grid ({expected_len})."
            )
        if not np.all(np.isfinite(arr)):
            raise InvalidParameterError(f"Branch response {idx} contains non-finite complex values.")
        h_total += arr

    return complex_response_to_frequency_response_data(freqs, h_total)


def evaluate_acoustic_target_loss(
    predicted_response: FrequencyResponseData,
    target_curve: AcousticTargetCurve,
    frequency_range_hz: tuple[float, float],
    ripple_weight: float = 0.0,
    delay_weight: float = 0.0,
    delays_seconds: Optional[Sequence[float]] = None,
    delay_bounds_seconds: Optional[tuple[float, float]] = None,
) -> float:
    """Evaluate the composite acoustic target tracking loss over the active frequency band.

    Normative Equation:
        L(p) = E_rms(p) + w_r * R(p) + w_tau * P_tau(p)

    where:
        E_rms = sqrt( (1 / N_band) * sum_{i in band} (M_total(f_i) - T(f_i))^2 )
        R = max_{i in band} |M_total(f_i) - T(f_i)| - min_{i in band} |M_total(f_i) - T(f_i)|
        P_tau = sum_{k=1}^K (tau_k / tau_max,k)^2

    Args:
        predicted_response: FrequencyResponseData representing the synthesized total acoustic output.
        target_curve: AcousticTargetCurve value object.
        frequency_range_hz: Active evaluation band (f_min, f_max) in Hz.
        ripple_weight: Non-negative weight w_r for passband ripple penalty (default: 0.0).
        delay_weight: Non-negative weight w_tau for delay regularization penalty (default: 0.0).
        delays_seconds: Optional sequence of branch delays tau_k in seconds.
        delay_bounds_seconds: Optional delay search bounds (tau_min, tau_max) in seconds.

    Returns:
        Scalar loss in dB as a float.

    Raises:
        InvalidParameterError: If arguments are invalid or no frequency points fall within the active band.
        NumericalEvaluationError: If predicted magnitudes or calculated loss contain NaN / Inf.
    """
    if not isinstance(predicted_response, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData, got {type(predicted_response)!r}.")

    if not isinstance(target_curve, AcousticTargetCurve):
        raise InvalidParameterError(f"Expected AcousticTargetCurve, got {type(target_curve)!r}.")

    if not isinstance(frequency_range_hz, (tuple, list)) or len(frequency_range_hz) != 2:
        raise InvalidParameterError("frequency_range_hz must be a tuple of 2 floats (f_min, f_max).")

    f_min, f_max = float(frequency_range_hz[0]), float(frequency_range_hz[1])
    if not math.isfinite(f_min) or not math.isfinite(f_max) or f_min <= 0.0 or f_max <= f_min:
        raise InvalidParameterError(f"frequency_range_hz must satisfy 0 < f_min < f_max, got ({f_min}, {f_max}).")

    if not isinstance(ripple_weight, (int, float)) or isinstance(ripple_weight, bool) or ripple_weight < 0.0:
        raise InvalidParameterError(f"ripple_weight must be a non-negative float, got {ripple_weight!r}.")

    if not isinstance(delay_weight, (int, float)) or isinstance(delay_weight, bool) or delay_weight < 0.0:
        raise InvalidParameterError(f"delay_weight must be a non-negative float, got {delay_weight!r}.")

    freqs = predicted_response.frequencies_hz
    mask = (freqs >= f_min) & (freqs <= f_max)
    active_indices = np.where(mask)[0]

    if active_indices.shape[0] == 0:
        raise InvalidParameterError(
            f"No frequency points found in active range [{f_min:.1f} Hz, {f_max:.1f} Hz] "
            f"for measurement span [{freqs[0]:.1f} Hz, {freqs[-1]:.1f} Hz]."
        )

    f_active = freqs[mask]
    m_active = predicted_response.magnitude_db[mask]

    if not np.all(np.isfinite(m_active)):
        raise NumericalEvaluationError("Predicted magnitude array contains non-finite values (NaN / Inf).")

    # Evaluate target curve over active frequencies
    t_active = np.asarray(evaluate_target_curve(target_curve, f_active), dtype=np.float64)

    # Error vector in dB
    error = m_active - t_active
    abs_error = np.abs(error)

    # 1. RMS Tracking Error
    e_rms = float(np.sqrt(np.mean(error ** 2)))

    # 2. Ripple Penalty
    if ripple_weight > 0.0:
        r_val = float(np.max(abs_error) - np.min(abs_error))
    else:
        r_val = 0.0

    # 3. Delay Penalty
    if delay_weight > 0.0 and delays_seconds is not None and len(delays_seconds) > 0:
        if delay_bounds_seconds is not None and len(delay_bounds_seconds) == 2:
            tau_max = float(delay_bounds_seconds[1])
            if tau_max <= 0.0:
                raise InvalidParameterError(f"delay_bounds_seconds max must be > 0, got {tau_max}.")
        else:
            tau_max = 1.0

        p_tau = float(sum((float(d) / tau_max) ** 2 for d in delays_seconds))
    else:
        p_tau = 0.0

    loss = e_rms + float(ripple_weight) * r_val + float(delay_weight) * p_tau

    if not math.isfinite(loss):
        raise NumericalEvaluationError(f"Calculated loss is non-finite: {loss!r}.")

    return loss


def is_candidate_better(
    loss_new: float,
    params_new: Sequence[float] | np.ndarray,
    loss_current: float,
    params_current: Sequence[float] | np.ndarray,
    tolerance_db: float = 1e-12,
) -> bool:
    """Determine if a new parameter candidate is strictly better under the normative tie-breaking contract.

    Normative Tie-Breaking Rule:
    1. If loss_new < loss_current - tolerance_db: return True.
    2. If loss_new > loss_current + tolerance_db: return False.
    3. If |loss_new - loss_current| <= tolerance_db: return tuple(params_new) < tuple(params_current)
       (lexicographically smaller parameter vector wins).

    Args:
        loss_new: Evaluated loss of new candidate.
        params_new: Parameter vector of new candidate.
        loss_current: Evaluated loss of current best candidate.
        params_current: Parameter vector of current best candidate.
        tolerance_db: Floating-point equivalence threshold (default: 1e-12 dB).

    Returns:
        True if the new candidate should replace the current candidate, False otherwise.
    """
    diff = loss_new - loss_current
    if diff < -tolerance_db:
        return True
    if diff > tolerance_db:
        return False

    # Within tolerance: lexicographic tie-breaking
    p_new_tuple = tuple(float(x) for x in params_new)
    p_cur_tuple = tuple(float(x) for x in params_current)
    return p_new_tuple < p_cur_tuple


def generate_crossover_candidate_grid(
    bounds_hz: tuple[float, float],
    num_points: int = 20,
) -> np.ndarray:
    """Generate a deterministic log-spaced grid of crossover frequency candidates.

    Args:
        bounds_hz: Crossover frequency search bounds (fc_min, fc_max) in Hz.
        num_points: Number of grid points (default: 20, must be >= 2).

    Returns:
        1D float64 np.ndarray of candidate crossover frequencies in ascending order.

    Raises:
        InvalidParameterError: If bounds or point count are invalid.
    """
    if not isinstance(bounds_hz, (tuple, list)) or len(bounds_hz) != 2:
        raise InvalidParameterError("bounds_hz must be a tuple of 2 floats.")
    fc_min, fc_max = float(bounds_hz[0]), float(bounds_hz[1])
    if not math.isfinite(fc_min) or not math.isfinite(fc_max) or fc_min <= 0.0 or fc_max <= fc_min:
        raise InvalidParameterError(f"bounds_hz must satisfy 0 < fc_min < fc_max, got ({fc_min}, {fc_max}).")
    if not isinstance(num_points, int) or isinstance(num_points, bool) or num_points < 2:
        raise InvalidParameterError(f"num_points must be an integer >= 2, got {num_points!r}.")

    return np.geomspace(fc_min, fc_max, num_points, dtype=np.float64)


def generate_delay_candidate_grid(
    bounds_seconds: tuple[float, float],
    num_points: int = 20,
) -> np.ndarray:
    """Generate a deterministic linearly-spaced grid of acoustic alignment delay candidates.

    Args:
        bounds_seconds: Delay search bounds (tau_min, tau_max) in seconds.
        num_points: Number of grid points (default: 20, must be >= 2).

    Returns:
        1D float64 np.ndarray of candidate delays in ascending order.

    Raises:
        InvalidParameterError: If bounds or point count are invalid.
    """
    if not isinstance(bounds_seconds, (tuple, list)) or len(bounds_seconds) != 2:
        raise InvalidParameterError("bounds_seconds must be a tuple of 2 floats.")
    tau_min, tau_max = float(bounds_seconds[0]), float(bounds_seconds[1])
    if not math.isfinite(tau_min) or not math.isfinite(tau_max) or tau_min < 0.0 or tau_max <= tau_min:
        raise InvalidParameterError(f"bounds_seconds must satisfy 0 <= tau_min < tau_max, got ({tau_min}, {tau_max}).")
    if not isinstance(num_points, int) or isinstance(num_points, bool) or num_points < 2:
        raise InvalidParameterError(f"num_points must be an integer >= 2, got {num_points!r}.")

    return np.linspace(tau_min, tau_max, num_points, dtype=np.float64)


def golden_section_line_search(
    objective_func: Callable[[float], float],
    bounds: tuple[float, float],
    max_iterations: int = 20,
    initial_candidate: Optional[float] = None,
) -> tuple[float, float]:
    """Perform a deterministic 1D bounded golden-section line search minimization.

    Normative Guarantees:
    1. Fixed iteration budget (default: 20 iterations).
    2. Golden ratio phi = (sqrt(5) - 1) / 2.
    3. Monotonicity: Evaluates baseline initial_candidate (if provided within bounds) and
       guarantees L_best <= L_initial.
    4. Deterministic tie-breaking across evaluated candidates.

    Args:
        objective_func: Deterministic scalar objective function g(x) -> float.
        bounds: Search interval (a, b) with a < b.
        max_iterations: Fixed number of golden-section iterations (default: 20).
        initial_candidate: Optional initial point to evaluate and ensure monotonic reduction.

    Returns:
        (best_x, best_loss)
    """
    a, b = float(bounds[0]), float(bounds[1])
    if not math.isfinite(a) or not math.isfinite(b) or b <= a:
        raise InvalidParameterError(f"bounds must satisfy a < b, got ({a}, {b}).")

    if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) or max_iterations < 1:
        raise InvalidParameterError(f"max_iterations must be an integer >= 1, got {max_iterations!r}.")

    phi = (math.sqrt(5.0) - 1.0) / 2.0  # ≈ 0.618033988749895

    # Track best candidate encountered
    best_x = a
    best_loss = objective_func(a)

    # Evaluate initial candidate if provided
    if initial_candidate is not None:
        init_c = float(initial_candidate)
        if a <= init_c <= b:
            init_loss = objective_func(init_c)
            if is_candidate_better(init_loss, [init_c], best_loss, [best_x]):
                best_x = init_c
                best_loss = init_loss

    # Evaluate upper endpoint
    b_loss = objective_func(b)
    if is_candidate_better(b_loss, [b], best_loss, [best_x]):
        best_x = b
        best_loss = b_loss

    # Interior points
    c = b - phi * (b - a)
    d = a + phi * (b - a)

    fc = objective_func(c)
    if is_candidate_better(fc, [c], best_loss, [best_x]):
        best_x = c
        best_loss = fc

    fd = objective_func(d)
    if is_candidate_better(fd, [d], best_loss, [best_x]):
        best_x = d
        best_loss = fd

    for _ in range(max_iterations):
        if fc < fd:
            b = d
            d = c
            fd = fc
            c = b - phi * (b - a)
            fc = objective_func(c)
            if is_candidate_better(fc, [c], best_loss, [best_x]):
                best_x = c
                best_loss = fc
        else:
            a = c
            c = d
            fc = fd
            d = a + phi * (b - a)
            fd = objective_func(d)
            if is_candidate_better(fd, [d], best_loss, [best_x]):
                best_x = d
                best_loss = fd

    # Final midpoint check
    mid_x = (a + b) / 2.0
    mid_loss = objective_func(mid_x)
    if is_candidate_better(mid_loss, [mid_x], best_loss, [best_x]):
        best_x = mid_x
        best_loss = mid_loss

    return best_x, best_loss


def coordinate_descent_search(
    objective_func: Callable[[np.ndarray], float],
    bounds: Sequence[tuple[float, float]],
    initial_params: Sequence[float] | np.ndarray,
    max_iterations: int = 50,
    convergence_tolerance_db: float = 1e-5,
    golden_iterations: int = 20,
    constraints: Optional[Sequence[Callable[[np.ndarray], bool]]] = None,
) -> tuple[np.ndarray, float, bool, int]:
    """Perform deterministic coordinate descent multi-parameter minimization.

    Normative Invariants:
    1. Baseline initial_params is evaluated first, guaranteeing L_final <= L_initial.
    2. Coordinates are optimized sequentially in deterministic order (0, 1, ..., D-1).
    3. Each coordinate is optimized via 1D bounded golden-section line search.
    4. Deterministic tie-breaking is applied to every candidate comparison.
    5. Search terminates when Delta L < convergence_tolerance_db or max_iterations reached.

    Args:
        objective_func: Deterministic objective function f(params) -> float.
        bounds: Sequence of (min_val, max_val) tuples for each parameter coordinate.
        initial_params: Initial parameter vector.
        max_iterations: Maximum coordinate descent cycles (default: 50).
        convergence_tolerance_db: Loss improvement threshold for convergence (default: 1e-5 dB).
        golden_iterations: Number of iterations per 1D golden-section search (default: 20).
        constraints: Optional list of boolean constraint predicates f(params) -> bool.

    Returns:
        (best_params, best_loss, converged, iterations_completed)
    """
    p_init = np.asarray(initial_params, dtype=np.float64)
    dim = p_init.shape[0]

    if len(bounds) != dim:
        raise InvalidParameterError(f"bounds length ({len(bounds)}) does not match initial_params length ({dim}).")

    for idx, (b_min, b_max) in enumerate(bounds):
        if not math.isfinite(b_min) or not math.isfinite(b_max) or b_max <= b_min:
            raise InvalidParameterError(f"Bounds at index {idx} must satisfy min < max, got ({b_min}, {b_max}).")
        if not (b_min <= p_init[idx] <= b_max):
            raise InvalidParameterError(
                f"Initial parameter at index {idx} ({p_init[idx]}) is outside bounds [{b_min}, {b_max}]."
            )

    if constraints:
        for c_idx, constraint_fn in enumerate(constraints):
            if not constraint_fn(p_init):
                raise InvalidParameterError(f"Initial parameter vector violates constraint at index {c_idx}.")

    # Evaluate baseline candidate
    best_params = p_init.copy()
    best_loss = float(objective_func(best_params))

    current_params = p_init.copy()
    current_loss = best_loss

    converged = False
    iterations_completed = 0

    for cycle in range(1, max_iterations + 1):
        iterations_completed = cycle
        loss_start_of_cycle = current_loss

        for coord_idx in range(dim):
            coord_bounds = bounds[coord_idx]

            def scalar_obj(x: float) -> float:
                candidate = current_params.copy()
                candidate[coord_idx] = x
                if constraints:
                    for c_fn in constraints:
                        if not c_fn(candidate):
                            return float("inf")
                return float(objective_func(candidate))

            opt_x, opt_loss = golden_section_line_search(
                objective_func=scalar_obj,
                bounds=coord_bounds,
                max_iterations=golden_iterations,
                initial_candidate=current_params[coord_idx],
            )

            if is_candidate_better(opt_loss, [opt_x], current_loss, [current_params[coord_idx]]):
                current_params[coord_idx] = opt_x
                current_loss = opt_loss

                if is_candidate_better(current_loss, current_params, best_loss, best_params):
                    best_params = current_params.copy()
                    best_loss = current_loss

        delta_loss = loss_start_of_cycle - current_loss
        rel_improvement = delta_loss / max(abs(loss_start_of_cycle), 1e-12)

        if delta_loss < convergence_tolerance_db or rel_improvement < 1e-5:
            converged = True
            break

    return best_params, best_loss, converged, iterations_completed


