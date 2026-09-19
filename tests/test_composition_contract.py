"""Unit and property tests for AcoustiForge Node Composition Contract.

Normative Authority:
- docs/contracts/NODE_COMPOSITION_CONTRACT.md
- docs/phases/PHASE_1E_NODE_COMPOSITION_CONTRACT_DISCOVERY.md
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
    MalformedBufferError,
    PCMBlock,
    PassThroughNode,
)


# ==============================================================================
# 1. Node Shape & Metadata Preservation across all 4 Node Types
# ==============================================================================

@pytest.mark.parametrize(
    "node_factory",
    [
        lambda: PassThroughNode(),
        lambda: GainNode(gain_db=-3.0),
        lambda: DelayNode(delay_frames=10),
        lambda: BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0, q=0.707107),
    ],
)
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("sample_rate", [44100, 48000, 96000])
def test_all_nodes_shape_and_metadata_invariance(node_factory, channels: int, sample_rate: int) -> None:
    """Verify all computational nodes preserve channels, sample rate, and layout."""
    node = node_factory()
    node.configure(sample_rate=sample_rate, channels=channels)

    x = np.random.uniform(-0.5, 0.5, (channels, 64)).astype(np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=sample_rate)
    blk_out = node.process(blk_in)

    assert blk_out.channels == channels
    assert blk_out.sample_rate == sample_rate
    assert blk_out.frames == 64
    assert blk_out.metadata.layout == (ChannelLayout.MONO if channels == 1 else ChannelLayout.STEREO)
    assert blk_out.dtype == np.float32


# ==============================================================================
# 2. Directional Link Compatibility & Composition Combinations
# ==============================================================================

def test_pairwise_directional_composition_chains() -> None:
    """Verify all pairwise link combinations execute compatibly."""
    sample_rate = 48000
    channels = 2

    pt = PassThroughNode()
    g = GainNode(gain_db=6.0)
    d = DelayNode(delay_frames=4)
    bq = BiquadNode(filter_type=FilterType.PEAKING, frequency=1000.0, q=2.0, gain_db=3.0)

    for n in (pt, g, d, bq):
        n.configure(sample_rate=sample_rate, channels=channels)

    x = np.random.uniform(-0.3, 0.3, (channels, 32)).astype(np.float32)
    blk = PCMBlock.from_array(x, sample_rate=sample_rate)

    # All pairwise compositions
    pairs = [
        (g, g),
        (g, d),
        (d, g),
        (g, bq),
        (bq, g),
        (d, bq),
        (bq, d),
        (pt, bq),
        (bq, pt),
    ]

    for first, second in pairs:
        first.reset()
        second.reset()
        out = second.process(first.process(blk))
        assert out.shape == (channels, 32)
        assert out.sample_rate == sample_rate
        assert np.all(np.isfinite(out.samples))


# ==============================================================================
# 3. Deterministic Incompatibility Rejection
# ==============================================================================

def test_incompatible_sample_rates_rejected() -> None:
    """Verify sample-rate mismatch between producer and consumer raises IncompatibleNodeError."""
    node_a = GainNode(gain_db=3.0)
    node_b = DelayNode(delay_frames=10)

    node_a.configure(sample_rate=48000, channels=2)
    node_b.configure(sample_rate=44100, channels=2)

    blk_48k = PCMBlock.from_array(np.zeros((2, 32), dtype=np.float32), sample_rate=48000)
    out_a = node_a.process(blk_48k)

    with pytest.raises(IncompatibleNodeError, match="Sample rate mismatch"):
        node_b.process(out_a)


def test_incompatible_channel_counts_rejected() -> None:
    """Verify channel-count mismatch raises IncompatibleNodeError."""
    node_a = GainNode(gain_db=0.0)
    node_b = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0)

    node_a.configure(sample_rate=48000, channels=1)
    node_b.configure(sample_rate=48000, channels=2)

    blk_mono = PCMBlock.from_array(np.zeros((1, 32), dtype=np.float32), sample_rate=48000)
    out_a = node_a.process(blk_mono)

    with pytest.raises(IncompatibleNodeError, match="Channel count mismatch"):
        node_b.process(out_a)


# ==============================================================================
# 4. Latency Composability Invariants
# ==============================================================================

@pytest.mark.parametrize(
    "d1, d2, expected_latency",
    [
        (0, 0, 0),
        (5, 0, 5),
        (0, 12, 12),
        (15, 25, 40),
    ],
)
def test_cumulative_latency_across_chain(d1: int, d2: int, expected_latency: int) -> None:
    """Verify algorithmic latency is strictly additive across stages."""
    g = GainNode(gain_db=0.0)
    d_node1 = DelayNode(delay_frames=d1)
    d_node2 = DelayNode(delay_frames=d2)
    bq = BiquadNode(filter_type=FilterType.HIGH_PASS, frequency=500.0)

    chain = [g, d_node1, d_node2, bq]
    total_latency = sum(node.latency_frames for node in chain)
    assert total_latency == expected_latency


# ==============================================================================
# 5. State Encapsulation and Isolation
# ==============================================================================

def test_node_state_isolation_during_composition() -> None:
    """Verify internal state of Node A is never overwritten or corrupted by Node B."""
    delay = DelayNode(delay_frames=8)
    biquad = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0)

    delay.configure(sample_rate=48000, channels=1)
    biquad.configure(sample_rate=48000, channels=1)

    impulse = np.zeros((1, 16), dtype=np.float32)
    impulse[0, 0] = 1.0
    blk = PCMBlock.from_array(impulse, sample_rate=48000)

    # Process block through Delay -> Biquad
    out_delay = delay.process(blk)
    out_biquad = biquad.process(out_delay)

    # Delay state must now store the last 8 samples of input (all zeros)
    assert delay._buffer is not None
    assert np.all(delay._buffer == 0.0)

    # Biquad internal state must be non-zero after filtering delayed impulse
    assert biquad._state is not None
    assert np.any(np.abs(biquad._state) > 0.0)


# ==============================================================================
# 6. Stream Continuity across Multiple Arbitrary Blocks
# ==============================================================================

def test_multi_node_arbitrary_block_continuity() -> None:
    """Verify continuous processing of concatenated stream matches chunked sequential processing."""
    total_frames = 256
    sample_rate = 48000
    channels = 2

    # Chain: Gain(+3dB) -> Delay(11) -> Biquad(Peaking)
    gain_a = GainNode(gain_db=3.0)
    delay_a = DelayNode(delay_frames=11)
    bq_a = BiquadNode(filter_type=FilterType.PEAKING, frequency=1500.0, q=1.5, gain_db=6.0)

    gain_b = GainNode(gain_db=3.0)
    delay_b = DelayNode(delay_frames=11)
    bq_b = BiquadNode(filter_type=FilterType.PEAKING, frequency=1500.0, q=1.5, gain_db=6.0)

    for n in (gain_a, delay_a, bq_a, gain_b, delay_b, bq_b):
        n.configure(sample_rate=sample_rate, channels=channels)

    np.random.seed(123)
    x = np.random.uniform(-0.5, 0.5, (channels, total_frames)).astype(np.float32)

    # 1. Monolithic run
    blk_full = PCMBlock.from_array(x.copy(), sample_rate=sample_rate)
    out_mono = bq_a.process(delay_a.process(gain_a.process(blk_full))).samples

    # 2. Chunked run with irregular partitions: 13, 29, 64, 1, 149
    partitions = [13, 29, 64, 1, 149]
    out_chunks = []
    idx = 0
    for p in partitions:
        chunk = x[:, idx : idx + p].copy()
        idx += p
        blk = PCMBlock.from_array(chunk, sample_rate=sample_rate)
        out_blk = bq_b.process(delay_b.process(gain_b.process(blk)))
        out_chunks.append(out_blk.samples)

    out_concatenated = np.concatenate(out_chunks, axis=1)

    # Numerical equivalence conformance threshold
    np.testing.assert_allclose(out_mono, out_concatenated, atol=1e-6, rtol=1e-6)
