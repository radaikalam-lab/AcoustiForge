"""Unit and Integration Tests for Linux ALSA Audio Capture Subsystem (Unit C).

Normative Authority:
- docs/architecture/PHASE_5_4C_PHYSICAL_VALIDATION_DISCOVERY.md
- docs/architecture/PHASE_5_4_LINUX_ALSA_HARDWARE_BACKEND.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import numpy as np
import pytest

from acoustiforge.contracts.pcm import PCMBlock
from acoustiforge.execution.alsa import (
    AlsaAudioCapture,
    AlsaCaptureConfig,
    AlsaCtypesBinding,
    AlsaPCMAdapter,
    EBADFD,
    EIO,
    EPIPE,
    ExecutionConfigError,
    ExecutionDeviceError,
    ExecutionState,
    ExecutionStateError,
    MockAlsaDeviceHandle,
)


class TestAlsaCaptureConfig:
    """Test suite for AlsaCaptureConfig validation."""

    def test_valid_default_config(self) -> None:
        cfg = AlsaCaptureConfig()
        assert cfg.alsa_device == "default"
        assert cfg.sample_rate == 48000
        assert cfg.channels == 1
        assert cfg.block_size == 256
        assert cfg.use_int16 is False

    def test_invalid_config_parameters_raise(self) -> None:
        with pytest.raises(ExecutionConfigError):
            AlsaCaptureConfig(alsa_device="")
        with pytest.raises(ExecutionConfigError):
            AlsaCaptureConfig(sample_rate=-1)
        with pytest.raises(ExecutionConfigError):
            AlsaCaptureConfig(sample_rate=4000)  # Below 8000 Hz
        with pytest.raises(ExecutionConfigError):
            AlsaCaptureConfig(channels=0)
        with pytest.raises(ExecutionConfigError):
            AlsaCaptureConfig(block_size=0)


class TestMockAlsaCapture:
    """Test suite for AlsaAudioCapture using deterministic MockAlsaDeviceHandle."""

    def test_capture_read_block_float32(self) -> None:
        cfg = AlsaCaptureConfig(sample_rate=48000, channels=2, block_size=128, use_int16=False)

        # 2 channels, 256 frames of source data
        source_data = np.linspace(-0.8, 0.8, 256 * 2, dtype=np.float32)
        mock_handle = MockAlsaDeviceHandle(
            device_name="hw:0,0",
            sample_rate=48000,
            channels=2,
            block_size=128,
            mock_capture_source=source_data,
        )

        capture = AlsaAudioCapture(config=cfg, mock_handle=mock_handle)
        assert capture.state == ExecutionState.UNINITIALIZED

        capture.start()
        assert capture.state == ExecutionState.RUNNING

        # Read first block (128 frames)
        block1 = capture.read_block()
        assert isinstance(block1, PCMBlock)
        assert block1.sample_rate == 48000
        assert block1.channels == 2
        assert block1.frames == 128
        assert capture.frames_captured == 128

        # Verify planar float32 representation matches interleaved source
        interleaved_slice = source_data[: 128 * 2]
        expected_block1 = AlsaPCMAdapter.interleaved_float32_to_planar_pcm_block(interleaved_slice, 48000, 2)
        np.testing.assert_allclose(block1.samples, expected_block1.samples)

        # Read second block (128 frames)
        block2 = capture.read_block()
        assert block2.frames == 128
        assert capture.frames_captured == 256

        capture.stop()
        assert capture.state == ExecutionState.STOPPED
        capture.close()
        assert capture.state == ExecutionState.CLOSED

    def test_capture_read_block_int16(self) -> None:
        cfg = AlsaCaptureConfig(sample_rate=48000, channels=1, block_size=64, use_int16=True)

        # Synthesize int16 source data
        int16_source = np.array([0, 16384, -16384, 32767, -32768] * 20, dtype=np.int16)
        mock_handle = MockAlsaDeviceHandle(
            device_name="hw:0,0",
            sample_rate=48000,
            channels=1,
            block_size=64,
            mock_capture_source=int16_source.astype(np.float32),  # Mock buffer array
        )

        capture = AlsaAudioCapture(config=cfg, mock_handle=mock_handle)
        capture.start()

        block = capture.read_block()
        assert block.frames == 64
        assert block.samples.dtype == np.float32
        capture.close()

    def test_record_frames_and_record_duration(self) -> None:
        cfg = AlsaCaptureConfig(sample_rate=48000, channels=1, block_size=100)
        source_data = np.sin(2.0 * np.pi * 440.0 * np.arange(1000) / 48000.0).astype(np.float32)

        mock_handle = MockAlsaDeviceHandle(
            device_name="mock_mic",
            sample_rate=48000,
            channels=1,
            block_size=100,
            mock_capture_source=source_data,
        )

        capture = AlsaAudioCapture(config=cfg, mock_handle=mock_handle)

        # Record exact 350 frames (requires 3 full blocks of 100 + 1 partial of 50)
        recorded_block = capture.record_frames(350)
        assert recorded_block.frames == 350
        assert recorded_block.channels == 1
        np.testing.assert_allclose(recorded_block.samples[0], source_data[:350], atol=1e-6)

        # Record 0.01 seconds = 480 samples
        mock_handle._read_cursor = 0
        duration_block = capture.record_duration(0.01)
        assert duration_block.frames == 480
        np.testing.assert_allclose(duration_block.samples[0], source_data[:480], atol=1e-6)

        capture.close()

    def test_capture_xrun_overrun_and_recovery(self) -> None:
        cfg = AlsaCaptureConfig(sample_rate=48000, channels=1, block_size=64)
        mock_handle = MockAlsaDeviceHandle(
            device_name="mock_mic",
            sample_rate=48000,
            channels=1,
            block_size=64,
            xrun_on_read_count=2,  # Trigger overrun on 2nd read
        )

        capture = AlsaAudioCapture(config=cfg, mock_handle=mock_handle, auto_recover_xruns=True)
        capture.start()

        # 1st read -> succeeds
        b1 = capture.read_block()
        assert b1.frames == 64
        assert capture.xrun_count == 0

        # 2nd read -> triggers overrun, auto-recovers, and completes retry
        b2 = capture.read_block()
        assert b2.frames == 64
        assert capture.xrun_count == 1
        assert capture.recovered_xrun_count == 1

        capture.close()

    def test_capture_fatal_error_handling(self) -> None:
        cfg = AlsaCaptureConfig(sample_rate=48000, channels=1, block_size=64)
        mock_handle = MockAlsaDeviceHandle(
            device_name="mock_mic",
            sample_rate=48000,
            channels=1,
            block_size=64,
            fail_on_read_count=2,  # Fatal I/O error on 2nd read
        )

        capture = AlsaAudioCapture(config=cfg, mock_handle=mock_handle)
        capture.start()

        capture.read_block()  # 1st read succeeds

        with pytest.raises(ExecutionDeviceError) as excinfo:
            capture.read_block()  # 2nd read raises fatal error

        assert "ALSA hardware read error" in str(excinfo.value)
        assert capture.state == ExecutionState.STOPPED
        capture.close()

    def test_capture_lifecycle_invariants(self) -> None:
        mock = MockAlsaDeviceHandle("mock_capture", sample_rate=48000, channels=1, block_size=256)
        cfg = AlsaCaptureConfig()
        capture = AlsaAudioCapture(config=cfg, mock_handle=mock)

        # Cannot read before start
        with pytest.raises(ExecutionStateError):
            capture.read_block()

        # Double start is idempotent
        capture.start()
        capture.start()
        assert capture.state == ExecutionState.RUNNING

        capture.stop()
        assert capture.state == ExecutionState.STOPPED

        capture.close()
        assert capture.state == ExecutionState.CLOSED

        # Cannot start after close
        with pytest.raises(ExecutionStateError):
            capture.start()
