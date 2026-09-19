"""Comprehensive unit, property, and verification tests for SequentialPipeline.

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
    InvalidParameterError,
    MalformedBufferError,
    PCMBlock,
    PassThroughNode,
    SequentialPipeline,
)


# ==============================================================================
# 1. Pipeline Construction & Topology Immutability
# ==============================================================================

def test_pipeline_construction_empty_rejected() -> None:
    """Reject empty sequence or non-sequence on construction."""
    with pytest.raises(InvalidParameterError, match="non-empty sequence"):
        SequentialPipeline(nodes=[])
    with pytest.raises(InvalidParameterError):
        SequentialPipeline(nodes="not-a-list")  # type: ignore


def test_pipeline_construction_invalid_element_type() -> None:
    """Reject objects that do not inherit from BaseProcessingNode."""
    with pytest.raises(TypeError, match="BaseProcessingNode"):
        SequentialPipeline(nodes=[GainNode(), "invalid_node"])  # type: ignore


def test_pipeline_topology_immutability() -> None:
    """Verify pipeline topology is fixed as an immutable tuple."""
    g = GainNode()
    d = DelayNode(delay_frames=5)
    pipeline = SequentialPipeline(nodes=[g, d])

    assert isinstance(pipeline.nodes, tuple)
    assert len(pipeline) == 2
    assert pipeline[0] is g
    assert pipeline[1] is d

    # Ensure tuple cannot be mutated
    with pytest.raises(AttributeError):
        pipeline.nodes.append(GainNode())  # type: ignore


# ==============================================================================
# 2. Configuration & Latency Propagation
# ==============================================================================

def test_pipeline_configuration_propagation() -> None:
    """Verify configure() propagates sample rate and channels to all child nodes."""
    g = GainNode()
    d = DelayNode(delay_frames=10)
    bq = BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1000.0)

    pipeline = SequentialPipeline(nodes=[g, d, bq])
    pipeline.configure(sample_rate=48000, channels=2)

    assert pipeline.latency_frames == 10
    assert pipeline.total_latency_frames == 10
    assert bq.coefficients is not None
    assert d._buffer is not None
    assert d._buffer.shape == (2, 10)


def test_pipeline_inactive_bypass_latency() -> None:
    """Verify inactive pipeline reports 0 latency and returns exact copy."""
    pipeline = SequentialPipeline(nodes=[GainNode(gain_db=6.0), DelayNode(delay_frames=16)])
    pipeline.configure(sample_rate=48000, channels=1)
    pipeline.is_active = False

    assert pipeline.latency_frames == 0

    x = np.array([[0.1, 0.2, 0.3]], dtype=np.float32)
    blk = PCMBlock.from_array(x, sample_rate=48000)
    out = pipeline.process(blk)

    np.testing.assert_array_equal(out.samples, x)


# ==============================================================================
# 3. End-to-End Processing & Independent Oracle Verification
# ==============================================================================

def test_pipeline_three_stage_processing_against_manual_composition() -> None:
    """Verify SequentialPipeline output matches manual step-by-step node execution."""
    sample_rate = 48000
    channels = 2

    g = GainNode(gain_db=6.0)
    d = DelayNode(delay_frames=8)
    bq = BiquadNode(filter_type=FilterType.PEAKING, frequency=1000.0, q=2.0, gain_db=3.0)

    # 1. Pipeline execution
    pipeline = SequentialPipeline(nodes=[g, d, bq])
    pipeline.configure(sample_rate=sample_rate, channels=channels)

    x = np.random.uniform(-0.5, 0.5, (channels, 64)).astype(np.float32)
    blk_in = PCMBlock.from_array(x.copy(), sample_rate=sample_rate)
    blk_pipeline_out = pipeline.process(blk_in)

    # 2. Independent manual cascade with identical parameters
    g_ref = GainNode(gain_db=6.0)
    d_ref = DelayNode(delay_frames=8)
    bq_ref = BiquadNode(filter_type=FilterType.PEAKING, frequency=1000.0, q=2.0, gain_db=3.0)

    for n in (g_ref, d_ref, bq_ref):
        n.configure(sample_rate=sample_rate, channels=channels)

    blk_ref_out = bq_ref.process(d_ref.process(g_ref.process(blk_in)))

    np.testing.assert_array_equal(blk_pipeline_out.samples, blk_ref_out.samples)


# ==============================================================================
# 4. Stream Processing & Arbitrary Block Boundary Continuity
# ==============================================================================

def test_pipeline_process_stream_generator() -> None:
    """Verify process_stream yields processed blocks sequentially."""
    pipeline = SequentialPipeline(nodes=[GainNode(gain_db=-6.0), DelayNode(delay_frames=4)])
    pipeline.configure(sample_rate=48000, channels=1)

    blocks = [
        PCMBlock.from_array(np.ones((1, 16), dtype=np.float32), sample_rate=48000),
        PCMBlock.from_array(np.ones((1, 16), dtype=np.float32), sample_rate=48000),
    ]

    out_stream = list(pipeline.process_stream(iter(blocks)))
    assert len(out_stream) == 2
    assert out_stream[0].frames == 16
    assert out_stream[1].frames == 16


def test_pipeline_arbitrary_block_continuity() -> None:
    """Verify processing stream across non-uniform chunks equals monolithic processing."""
    sample_rate = 48000
    channels = 2
    total_frames = 300

    pipeline_mono = SequentialPipeline(
        nodes=[
            GainNode(gain_db=2.0),
            DelayNode(delay_frames=15),
            BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1200.0, q=1.0),
        ]
    )
    pipeline_mono.configure(sample_rate=sample_rate, channels=channels)

    pipeline_chunked = SequentialPipeline(
        nodes=[
            GainNode(gain_db=2.0),
            DelayNode(delay_frames=15),
            BiquadNode(filter_type=FilterType.LOW_PASS, frequency=1200.0, q=1.0),
        ]
    )
    pipeline_chunked.configure(sample_rate=sample_rate, channels=channels)

    np.random.seed(99)
    x = np.random.uniform(-0.4, 0.4, (channels, total_frames)).astype(np.float32)

    # 1. Monolithic run
    out_mono = pipeline_mono.process(PCMBlock.from_array(x.copy(), sample_rate=sample_rate)).samples

    # 2. Non-uniform chunks: 1, 2, 7, 17, 31, 64, 100, 78
    chunks = [1, 2, 7, 17, 31, 64, 100, 78]
    out_chunks = []
    idx = 0
    for sz in chunks:
        chunk = x[:, idx : idx + sz].copy()
        idx += sz
        blk = PCMBlock.from_array(chunk, sample_rate=sample_rate)
        out_chunks.append(pipeline_chunked.process(blk).samples)

    out_concatenated = np.concatenate(out_chunks, axis=1)

    np.testing.assert_allclose(out_mono, out_concatenated, atol=1e-6, rtol=1e-6)


# ==============================================================================
# 5. Reset Propagation & Determinism
# ==============================================================================

def test_pipeline_reset_reproduces_initial_stream() -> None:
    """Verify pipeline reset() zeroes all child state and reproduces identical run."""
    pipeline = SequentialPipeline(
        nodes=[
            DelayNode(delay_frames=6),
            BiquadNode(filter_type=FilterType.HIGH_PASS, frequency=800.0),
        ]
    )
    pipeline.configure(sample_rate=48000, channels=1)

    x = np.random.uniform(-0.5, 0.5, (1, 64)).astype(np.float32)
    blk1 = PCMBlock.from_array(x.copy(), sample_rate=48000)

    # Run 1
    out1 = pipeline.process(blk1).samples

    # Reset
    pipeline.reset()

    # Run 2 after reset with identical input
    blk2 = PCMBlock.from_array(x.copy(), sample_rate=48000)
    out2 = pipeline.process(blk2).samples

    np.testing.assert_array_equal(out1, out2)


# ==============================================================================
# 6. Error & Mismatch Handling
# ==============================================================================

def test_pipeline_rate_and_channel_mismatch_rejection() -> None:
    """Verify IncompatibleNodeError when input block metadata does not match configured pipeline."""
    pipeline = SequentialPipeline(nodes=[GainNode()])
    pipeline.configure(sample_rate=48000, channels=2)

    blk_bad_rate = PCMBlock.from_array(np.zeros((2, 10), dtype=np.float32), sample_rate=44100)
    with pytest.raises(IncompatibleNodeError, match="Sample rate mismatch"):
        pipeline.process(blk_bad_rate)

    blk_bad_chan = PCMBlock.from_array(np.zeros((1, 10), dtype=np.float32), sample_rate=48000)
    with pytest.raises(IncompatibleNodeError, match="Channel count mismatch"):
        pipeline.process(blk_bad_chan)


def test_pipeline_invalid_block_type_rejected() -> None:
    """Verify MalformedBufferError if non-PCMBlock is passed."""
    pipeline = SequentialPipeline(nodes=[GainNode()])
    pipeline.configure(sample_rate=48000, channels=1)

    with pytest.raises(MalformedBufferError):
        pipeline.process("not-a-pcm-block")  # type: ignore
