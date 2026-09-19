"""Unit and Invariant Tests for Logarithmic Sine Sweep Generation & Deconvolution.

Normative Authority:
- docs/architecture/PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import io
import math
from pathlib import Path
import numpy as np
import pytest

from acoustiforge.acoustic_math.sweep import (
    LogSweepSpecification,
    deconvolve_sweep,
    export_sweep_to_wav_bytes,
    export_sweep_to_wav_file,
    generate_inverse_sweep,
    generate_log_sweep,
    sweep_to_pcm_block,
)
from acoustiforge.contracts.pcm import PCMBlock
from acoustiforge.contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
)
from acoustiforge.io.impulse_parser import parse_impulse_file


class TestLogSweepSpecification:
    """Test suite for LogSweepSpecification parameter validation."""

    def test_default_specification_is_valid(self) -> None:
        spec = LogSweepSpecification()
        assert spec.f_start == 20.0
        assert spec.f_end == 20000.0
        assert spec.duration_seconds == 5.0
        assert spec.sample_rate == 48000
        assert spec.amplitude == 0.5
        assert spec.channels == 1

    def test_invalid_sample_rates_rejected(self) -> None:
        with pytest.raises(InvalidSampleRateError):
            LogSweepSpecification(sample_rate=0)
        with pytest.raises(InvalidSampleRateError):
            LogSweepSpecification(sample_rate=-48000)
        with pytest.raises(InvalidSampleRateError):
            LogSweepSpecification(sample_rate=4000)  # Below 8000 Hz
        with pytest.raises(InvalidSampleRateError):
            LogSweepSpecification(sample_rate=500000)  # Above 384000 Hz

    def test_invalid_frequency_bounds_rejected(self) -> None:
        # f_start <= 0
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(f_start=0.0)
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(f_start=-20.0)

        # f_end <= f_start
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(f_start=1000.0, f_end=500.0)
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(f_start=1000.0, f_end=1000.0)

        # f_end > Nyquist (at 48 kHz, Nyquist is 24 kHz)
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(sample_rate=48000, f_end=24001.0)

    def test_invalid_duration_and_amplitude_rejected(self) -> None:
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(duration_seconds=0.05)  # < 0.1 s
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(amplitude=0.0)
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(amplitude=1.5)  # > 1.0

    def test_invalid_fade_times_rejected(self) -> None:
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(fade_in_seconds=-0.1)
        with pytest.raises(InvalidParameterError):
            LogSweepSpecification(duration_seconds=1.0, fade_in_seconds=0.6, fade_out_seconds=0.6)


class TestLogSweepGeneration:
    """Test suite for deterministic sweep generation and properties."""

    def test_generate_log_sweep_dimensions_and_determinism(self) -> None:
        spec = LogSweepSpecification(
            f_start=20.0,
            f_end=20000.0,
            duration_seconds=1.0,
            sample_rate=48000,
            amplitude=0.5,
        )
        sweep1 = generate_log_sweep(spec)
        sweep2 = generate_log_sweep(spec)

        assert isinstance(sweep1, np.ndarray)
        assert sweep1.shape == (48000,)
        assert sweep1.dtype == np.float64
        # Bit-exact determinism across repeated runs
        np.testing.assert_array_equal(sweep1, sweep2)

        # Amplitude peak bounded by spec.amplitude
        assert np.max(np.abs(sweep1)) <= 0.5000001

    def test_fade_in_fade_out_smoothness(self) -> None:
        spec = LogSweepSpecification(
            duration_seconds=1.0,
            sample_rate=48000,
            amplitude=1.0,
            fade_in_seconds=0.1,
            fade_out_seconds=0.1,
        )
        sweep = generate_log_sweep(spec)
        # First sample should be close to 0 due to cosine taper
        assert abs(sweep[0]) < 1e-6
        # End sample should be close to 0
        assert abs(sweep[-1]) < 1e-2


class TestFarinaDeconvolution:
    """Test suite for analytical inverse sweep filtering and deconvolution."""

    def test_inverse_sweep_determinism(self) -> None:
        spec = LogSweepSpecification(
            f_start=50.0,
            f_end=15000.0,
            duration_seconds=0.5,
            sample_rate=48000,
            amplitude=0.5,
        )
        inv1 = generate_inverse_sweep(spec)
        inv2 = generate_inverse_sweep(spec)

        assert inv1.shape == (24000,)
        assert inv1.dtype == np.float64
        np.testing.assert_array_equal(inv1, inv2)

    def test_deconvolution_ideal_loopback_recovers_unit_impulse(self) -> None:
        spec = LogSweepSpecification(
            f_start=20.0,
            f_end=20000.0,
            duration_seconds=0.5,
            sample_rate=48000,
            amplitude=0.5,
            fade_in_seconds=0.01,
            fade_out_seconds=0.01,
        )
        sweep = generate_log_sweep(spec)
        inv_sweep = generate_inverse_sweep(spec)

        # Ideal loopback: recorded signal is identical to sweep
        ir = deconvolve_sweep(sweep, inv_sweep)

        expected_peak_index = len(sweep) - 1
        actual_peak_index = int(np.argmax(np.abs(ir)))

        assert actual_peak_index == expected_peak_index
        # Peak amplitude normalized to 1.0
        assert abs(ir[actual_peak_index] - 1.0) < 1e-4

        # Verify that pre-impulse and post-impulse energy is low
        pre_noise = np.max(np.abs(ir[: expected_peak_index - 50]))
        assert pre_noise < 0.05

    def test_deconvolution_known_gain_and_delay(self) -> None:
        spec = LogSweepSpecification(
            f_start=20.0,
            f_end=20000.0,
            duration_seconds=0.4,
            sample_rate=48000,
            amplitude=0.6,
            fade_in_seconds=0.01,
            fade_out_seconds=0.01,
        )
        sweep = generate_log_sweep(spec)
        inv_sweep = generate_inverse_sweep(spec)

        known_delay = 120  # 120 samples delay = 2.5 ms
        known_gain = 0.75  # -2.5 dB gain

        # Synthesize delayed and scaled recorded signal
        recorded = np.zeros(len(sweep) + known_delay + 200, dtype=np.float64)
        recorded[known_delay : known_delay + len(sweep)] = sweep * known_gain

        ir = deconvolve_sweep(recorded, inv_sweep)

        expected_peak_index = (len(sweep) - 1) + known_delay
        actual_peak_index = int(np.argmax(np.abs(ir)))

        assert actual_peak_index == expected_peak_index
        assert abs(ir[actual_peak_index] - known_gain) < 1e-3

    def test_deconvolution_fir_synthetic_path(self) -> None:
        spec = LogSweepSpecification(
            f_start=40.0,
            f_end=18000.0,
            duration_seconds=0.3,
            sample_rate=48000,
            amplitude=0.5,
            fade_in_seconds=0.01,
            fade_out_seconds=0.01,
        )
        sweep = generate_log_sweep(spec)
        inv_sweep = generate_inverse_sweep(spec)

        # Known FIR channel: direct path 1.0, reflection at +50 samples with -0.5 gain
        recorded = np.zeros(len(sweep) + 100, dtype=np.float64)
        recorded[: len(sweep)] += sweep * 1.0
        recorded[50 : 50 + len(sweep)] += sweep * (-0.5)

        ir = deconvolve_sweep(recorded, inv_sweep)

        peak_0 = len(sweep) - 1
        peak_50 = peak_0 + 50

        assert abs(ir[peak_0] - 1.0) < 1e-2
        assert abs(ir[peak_50] - (-0.5)) < 1e-2

    def test_deconvolve_sweep_malformed_inputs_rejected(self) -> None:
        inv = np.ones(100, dtype=np.float64)
        with pytest.raises(InvalidParameterError):
            deconvolve_sweep("not_an_array", inv)  # type: ignore
        with pytest.raises(InvalidParameterError):
            deconvolve_sweep(np.ones((10, 10)), inv)  # 2D array
        with pytest.raises(InvalidParameterError):
            deconvolve_sweep(np.array([]), inv)  # empty
        with pytest.raises(InvalidParameterError):
            deconvolve_sweep(np.array([1.0, np.nan]), inv)  # NaN


class TestSweepPCMAndWAVExport:
    """Test suite for PCMBlock conversion and pure WAV file export."""

    def test_sweep_to_pcm_block(self) -> None:
        spec = LogSweepSpecification(duration_seconds=0.2, sample_rate=48000, channels=2)
        sweep = generate_log_sweep(spec)

        block = sweep_to_pcm_block(sweep, sample_rate=48000, channels=2)
        assert isinstance(block, PCMBlock)
        assert block.sample_rate == 48000
        assert block.channels == 2
        assert block.frames == len(sweep)
        assert block.samples.shape == (2, len(sweep))
        assert block.samples.dtype == np.float32

    def test_export_sweep_to_wav_roundtrip(self, tmp_path: Path) -> None:
        spec = LogSweepSpecification(duration_seconds=0.25, sample_rate=48000, amplitude=0.5)
        sweep = generate_log_sweep(spec)

        # 16-bit WAV
        wav_file_16 = tmp_path / "sweep16.wav"
        export_sweep_to_wav_file(sweep, 48000, wav_file_16, bits_per_sample=16)
        assert wav_file_16.exists()
        ir_data_16 = parse_impulse_file(wav_file_16)
        assert ir_data_16.sample_rate == 48000
        assert ir_data_16.num_samples == len(sweep)
        # Quantization error for 16-bit is < 1/32767
        np.testing.assert_allclose(ir_data_16.samples, sweep, atol=1e-4)

        # 24-bit WAV
        wav_file_24 = tmp_path / "sweep24.wav"
        export_sweep_to_wav_file(sweep, 48000, wav_file_24, bits_per_sample=24)
        ir_data_24 = parse_impulse_file(wav_file_24)
        np.testing.assert_allclose(ir_data_24.samples, sweep, atol=1e-6)

        # 32-bit Float WAV
        wav_file_32 = tmp_path / "sweep32.wav"
        export_sweep_to_wav_file(sweep, 48000, wav_file_32, bits_per_sample=32)
        ir_data_32 = parse_impulse_file(wav_file_32)
        np.testing.assert_allclose(ir_data_32.samples, sweep, atol=1e-7)
