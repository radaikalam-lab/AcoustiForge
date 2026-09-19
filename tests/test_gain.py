"""Unit and property tests for AcoustiForge GainNode.

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
    ChannelLayout,
    GainNode,
    IncompatibleNodeError,
    InvalidParameterError,
    NonFiniteValueError,
    PCMBlock,
)


# ==============================================================================
# 1. Construction and Configuration
# ==============================================================================

def test_gain_node_construction_default() -> None:
    """Verify default initialization: 0.0 dB gain, 0 latency."""
    node = GainNode()
    assert node.gain_db == 0.0
    assert math.isclose(node.gain_linear, 1.0, rel_tol=1e-12)
    assert node.latency_frames == 0
    assert node.is_active is True


def test_gain_node_construction_custom() -> None:
    """Verify initialization with custom gain and explicit configuration."""
    node = GainNode(gain_db=6.020599913279624, sample_rate=48000, channels=2, name="PreAmp")
    assert node.name == "PreAmp"
    assert math.isclose(node.gain_linear, 2.0, rel_tol=1e-7)
    assert node.latency_frames == 0


# ==============================================================================
# 2. Known Numerical Gains & Processing (Positive, Negative, 0 dB)
# ==============================================================================

def test_gain_positive_db() -> None:
    """Verify +6 dB gain scales amplitude by ~2x."""
    node = GainNode(gain_db=6.0)
    node.configure(sample_rate=48000, channels=1)

    x = np.array([[0.1, 0.2, -0.3, 0.4]], dtype=np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)
    blk_out = node.process(blk_in)

    expected = x * np.float32(math.pow(10.0, 6.0 / 20.0))
    np.testing.assert_allclose(blk_out.samples, expected, atol=1e-7, rtol=1e-7)


def test_gain_negative_db() -> None:
    """Verify -20 dB gain scales amplitude by 0.1x."""
    node = GainNode(gain_db=-20.0)
    node.configure(sample_rate=48000, channels=2)

    x = np.ones((2, 64), dtype=np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)
    blk_out = node.process(blk_in)

    expected = x * np.float32(0.1)
    np.testing.assert_allclose(blk_out.samples, expected, atol=1e-7, rtol=1e-7)


def test_gain_zero_db_identity() -> None:
    """Verify 0 dB produces exact sample values."""
    node = GainNode(gain_db=0.0)
    node.configure(sample_rate=48000, channels=2)

    x = np.random.uniform(-0.9, 0.9, (2, 128)).astype(np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)
    blk_out = node.process(blk_in)

    np.testing.assert_allclose(blk_out.samples, x, atol=1e-7, rtol=1e-7)


# ==============================================================================
# 3. Channels, Arbitrary Block Sizes, and Metadata Preservation
# ==============================================================================

@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("frames", [1, 7, 17, 31, 64, 256, 1024])
def test_gain_arbitrary_channels_and_block_sizes(channels: int, frames: int) -> None:
    """Verify correct processing across arbitrary channel counts and block sizes."""
    node = GainNode(gain_db=3.0)
    x = np.random.uniform(-0.5, 0.5, (channels, frames)).astype(np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=44100)

    blk_out = node.process(blk_in)

    assert blk_out.channels == channels
    assert blk_out.frames == frames
    assert blk_out.sample_rate == 44100
    assert blk_out.metadata.layout == (ChannelLayout.MONO if channels == 1 else ChannelLayout.STEREO)

    expected = x * np.float32(math.pow(10.0, 3.0 / 20.0))
    np.testing.assert_allclose(blk_out.samples, expected, atol=1e-7, rtol=1e-7)


# ==============================================================================
# 4. Parameter Validation & Transactions
# ==============================================================================

def test_gain_parameter_rejection() -> None:
    """Reject non-finite and invalid parameter values."""
    with pytest.raises(NonFiniteValueError):
        GainNode(gain_db=float("nan"))
    with pytest.raises(NonFiniteValueError):
        GainNode(gain_db=float("inf"))
    with pytest.raises(NonFiniteValueError):
        GainNode(gain_db=float("-inf"))
    with pytest.raises(InvalidParameterError):
        GainNode(gain_db=True)  # type: ignore
    with pytest.raises(InvalidParameterError):
        GainNode(gain_db="6dB")  # type: ignore


def test_gain_parameter_transaction_rollback() -> None:
    """Verify failed parameter update leaves active configuration untouched."""
    node = GainNode(gain_db=6.0)
    assert node.gain_db == 6.0
    orig_linear = node.gain_linear

    # Failed update
    with pytest.raises(NonFiniteValueError):
        node.set_parameters(gain_db=float("nan"))

    assert node.gain_db == 6.0
    assert node.gain_linear == orig_linear

    # Successful update
    node.set_parameters(gain_db=-12.0)
    assert node.gain_db == -12.0
    assert math.isclose(node.gain_linear, math.pow(10.0, -12.0 / 20.0), rel_tol=1e-12)


# ==============================================================================
# 5. Statelessness, Reset, Bypass, and Incompatibilities
# ==============================================================================

def test_gain_stateless_reset() -> None:
    """Verify reset() is a deterministic no-op on state."""
    node = GainNode(gain_db=3.0)
    node.configure(sample_rate=48000, channels=1)

    node.reset()
    assert node.gain_db == 3.0
    assert node.latency_frames == 0


def test_gain_bypass_mode() -> None:
    """Verify inactive GainNode returns exact copy."""
    node = GainNode(gain_db=12.0)
    node.configure(sample_rate=48000, channels=1)
    node.is_active = False

    x = np.array([[0.5, -0.5]], dtype=np.float32)
    blk_in = PCMBlock.from_array(x, sample_rate=48000)
    blk_out = node.process(blk_in)

    np.testing.assert_array_equal(blk_out.samples, x)


def test_gain_rate_and_channel_mismatch() -> None:
    """Verify IncompatibleNodeError when input block metadata does not match configured node."""
    node = GainNode(gain_db=0.0)
    node.configure(sample_rate=48000, channels=2)

    blk_wrong_rate = PCMBlock.from_array(np.zeros((2, 10), dtype=np.float32), sample_rate=44100)
    with pytest.raises(IncompatibleNodeError, match="Sample rate mismatch"):
        node.process(blk_wrong_rate)

    blk_wrong_chan = PCMBlock.from_array(np.zeros((1, 10), dtype=np.float32), sample_rate=48000)
    with pytest.raises(IncompatibleNodeError, match="Channel count mismatch"):
        node.process(blk_wrong_chan)


# ==============================================================================
# 6. Property & Invariant Tests
# ==============================================================================

def test_gain_cascade_composition_invariant() -> None:
    """Verify gain(g1, gain(g2, x)) is equivalent to gain(g1 + g2, x)."""
    node1 = GainNode(gain_db=6.0)
    node2 = GainNode(gain_db=-18.0)
    node_combined = GainNode(gain_db=-12.0)

    x = np.random.uniform(-0.8, 0.8, (2, 256)).astype(np.float32)
    blk = PCMBlock.from_array(x, sample_rate=48000)

    out_cascade = node2.process(node1.process(blk))
    out_combined = node_combined.process(blk)

    np.testing.assert_allclose(out_cascade.samples, out_combined.samples, atol=1e-7, rtol=1e-7)
