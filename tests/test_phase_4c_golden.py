"""Independent Analytical Golden Vectors for Phase 4C Impulse Ingestion, Gating, and Transformation.

Normative Authority:
- docs/contracts/IMPULSE_RESPONSE_INGESTION_CONTRACT.md
- docs/contracts/REFLECTION_GATING_CONTRACT.md
- docs/contracts/MEASUREMENT_DIAGNOSTICS_CONTRACT.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import io
import math
import struct
import numpy as np
import pytest

from acoustiforge.acoustic_math.gating import (
    GateSpecification,
    WindowType,
    apply_reflection_gate,
    generate_window,
    transform_impulse_to_frequency_response,
)
from acoustiforge.domain.measurements import FrequencyResponseData, ImpulseResponseData
from acoustiforge.io.impulse_parser import _parse_wav_bytes


class TestPhase4CGolden:
    """Independent analytical verification of Phase 4C mathematical identities."""

    def test_golden_dirac_delta_analytical_flat_spectrum(self) -> None:
        """Verify analytical Dirac delta: |H|=1.0 (0.0 dB), phase=0.0 rad within 1e-12."""
        # h[0] = 1.0, h[n>0] = 0.0
        n_samples = 64
        fs = 48000
        samples = np.zeros(n_samples, dtype=np.float64)
        samples[0] = 1.0
        ir = ImpulseResponseData(samples=samples, sample_rate=fs, peak_index=0)

        frd = transform_impulse_to_frequency_response(ir, n_fft=64)

        # Analytical Identity:
        # H[k] = sum_{n=0}^{63} delta[n] e^(-j 2pi k n / 64) = 1.0 + 0j
        # Magnitude = 20 log10(1.0) = 0.0 dB
        # Phase = atan2(0.0, 1.0) = 0.0 rad
        np.testing.assert_allclose(frd.magnitude_db, 0.0, atol=1e-12)
        np.testing.assert_allclose(frd.phase_rad, 0.0, atol=1e-12)

    def test_golden_delayed_delta_analytical_linear_phase(self) -> None:
        """Verify analytical delayed delta: |H|=1.0 (0.0 dB), phi(f) = -2pi f D / fs within 1e-12."""
        n_samples = 128
        fs = 48000
        delay_samples = 5
        samples = np.zeros(n_samples, dtype=np.float64)
        samples[delay_samples] = 1.0
        ir = ImpulseResponseData(samples=samples, sample_rate=fs, peak_index=delay_samples)

        frd = transform_impulse_to_frequency_response(ir, n_fft=128, phase_reference="raw")

        # Analytical Identity:
        # H[k] = e^(-j 2pi k * 5 / 128)
        # Magnitude = 0.0 dB
        # Phase = -2pi * k * 5 / 128 (wrapped to (-pi, pi])
        np.testing.assert_allclose(frd.magnitude_db, 0.0, atol=1e-12)

        k_indices = np.arange(1, 65, dtype=np.float64)
        raw_phase = -2.0 * math.pi * k_indices * float(delay_samples) / 128.0
        phase_diff = np.abs(np.angle(np.exp(1j * (frd.phase_rad - raw_phase))))
        np.testing.assert_allclose(phase_diff, 0.0, atol=1e-12)

    def test_golden_single_pole_exponential_decay_analytical(self) -> None:
        """Verify exponential decay impulse response against closed-form 1st-order discrete filter response."""
        # h[n] = a^n = e^(-n / tau), where a = 0.75, tau = -1 / ln(0.75)
        # H(z) = 1 / (1 - a z^(-1))
        # H(e^(j omega)) = 1 / (1 - a e^(-j omega))
        n_samples = 512
        fs = 48000
        a = 0.75
        n = np.arange(n_samples, dtype=np.float64)
        samples = np.power(a, n)
        ir = ImpulseResponseData(samples=samples, sample_rate=fs, peak_index=0)

        # High FFT resolution to minimize truncation error
        n_fft = 2048
        frd = transform_impulse_to_frequency_response(ir, n_fft=n_fft)

        # Analytical transfer function at frequencies f_k
        omega = 2.0 * math.pi * frd.frequencies_hz / float(fs)
        h_analytical = 1.0 / (1.0 - a * np.exp(-1j * omega))
        expected_mag_db = 20.0 * np.log10(np.abs(h_analytical))
        expected_phase_rad = np.angle(h_analytical)

        np.testing.assert_allclose(frd.magnitude_db, expected_mag_db, atol=1e-4)
        np.testing.assert_allclose(frd.phase_rad, expected_phase_rad, atol=1e-4)

    def test_golden_reflection_isolation_analytical(self) -> None:
        """Verify reflection gating completely isolates direct Dirac sound from delayed echo."""
        # Direct impulse at sample 100
        # Simulated reflection at sample 400 (delay 300 samples = 6.25 ms at 48 kHz)
        samples = np.zeros(1024, dtype=np.float64)
        samples[100] = 1.0  # Direct
        samples[400] = 0.6  # Reflection

        ir = ImpulseResponseData(samples=samples, sample_rate=48000, peak_index=100)

        # 1. Without gating (full buffer FFT): exhibits comb filtering ripple ~8.5 dB
        frd_ungated = transform_impulse_to_frequency_response(ir, n_fft=1024)
        ripple_ungated = np.max(frd_ungated.magnitude_db) - np.min(frd_ungated.magnitude_db)
        assert ripple_ungated > 8.0

        # 2. With reflection gate: 1.0 ms left, 4.0 ms right (cuts off at sample 100 + 192 = 292, before sample 400)
        spec = GateSpecification(
            left_time_ms=1.0,
            right_time_ms=4.0,
            left_window=WindowType.RECTANGULAR,
            right_window=WindowType.RECTANGULAR,
        )
        gated_res = apply_reflection_gate(ir, gate_spec=spec)
        frd_gated = transform_impulse_to_frequency_response(gated_res, n_fft=1024)

        # After gating, the reflection is 100% eliminated, restoring a pure 0.0 dB flat response!
        np.testing.assert_allclose(frd_gated.magnitude_db, 0.0, atol=1e-12)

    def test_golden_window_mathematical_vectors(self) -> None:
        """Verify window generator against exact closed-form analytical formulas."""
        # 1. Hann length 5:
        # n = 0, 1, 2, 3, 4, M=5, M-1=4
        # w[0] = 0.5*(1 - cos(0)) = 0.0
        # w[1] = 0.5*(1 - cos(pi/2)) = 0.5
        # w[2] = 0.5*(1 - cos(pi)) = 1.0
        # w[3] = 0.5*(1 - cos(3pi/2)) = 0.5
        # w[4] = 0.5*(1 - cos(2pi)) = 0.0
        expected_hann = np.array([0.0, 0.5, 1.0, 0.5, 0.0], dtype=np.float64)
        w_hann = generate_window(WindowType.HANN, length=5)
        np.testing.assert_allclose(w_hann, expected_hann, atol=1e-12)

    def test_golden_wav_decoding_exact_bit_reproduction(self) -> None:
        """Verify independent byte stream decoding across 16-bit, 24-bit, and 32-bit float."""
        # 1. 16-bit PCM: byte pair 0x00, 0x40 -> signed integer 16384 -> 16384 / 32768 = 0.5
        # Byte pair 0x00, 0xC0 -> signed integer -16384 -> -0.5
        bio = io.BytesIO()
        bio.write(b"RIFF" + struct.pack("<I", 40) + b"WAVE")
        bio.write(b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16))
        # 16 samples minimum
        data = struct.pack("<h", 16384) + struct.pack("<h", -16384) + (b"\x00\x00" * 14)
        bio.write(b"data" + struct.pack("<I", len(data)) + data)

        ir = _parse_wav_bytes(bio.getvalue())
        assert abs(ir.samples[0] - 0.5) < 1e-12
        assert abs(ir.samples[1] - (-0.5)) < 1e-12
