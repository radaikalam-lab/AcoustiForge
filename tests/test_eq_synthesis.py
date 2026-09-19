"""Tests for Phase 3C Parametric EQ Synthesis Mathematics.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3B_ACOUSTIC_DOMAIN_VALUE_TYPES_IMPLEMENTATION_AND_VERIFICATION.md
"""

from __future__ import annotations

import numpy as np
import pytest

from acoustiforge.acoustic_math.equalizer import (
    EQSynthesisResult,
    synthesize_parametric_eq,
)
from acoustiforge.contracts.validation import InvalidParameterError, InvalidSampleRateError
from acoustiforge.domain.measurements import FrequencyResponseData
from acoustiforge.domain.specifications import AcousticTargetCurve, EqualizerBudget


class TestEqualizerSynthesis:
    """Mathematical verification of parametric EQ synthesis."""

    def test_synthesize_eq_single_resonant_peak(self) -> None:
        """Verify equalizer correctly detects and corrects a synthetic resonant peak."""
        # Create synthetic measurement with a +6 dB resonant peak at 1000 Hz
        freqs = np.geomspace(20.0, 20000.0, num=100)
        # Baseline 85 dB SPL with Gaussian bump around 1000 Hz
        bump = 6.0 * np.exp(-0.5 * ((np.log10(freqs) - np.log10(1000.0)) / 0.1) ** 2)
        mags = 85.0 + bump

        meas = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        budget = EqualizerBudget(max_bands=3, max_boost_db=6.0, max_cut_db=12.0)
        target = AcousticTargetCurve(name="Flat_85dB", points=[(20.0, 85.0), (20000.0, 85.0)])

        result = synthesize_parametric_eq(
            measurement=meas,
            budget=budget,
            sample_rate=48000,
            target_curve=target,
        )

        assert isinstance(result, EQSynthesisResult)
        assert len(result.bands) >= 1
        assert len(result.sections) == len(result.bands)

        # Primary peak frequency should be close to 1000 Hz
        primary_band = result.bands[0]
        peak_freq = primary_band[0]
        peak_gain = primary_band[1]
        assert pytest.approx(1000.0, rel=0.15) == peak_freq
        # Gain should be negative (attenuating the +6 dB peak)
        assert peak_gain < 0.0

        # Residual RMS error should have reduced significantly from initial error (~1.5 dB down to <0.8 dB)
        assert result.residual_rms_error_db < 1.0

    def test_synthesize_eq_flat_response_requires_zero_bands(self) -> None:
        """Verify equalizer places zero bands when response already matches target."""
        freqs = np.geomspace(20.0, 20000.0, num=50)
        mags = np.full_like(freqs, 85.0)
        meas = FrequencyResponseData(frequencies_hz=freqs, magnitude_db=mags)

        budget = EqualizerBudget(max_bands=5)
        target = AcousticTargetCurve(name="Flat_85dB", points=[(20.0, 85.0), (20000.0, 85.0)])

        result = synthesize_parametric_eq(
            measurement=meas,
            budget=budget,
            sample_rate=48000,
            target_curve=target,
        )

        assert len(result.bands) == 0
        assert len(result.sections) == 0
        assert result.residual_rms_error_db == 0.0
