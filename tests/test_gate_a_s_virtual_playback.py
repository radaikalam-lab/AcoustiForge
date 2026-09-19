"""Gate A-S Validation Test Suite: Digital / Software ALSA Playback Validation.

This module validates the complete AcoustiForge playback path digitally through ALSA
using either the virtual ALSA 'null' device (on Linux / Docker) or the mock ALSA device
infrastructure (on Windows / CI).

Validated Pipeline:
    PCMBlock / compiled ComputeGraph
    ↓
    AudioExecutionController / AlsaExecutionBackend
    ↓
    ALSA ctypes binding (libasound.so.2)
    ↓
    Virtual ALSA PCM device ('null') / Mock device
    ↓
    PCM Transfer (snd_pcm_writei)

Normative Scope:
    Gate A-S is software/digital validation only.
    Physical audio hardware (DAC, speaker, mic) remains UNVALIDATED (Gate A-H).
"""

from __future__ import annotations

import sys
import numpy as np
import pytest

from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.contracts.validation import MalformedBufferError
from acoustiforge.execution.alsa import (
    AlsaCtypesBinding,
    AlsaExecutionBackend,
    AlsaPCMAdapter,
    MockAlsaDeviceHandle,
    SND_PCM_ACCESS_RW_INTERLEAVED,
    SND_PCM_FORMAT_FLOAT_LE,
    SND_PCM_FORMAT_S16_LE,
)
from acoustiforge.execution.interface import (
    AudioExecutionController,
    ExecutionDeviceError,
    ExecutionState,
    ExecutionStateError,
    StreamConfig,
)
from acoustiforge.execution.linux import LinuxStreamConfig
from acoustiforge.execution.offline import OfflineExecutionBackend
from acoustiforge.graph.compute_graph import ComputeGraph
from acoustiforge.nodes.biquad import BiquadNode
from acoustiforge.nodes.delay import DelayNode
from acoustiforge.nodes.gain import GainNode
from acoustiforge.nodes.passthrough import PassThroughNode


def _build_deterministic_dsp_graph(sample_rate: int = 48000, channels: int = 2) -> ComputeGraph:
    """Build a deterministic ComputeGraph with Delay, Biquad, and Gain nodes."""
    graph = ComputeGraph(name="GateAS_Validation_Graph")
    in_node = PassThroughNode(name="in")
    delay_node = DelayNode(delay_frames=16, sample_rate=sample_rate, channels=channels, name="delay")
    biquad_node = BiquadNode(
        filter_type="low_pass",
        frequency=1000.0,
        q=0.7071,
        sample_rate=sample_rate,
        channels=channels,
        name="biquad",
    )
    gain_node = GainNode(gain_db=-3.0, sample_rate=sample_rate, channels=channels, name="gain")

    graph.add_node("in", in_node, auto_bind_ports=True)
    graph.add_node("delay", delay_node, auto_bind_ports=True)
    graph.add_node("biquad", biquad_node, auto_bind_ports=True)
    graph.add_node("gain", gain_node, auto_bind_ports=True)

    graph.connect("in", "out", "delay", "in")
    graph.connect("delay", "out", "biquad", "in")
    graph.connect("biquad", "out", "gain", "in")

    graph.declare_input("in", "in")
    graph.declare_output("gain", "out")
    graph.freeze()
    return graph


def _generate_sine_block(
    sample_rate: int,
    channels: int,
    frames: int,
    freq: float = 440.0,
    block_index: int = 0,
) -> PCMBlock:
    """Generate phase-continuous sine wave block across block boundaries."""
    t_start = block_index * frames / sample_rate
    t = t_start + np.arange(frames, dtype=np.float32) / sample_rate
    sine = 0.5 * np.sin(2.0 * np.pi * freq * t).astype(np.float32)
    samples = np.vstack([sine] * channels)
    return PCMBlock(samples=samples, metadata=AudioMetadata(sample_rate=sample_rate, channels=channels))


# ==============================================================================
# Gate A-S: Core Digital Lifecycle & Verification Tests
# ==============================================================================

class TestGateASDigitalPlayback:
    """Gate A-S Digital / Software ALSA Playback Verification."""

    def test_gate_a_s_01_alsa_ctypes_symbol_resolution(self) -> None:
        """Verify that ALSA ctypes binding exposes required playback symbols."""
        if AlsaCtypesBinding.is_available():
            lib = AlsaCtypesBinding.get_lib()
            assert hasattr(lib, "snd_pcm_open")
            assert hasattr(lib, "snd_pcm_close")
            assert hasattr(lib, "snd_pcm_prepare")
            assert hasattr(lib, "snd_pcm_writei")
            assert hasattr(lib, "snd_pcm_recover")
            assert hasattr(lib, "snd_pcm_drop")
            assert hasattr(lib, "snd_pcm_drain")
            assert hasattr(lib, "snd_pcm_set_params")

    def test_gate_a_s_02_lifecycle_state_machine(self) -> None:
        """Verify standard lifecycle transitions: UNINITIALIZED -> CONFIGURED -> RUNNING -> STOPPED -> CLOSED."""
        graph = _build_deterministic_dsp_graph(48000, 2)
        cfg = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=256, alsa_device="null")

        backend = AlsaExecutionBackend()
        assert backend.state == ExecutionState.UNINITIALIZED

        backend.initialize(graph, cfg)
        assert backend.state == ExecutionState.CONFIGURED

        backend.start()
        assert backend.state == ExecutionState.RUNNING

        # Process a single block
        blk = _generate_sine_block(48000, 2, 256)
        out = backend.process(blk)
        assert isinstance(out, PCMBlock)
        assert backend.frames_transferred == 256

        backend.stop()
        assert backend.state == ExecutionState.STOPPED

        backend.close()
        assert backend.state == ExecutionState.CLOSED

    @pytest.mark.parametrize("sample_rate", [44100, 48000, 96000])
    @pytest.mark.parametrize("channels", [1, 2])
    @pytest.mark.parametrize("block_size", [128, 256, 512])
    def test_gate_a_s_03_multi_rate_channel_block_configurations(
        self,
        sample_rate: int,
        channels: int,
        block_size: int,
    ) -> None:
        """Verify parameter configurations across common sample rates, channel counts, and block sizes."""
        graph = _build_deterministic_dsp_graph(sample_rate, channels)
        cfg = LinuxStreamConfig(
            sample_rate=sample_rate,
            channels=channels,
            block_size=block_size,
            alsa_device="null",
        )

        backend = AlsaExecutionBackend()
        backend.initialize(graph, cfg)
        backend.start()
        assert backend.state == ExecutionState.RUNNING
        assert backend.negotiated_format in ("float32", "int16")

        for b_idx in range(4):
            blk = _generate_sine_block(sample_rate, channels, block_size, block_index=b_idx)
            out = backend.process(blk)
            assert isinstance(out, PCMBlock)
            assert out.shape == (channels, block_size)

        assert backend.frames_transferred == block_size * 4
        backend.stop()
        backend.close()

    def test_gate_a_s_04_sustained_multi_block_streaming(self) -> None:
        """Verify sustained streaming of 64 consecutive blocks without xruns or memory leaks."""
        sample_rate = 48000
        channels = 2
        block_size = 256
        total_blocks = 64

        graph = _build_deterministic_dsp_graph(sample_rate, channels)
        cfg = LinuxStreamConfig(
            sample_rate=sample_rate,
            channels=channels,
            block_size=block_size,
            alsa_device="null",
        )

        backend = AlsaExecutionBackend()
        backend.initialize(graph, cfg)
        backend.start()

        for idx in range(total_blocks):
            blk = _generate_sine_block(sample_rate, channels, block_size, freq=1000.0, block_index=idx)
            out = backend.process(blk)
            assert isinstance(out, PCMBlock)

        expected_frames = total_blocks * block_size
        assert backend.frames_transferred == expected_frames
        assert backend.xrun_count == 0
        assert backend.recovered_xrun_count == 0

        backend.stop()
        backend.close()

    def test_gate_a_s_05_dsp_continuity_parity_with_offline_backend(self) -> None:
        """Verify bit-identical DSP numerical continuity between AlsaExecutionBackend and OfflineExecutionBackend."""
        sample_rate = 48000
        channels = 2
        block_size = 256
        num_blocks = 8

        graph_offline = _build_deterministic_dsp_graph(sample_rate, channels)
        graph_alsa = _build_deterministic_dsp_graph(sample_rate, channels)

        offline_backend = OfflineExecutionBackend()
        offline_backend.initialize(graph_offline, StreamConfig(sample_rate, channels, block_size))
        offline_backend.start()

        alsa_backend = AlsaExecutionBackend()
        alsa_backend.initialize(
            graph_alsa,
            LinuxStreamConfig(sample_rate, channels, block_size, alsa_device="null"),
        )
        alsa_backend.start()

        for idx in range(num_blocks):
            blk = _generate_sine_block(sample_rate, channels, block_size, freq=500.0, block_index=idx)
            out_offline = offline_backend.process(blk)
            out_alsa = alsa_backend.process(blk)

            assert isinstance(out_offline, PCMBlock)
            assert isinstance(out_alsa, PCMBlock)
            assert np.array_equal(out_offline.samples, out_alsa.samples)

        offline_backend.stop()
        offline_backend.close()
        alsa_backend.stop()
        alsa_backend.close()

    def test_gate_a_s_06_execution_controller_integration(self) -> None:
        """Verify integration with top-level AudioExecutionController."""
        graph = _build_deterministic_dsp_graph(48000, 2)
        cfg = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=256, alsa_device="null")
        backend = AlsaExecutionBackend()

        controller = AudioExecutionController(backend=backend)
        assert controller.state == ExecutionState.UNINITIALIZED

        controller.configure(graph=graph, config=cfg)
        assert controller.state == ExecutionState.CONFIGURED

        controller.start()
        assert controller.state == ExecutionState.RUNNING

        blk = _generate_sine_block(48000, 2, 256)
        out = controller.process(blk)
        assert isinstance(out, PCMBlock)

        controller.stop()
        assert controller.state == ExecutionState.STOPPED

        controller.close()
        assert controller.state == ExecutionState.CLOSED

    def test_gate_a_s_07_repeatability_determinism(self) -> None:
        """Verify identical DSP outputs and frame counts across multiple independent runs."""
        outputs_run1: list[np.ndarray] = []
        outputs_run2: list[np.ndarray] = []

        for run_outputs in (outputs_run1, outputs_run2):
            graph = _build_deterministic_dsp_graph(48000, 2)
            cfg = LinuxStreamConfig(sample_rate=48000, channels=2, block_size=256, alsa_device="null")
            backend = AlsaExecutionBackend()
            backend.initialize(graph, cfg)
            backend.start()

            for idx in range(4):
                blk = _generate_sine_block(48000, 2, 256, freq=440.0, block_index=idx)
                out = backend.process(blk)
                assert isinstance(out, PCMBlock)
                run_outputs.append(out.samples.copy())

            backend.stop()
            backend.close()

        assert len(outputs_run1) == len(outputs_run2)
        for s1, s2 in zip(outputs_run1, outputs_run2):
            assert np.array_equal(s1, s2)
