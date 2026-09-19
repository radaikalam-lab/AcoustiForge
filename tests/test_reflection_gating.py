"""Unit and Contract Tests for Reflection Gating and Spectral Fourier Transformation.

Normative Authority:
- docs/contracts/REFLECTION_GATING_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.gating import (
    GateSpecification,
    GatedImpulseResult,
    WindowType,
    apply_reflection_gate,
    generate_window,
    transform_impulse_to_frequency_response,
)
from acoustiforge.contracts.validation import InvalidParameterError
from acoustiforge.domain.measurements import FrequencyResponseData, ImpulseResponseData


class TestReflectionGating:
    """Test suite for reflection gating algorithms and FFT spectral transformation."""

    def test_window_generation_rectangular(self) -> None:
        """Verify rectangular window generates all ones."""
        w = generate_window(WindowType.RECTANGULAR, length=10)
        assert len(w) == 10
        np.testing.assert_allclose(w, 1.0)

    def test_window_generation_hann(self) -> None:
        """Verify Hann window endpoints and symmetry."""
        w = generate_window(WindowType.HANN, length=9)
        assert len(w) == 9
        # Endpoints should be 0.0
        assert abs(w[0] - 0.0) < 1e-12
        assert abs(w[-1] - 0.0) < 1e-12
        # Midpoint should be 1.0
        assert abs(w[4] - 1.0) < 1e-12
        # Symmetric
        np.testing.assert_allclose(w, w[::-1])

    def test_window_generation_tukey(self) -> None:
        """Verify Tukey window with alpha=0.5."""
        w = generate_window(WindowType.TUKEY, length=16, alpha=0.5)
        assert len(w) == 16
        # Center should be flat 1.0
        assert np.all(w[4:12] == 1.0)
        # Symmetrical
        np.testing.assert_allclose(w, w[::-1])

    def test_reflection_gate_preserves_buffer_and_peak(self) -> None:
        """Verify reflection gate preserves buffer length, time reference, and peak index."""
        # 1000 samples at 48 kHz (duration ~20.8 ms)
        # Direct peak at sample 100 (t ~ 2.08 ms)
        # Floor reflection at sample 400 (t ~ 8.33 ms)
        samples = np.zeros(1000, dtype=np.float64)
        samples[100] = 1.0  # Direct arrival
        samples[400] = 0.5  # Reflection echo

        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=100)

        # Apply gate: 1.0 ms left (48 samples), 4.0 ms right (192 samples)
        # Gate spans from sample (100 - 48 = 52) to sample (100 + 192 = 292)
        # The reflection at sample 400 must be zeroed out!
        spec = GateSpecification(left_time_ms=1.0, right_time_ms=4.0)
        result = apply_reflection_gate(ir, gate_spec=spec)

        assert isinstance(result, GatedImpulseResult)
        assert result.gated_impulse.num_samples == 1000
        assert result.gated_impulse.sample_rate == 48000
        assert result.gated_impulse.peak_index == 100

        # Peak preserved at full amplitude
        assert abs(result.gated_impulse.samples[100] - 1.0) < 1e-12
        # Pre-gate samples zeroed
        assert result.gated_impulse.samples[10] == 0.0
        # Reflection at sample 400 zeroed
        assert result.gated_impulse.samples[400] == 0.0

        # Gate boundaries
        assert result.gate_start_index == 100 - 48
        assert result.gate_end_index == 100 + 192
        assert result.gate_duration_seconds == (240 / 48000.0)
        assert abs(result.f_min_valid_hz - (48000.0 / 240.0)) < 1e-6

    def test_spectral_fft_transformation_dc_exclusion(self) -> None:
        """Verify FFT spectral transformation excludes DC (k=0) and generates valid FRD."""
        # Unit impulse at index 0 (Dirac delta)
        samples = np.zeros(64, dtype=np.float64)
        samples[0] = 1.0
        ir = ImpulseResponseData(samples=samples, sample_rate=48000)

        frd = transform_impulse_to_frequency_response(ir, n_fft=64)
        assert isinstance(frd, FrequencyResponseData)

        # N_fft = 64 -> rfft has 33 bins (k = 0..32)
        # DC (k=0) excluded -> 32 AC bins (k = 1..32)
        assert frd.num_points == 32
        assert frd.frequencies_hz[0] == 48000.0 / 64.0  # 750 Hz
        assert frd.frequencies_hz[-1] == 24000.0  # Nyquist

        # Dirac delta has 0.0 dB flat response across all AC bins
        np.testing.assert_allclose(frd.magnitude_db, 0.0, atol=1e-12)
        # Dirac delta at index 0 has 0.0 rad phase
        np.testing.assert_allclose(frd.phase_rad, 0.0, atol=1e-12)

    def test_spectral_fft_phase_reference_modes(self) -> None:
        """Verify raw vs peak-aligned phase transformation."""
        # Delayed delta at index D = 4
        # At fs=48000, n_fft=64: delay = 4 samples
        samples = np.zeros(64, dtype=np.float64)
        samples[4] = 1.0
        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=4)

        # 1. Raw phase retains linear time-of-flight phase slope
        frd_raw = transform_impulse_to_frequency_response(ir, n_fft=64, phase_reference="raw")
        k_indices = np.arange(1, 33, dtype=np.float64)
        raw_phase = -2.0 * np.pi * k_indices * 4.0 / 64.0
        phase_diff = np.abs(np.angle(np.exp(1j * (frd_raw.phase_rad - raw_phase))))
        np.testing.assert_allclose(phase_diff, 0.0, atol=1e-12)

        # 2. Peak-aligned phase removes the time-of-flight phase delay
        frd_aligned = transform_impulse_to_frequency_response(ir, n_fft=64, phase_reference="peak_aligned")
        np.testing.assert_allclose(frd_aligned.phase_rad, 0.0, atol=1e-12)
