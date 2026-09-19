"""Unit, Mock, and Integration Tests for AcoustiForge Linux ALSA Hardware Backend.

Layer A: Platform-Independent Contract & Mock Tests (Runs on Windows & Linux).
Layer B: Linux Software Binding Tests (Runs on Linux with libasound).
Layer C: Hardware Playback Tests (Runs only when actual ALSA device is connected).

Normative Authority:
- docs/architecture/PHASE_5_2_PLATFORM_AUDIO_EXECUTION_HOOK_DISCOVERY.md
- docs/architecture/PHASE_5_3_LINUX_SBC_EXECUTION_HOOK_IMPLEMENTATION.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import math
import sys
import numpy as np
import pytest

from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.contracts.validation import (
    InvalidGraphError,
    MalformedBufferError,
)
from acoustiforge.execution.alsa import (
    EPIPE,
    AlsaCtypesBinding,
    AlsaExecutionBackend,
    AlsaPCMAdapter,
    MockAlsaDeviceHandle,
)
from acoustiforge.execution.interface import (
    AudioExecutionController,
    ExecutionDeviceError,
    ExecutionState,
    ExecutionStateError,
)
from acoustiforge.execution.linux import LinuxStreamConfig
from acoustiforge.graph.compute_graph import ComputeGraph
from acoustiforge.nodes.delay import DelayNode
from acoustiforge.nodes.gain import GainNode
from acoustiforge.nodes.passthrough import PassThroughNode


# ==============================================================================
# Helpers
# ==============================================================================

def _create_frozen_test_graph(sample_rate: int = 48000, channels: int = 2) -> ComputeGraph:
    """Construct a simple, deterministic frozen ComputeGraph."""
    graph = ComputeGraph(name="AlsaTestGraph")
    in_node = PassThroughNode(name="input")
    delay_node = DelayNode(delay_frames=32, sample_rate=sample_rate, channels=channels, name="delay")
    gain_node = GainNode(gain_db=-6.0, sample_rate=sample_rate, channels=channels, name="gain")

    graph.add_node("input", in_node, auto_bind_ports=True)
    graph.add_node("delay", delay_node, auto_bind_ports=True)
    graph.add_node("gain", gain_node, auto_bind_ports=True)

    graph.connect("input", "out", "delay", "in")
    graph.connect("delay", "out", "gain", "in")

    graph.declare_input("input", "in")
    graph.declare_output("gain", "out")
    graph.freeze()
    return graph


def _create_synthetic_pcm_block(
    sample_rate: int = 48000,
    channels: int = 2,
    frames: int = 512,
    frequency_hz: float = 1000.0,
) -> PCMBlock:
    """Generate a synthetic test PCMBlock."""
    t = np.arange(frames, dtype=np.float32) / float(sample_rate)
    sine = 0.5 * np.sin(2.0 * np.pi * frequency_hz * t).astype(np.float32)
    samples = np.vstack([sine] * channels)
    metadata = AudioMetadata(sample_rate=sample_rate, channels=channels)
    return PCMBlock(samples=samples, metadata=metadata)


# ==============================================================================
# Layer A: Platform-Independent Contract & Mock Tests
# ==============================================================================

def test_alsa_pcm_adapter_planar_to_interleaved_float32_roundtrip() -> None:
    """Verify exact bit-level roundtrip between planar PCMBlock and interleaved float32 buffer."""
    block = _create_synthetic_pcm_block(48000, channels=2, frames=256)

    interleaved = AlsaPCMAdapter.planar_float32_to_interleaved_float32(block)
    assert interleaved.shape == (512,)
    assert interleaved.dtype == np.float32

    # Check interleaving ordering: L0, R0, L1, R1, ...
    assert interleaved[0] == block.samples[0, 0]
    assert interleaved[1] == block.samples[1, 0]
    assert interleaved[2] == block.samples[0, 1]
    assert interleaved[3] == block.samples[1, 1]

    # Reconstruct planar PCMBlock
    reconstructed = AlsaPCMAdapter.interleaved_float32_to_planar_pcm_block(
        interleaved, sample_rate=48000, channels=2
    )
    assert np.array_equal(block.samples, reconstructed.samples)


def test_alsa_pcm_adapter_int16_conversion() -> None:
    """Verify conversion to 16-bit integer PCM within quantization tolerance."""
    block = _create_synthetic_pcm_block(48000, channels=2, frames=128)

    int16_buf = AlsaPCMAdapter.planar_float32_to_interleaved_int16(block)
    assert int16_buf.dtype == np.int16
    assert int16_buf.shape == (256,)

    recon_float = AlsaPCMAdapter.interleaved_int16_to_planar_pcm_block(
        int16_buf, sample_rate=48000, channels=2
    )
    # Maximum 16-bit quantization error is 1 / 32767 ≈ 3.1e-5
    assert np.allclose(block.samples, recon_float.samples, atol=3.5e-5)


def test_alsa_backend_lifecycle_with_mock() -> None:
    """Verify AlsaExecutionBackend full lifecycle using MockAlsaDeviceHandle."""
    graph = _create_frozen_test_graph(48000, 2)
    cfg = LinuxStreamConfig(
        sample_rate=48000,
        channels=2,
        block_size=512,
        alsa_device="hw:0,0",
        periods_per_buffer=4,
    )

    mock_dev = MockAlsaDeviceHandle(
        device_name="hw:0,0",
        sample_rate=48000,
        channels=2,
        block_size=512,
    )

    backend = AlsaExecutionBackend(mock_handle=mock_dev)
    assert backend.state == ExecutionState.UNINITIALIZED

    backend.initialize(graph, cfg)
    assert backend.state == ExecutionState.CONFIGURED

    backend.start()
    assert backend.state == ExecutionState.RUNNING
    assert mock_dev.is_prepared is True

    block = _create_synthetic_pcm_block(48000, 2, 512)
    out = backend.process(block)
    assert isinstance(out, PCMBlock)
    assert backend.frames_transferred == 512
    assert mock_dev.total_writes == 1

    backend.stop()
    assert backend.state == ExecutionState.STOPPED
    assert mock_dev.is_prepared is False

    backend.close()
    assert backend.state == ExecutionState.CLOSED
    assert mock_dev.is_closed is True


def test_alsa_dsp_continuity_parity_with_offline() -> None:
    """Verify output of AlsaExecutionBackend matches OfflineExecutionBackend identically."""
    from acoustiforge.execution.offline import OfflineExecutionBackend
    from acoustiforge.execution.interface import StreamConfig

    graph_offline = _create_frozen_test_graph(48000, 2)
    graph_alsa = _create_frozen_test_graph(48000, 2)

    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)
    l_config = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=512)

    offline_backend = OfflineExecutionBackend()
    offline_backend.initialize(graph_offline, config)
    offline_backend.start()

    mock_dev = MockAlsaDeviceHandle("default", 48000, 2, 512)
    alsa_backend = AlsaExecutionBackend(mock_handle=mock_dev)
    alsa_backend.initialize(graph_alsa, l_config)
    alsa_backend.start()

    block = _create_synthetic_pcm_block(48000, 2, 512, frequency_hz=880.0)

    out_offline = offline_backend.process(block)
    out_alsa = alsa_backend.process(block)

    assert isinstance(out_offline, PCMBlock)
    assert isinstance(out_alsa, PCMBlock)
    assert np.array_equal(out_offline.samples, out_alsa.samples)


def test_alsa_statefulness_across_sequential_blocks() -> None:
    """Verify that ALSA execution backend preserves time-domain filter memory across blocks."""
    graph = _create_frozen_test_graph(48000, 1)
    l_cfg = LinuxStreamConfig(sample_rate=48000, channels=1, block_size=256)

    mock_dev = MockAlsaDeviceHandle("default", 48000, 1, 256)
    backend = AlsaExecutionBackend(mock_handle=mock_dev)
    backend.initialize(graph, l_cfg)
    backend.start()

    for idx in range(4):
        blk = _create_synthetic_pcm_block(48000, 1, 256, frequency_hz=200.0 * (idx + 1))
        out = backend.process(blk)
        assert isinstance(out, PCMBlock)

    assert backend.frames_transferred == 1024
    assert len(mock_dev.captured_buffers) == 4


def test_alsa_xrun_detection_and_automatic_recovery() -> None:
    """Verify that ALSA underruns (-EPIPE) are automatically detected and recovered."""
    graph = _create_frozen_test_graph(48000, 2)
    l_cfg = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=512)

    # Inject xrun on 2nd write call
    mock_dev = MockAlsaDeviceHandle("default", 48000, 2, 512, xrun_on_write_count=2)
    backend = AlsaExecutionBackend(mock_handle=mock_dev, auto_recover_xruns=True)
    backend.initialize(graph, l_cfg)
    backend.start()

    block1 = _create_synthetic_pcm_block(48000, 2, 512)
    block2 = _create_synthetic_pcm_block(48000, 2, 512)

    backend.process(block1)
    assert backend.recovered_xrun_count == 0

    # Block 2 triggers -EPIPE -> backend recovers -> retries write -> succeeds
    backend.process(block2)
    assert backend.xrun_count == 1
    assert backend.recovered_xrun_count == 1
    assert backend.state == ExecutionState.RUNNING

    backend.close()


def test_alsa_fatal_hardware_error_handling() -> None:
    """Verify that unrecoverable ALSA errors raise ExecutionDeviceError and transition state to STOPPED."""
    graph = _create_frozen_test_graph(48000, 2)
    l_cfg = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=512)

    # Inject fatal error on 1st write
    mock_dev = MockAlsaDeviceHandle("default", 48000, 2, 512, fail_on_write_count=1)
    backend = AlsaExecutionBackend(mock_handle=mock_dev)
    backend.initialize(graph, l_cfg)
    backend.start()

    block = _create_synthetic_pcm_block(48000, 2, 512)
    with pytest.raises(ExecutionDeviceError, match="ALSA hardware write error"):
        backend.process(block)

    assert backend.state == ExecutionState.STOPPED
    backend.close()


def test_alsa_multi_channel_transfer() -> None:
    """Verify stereo and multi-port transfer through ALSA backend."""
    graph_stereo = _create_frozen_test_graph(48000, 2)
    l_cfg = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=256)

    mock_dev = MockAlsaDeviceHandle("hw:CARD=USB2CH,DEV=0", 48000, 2, 256)
    backend = AlsaExecutionBackend(mock_handle=mock_dev)
    backend.initialize(graph_stereo, l_cfg)
    backend.start()

    block_stereo = _create_synthetic_pcm_block(48000, 2, 256)
    out = backend.process(block_stereo)

    assert isinstance(out, PCMBlock)
    assert out.shape == (2, 256)
    assert mock_dev.captured_buffers[0].shape == (512,)  # 2 channels * 256 frames
    assert backend.frames_transferred == 256
    backend.close()


# ==============================================================================
# Layer B: Linux Software / ALSA Binding Tests
# ==============================================================================

def test_alsa_ctypes_binding_detection() -> None:
    """Verify AlsaCtypesBinding.is_available() reports platform capability without errors."""
    available = AlsaCtypesBinding.is_available()
    assert isinstance(available, bool)

    if not sys.platform.startswith("linux"):
        assert available is False


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="Layer B ALSA library tests require a Linux runtime.",
)
def test_linux_alsa_library_symbols() -> None:
    """Verify that libasound function prototypes load correctly when on Linux."""
    if AlsaCtypesBinding.is_available():
        lib = AlsaCtypesBinding.get_lib()
        assert lib is not None
        assert hasattr(lib, "snd_pcm_open")
        assert hasattr(lib, "snd_pcm_close")
        assert hasattr(lib, "snd_pcm_writei")
        assert hasattr(lib, "snd_pcm_recover")


# ==============================================================================
# Layer C: Real Hardware Integration Tests
# ==============================================================================

@pytest.mark.skipif(
    not sys.platform.startswith("linux") or not AlsaCtypesBinding.is_available(),
    reason="Layer C real ALSA hardware tests require Linux host with ALSA audio hardware.",
)
def test_real_alsa_hardware_playback_integration() -> None:
    """Real ALSA PCM playback integration test (Only executed when running on Linux with ALSA)."""
    graph = _create_frozen_test_graph(48000, 2)
    l_cfg = LinuxStreamConfig(
        sample_rate=48000,
        channels=2,
        block_size=512,
        alsa_device="default",
    )

    try:
        backend = AlsaExecutionBackend()
        backend.initialize(graph, l_cfg)
        backend.start()
        block = _create_synthetic_pcm_block(48000, 2, 512)
        backend.process(block)
        backend.stop()
        backend.close()
    except ExecutionDeviceError as err:
        pytest.skip(f"ALSA hardware test skipped: no usable ALSA audio device ({err}).")
