"""AcoustiForge Parametric Equalizer Synthesis Mathematics.

Deterministic parametric EQ synthesis and optimization without external optimization packages.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3B_ACOUSTIC_DOMAIN_VALUE_TYPES_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple
import numpy as np

from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..domain.measurements import FrequencyResponseData
from ..domain.specifications import AcousticTargetCurve, EqualizerBudget
from ..nodes.biquad import BiquadCoefficients, FilterType, calculate_biquad_coefficients
from .target_curve import evaluate_target_curve


@dataclass(frozen=True, slots=True)
class EQSynthesisResult:
    """Immutable result container for parametric equalizer synthesis."""
    bands: Tuple[Tuple[float, float, float], ...]  # Tuple of (frequency_hz, gain_db, q)
    sections: Tuple[BiquadCoefficients, ...]
    sample_rate: int
    residual_rms_error_db: float


def _biquad_response_db(
    coeff: BiquadCoefficients,
    frequencies: np.ndarray,
    sample_rate: int,
) -> np.ndarray:
    """Compute exact complex frequency response magnitude in dB for a Biquad filter."""
    omega = 2.0 * np.pi * frequencies / float(sample_rate)
    z1 = np.exp(-1j * omega)
    z2 = np.exp(-2j * omega)

    num = coeff.b0 + coeff.b1 * z1 + coeff.b2 * z2
    den = 1.0 + coeff.a1 * z1 + coeff.a2 * z2
    h = num / den
    mag = np.abs(h)
    # Numerical guard against log(0)
    mag = np.maximum(mag, 1e-12)
    return 20.0 * np.log10(mag)


def synthesize_parametric_eq(
    measurement: FrequencyResponseData,
    budget: EqualizerBudget,
    sample_rate: int,
    target_curve: Optional[AcousticTargetCurve] = None,
    min_freq_hz: float = 20.0,
    max_freq_hz: Optional[float] = None,
) -> EQSynthesisResult:
    """Deterministically synthesize a cascaded set of parametric peaking EQ biquad filters.

    Algorithm Specification:
    1. Grid Evaluation: Evaluates error E(f) = M(f) - T(f) across measurement frequency points within [min_freq_hz, max_freq_hz].
    2. Greedy Peak/Dip Identification: At each iteration k, finds frequency f* with maximum absolute error |E(f*)|.
       Deterministic tie-breaking selects the lower frequency.
    3. Gain Clamping: Inverts peak/dip error G = -E(f*), clamped within [-budget.max_cut_db, +budget.max_boost_db].
    4. Q-Factor Search: Evaluates a deterministic candidate grid of Q values between [budget.min_q, budget.max_q],
       selecting the Q that maximizes RMS error reduction.
    5. Residual Update: Subtracts synthesized filter transfer function from error profile.
    6. Stopping Criteria: Terminates when budget.max_bands is reached, max absolute error < 0.25 dB,
       or RMS error improvement per band < 0.05 dB.

    Args:
        measurement: FrequencyResponseData containing measured SPL response.
        budget: EqualizerBudget defining max_bands, gain limits, and Q limits.
        sample_rate: Audio sampling rate in Hz.
        target_curve: Optional AcousticTargetCurve (defaults to flat 0 dB target).
        min_freq_hz: Minimum frequency bound for EQ synthesis (default: 20 Hz).
        max_freq_hz: Maximum frequency bound (defaults to 0.45 * sample_rate or 20 kHz).

    Returns:
        EQSynthesisResult with band parameters, BiquadCoefficients, and residual RMS error.

    Raises:
        InvalidSampleRateError: If sample_rate is non-positive.
        InvalidParameterError: If budget or measurement data is invalid.
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    if not isinstance(measurement, FrequencyResponseData):
        raise InvalidParameterError(f"Expected FrequencyResponseData, got {type(measurement)!r}.")

    if not isinstance(budget, EqualizerBudget):
        raise InvalidParameterError(f"Expected EqualizerBudget, got {type(budget)!r}.")

    nyquist = sample_rate / 2.0
    effective_max_freq = min(20000.0, 0.45 * sample_rate) if max_freq_hz is None else float(max_freq_hz)
    if effective_max_freq >= nyquist:
        raise InvalidParameterError(f"max_freq_hz ({effective_max_freq} Hz) must be less than Nyquist ({nyquist} Hz).")

    meas_f = np.array(measurement.frequencies_hz, dtype=np.float64)
    meas_m = np.array(measurement.magnitude_db, dtype=np.float64)

    # Filter frequencies within optimization range
    mask = (meas_f >= min_freq_hz) & (meas_f <= effective_max_freq)
    if not np.any(mask):
        raise InvalidParameterError(f"No measurement points found in range [{min_freq_hz}, {effective_max_freq}] Hz.")

    eval_f = meas_f[mask]
    eval_m = meas_m[mask]

    # Target response
    if target_curve is not None:
        target_m = evaluate_target_curve(target_curve, eval_f)
    else:
        # Flat 0 dB target
        target_m = np.zeros_like(eval_f)

    # Current error in dB (positive = peak needing cut, negative = dip needing boost)
    error_db = eval_m - target_m
    current_rms = float(np.sqrt(np.mean(error_db ** 2)))

    bands: list[Tuple[float, float, float]] = []
    sections: list[BiquadCoefficients] = []

    # Candidate Q evaluation grid (logarithmically spaced within budget bounds)
    q_candidates = np.geomspace(budget.min_q, budget.max_q, num=9)

    for _ in range(budget.max_bands):
        # 1. Check stopping criteria
        max_err_idx = int(np.argmax(np.abs(error_db)))
        max_err_val = error_db[max_err_idx]
        if abs(max_err_val) < 0.25:
            break

        f0 = float(eval_f[max_err_idx])
        # Invert the error to produce correcting filter gain
        desired_gain = -max_err_val
        if desired_gain > 0.0:
            gain_db = min(desired_gain, budget.max_boost_db)
        else:
            gain_db = max(desired_gain, -budget.max_cut_db)

        if abs(gain_db) < 0.2:
            break

        # 2. Evaluate candidate Q values
        best_q: Optional[float] = None
        best_coeff: Optional[BiquadCoefficients] = None
        best_new_rms = current_rms
        best_new_error: Optional[np.ndarray] = None

        for q_cand in q_candidates:
            try:
                coeff = calculate_biquad_coefficients(
                    filter_type=FilterType.PEAKING,
                    sample_rate=sample_rate,
                    frequency=f0,
                    q=float(q_cand),
                    gain_db=float(gain_db),
                )
            except Exception:
                continue

            filter_resp = _biquad_response_db(coeff, eval_f, sample_rate)
            candidate_error = error_db + filter_resp
            cand_rms = float(np.sqrt(np.mean(candidate_error ** 2)))

            if cand_rms < best_new_rms:
                best_new_rms = cand_rms
                best_q = float(q_cand)
                best_coeff = coeff
                best_new_error = candidate_error

        # 3. If significant RMS reduction achieved, accept band
        rms_improvement = current_rms - best_new_rms
        if best_coeff is not None and best_q is not None and best_new_error is not None and rms_improvement >= 0.05:
            bands.append((f0, gain_db, best_q))
            sections.append(best_coeff)
            error_db = best_new_error
            current_rms = best_new_rms
        else:
            # Cannot find effective band; terminate iteration
            break

    return EQSynthesisResult(
        bands=tuple(bands),
        sections=tuple(sections),
        sample_rate=sample_rate,
        residual_rms_error_db=current_rms,
    )
