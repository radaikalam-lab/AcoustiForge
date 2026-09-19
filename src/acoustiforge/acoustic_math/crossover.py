"""AcoustiForge Crossover Filter Synthesis Mathematics.

Pure deterministic synthesis of Butterworth and Linkwitz-Riley crossover biquad filter sections.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/contracts/PCM_CONTRACT.md
- docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..domain.specifications import CrossoverFamily, CrossoverSpecification
from ..nodes.biquad import BiquadCoefficients


@dataclass(frozen=True, slots=True)
class CrossoverSynthesisResult:
    """Immutable result container for acoustic crossover filter coefficient synthesis."""
    family: CrossoverFamily
    order: int
    crossover_frequency_hz: float
    sample_rate: int
    low_pass_sections: Tuple[BiquadCoefficients, ...]
    high_pass_sections: Tuple[BiquadCoefficients, ...]


def _calculate_butterworth_q_values(order: int) -> Tuple[float, ...]:
    """Calculate the Q-factors for the cascaded 2nd-order sections of an analog Butterworth filter.

    For an even order N, poles are given by:
        s_k = exp(j * pi * (2k + N - 1) / (2N)), k = 1, ..., N
    Pairing complex conjugate poles gives Q_k = 1 / (2 * cos((2k - 1) * pi / (2N))) for k = 1, ..., N/2.
    """
    num_sections = order // 2
    q_values = []
    for k in range(1, num_sections + 1):
        theta = (2 * k - 1) * math.pi / (2 * order)
        q = 1.0 / (2.0 * math.cos(theta))
        q_values.append(q)
    # Order sections by ascending Q for optimal numerical stability and dynamic range
    q_values.sort()
    return tuple(q_values)


def _synthesize_second_order_butterworth_section(
    k_tan: float, q: float
) -> Tuple[BiquadCoefficients, BiquadCoefficients]:
    """Synthesize 2nd-order digital Butterworth biquad sections using bilinear transform with pre-warping.

    Returns:
        (low_pass_section, high_pass_section)
    """
    k_sq = k_tan * k_tan
    d = 1.0 + (k_tan / q) + k_sq

    # Denominator coefficients (normalized by d with implicit a0 = 1.0)
    a1 = float(2.0 * (k_sq - 1.0) / d)
    a2 = float((1.0 - (k_tan / q) + k_sq) / d)

    # Low-pass numerator coefficients
    lp_b0 = float(k_sq / d)
    lp_b1 = float(2.0 * k_sq / d)
    lp_b2 = float(k_sq / d)
    lp_coeff = BiquadCoefficients(b0=lp_b0, b1=lp_b1, b2=lp_b2, a1=a1, a2=a2)

    # High-pass numerator coefficients
    hp_b0 = float(1.0 / d)
    hp_b1 = float(-2.0 / d)
    hp_b2 = float(1.0 / d)
    hp_coeff = BiquadCoefficients(b0=hp_b0, b1=hp_b1, b2=hp_b2, a1=a1, a2=a2)

    return lp_coeff, hp_coeff


def _synthesize_first_order_section(
    k_tan: float,
) -> Tuple[BiquadCoefficients, BiquadCoefficients]:
    """Synthesize 1st-order analog prototype transformed via bilinear transform with pre-warping.

    Represented explicitly in standard BiquadCoefficients format with b2 = 0.0 and a2 = 0.0.

    Low-pass transfer function:
        H_lp(z) = (K/(1+K) + K/(1+K)*z^-1) / (1 + (K-1)/(1+K)*z^-1)

    High-pass transfer function:
        H_hp(z) = (1/(1+K) - 1/(1+K)*z^-1) / (1 + (K-1)/(1+K)*z^-1)

    Returns:
        (low_pass_section, high_pass_section)
    """
    d = 1.0 + k_tan
    a1 = float((k_tan - 1.0) / d)
    a2 = 0.0

    lp_b0 = float(k_tan / d)
    lp_b1 = float(k_tan / d)
    lp_b2 = 0.0
    lp_coeff = BiquadCoefficients(b0=lp_b0, b1=lp_b1, b2=lp_b2, a1=a1, a2=a2)

    hp_b0 = float(1.0 / d)
    hp_b1 = float(-1.0 / d)
    hp_b2 = 0.0
    hp_coeff = BiquadCoefficients(b0=hp_b0, b1=hp_b1, b2=hp_b2, a1=a1, a2=a2)

    return lp_coeff, hp_coeff


def synthesize_crossover_biquads(
    specification: CrossoverSpecification,
    sample_rate: int,
) -> CrossoverSynthesisResult:
    """Deterministically synthesize digital Biquad coefficient sections for a crossover specification.

    Supported families and orders:
    - Butterworth: orders 2, 4, 8
    - Linkwitz-Riley: orders 2, 4, 8

    Args:
        specification: CrossoverSpecification containing family, order, and crossover frequency.
        sample_rate: Audio sampling rate in Hz (must be positive).

    Returns:
        CrossoverSynthesisResult containing the cascaded low_pass and high_pass BiquadCoefficients.

    Raises:
        InvalidSampleRateError: If sample_rate is non-positive or invalid.
        InvalidParameterError: If crossover frequency exceeds Nyquist limit (sample_rate / 2).
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    fc = specification.frequency_hz
    nyquist = sample_rate / 2.0
    if fc >= nyquist:
        raise InvalidParameterError(
            f"Crossover frequency {fc} Hz must be strictly less than Nyquist frequency {nyquist} Hz at Fs={sample_rate} Hz."
        )

    # Pre-warped bilinear transform frequency factor: K = tan(pi * fc / Fs)
    k_tan = math.tan(math.pi * fc / sample_rate)

    lp_sections: list[BiquadCoefficients] = []
    hp_sections: list[BiquadCoefficients] = []

    if specification.family == CrossoverFamily.BUTTERWORTH:
        q_values = _calculate_butterworth_q_values(specification.order)
        for q in q_values:
            lp_sec, hp_sec = _synthesize_second_order_butterworth_section(k_tan, q)
            lp_sections.append(lp_sec)
            hp_sections.append(hp_sec)

    elif specification.family == CrossoverFamily.LINKWITZ_RILEY:
        if specification.order == 2:
            # LR-2 is the square of a 1st-order Butterworth filter.
            # Represented as two cascaded 1st-order sections (b2=0, a2=0).
            lp_sec1, hp_sec1 = _synthesize_first_order_section(k_tan)
            lp_sections = [lp_sec1, lp_sec1]
            hp_sections = [hp_sec1, hp_sec1]
        else:
            # LR-N (for N=4, 8) is the square of an (N/2)-th order Butterworth filter.
            # That is, two cascaded Butterworth filters of order N/2.
            half_order = specification.order // 2
            bw_q_values = _calculate_butterworth_q_values(half_order)
            # Repeat the Butterworth stages twice
            for _ in range(2):
                for q in bw_q_values:
                    lp_sec, hp_sec = _synthesize_second_order_butterworth_section(k_tan, q)
                    lp_sections.append(lp_sec)
                    hp_sections.append(hp_sec)
    else:
        raise InvalidParameterError(f"Unsupported crossover family: {specification.family!r}")

    return CrossoverSynthesisResult(
        family=specification.family,
        order=specification.order,
        crossover_frequency_hz=fc,
        sample_rate=sample_rate,
        low_pass_sections=tuple(lp_sections),
        high_pass_sections=tuple(hp_sections),
    )
