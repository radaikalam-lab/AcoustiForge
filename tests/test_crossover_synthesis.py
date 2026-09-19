"""Tests for Phase 3C Crossover Filter Synthesis Mathematics.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pytest

from acoustiforge.acoustic_math.crossover import (
    CrossoverSynthesisResult,
    synthesize_crossover_biquads,
)
from acoustiforge.contracts.validation import InvalidParameterError, InvalidSampleRateError
from acoustiforge.domain.specifications import CrossoverFamily, CrossoverSpecification


def compute_transfer_function(
    sections: tuple,
    frequencies: np.ndarray,
    sample_rate: int,
) -> np.ndarray:
    """Compute complex cascaded frequency response of biquad sections."""
    omega = 2.0 * np.pi * frequencies / float(sample_rate)
    z1 = np.exp(-1j * omega)
    z2 = np.exp(-2j * omega)

    h_total = np.ones(len(frequencies), dtype=np.complex128)
    for sec in sections:
        num = sec.b0 + sec.b1 * z1 + sec.b2 * z2
        den = 1.0 + sec.a1 * z1 + sec.a2 * z2
        h_total *= num / den
    return h_total


class TestCrossoverSynthesis:
    """Mathematical verification of crossover filter synthesis."""

    def test_butterworth_order_2_characteristics(self) -> None:
        """Verify 2nd-order Butterworth crossover frequency response and attenuation."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.BUTTERWORTH,
            order=2,
            frequency_hz=1000.0,
        )
        result = synthesize_crossover_biquads(spec, sample_rate=48000)

        assert isinstance(result, CrossoverSynthesisResult)
        assert result.family == CrossoverFamily.BUTTERWORTH
        assert result.order == 2
        assert len(result.low_pass_sections) == 1
        assert len(result.high_pass_sections) == 1

        sec_lp = result.low_pass_sections[0]
        sec_hp = result.high_pass_sections[0]
        assert sec_lp.is_stable()
        assert sec_hp.is_stable()

        # Evaluate at fc = 1000 Hz
        freqs = np.array([10.0, 1000.0, 20000.0])
        h_lp = compute_transfer_function(result.low_pass_sections, freqs, 48000)
        h_hp = compute_transfer_function(result.high_pass_sections, freqs, 48000)

        # At fc=1000 Hz, Butterworth-2 has |H(fc)| = 1 / sqrt(2) (-3.01 dB)
        mag_lp_fc = np.abs(h_lp[1])
        mag_hp_fc = np.abs(h_hp[1])
        assert pytest.approx(1.0 / np.sqrt(2.0), rel=1e-4) == mag_lp_fc
        assert pytest.approx(1.0 / np.sqrt(2.0), rel=1e-4) == mag_hp_fc

        # Power sum at fc: |H_lp|^2 + |H_hp|^2 = 1.0 (Butterworth constant power)
        assert pytest.approx(1.0, rel=1e-4) == (mag_lp_fc**2 + mag_hp_fc**2)

    def test_butterworth_order_4_and_8(self) -> None:
        """Verify 4th and 8th order Butterworth filter section counts and stability."""
        for order, expected_sections in [(4, 2), (8, 4)]:
            spec = CrossoverSpecification(
                family=CrossoverFamily.BUTTERWORTH,
                order=order,
                frequency_hz=1500.0,
            )
            result = synthesize_crossover_biquads(spec, sample_rate=44100)
            assert len(result.low_pass_sections) == expected_sections
            assert len(result.high_pass_sections) == expected_sections
            for sec in result.low_pass_sections + result.high_pass_sections:
                assert sec.is_stable()

    def test_linkwitz_riley_order_2_first_order_representation(self) -> None:
        """Verify LR-2 contains two cascaded 1st-order biquads with b2=0, a2=0."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=2,
            frequency_hz=1000.0,
        )
        result = synthesize_crossover_biquads(spec, sample_rate=48000)

        assert len(result.low_pass_sections) == 2
        assert len(result.high_pass_sections) == 2

        for sec in result.low_pass_sections + result.high_pass_sections:
            assert sec.b2 == 0.0
            assert sec.a2 == 0.0
            assert sec.is_stable()

        # At fc=1000 Hz, LR-2 has -6.02 dB (mag = 0.5) per branch
        freqs = np.array([1000.0])
        h_lp = compute_transfer_function(result.low_pass_sections, freqs, 48000)
        h_hp = compute_transfer_function(result.high_pass_sections, freqs, 48000)
        assert pytest.approx(0.5, rel=1e-4) == np.abs(h_lp[0])
        assert pytest.approx(0.5, rel=1e-4) == np.abs(h_hp[0])

    def test_linkwitz_riley_order_4_allpass_summation(self) -> None:
        """Verify LR-4 produces exact -6 dB at fc and flat unity all-pass summation magnitude across all frequencies."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=4,
            frequency_hz=2000.0,
        )
        result = synthesize_crossover_biquads(spec, sample_rate=48000)

        assert len(result.low_pass_sections) == 2
        assert len(result.high_pass_sections) == 2

        freqs = np.geomspace(20.0, 20000.0, num=500)
        h_lp = compute_transfer_function(result.low_pass_sections, freqs, 48000)
        h_hp = compute_transfer_function(result.high_pass_sections, freqs, 48000)

        # 1. Check exact -6.02 dB (mag = 0.5) at fc = 2000 Hz
        h_lp_fc = compute_transfer_function(result.low_pass_sections, np.array([2000.0]), 48000)
        h_hp_fc = compute_transfer_function(result.high_pass_sections, np.array([2000.0]), 48000)
        assert pytest.approx(0.5, rel=1e-5) == np.abs(h_lp_fc[0])
        assert pytest.approx(0.5, rel=1e-5) == np.abs(h_hp_fc[0])

        # 2. Check LR-4 complex summation magnitude |H_lp + H_hp| == 1.0 for all frequencies
        h_sum = h_lp + h_hp
        mag_sum = np.abs(h_sum)
        np.testing.assert_allclose(mag_sum, 1.0, rtol=1e-4, atol=1e-4)

    def test_linkwitz_riley_order_8_allpass_summation(self) -> None:
        """Verify LR-8 8th-order Linkwitz-Riley all-pass magnitude summation."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.LINKWITZ_RILEY,
            order=8,
            frequency_hz=3000.0,
        )
        result = synthesize_crossover_biquads(spec, sample_rate=48000)

        assert len(result.low_pass_sections) == 4
        assert len(result.high_pass_sections) == 4

        freqs = np.geomspace(20.0, 20000.0, num=500)
        h_lp = compute_transfer_function(result.low_pass_sections, freqs, 48000)
        h_hp = compute_transfer_function(result.high_pass_sections, freqs, 48000)

        # LR-8 sums in-phase to unity all-pass magnitude
        h_sum = h_lp + h_hp
        mag_sum = np.abs(h_sum)
        np.testing.assert_allclose(mag_sum, 1.0, rtol=1e-3, atol=1e-3)

    def test_golden_vectors_conformance(self) -> None:
        """Verify mathematical output against frozen golden reference vector files."""
        golden_file = Path(__file__).resolve().parent.parent / "docs" / "phases" / "golden" / "crossover_golden_vectors.json"
        assert golden_file.exists(), f"Golden vectors file missing: {golden_file}"

        with open(golden_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for vec in data["vectors"]:
            spec = CrossoverSpecification(
                family=CrossoverFamily(vec["family"]),
                order=vec["order"],
                frequency_hz=vec["crossover_frequency_hz"],
            )
            result = synthesize_crossover_biquads(spec, sample_rate=vec["sample_rate"])
            tol = vec["tolerance"]

            # Low pass sections
            for i, exp_sec in enumerate(vec["low_pass_sections"]):
                act_sec = result.low_pass_sections[i]
                assert pytest.approx(exp_sec["b0"], abs=tol) == act_sec.b0
                assert pytest.approx(exp_sec["b1"], abs=tol) == act_sec.b1
                assert pytest.approx(exp_sec["b2"], abs=tol) == act_sec.b2
                assert pytest.approx(exp_sec["a1"], abs=tol) == act_sec.a1
                assert pytest.approx(exp_sec["a2"], abs=tol) == act_sec.a2

            # High pass sections
            for i, exp_sec in enumerate(vec["high_pass_sections"]):
                act_sec = result.high_pass_sections[i]
                assert pytest.approx(exp_sec["b0"], abs=tol) == act_sec.b0
                assert pytest.approx(exp_sec["b1"], abs=tol) == act_sec.b1
                assert pytest.approx(exp_sec["b2"], abs=tol) == act_sec.b2
                assert pytest.approx(exp_sec["a1"], abs=tol) == act_sec.a1
                assert pytest.approx(exp_sec["a2"], abs=tol) == act_sec.a2

    def test_invalid_parameters(self) -> None:
        """Verify strict error handling for invalid crossover inputs."""
        spec = CrossoverSpecification(
            family=CrossoverFamily.BUTTERWORTH,
            order=2,
            frequency_hz=1000.0,
        )

        with pytest.raises(InvalidSampleRateError):
            synthesize_crossover_biquads(spec, sample_rate=0)

        with pytest.raises(InvalidSampleRateError):
            synthesize_crossover_biquads(spec, sample_rate=-48000)

        # Exceeding Nyquist
        spec_high = CrossoverSpecification(
            family=CrossoverFamily.BUTTERWORTH,
            order=2,
            frequency_hz=24000.0,
        )
        with pytest.raises(InvalidParameterError, match="strictly less than Nyquist"):
            synthesize_crossover_biquads(spec_high, sample_rate=48000)
