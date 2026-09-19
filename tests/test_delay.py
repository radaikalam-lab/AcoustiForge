"""Unit, property, and composition tests for AcoustiForge DelayNode.

Normative Authority:
- prompts/MASTER_PROMPT.md
- docs/contracts/PCM_CONTRACT.md
- docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from acoustiforge import (
    AudioMetadata,
    BiquadNode,
    ChannelLayout,
    DelayNode,
    FilterType,
    GainNode,
    IncompatibleNodeError,
    InvalidParameterError,
    NonFiniteValueError,
    PCMBlock,
)


# ==============================================================================
# Independent Test Reference Oracle (Step 13)
# ==============================================================================

def independent_delay_oracle(x: np.ndarray, delay_frames: int) -> np.ndarray:
    """Independent oracle for streaming delay with zero-initial state."""
    channels, frames = x.shape
    if delay_frames == 0:
        return x.copy()
    y = np.zeros((channels, frames), dtype=np.float32)
    if frames > delay_frames:
        y[:, delay_frames:] = x[:, : frames - delay_frames]
    return y


# ==============================================================================
# 1. Construction & Parameter Validation
# ==============================================================================

def test_delay_node_construction_default() -> None:
    """Verify default DelayNode: delay=0, latency=0."""
    node = DelayNode()
    assert node.delay_frames == 0
    assert node.latency_frames == 0
    assert node.is_active is True


def test_delay_node_construction_custom() -> None:
    """Verify custom delay initialization."""
    node = DelayNode(delay_frames=48, sample_rate=48000, channels=2, name="EchoLine")
    assert node.name == "EchoLine"
    assert node.delay_frames == 48
    assert node.latency_frames == 48


def test_delay_parameter_validation() -> None:
    """Reject invalid delay parameters (negative, non-integer, NaN, Inf, bool, string)."""
    with pytest.raises(InvalidParameterError, match=">= 0"):
        DelayNode(delay_frames=-1)
    with pytest.raises(InvalidParameterError, match="integer"):
        DelayNode(delay_frames=2.5)  # type: ignore
    with pytest.raises(NonFiniteValueError):
        DelayNode(delay_frames=float("nan"))  # type: ignore
    with pytest.raises(NonFiniteValueError):
        DelayNode(delay_frames=float("inf"))  # type: ignore
    with pytest.raises(InvalidParameterError):
        DelayNode(delay_frames=True)  # type: ignore
    with pytest.raises(InvalidParameterError):
        DelayNode(delay_frames="10")  # type: ignore


def test_delay_parameter_transaction_rollback() -> None:
    """Verify failed parameter update leaves active delay and state intact."""
    node = DelayNode(delay_frames=10)
    node.configure(sample_rate=48000, channels=1)

    with pytest.raises(InvalidParameterError):
        node.set_parameters(delay_frames=-5)

    assert node.delay_frames == 10
    assert node.latency_frames == 10

    # Successful update
    node.set_parameters(delay_frames=20)
    assert node.delay_frames == 20
    assert node.latency_frames == 20


# ==============================================================================
# 2. Delay Semantics: D=0, D=1, D < block, D > block, Multi-block
# ==============================================================================

def test_delay_zero_exact_identity() -> None:
    """Verify DelayNode with delay=0 acts as exact identity."""
    node = DelayNode(delay_frames=0)
    node.configure(sample_rate=48000, channels=2)

    x = np.random.uniform(-1.0, 1.0, (2, 128)).astype(np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)
    blk_out = node.process(blk_in)

    np.testing.assert_array_equal(blk_out.samples, x)


@pytest.mark.parametrize("delay_frames", [1, 2, 8, 32, 100])
def test_delay_single_block_against_oracle(delay_frames: int) -> None:
    """Verify single-block processing matches independent delay oracle."""
    node = DelayNode(delay_frames=delay_frames)
    node.configure(sample_rate=48000, channels=1)

    frames = 128
    x = np.random.uniform(-1.0, 1.0, (1, frames)).astype(np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)
    blk_out = node.process(blk_in)

    expected = independent_delay_oracle(x, delay_frames)
    np.testing.assert_array_equal(blk_out.samples, expected)


def test_delay_larger_than_multiple_blocks() -> None:
    """Verify delay spanning across several successive small blocks."""
    # Delay = 10 samples; block size = 3 samples
    node = DelayNode(delay_frames=10)
    node.configure(sample_rate=48000, channels=1)

    # Input stream of 5 blocks of 3 samples = 15 samples total: [1, 2, 3, ..., 15]
    full_input = np.arange(1, 16, dtype=np.float32).reshape(1, 15)

    out_chunks = []
    for i in range(5):
        chunk = full_input[:, i * 3 : (i + 1) * 3]
        blk = PCMBlock.from_array(chunk, sample_rate=48000)
        out_chunks.append(node.process(blk).samples)

    concatenated_out = np.concatenate(out_chunks, axis=1)

    # First 10 samples must be 0; subsequent samples must be [1, 2, 3, 4, 5]
    expected = np.array([[0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5]], dtype=np.float32)
    np.testing.assert_array_equal(concatenated_out, expected)


# ==============================================================================
# 3. State Continuity Across Variable Block Boundaries & Reset
# ==============================================================================

def test_delay_state_continuity_arbitrary_partitions() -> None:
    """Verify arbitrary block sizes yield identical output to monolithic processing."""
    total_frames = 500
    delay_frames = 37
    x = np.random.uniform(-1.0, 1.0, (2, total_frames)).astype(np.float32)

    # 1. Monolithic single-block execution
    node_mono = DelayNode(delay_frames=delay_frames)
    node_mono.configure(sample_rate=48000, channels=2)
    out_mono = node_mono.process(PCMBlock.from_array(x.copy(), sample_rate=48000)).samples

    # 2. Highly irregular partitions: 1, 2, 3, 7, 17, 31, 64, 100, remainder
    node_part = DelayNode(delay_frames=delay_frames)
    node_part.configure(sample_rate=48000, channels=2)

    partitions = [1, 2, 3, 7, 17, 31, 64, 100, total_frames - (1 + 2 + 3 + 7 + 17 + 31 + 64 + 100)]
    out_parts = []
    idx = 0
    for p in partitions:
        chunk = x[:, idx : idx + p].copy()
        idx += p
        blk = PCMBlock.from_array(chunk, sample_rate=48000)
        out_parts.append(node_part.process(blk).samples)

    out_concatenated = np.concatenate(out_parts, axis=1)

    np.testing.assert_array_equal(out_mono, out_concatenated)


def test_delay_channel_isolation() -> None:
    """Verify channel 0 and channel 1 delay state are completely isolated."""
    node = DelayNode(delay_frames=4)
    node.configure(sample_rate=48000, channels=2)

    # Ch 0 has impulse [1, 0, ...], Ch 1 is all zeros
    x = np.zeros((2, 16), dtype=np.float32)
    x[0, 0] = 1.0

    blk_out = node.process(PCMBlock.from_array(x, sample_rate=48000))
    y = blk_out.samples

    # Ch 0 has impulse delayed at sample index 4
    assert y[0, 4] == 1.0
    assert np.sum(y[0]) == 1.0
    # Ch 1 is strictly zero throughout
    assert np.all(y[1] == 0.0)


def test_delay_reset_clears_history() -> None:
    """Verify reset() clears delay history and reproduces initial-state output."""
    node = DelayNode(delay_frames=8)
    node.configure(sample_rate=48000, channels=1)

    x = np.ones((1, 16), dtype=np.float32)
    out1 = node.process(PCMBlock.from_array(x, sample_rate=48000)).samples

    # Reset
    node.reset()

    # Re-run identical input
    out2 = node.process(PCMBlock.from_array(x, sample_rate=48000)).samples

    np.testing.assert_array_equal(out1, out2)


# ==============================================================================
# 4. Sequential Composition Tests (Gain -> Delay -> Biquad)
# ==============================================================================

def test_composition_gain_and_delay() -> None:
    """Verify sequential composition of GainNode and DelayNode."""
    gain = GainNode(gain_db=6.0)
    delay = DelayNode(delay_frames=5)

    gain.configure(sample_rate=48000, channels=1)
    delay.configure(sample_rate=48000, channels=1)

    # Invariant: cumulative latency
    total_latency = gain.latency_frames + delay.latency_frames
    assert total_latency == 5

    x = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]], dtype=np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)

    # Chain: Gain -> Delay
    blk_g = gain.process(blk_in)
    blk_out = delay.process(blk_g)

    g_val = np.float32(math.pow(10.0, 6.0 / 20.0))
    expected = np.zeros((1, 8), dtype=np.float32)
    expected[0, 5:] = x[0, :3] * g_val

    np.testing.assert_allclose(blk_out.samples, expected, atol=1e-7, rtol=1e-7)


def test_composition_delay_and_gain_commutative_property() -> None:
    """Verify linearity/commutativity: Gain(Delay(x)) == Delay(Gain(x))."""
    gain1 = GainNode(gain_db=-6.0)
    delay1 = DelayNode(delay_frames=12)

    gain2 = GainNode(gain_db=-6.0)
    delay2 = DelayNode(delay_frames=12)

    x = np.random.uniform(-1.0, 1.0, (2, 64)).astype(np.float32)
    blk1 = PCMBlock.from_array(x.copy(), sample_rate=48000)
    blk2 = PCMBlock.from_array(x.copy(), sample_rate=48000)

    # Path 1: Gain -> Delay
    out1 = delay1.process(gain1.process(blk1)).samples
    # Path 2: Delay -> Gain
    out2 = gain2.process(delay2.process(blk2)).samples

    np.testing.assert_allclose(out1, out2, atol=1e-7, rtol=1e-7)


def test_composition_gain_delay_biquad_pipeline() -> None:
    """Verify 3-stage sequential chain: Gain -> Delay -> Biquad."""
    gain = GainNode(gain_db=3.0)
    delay = DelayNode(delay_frames=16)
    biquad = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0, q=0.707107)

    sample_rate = 48000
    channels = 2
    gain.configure(sample_rate, channels)
    delay.configure(sample_rate, channels)
    biquad.configure(sample_rate, channels)

    # Verify cumulative latency = 0 + 16 + 0 = 16 frames
    total_latency = gain.latency_frames + delay.latency_frames + biquad.latency_frames
    assert total_latency == 16

    x = np.random.uniform(-0.5, 0.5, (channels, 128)).astype(np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=sample_rate)

    # Process through sequence
    blk_g = gain.process(blk_in)
    assert blk_g.shape == (channels, 128)
    assert blk_g.sample_rate == sample_rate

    blk_d = delay.process(blk_g)
    assert blk_d.shape == (channels, 128)
    assert blk_d.sample_rate == sample_rate

    blk_b = biquad.process(blk_d)
    assert blk_b.shape == (channels, 128)
    assert blk_b.sample_rate == sample_rate

    # Verify first 16 frames of delay output are 0, and output is finite
    assert np.all(blk_d.samples[:, :16] == 0.0)
    assert np.all(np.isfinite(blk_b.samples))
