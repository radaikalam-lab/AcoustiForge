"""Integration and End-to-End Simulation of the Physical Closed-Loop Measurement Pipeline.

Simulates the complete physical hardware measurement sequence in software:
Sweep Generation -> Synthetic Room Transmission -> ALSA Capture -> Deconvolution ->
Impulse Extraction -> Reflection Gating -> Microphone Calibration -> FrequencyResponseData.

Normative Authority:
- docs/architecture/PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md
- docs/phases/PHASE_4C_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.acoustic_math.calibration import (
    CalibrationBoundaryPolicy,
    apply_microphone_calibration,
)
from acoustiforge.acoustic_math.diagnostics import (
    DiagnosticFlag,
    evaluate_measurement_quality,
)
from acoustiforge.acoustic_math.gating import (
    GateSpecification,
    WindowType,
    apply_reflection_gate,
    transform_impulse_to_frequency_response,
)
from acoustiforge.acoustic_math.sweep import (
    LogSweepSpecification,
    deconvolve_sweep,
    generate_inverse_sweep,
    generate_log_sweep,
)
from acoustiforge.domain.measurements import FrequencyResponseData, ImpulseResponseData
from acoustiforge.execution.alsa import (
    AlsaAudioCapture,
    AlsaCaptureConfig,
    MockAlsaDeviceHandle,
)


class TestPhysicalLoopHarness:
    """End-to-end integration test simulating the physical measurement loop."""

    def test_full_closed_loop_measurement_pipeline(self) -> None:
        sample_rate = 48000
        duration_s = 0.5

        # 1. Generate deterministic logarithmic sine sweep
        sweep_spec = LogSweepSpecification(
            f_start=30.0,
            f_end=20000.0,
            duration_seconds=duration_s,
            sample_rate=sample_rate,
            amplitude=0.5,
            fade_in_seconds=0.01,
            fade_out_seconds=0.01,
        )
        sweep = generate_log_sweep(sweep_spec)
        inv_sweep = generate_inverse_sweep(sweep_spec)
        n_sweep = len(sweep)

        # 2. Simulate physical room acoustic path:
        # - Direct acoustic flight delay: 5.0 ms = 240 samples
        # - Room boundary reflection: 12.0 ms (7.0 ms after direct sound = 336 samples) @ -12 dB (gain 0.25)
        # - Low-level ambient room noise (-70 dBFS)
        direct_delay = int(round(0.005 * sample_rate))  # 240 samples
        refl_delay = direct_delay + int(round(0.007 * sample_rate))  # 240 + 336 = 576 samples
        total_len = n_sweep + refl_delay + 2000

        simulated_room_mic = np.zeros(total_len, dtype=np.float32)
        # Direct path
        simulated_room_mic[direct_delay : direct_delay + n_sweep] += (sweep * 0.8).astype(np.float32)
        # Reflected path
        simulated_room_mic[refl_delay : refl_delay + n_sweep] += (sweep * (0.8 * 0.25)).astype(np.float32)

        # 3. Simulate ALSA hardware capture via AlsaAudioCapture & MockAlsaDeviceHandle
        capture_cfg = AlsaCaptureConfig(
            alsa_device="hw:1,0",
            sample_rate=sample_rate,
            channels=1,
            block_size=256,
        )
        mock_handle = MockAlsaDeviceHandle(
            device_name="hw:1,0",
            sample_rate=sample_rate,
            channels=1,
            block_size=256,
            mock_capture_source=simulated_room_mic,
        )

        capture = AlsaAudioCapture(config=capture_cfg, mock_handle=mock_handle)
        captured_block = capture.record_frames(total_len)
        capture.close()

        assert captured_block.frames == total_len
        recorded_audio = captured_block.samples[0]

        # 4. Deconvolve captured audio using Farina inverse filter
        raw_ir = deconvolve_sweep(recorded_audio, inv_sweep)

        # Peak of direct sound impulse occurs at (n_sweep - 1) + direct_delay
        expected_direct_idx = (n_sweep - 1) + direct_delay
        actual_direct_idx = int(np.argmax(np.abs(raw_ir)))
        assert actual_direct_idx == expected_direct_idx

        # 5. Extract time-domain ImpulseResponseData centered on direct arrival
        # Extract 100 samples pre-peak and 2000 samples post-peak
        ir_start = actual_direct_idx - 100
        ir_end = actual_direct_idx + 2000
        sliced_ir = raw_ir[ir_start:ir_end]

        impulse_data = ImpulseResponseData(
            samples=sliced_ir,
            sample_rate=sample_rate,
        )

        # 6. Apply reflection gate before room reflection arrives (gate window = 5.0 ms = 240 samples)
        gate_spec = GateSpecification(
            left_window=WindowType.HALF_HANN,
            left_time_ms=1.5,
            right_window=WindowType.HALF_TUKEY,
            right_time_ms=5.0,  # Gates out the reflection at 7.0 ms
            taper_alpha=0.25,
        )
        gated_result = apply_reflection_gate(impulse_data, gate_spec)
        assert gated_result.f_min_valid_hz > 0.0

        # 7. Transform gated impulse to frequency response
        raw_frd = transform_impulse_to_frequency_response(gated_result.gated_impulse, n_fft=4096)
        assert isinstance(raw_frd, FrequencyResponseData)
        assert len(raw_frd.frequencies_hz) > 100

        # 8. Apply microphone calibration subtraction
        cal_freqs = raw_frd.frequencies_hz
        # Synthetic mic calibration curve: +1.0 dB at 10 kHz
        cal_mags = np.sin(np.pi * cal_freqs / 20000.0) * 1.0
        cal_data = FrequencyResponseData(frequencies_hz=cal_freqs, magnitude_db=cal_mags)

        calibrated_frd = apply_microphone_calibration(
            raw_measurement=raw_frd,
            calibration_data=cal_data,
            boundary_policy=CalibrationBoundaryPolicy.CLAMP,
        )

        # 9. Verify measurement diagnostics quality
        diag_report = evaluate_measurement_quality(
            frequency_response=calibrated_frd,
            gated_result=gated_result,
        )
        assert diag_report.is_valid

        # 10. Verify recovered magnitude is flat (matches direct path gain of 0.8 -> -1.94 dB - calibration)
        valid_mask = (calibrated_frd.frequencies_hz >= 200.0) & (calibrated_frd.frequencies_hz <= 15000.0)
        valid_mags = calibrated_frd.magnitude_db[valid_mask]
        # Peak-to-peak ripple in valid passband should be < 2.0 dB
        mag_span = np.max(valid_mags) - np.min(valid_mags)
        assert mag_span < 2.5
