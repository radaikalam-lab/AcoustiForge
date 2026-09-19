"""Unit and Integration Tests for AcoustiForge Platform Audio Execution Hook Interface.

Normative Authority:
- docs/architecture/PHASE_5_2_PLATFORM_AUDIO_EXECUTION_HOOK_DISCOVERY.md
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/PCM_CONTRACT.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge.contracts.pcm import AudioMetadata, PCMBlock
from acoustiforge.contracts.validation import (
    InvalidGraphError,
    InvalidSampleRateError,
    MalformedBufferError,
)
from acoustiforge.execution.interface import (
    AudioExecutionBackend,
    AudioExecutionController,
    ExecutionConfigError,
    ExecutionState,
    ExecutionStateError,
    StreamConfig,
)
from acoustiforge.execution.linux import LinuxExecutionBackend, LinuxStreamConfig
from acoustiforge.execution.offline import OfflineExecutionBackend
from acoustiforge.graph.compute_graph import ComputeGraph
from acoustiforge.nodes.biquad import BiquadCoefficients, BiquadNode
from acoustiforge.nodes.delay import DelayNode
from acoustiforge.nodes.gain import GainNode
from acoustiforge.nodes.passthrough import PassThroughNode


# ==============================================================================
# Helper Graph Synthesizers
# ==============================================================================

def _create_frozen_test_graph(sample_rate: int = 48000, channels: int = 2) -> ComputeGraph:
    """Construct a simple, deterministic frozen ComputeGraph (Input -> Delay -> Gain -> Output)."""
    graph = ComputeGraph(name="TestAudioGraph")

    in_node = PassThroughNode(name="input")
    delay_node = DelayNode(delay_frames=64, sample_rate=sample_rate, channels=channels, name="delay")
    gain_node = GainNode(gain_db=-3.0, sample_rate=sample_rate, channels=channels, name="gain")

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
    """Create a synthetic sinusoidal PCMBlock."""
    t = np.arange(frames, dtype=np.float32) / float(sample_rate)
    sine = 0.5 * np.sin(2.0 * np.pi * frequency_hz * t).astype(np.float32)
    samples = np.vstack([sine] * channels)
    metadata = AudioMetadata(sample_rate=sample_rate, channels=channels)
    return PCMBlock(samples=samples, metadata=metadata)


# ==============================================================================
# 1. Lifecycle & State Machine Tests
# ==============================================================================

def test_execution_backend_lifecycle_transitions() -> None:
    """Verify standard lifecycle transitions: UNINITIALIZED -> CONFIGURED -> RUNNING -> STOPPED -> CLOSED."""
    backend = OfflineExecutionBackend()
    assert backend.state == ExecutionState.UNINITIALIZED
    assert backend.graph is None
    assert backend.config is None

    graph = _create_frozen_test_graph(48000, 2)
    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)

    # 1. Initialize
    backend.initialize(graph, config)
    assert backend.state == ExecutionState.CONFIGURED
    assert backend.graph is graph
    assert backend.config is config

    # 2. Start
    backend.start()
    assert backend.state == ExecutionState.RUNNING

    # 3. Process
    block = _create_synthetic_pcm_block(48000, 2, 512)
    out = backend.process(block)
    assert isinstance(out, PCMBlock)
    assert out.shape == (2, 512)

    # 4. Stop
    backend.stop()
    assert backend.state == ExecutionState.STOPPED

    # 5. Resume (Start from STOPPED)
    backend.start()
    assert backend.state == ExecutionState.RUNNING

    # 6. Close
    backend.close()
    assert backend.state == ExecutionState.CLOSED
    assert backend.graph is None


def test_invalid_lifecycle_operations_rejected() -> None:
    """Verify that invalid lifecycle operations raise ExecutionStateError."""
    backend = OfflineExecutionBackend()
    block = _create_synthetic_pcm_block(48000, 2, 512)

    # Cannot start uninitialized backend
    with pytest.raises(ExecutionStateError, match="Cannot start"):
        backend.start()

    # Cannot process on uninitialized backend
    with pytest.raises(ExecutionStateError, match="expected RUNNING"):
        backend.process(block)

    graph = _create_frozen_test_graph(48000, 2)
    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)
    backend.initialize(graph, config)

    # Cannot process when CONFIGURED but not RUNNING
    with pytest.raises(ExecutionStateError, match="expected RUNNING"):
        backend.process(block)

    backend.start()
    # Cannot re-initialize when RUNNING
    with pytest.raises(ExecutionStateError, match="while backend is in RUNNING state"):
        backend.initialize(graph, config)

    backend.close()
    # Cannot start, stop, initialize, or process when CLOSED
    with pytest.raises(ExecutionStateError):
        backend.start()
    with pytest.raises(ExecutionStateError):
        backend.stop()
    with pytest.raises(ExecutionStateError):
        backend.initialize(graph, config)
    with pytest.raises(ExecutionStateError):
        backend.process(block)


# ==============================================================================
# 2. Configuration Validation Tests
# ==============================================================================

def test_stream_config_validation() -> None:
    """Verify StreamConfig parameter validation."""
    # Valid
    cfg = StreamConfig(sample_rate=48000, channels=2, block_size=256, stream_name="Main")
    assert cfg.sample_rate == 48000
    assert cfg.channels == 2
    assert cfg.block_size == 256
    assert cfg.metadata.sample_rate == 48000

    # Invalid sample rate
    with pytest.raises(InvalidSampleRateError):
        StreamConfig(sample_rate=-48000, channels=2)

    # Invalid channels
    with pytest.raises(ExecutionConfigError, match="channels must be a positive integer"):
        StreamConfig(sample_rate=48000, channels=0)

    # Invalid block size
    with pytest.raises(ExecutionConfigError, match="block_size must be a positive integer"):
        StreamConfig(sample_rate=48000, channels=2, block_size=-128)

    # Invalid stream name
    with pytest.raises(ExecutionConfigError, match="stream_name must be a non-empty string"):
        StreamConfig(sample_rate=48000, channels=2, stream_name="   ")


def test_linux_stream_config_validation() -> None:
    """Verify LinuxStreamConfig parameter validation."""
    l_cfg = LinuxStreamConfig(
        sample_rate=44100,
        channels=2,
        block_size=512,
        alsa_device="hw:0,0",
        periods_per_buffer=3,
        is_headless_appliance=True,
    )
    assert l_cfg.alsa_device == "hw:0,0"
    assert l_cfg.periods_per_buffer == 3
    assert l_cfg.total_buffer_frames == 1536
    assert l_cfg.is_headless_appliance is True

    # Invalid periods
    with pytest.raises(ExecutionConfigError, match="periods_per_buffer must be an integer >= 2"):
        LinuxStreamConfig(sample_rate=44100, channels=2, periods_per_buffer=1)

    # Empty alsa device
    with pytest.raises(ExecutionConfigError, match="alsa_device must be a non-empty string"):
        LinuxStreamConfig(sample_rate=44100, channels=2, alsa_device="")


# ==============================================================================
# 3. Unfrozen Graph Rejection
# ==============================================================================

def test_unfrozen_graph_rejected_by_backend() -> None:
    """Backend must strictly reject ComputeGraph instances that are not in FROZEN state."""
    unfrozen_graph = ComputeGraph(name="Unfrozen")
    in_node = PassThroughNode(name="in")
    unfrozen_graph.add_node("in", in_node, auto_bind_ports=True)
    unfrozen_graph.declare_input("in", "in")
    unfrozen_graph.declare_output("in", "out")
    # Not frozen!

    backend = OfflineExecutionBackend()
    config = StreamConfig(sample_rate=48000, channels=1)

    with pytest.raises(InvalidGraphError, match="must be in FROZEN lifecycle state"):
        backend.initialize(unfrozen_graph, config)


# ==============================================================================
# 4. DSP Continuity & Statefulness
# ==============================================================================

def test_dsp_execution_continuity_and_exact_match() -> None:
    """Verify that backend processing produces identical output to direct ComputeGraph.process()."""
    graph_direct = _create_frozen_test_graph(48000, 2)
    graph_backend = _create_frozen_test_graph(48000, 2)

    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)
    backend = OfflineExecutionBackend()
    backend.initialize(graph_backend, config)
    backend.start()

    block_in = _create_synthetic_pcm_block(48000, 2, 512, frequency_hz=440.0)

    out_direct = graph_direct.process(block_in)
    out_backend = backend.process(block_in)

    assert isinstance(out_direct, PCMBlock)
    assert isinstance(out_backend, PCMBlock)
    assert np.array_equal(out_direct.samples, out_backend.samples)


def test_statefulness_across_sequential_blocks() -> None:
    """Verify that execution backend preserves filter and delay memory states across multiple blocks."""
    graph_direct = _create_frozen_test_graph(48000, 1)
    graph_backend = _create_frozen_test_graph(48000, 1)

    config = StreamConfig(sample_rate=48000, channels=1, block_size=256)
    backend = OfflineExecutionBackend()
    backend.initialize(graph_backend, config)
    backend.start()

    for idx in range(5):
        block = _create_synthetic_pcm_block(48000, 1, 256, frequency_hz=200.0 * (idx + 1))
        out_d = graph_direct.process(block)
        out_b = backend.process(block)
        assert np.allclose(out_d.samples, out_b.samples, atol=1e-7)


# ==============================================================================
# 5. AudioExecutionController & Context Manager Tests
# ==============================================================================

def test_execution_controller_context_management() -> None:
    """Verify AudioExecutionController lifecycle management via context manager."""
    graph = _create_frozen_test_graph(48000, 2)
    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)

    backend = OfflineExecutionBackend()
    backend.initialize(graph, config)
    controller = AudioExecutionController(backend)

    assert controller.state == ExecutionState.CONFIGURED

    with controller:
        assert controller.state == ExecutionState.RUNNING
        block = _create_synthetic_pcm_block(48000, 2, 512)
        out = controller.process(block)
        assert isinstance(out, PCMBlock)
        assert out.shape == (2, 512)

    assert controller.state == ExecutionState.CLOSED


def test_execution_controller_stream_processing() -> None:
    """Verify AudioExecutionController.process_stream generator."""
    graph = _create_frozen_test_graph(48000, 2)
    config = StreamConfig(sample_rate=48000, channels=2, block_size=256)

    backend = OfflineExecutionBackend()
    backend.initialize(graph, config)
    controller = AudioExecutionController(backend)
    controller.start()

    blocks = [_create_synthetic_pcm_block(48000, 2, 256) for _ in range(4)]
    results = list(controller.process_stream(blocks))

    assert len(results) == 4
    for r in results:
        assert isinstance(r, PCMBlock)
        assert r.shape == (2, 256)

    controller.close()


# ==============================================================================
# 6. Linux Execution Adapter Tests
# ==============================================================================

def test_linux_execution_backend_simulation() -> None:
    """Verify LinuxExecutionBackend initializes, starts, processes, and closes seamlessly."""
    graph = _create_frozen_test_graph(48000, 2)
    l_cfg = LinuxStreamConfig(
        sample_rate=48000,
        channels=2,
        block_size=512,
        alsa_device="hw:1,0",
        periods_per_buffer=4,
        is_headless_appliance=True,
    )

    linux_backend = LinuxExecutionBackend(simulation_mode=True)
    linux_backend.initialize(graph, l_cfg)
    assert linux_backend.state == ExecutionState.CONFIGURED
    assert linux_backend.linux_config.alsa_device == "hw:1,0"
    assert linux_backend.linux_config.total_buffer_frames == 2048

    linux_backend.start()
    assert linux_backend.state == ExecutionState.RUNNING

    block = _create_synthetic_pcm_block(48000, 2, 512)
    out = linux_backend.process(block)
    assert isinstance(out, PCMBlock)
    assert out.shape == (2, 512)

    linux_backend.stop()
    assert linux_backend.state == ExecutionState.STOPPED
    linux_backend.close()
    assert linux_backend.state == ExecutionState.CLOSED


# ==============================================================================
# 7. Determinism & Buffer Validation Tests
# ==============================================================================

def test_execution_determinism_100_runs() -> None:
    """Verify bit-exact determinism across 100 consecutive executions."""
    graph = _create_frozen_test_graph(48000, 2)
    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)

    backend = OfflineExecutionBackend()
    backend.initialize(graph, config)
    backend.start()

    block = _create_synthetic_pcm_block(48000, 2, 512, frequency_hz=1000.0)
    baseline_out = backend.process(block)

    for run_idx in range(100):
        # Reset graph state by re-running fresh graph
        fresh_graph = _create_frozen_test_graph(48000, 2)
        fresh_backend = OfflineExecutionBackend()
        fresh_backend.initialize(fresh_graph, config)
        fresh_backend.start()
        fresh_out = fresh_backend.process(block)

        assert np.array_equal(baseline_out.samples, fresh_out.samples), (
            f"Execution output deviated on run {run_idx}"
        )


def test_mismatched_block_parameters_rejected() -> None:
    """Verify that PCMBlocks with mismatched sample rate or channel count are rejected."""
    graph = _create_frozen_test_graph(48000, 2)
    config = StreamConfig(sample_rate=48000, channels=2, block_size=512)

    backend = OfflineExecutionBackend()
    backend.initialize(graph, config)
    backend.start()

    # Mismatched sample rate (44100 vs 48000)
    block_bad_fs = _create_synthetic_pcm_block(44100, 2, 512)
    with pytest.raises(MalformedBufferError, match="sample rate"):
        backend.process(block_bad_fs)

    # Mismatched channel count (1 vs 2)
    block_bad_ch = _create_synthetic_pcm_block(48000, 1, 512)
    with pytest.raises(MalformedBufferError, match="channel count"):
        backend.process(block_bad_ch)

    backend.close()


def test_multi_way_crossover_graph_execution() -> None:
    """Verify that execution backend properly handles multi-output multi-way crossover graphs."""
    from acoustiforge.builders.crossover_builder import CrossoverGraphBuilder
    from acoustiforge.domain.specifications import CrossoverFamily, CrossoverSpecification
    from acoustiforge.acoustic_math.crossover import synthesize_crossover_biquads

    crossover_spec = CrossoverSpecification(
        family=CrossoverFamily.LINKWITZ_RILEY,
        order=4,
        frequency_hz=2000.0,
    )
    xover_res = synthesize_crossover_biquads(crossover_spec, sample_rate=48000)

    builder = CrossoverGraphBuilder(
        sample_rate=48000,
        channels=1,
        woofer_name="woofer",
        tweeter_name="tweeter",
        graph_name="MultiWayExecTest",
    )
    graph = builder.build_2way_graph(crossover_result=xover_res)

    config = StreamConfig(sample_rate=48000, channels=1, block_size=512)
    backend = OfflineExecutionBackend()
    backend.initialize(graph, config)
    backend.start()

    block_in = _create_synthetic_pcm_block(48000, 1, 512, frequency_hz=1000.0)
    out = backend.process(block_in)

    # Multi-output crossover graph returns dict of output ports
    assert isinstance(out, dict)
    assert len(out) == 2
    for out_key, out_blk in out.items():
        assert isinstance(out_blk, PCMBlock)
        assert out_blk.shape == (1, 512)

    backend.close()
