"""AcoustiForge Deterministic Logarithmic Sine Sweep & Deconvolution Engine.

Provides mathematically rigorous, reproducible excitation signal generation,
analytical inverse filtering (Farina method), and fast Fourier deconvolution
for physical and synthetic acoustic transfer function measurement.

Normative Authority:
- docs/architecture/PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import math
from pathlib import Path
import struct
from typing import Optional, Tuple, Union
import numpy as np

from ..contracts.pcm import AudioMetadata, PCMBlock
from ..contracts.validation import (
    InvalidParameterError,
    InvalidSampleRateError,
    MalformedBufferError,
)
from ..domain.measurements import ImpulseResponseData


@dataclass(frozen=True, slots=True)
class LogSweepSpecification:
    """Immutable configuration specification for logarithmic sine sweep generation."""

    f_start: float = 20.0
    f_end: float = 20000.0
    duration_seconds: float = 5.0
    sample_rate: int = 48000
    amplitude: float = 0.5  # ~-6.0 dBFS, provides headroom against DAC inter-sample clipping
    fade_in_seconds: float = 0.05  # 50 ms cosine fade-in
    fade_out_seconds: float = 0.05  # 50 ms cosine fade-out
    channels: int = 1

    def __post_init__(self) -> None:
        """Validate specification parameter bounds strictly."""
        if not isinstance(self.sample_rate, int) or isinstance(self.sample_rate, bool) or self.sample_rate <= 0:
            raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {self.sample_rate!r}.")

        if not (8000 <= self.sample_rate <= 384000):
            raise InvalidSampleRateError(
                f"sample_rate {self.sample_rate} Hz is outside supported range [8000, 384000] Hz."
            )

        if not isinstance(self.channels, int) or isinstance(self.channels, bool) or self.channels < 1:
            raise InvalidParameterError(f"channels must be an integer >= 1, got {self.channels!r}.")

        if not isinstance(self.duration_seconds, (int, float)) or isinstance(self.duration_seconds, bool) or not math.isfinite(self.duration_seconds) or self.duration_seconds < 0.1:
            raise InvalidParameterError(
                f"duration_seconds must be a finite float >= 0.1 s, got {self.duration_seconds!r}."
            )

        if not isinstance(self.amplitude, (int, float)) or isinstance(self.amplitude, bool) or not math.isfinite(self.amplitude) or not (0.0 < self.amplitude <= 1.0):
            raise InvalidParameterError(
                f"amplitude must be in range (0.0, 1.0], got {self.amplitude!r}."
            )

        if not isinstance(self.f_start, (int, float)) or isinstance(self.f_start, bool) or not math.isfinite(self.f_start) or self.f_start <= 0.0:
            raise InvalidParameterError(f"f_start must be positive finite float, got {self.f_start!r}.")

        nyquist = self.sample_rate / 2.0
        if not isinstance(self.f_end, (int, float)) or isinstance(self.f_end, bool) or not math.isfinite(self.f_end) or self.f_end <= self.f_start or self.f_end > nyquist:
            raise InvalidParameterError(
                f"f_end ({self.f_end} Hz) must satisfy f_start ({self.f_start} Hz) < f_end <= Nyquist ({nyquist} Hz)."
            )

        if not isinstance(self.fade_in_seconds, (int, float)) or isinstance(self.fade_in_seconds, bool) or self.fade_in_seconds < 0.0:
            raise InvalidParameterError(f"fade_in_seconds must be non-negative float, got {self.fade_in_seconds!r}.")

        if not isinstance(self.fade_out_seconds, (int, float)) or isinstance(self.fade_out_seconds, bool) or self.fade_out_seconds < 0.0:
            raise InvalidParameterError(f"fade_out_seconds must be non-negative float, got {self.fade_out_seconds!r}.")

        if (self.fade_in_seconds + self.fade_out_seconds) > self.duration_seconds:
            raise InvalidParameterError(
                f"Sum of fade_in ({self.fade_in_seconds}s) and fade_out ({self.fade_out_seconds}s) "
                f"exceeds total duration ({self.duration_seconds}s)."
            )


def generate_log_sweep(spec: LogSweepSpecification) -> np.ndarray:
    """Generate a deterministic 1D logarithmic sine sweep waveform.

    Mathematical Formulation:
    L = ln(f_end / f_start)
    phi(t) = (2 * pi * f_start * T / L) * (exp(t * L / T) - 1)
    x(t) = amplitude * sin(phi(t))

    Args:
        spec: Valid LogSweepSpecification.

    Returns:
        1D float64 NumPy array of sweep samples.
    """
    if not isinstance(spec, LogSweepSpecification):
        raise InvalidParameterError(f"Expected LogSweepSpecification, got {type(spec)!r}.")

    num_samples = int(round(spec.duration_seconds * spec.sample_rate))
    t = np.arange(num_samples, dtype=np.float64) / spec.sample_rate

    f1 = float(spec.f_start)
    f2 = float(spec.f_end)
    t_tot = float(spec.duration_seconds)
    rate = float(spec.sample_rate)

    rate_factor = math.log(f2 / f1)
    k = (2.0 * math.pi * f1 * t_tot) / rate_factor
    phi = k * (np.exp(t * rate_factor / t_tot) - 1.0)
    sweep = spec.amplitude * np.sin(phi)

    # Apply smooth cosine taper to boundaries
    if spec.fade_in_seconds > 0.0:
        n_in = min(num_samples, int(round(spec.fade_in_seconds * spec.sample_rate)))
        if n_in > 0:
            w_in = 0.5 * (1.0 - np.cos(np.pi * np.arange(n_in, dtype=np.float64) / n_in))
            sweep[:n_in] *= w_in

    if spec.fade_out_seconds > 0.0:
        n_out = min(num_samples, int(round(spec.fade_out_seconds * spec.sample_rate)))
        if n_out > 0:
            w_out = 0.5 * (1.0 + np.cos(np.pi * np.arange(n_out, dtype=np.float64) / n_out))
            sweep[-n_out:] *= w_out

    return sweep


def generate_inverse_sweep(spec: LogSweepSpecification) -> np.ndarray:
    """Generate the deterministic analytical inverse sweep filter using the Farina method.

    The inverse filter is constructed by time-reversing the sweep waveform and modulating
    it with an exponential decay envelope (-6 dB/octave attenuation) to compensate for the
    pink spectral distribution of logarithmic sweeps. The filter is normalized such that
    linear deconvolution of an ideal loopback sweep yields an impulse of peak amplitude 1.0.

    Args:
        spec: Valid LogSweepSpecification.

    Returns:
        1D float64 NumPy array of inverse sweep filter coefficients.
    """
    if not isinstance(spec, LogSweepSpecification):
        raise InvalidParameterError(f"Expected LogSweepSpecification, got {type(spec)!r}.")

    sweep = generate_log_sweep(spec)
    num_samples = len(sweep)
    t = np.arange(num_samples, dtype=np.float64) / spec.sample_rate

    f1 = float(spec.f_start)
    f2 = float(spec.f_end)
    t_tot = float(spec.duration_seconds)
    rate_factor = math.log(f2 / f1)

    # Time-reversal and -6 dB/octave modulation
    envelope = np.exp(-t * rate_factor / t_tot)
    inv_unnormalized = sweep[::-1] * envelope

    # Analytical peak normalization via FFT convolution with clean sweep
    n_conv = 2 * num_samples - 1
    n_fft = 1 << (n_conv - 1).bit_length()

    fft_sweep = np.fft.rfft(sweep, n=n_fft)
    fft_inv = np.fft.rfft(inv_unnormalized, n=n_fft)
    conv_result = np.fft.irfft(fft_sweep * fft_inv, n=n_fft)[:n_conv]

    peak_val = float(np.max(np.abs(conv_result)))
    if peak_val > 0.0:
        inv_normalized = inv_unnormalized / peak_val
    else:
        inv_normalized = inv_unnormalized

    return inv_normalized


def deconvolve_sweep(
    recorded_signal: np.ndarray,
    inverse_sweep: np.ndarray,
    n_fft: Optional[int] = None,
) -> np.ndarray:
    """Deconvolve a recorded acoustic response against the inverse sweep filter.

    Computes linear convolution: ir[n] = recorded_signal[n] * inverse_sweep[n]
    via fast Fourier transform.

    Args:
        recorded_signal: 1D NumPy array of recorded audio samples.
        inverse_sweep: 1D NumPy array of inverse sweep filter coefficients.
        n_fft: Optional explicit FFT length (must be >= len(recorded) + len(inv) - 1).

    Returns:
        1D float64 NumPy array of deconvolved linear response samples.

    Raises:
        InvalidParameterError: If inputs are malformed or non-1D.
    """
    if not isinstance(recorded_signal, np.ndarray) or not isinstance(inverse_sweep, np.ndarray):
        raise InvalidParameterError("recorded_signal and inverse_sweep must be numpy ndarrays.")

    if recorded_signal.ndim != 1 or inverse_sweep.ndim != 1:
        raise InvalidParameterError(
            f"Expected 1D arrays, got recorded_signal ndim={recorded_signal.ndim}, inverse_sweep ndim={inverse_sweep.ndim}."
        )

    if recorded_signal.size == 0 or inverse_sweep.size == 0:
        raise InvalidParameterError("Inputs must not be empty.")

    if not np.all(np.isfinite(recorded_signal)) or not np.all(np.isfinite(inverse_sweep)):
        raise InvalidParameterError("Input arrays must contain finite numbers.")

    n_y = len(recorded_signal)
    n_inv = len(inverse_sweep)
    n_conv = n_y + n_inv - 1

    if n_fft is None:
        calc_fft = 1 << (n_conv - 1).bit_length()
    else:
        if not isinstance(n_fft, int) or n_fft < n_conv:
            raise InvalidParameterError(f"Explicit n_fft ({n_fft}) must be integer >= {n_conv}.")
        calc_fft = n_fft

    y_fft = np.fft.rfft(recorded_signal.astype(np.float64), n=calc_fft)
    h_fft = np.fft.rfft(inverse_sweep.astype(np.float64), n=calc_fft)
    ir = np.fft.irfft(y_fft * h_fft, n=calc_fft)[:n_conv]

    return ir


def sweep_to_pcm_block(
    sweep: np.ndarray,
    sample_rate: int,
    channels: int = 1,
) -> PCMBlock:
    """Convert a 1D sweep array into a canonical planar float32 PCMBlock.

    Args:
        sweep: 1D NumPy array.
        sample_rate: Audio sampling rate in Hz.
        channels: Channel count (samples will be replicated across channels).

    Returns:
        Canonical planar float32 PCMBlock of shape (channels, frames).
    """
    if not isinstance(sweep, np.ndarray) or sweep.ndim != 1:
        raise InvalidParameterError(f"Expected 1D numpy array, got {type(sweep)!r}.")

    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    if not isinstance(channels, int) or isinstance(channels, bool) or channels < 1:
        raise InvalidParameterError(f"channels must be an integer >= 1, got {channels!r}.")

    frames = len(sweep)
    planar = np.tile(sweep.astype(np.float32), (channels, 1))
    metadata = AudioMetadata(sample_rate=sample_rate, channels=channels)
    return PCMBlock(samples=planar, metadata=metadata)


def export_sweep_to_wav_bytes(
    sweep: np.ndarray,
    sample_rate: int,
    bits_per_sample: int = 16,
) -> bytes:
    """Export a 1D float sweep array to standard RIFF/WAVE binary bytes without third-party dependencies.

    Args:
        sweep: 1D NumPy array in range [-1.0, 1.0].
        sample_rate: Sample rate in Hz.
        bits_per_sample: Bit depth (16 or 32 for float).

    Returns:
        Standard RIFF/WAVE byte stream.
    """
    if not isinstance(sweep, np.ndarray) or sweep.ndim != 1:
        raise InvalidParameterError("sweep must be a 1D numpy ndarray.")

    if not isinstance(sample_rate, int) or sample_rate <= 0:
        raise InvalidSampleRateError(f"Invalid sample_rate: {sample_rate!r}.")

    if bits_per_sample not in (16, 24, 32):
        raise InvalidParameterError(f"bits_per_sample must be 16, 24, or 32, got {bits_per_sample!r}.")

    num_channels = 1
    total_frames = len(sweep)
    bytes_per_sample = bits_per_sample // 8
    data_size = total_frames * num_channels * bytes_per_sample

    bio = io.BytesIO()

    # 1. RIFF Header
    bio.write(b"RIFF")
    bio.write(struct.pack("<I", 36 + data_size))
    bio.write(b"WAVE")

    # 2. fmt Chunk
    format_code = 3 if bits_per_sample == 32 else 1  # 3 = IEEE Float, 1 = PCM
    byte_rate = sample_rate * num_channels * bytes_per_sample
    block_align = num_channels * bytes_per_sample
    bio.write(b"fmt ")
    bio.write(struct.pack("<IHHIIHH", 16, format_code, num_channels, sample_rate, byte_rate, block_align, bits_per_sample))

    # 3. data Chunk
    bio.write(b"data")
    bio.write(struct.pack("<I", data_size))

    if bits_per_sample == 16:
        int_samples = np.clip(np.round(sweep * 32767.0), -32768, 32767).astype(np.int16)
        bio.write(int_samples.tobytes())
    elif bits_per_sample == 24:
        int_samples = np.clip(np.round(sweep * 8388607.0), -8388608, 8388607).astype(np.int32)
        raw_bytes = bytearray()
        for val in int_samples:
            raw_bytes.append(val & 0xFF)
            raw_bytes.append((val >> 8) & 0xFF)
            raw_bytes.append((val >> 16) & 0xFF)
        bio.write(bytes(raw_bytes))
    elif bits_per_sample == 32:
        float_samples = sweep.astype(np.float32)
        bio.write(float_samples.tobytes())

    return bio.getvalue()


def export_sweep_to_wav_file(
    sweep: np.ndarray,
    sample_rate: int,
    file_path: Union[str, Path],
    bits_per_sample: int = 16,
) -> Path:
    """Export sweep to a WAV file on disk."""
    wav_bytes = export_sweep_to_wav_bytes(sweep, sample_rate, bits_per_sample=bits_per_sample)
    path = Path(file_path)
    path.write_bytes(wav_bytes)
    return path
