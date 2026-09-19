"""Comprehensive test suite for AcoustiForge Biquad Filter Node and Coefficients.

Normative Authority:
- prompts/MASTER_PROMPT.md
- docs/phases/PHASE_1B_BIQUAD_FILTER_CONTRACT_AND_MATHEMATICAL_FOUNDATION.md
- docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import numpy as np
import pytest

from acoustiforge import (
    AudioMetadata,
    BiquadCoefficients,
    BiquadNode,
    ChannelLayout,
    FilterType,
    IncompatibleNodeError,
    InvalidBlockSizeError,
    InvalidChannelCountError,
    InvalidParameterError,
    InvalidSampleFormatError,
    InvalidSampleRateError,
    NonFiniteValueError,
    PCMBlock,
    UnstableFilterError,
    calculate_biquad_coefficients,
)

GOLDEN_VECTORS_PATH = (
    Path(__file__).resolve().parent.parent
    / "docs"
    / "phases"
    / "golden"
    / "biquad_golden_vectors.json"
)


# ==============================================================================
# Independent Test Reference Oracle (Step 15)
# ==============================================================================

def independent_rbj_coefficients(
    filter_type: str,
    fs: float,
    f0: float,
    q: float | None = None,
    gain_db: float = 0.0,
    s: float | None = None,
) -> tuple[float, float, float, float, float]:
    """Independent oracle for RBJ cookbook coefficients computed purely in float64."""
    w0 = 2.0 * math.pi * (f0 / fs)
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    A = math.pow(10.0, gain_db / 40.0)

    if s is not None and filter_type in ("low_shelf", "high_shelf"):
        inner = (A + 1.0 / A) * (1.0 / s - 1.0) + 2.0
        alpha = (sin_w0 / 2.0) * math.sqrt(max(0.0, inner))
    else:
        q_val = q if q is not None else 1.0 / math.sqrt(2.0)
        alpha = sin_w0 / (2.0 * q_val)

    if filter_type == "low_pass":
        b0 = (1.0 - cos_w0) / 2.0
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif filter_type == "high_pass":
        b0 = (1.0 + cos_w0) / 2.0
        b1 = -(1.0 + cos_w0)
        b2 = (1.0 + cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif filter_type == "band_pass":
        b0 = sin_w0 / 2.0
        b1 = 0.0
        b2 = -sin_w0 / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif filter_type == "notch":
        b0 = 1.0
        b1 = -2.0 * cos_w0
        b2 = 1.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha
    elif filter_type == "peaking":
        b0 = 1.0 + alpha * A
        b1 = -2.0 * cos_w0
        b2 = 1.0 - alpha * A
        a0 = 1.0 + alpha / A
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha / A
    elif filter_type == "low_shelf":
        sqrt_A = math.sqrt(A)
        b0 = A * ((A + 1.0) - (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha)
        b1 = 2.0 * A * ((A - 1.0) - (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) - (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha)
        a0 = (A + 1.0) + (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha
        a1 = -2.0 * ((A - 1.0) + (A + 1.0) * cos_w0)
        a2 = (A + 1.0) + (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha
    elif filter_type == "high_shelf":
        sqrt_A = math.sqrt(A)
        b0 = A * ((A + 1.0) + (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha)
        b1 = -2.0 * A * ((A - 1.0) + (A + 1.0) * cos_w0)
        b2 = A * ((A + 1.0) + (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha)
        a0 = (A + 1.0) - (A - 1.0) * cos_w0 + 2.0 * sqrt_A * alpha
        a1 = 2.0 * ((A - 1.0) - (A + 1.0) * cos_w0)
        a2 = (A + 1.0) - (A - 1.0) * cos_w0 - 2.0 * sqrt_A * alpha
    else:
        raise ValueError(f"Unknown filter: {filter_type}")

    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def independent_df2t_filter(
    x: np.ndarray, b0: float, b1: float, b2: float, a1: float, a2: float
) -> np.ndarray:
    """Independent oracle for Direct Form II Transposed filtering in double precision."""
    channels, frames = x.shape
    y = np.zeros((channels, frames), dtype=np.float64)
    for c in range(channels):
        s1 = 0.0
        s2 = 0.0
        for n in range(frames):
            x_n = float(x[c, n])
            y_n = b0 * x_n + s1
            s1 = b1 * x_n - a1 * y_n + s2
            s2 = b2 * x_n - a2 * y_n
            y[c, n] = y_n
    return y


# ==============================================================================
# A. Filter Type Coverage & B. Coefficient Correctness
# ==============================================================================

@pytest.mark.parametrize("ftype", list(FilterType))
def test_all_seven_filter_families_coefficient_calculation(ftype: FilterType) -> None:
    """Test that all 7 filter types compute mathematically exact normalized coefficients."""
    fs = 48000
    f0 = 1000.0
    q = 0.707107
    gain_db = 3.0
    s = 1.0 if "shelf" in ftype.value else None

    coeffs = calculate_biquad_coefficients(
        filter_type=ftype,
        sample_rate=fs,
        frequency=f0,
        q=q if s is None else None,
        shelf_slope=s,
        gain_db=gain_db,
    )

    oracle = independent_rbj_coefficients(
        filter_type=ftype.value,
        fs=fs,
        f0=f0,
        q=q if s is None else None,
        gain_db=gain_db,
        s=s,
    )

    # Conformance check: |w_runtime - w_ref| <= 1e-6
    np.testing.assert_allclose(coeffs.as_tuple(), oracle, atol=1e-12, rtol=1e-12)
    assert coeffs.a0 == 1.0
    assert coeffs.is_stable()


def test_bandwidth_parameterization() -> None:
    """Test filter coefficient calculation using bandwidth in octaves."""
    coeffs = calculate_biquad_coefficients(
        filter_type=FilterType.PEAKING,
        sample_rate=48000,
        frequency=1000.0,
        bandwidth=1.0,
        gain_db=6.0,
    )
    assert coeffs.is_stable()
    assert abs(coeffs.b0) > 0


# ==============================================================================
# C. Parameter Validation & Edge Cases
# ==============================================================================

def test_invalid_sample_rate() -> None:
    """Reject non-positive or invalid sample rates."""
    with pytest.raises(InvalidSampleRateError):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=0, frequency=1000.0)
    with pytest.raises(InvalidSampleRateError):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=-48000, frequency=1000.0)
    with pytest.raises(InvalidSampleRateError):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=True, frequency=1000.0)  # type: ignore


def test_dc_boundary_rejection() -> None:
    """Reject f0 <= 0 Hz (DC boundary singularity)."""
    with pytest.raises(InvalidParameterError, match="DC boundary"):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=0.0)
    with pytest.raises(InvalidParameterError, match="DC boundary"):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=-50.0)


def test_nyquist_boundary_rejection() -> None:
    """Reject f0 >= fs/2 (Nyquist boundary singularity)."""
    with pytest.raises(InvalidParameterError, match="Nyquist"):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=24000.0)
    with pytest.raises(InvalidParameterError, match="Nyquist"):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=25000.0)


def test_invalid_quality_factor() -> None:
    """Reject Q <= 0."""
    with pytest.raises(InvalidParameterError, match="Quality factor"):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=1000.0, q=0.0)
    with pytest.raises(InvalidParameterError, match="Quality factor"):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=1000.0, q=-1.0)


def test_invalid_bandwidth_and_shelf_slope() -> None:
    """Reject BW <= 0 and S <= 0."""
    with pytest.raises(InvalidParameterError, match="Bandwidth"):
        calculate_biquad_coefficients(FilterType.PEAKING, sample_rate=48000, frequency=1000.0, bandwidth=0.0)
    with pytest.raises(InvalidParameterError, match="Shelf slope"):
        calculate_biquad_coefficients(FilterType.LOW_SHELF, sample_rate=48000, frequency=1000.0, shelf_slope=0.0)


def test_non_finite_parameter_rejection() -> None:
    """Reject NaN and Inf parameters."""
    with pytest.raises(NonFiniteValueError):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=float("nan"))
    with pytest.raises(NonFiniteValueError):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=float("inf"))
    with pytest.raises(NonFiniteValueError):
        calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=1000.0, q=float("nan"))
    with pytest.raises(NonFiniteValueError):
        calculate_biquad_coefficients(FilterType.PEAKING, sample_rate=48000, frequency=1000.0, gain_db=float("inf"))


def test_unsupported_filter_type_string() -> None:
    """Reject invalid filter type strings."""
    with pytest.raises(InvalidParameterError, match="Unsupported filter type"):
        calculate_biquad_coefficients("super_pass", sample_rate=48000, frequency=1000.0)


# ==============================================================================
# D. Stability Validation
# ==============================================================================

def test_stability_checker_schur_jury() -> None:
    """Test Schur/Jury conditions for both stable and unstable coefficients."""
    # Stable Butterworth lowpass
    stable_coeffs = calculate_biquad_coefficients(FilterType.LOW_PASS, sample_rate=48000, frequency=1000.0)
    assert stable_coeffs.is_stable()

    # Unstable coefficient mock (|a2| >= 1.0)
    unstable_coeffs_a2 = BiquadCoefficients(b0=1.0, b1=0.0, b2=0.0, a1=-0.5, a2=1.05)
    assert not unstable_coeffs_a2.is_stable()

    # Unstable condition 2: 1 + a1 + a2 <= 0
    unstable_coeffs_c2 = BiquadCoefficients(b0=1.0, b1=0.0, b2=0.0, a1=-1.5, a2=0.4)
    assert not unstable_coeffs_c2.is_stable()


# ==============================================================================
# E. DF-II-T Impulse Response & Conformance
# ==============================================================================

def test_df2t_impulse_response_matches_oracle() -> None:
    """Verify BiquadNode impulse response against independent float64 oracle."""
    node = BiquadNode(FilterType.PEAKING, frequency=1000.0, q=2.0, gain_db=6.0)
    node.configure(sample_rate=48000, channels=1)

    impulse_data = np.zeros((1, 128), dtype=np.float32)
    impulse_data[0, 0] = 1.0
    block_in = PCMBlock.from_array(impulse_data, sample_rate=48000)

    block_out = node.process(block_in)

    # Independent oracle calculation
    oracle_coeffs = independent_rbj_coefficients("peaking", fs=48000, f0=1000.0, q=2.0, gain_db=6.0)
    oracle_y = independent_df2t_filter(impulse_data, *oracle_coeffs)

    # Conformance tier: |y_runtime - y_ref| <= 1.0e-5
    np.testing.assert_allclose(block_out.samples, oracle_y.astype(np.float32), atol=1e-5, rtol=1e-5)


# ==============================================================================
# F. State Continuity (Block Boundary Invariance)
# ==============================================================================

def test_state_continuity_across_variable_block_sizes() -> None:
    """Verify that processing in multiple small blocks equals one large block."""
    np.random.seed(42)
    total_frames = 1024
    input_data = np.random.uniform(-0.5, 0.5, (2, total_frames)).astype(np.float32)

    # 1. Process as one single large block
    node_monolithic = BiquadNode(FilterType.LOW_PASS, frequency=1500.0, q=1.0)
    node_monolithic.configure(sample_rate=48000, channels=2)
    block_full = PCMBlock.from_array(input_data.copy(), sample_rate=48000)
    out_full = node_monolithic.process(block_full).samples

    # 2. Process in irregular sequential chunks: 17, 31, 64, 1, 512, remainder
    node_chunked = BiquadNode(FilterType.LOW_PASS, frequency=1500.0, q=1.0)
    node_chunked.configure(sample_rate=48000, channels=2)

    chunk_sizes = [17, 31, 64, 1, 512, total_frames - (17 + 31 + 64 + 1 + 512)]
    out_chunks = []
    idx = 0
    for sz in chunk_sizes:
        chunk_data = input_data[:, idx : idx + sz].copy()
        idx += sz
        blk = PCMBlock.from_array(chunk_data, sample_rate=48000)
        out_chunks.append(node_chunked.process(blk).samples)

    out_concatenated = np.concatenate(out_chunks, axis=1)

    # Strict sample-accurate equality
    np.testing.assert_allclose(out_full, out_concatenated, atol=1e-6, rtol=1e-6)


# ==============================================================================
# G. Reset Semantics
# ==============================================================================

def test_reset_clears_state_and_preserves_configuration() -> None:
    """Verify reset() clears internal state registers to produce identical run from zero."""
    node = BiquadNode(FilterType.HIGH_PASS, frequency=500.0, q=0.707107)
    node.configure(sample_rate=48000, channels=1)

    impulse = np.zeros((1, 64), dtype=np.float32)
    impulse[0, 0] = 1.0

    # Run 1
    blk1 = PCMBlock.from_array(impulse.copy(), sample_rate=48000)
    out1 = node.process(blk1).samples

    # Node now has non-zero internal state. Run a zero block without reset:
    zero_blk = PCMBlock.from_array(np.zeros((1, 64), dtype=np.float32), sample_rate=48000)
    out_tail = node.process(zero_blk).samples
    assert np.any(np.abs(out_tail) > 1e-10), "Filter tail should decay across blocks"

    # Reset
    node.reset()

    # Run 2 after reset with identical impulse
    blk2 = PCMBlock.from_array(impulse.copy(), sample_rate=48000)
    out2 = node.process(blk2).samples

    # Must be bit-exact identical to run 1
    np.testing.assert_array_equal(out1, out2)


# ==============================================================================
# H. Channel Isolation
# ==============================================================================

def test_stereo_channel_state_isolation() -> None:
    """Verify channel 0 and channel 1 have completely isolated state registers."""
    node = BiquadNode(FilterType.PEAKING, frequency=1000.0, q=2.0, gain_db=6.0)
    node.configure(sample_rate=48000, channels=2)

    # Stereo block: channel 0 has impulse, channel 1 has silence
    stereo_data = np.zeros((2, 64), dtype=np.float32)
    stereo_data[0, 0] = 1.0

    blk = PCMBlock.from_array(stereo_data, sample_rate=48000)
    out = node.process(blk).samples

    # Channel 0 must have filter response
    assert np.any(np.abs(out[0]) > 0.0)
    # Channel 1 must remain strictly identically zero
    assert np.all(out[1] == 0.0)


# ==============================================================================
# I. Parameter Transaction Semantics
# ==============================================================================

def test_atomic_parameter_update_success_and_failure() -> None:
    """Verify atomic parameter transaction guarantees."""
    node = BiquadNode(FilterType.LOW_PASS, frequency=1000.0, q=0.707107)
    node.configure(sample_rate=48000, channels=1)

    initial_coeffs = node.coefficients
    assert initial_coeffs is not None

    # 1. Failed parameter update (invalid frequency f0 >= Nyquist)
    with pytest.raises(InvalidParameterError):
        node.set_parameters(frequency=30000.0)

    # Confirm active parameters & coefficients remain untouched
    assert node.frequency == 1000.0
    assert node.coefficients == initial_coeffs

    # 2. Failed parameter update (non-finite Q)
    with pytest.raises(NonFiniteValueError):
        node.set_parameters(q=float("nan"))

    assert node.q == 0.707107
    assert node.coefficients == initial_coeffs

    # 3. Successful parameter update
    node.set_parameters(frequency=2000.0, q=1.5)
    assert node.frequency == 2000.0
    assert node.q == 1.5
    assert node.coefficients != initial_coeffs


# ==============================================================================
# J. Determinism & Bypass
# ==============================================================================

def test_processing_determinism() -> None:
    """Verify that identical input data and node configuration produces deterministic output."""
    node1 = BiquadNode(FilterType.NOTCH, frequency=60.0, q=10.0)
    node2 = BiquadNode(FilterType.NOTCH, frequency=60.0, q=10.0)

    data = np.random.uniform(-1.0, 1.0, (2, 256)).astype(np.float32)
    blk1 = PCMBlock.from_array(data.copy(), sample_rate=48000)
    blk2 = PCMBlock.from_array(data.copy(), sample_rate=48000)

    out1 = node1.process(blk1).samples
    out2 = node2.process(blk2).samples

    np.testing.assert_array_equal(out1, out2)


def test_node_bypass_mode() -> None:
    """Verify that when is_active is False, the node performs bit-accurate pass-through."""
    node = BiquadNode(FilterType.LOW_PASS, frequency=200.0)
    node.configure(sample_rate=48000, channels=1)
    node.is_active = False

    data = np.random.uniform(-0.5, 0.5, (1, 128)).astype(np.float32)
    blk = PCMBlock.from_array(data, sample_rate=48000)
    out_blk = node.process(blk)

    np.testing.assert_array_equal(out_blk.samples, data)


# ==============================================================================
# K. PCM Contract Integration & Errors
# ==============================================================================

def test_pcm_contract_rate_and_channel_mismatch() -> None:
    """Verify IncompatibleNodeError on block rate or channel mismatch."""
    node = BiquadNode(FilterType.LOW_PASS, frequency=1000.0)
    node.configure(sample_rate=48000, channels=2)

    # Rate mismatch
    blk_bad_rate = PCMBlock.from_array(np.zeros((2, 64), dtype=np.float32), sample_rate=44100)
    with pytest.raises(IncompatibleNodeError, match="Sample rate mismatch"):
        node.process(blk_bad_rate)

    # Channel mismatch
    blk_bad_chan = PCMBlock.from_array(np.zeros((1, 64), dtype=np.float32), sample_rate=48000)
    with pytest.raises(IncompatibleNodeError, match="Channel count mismatch"):
        node.process(blk_bad_chan)


# ==============================================================================
# L. Latency Contract
# ==============================================================================

def test_latency_frames_is_zero() -> None:
    """Verify algorithmic latency is reported as 0 frames."""
    node = BiquadNode(FilterType.LOW_PASS, frequency=1000.0)
    assert node.latency_frames == 0


# ==============================================================================
# M & N. Verification of All 10 Golden Vectors (Step 13 & 14)
# ==============================================================================

def test_all_ten_golden_vectors() -> None:
    """Verify BiquadNode against all 10 canonical golden reference vectors."""
    assert GOLDEN_VECTORS_PATH.exists(), f"Golden vectors file missing: {GOLDEN_VECTORS_PATH}"

    with open(GOLDEN_VECTORS_PATH, "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)

    vectors = golden_dataset["vectors"]
    assert len(vectors) == 10, f"Expected 10 golden vectors, got {len(vectors)}"

    for gv in vectors:
        vec_id = gv["vector_id"]
        ftype = gv["filter_type"]
        fs = gv["sample_rate"]
        f0 = gv["frequency"]
        q = gv["q"]
        s = gv["shelf_slope"]
        gain_db = gv["gain_db"]
        expected_coeffs = gv["coefficients"]
        expected_impulse = np.array(gv["impulse_response_16"], dtype=np.float32)

        # 1. Compute coefficients and verify numerical equivalence (|w_rt - w_ref| <= 1e-6)
        coeffs = calculate_biquad_coefficients(
            filter_type=ftype,
            sample_rate=fs,
            frequency=f0,
            q=q,
            shelf_slope=s,
            gain_db=gain_db,
        )

        assert abs(coeffs.b0 - expected_coeffs["b0"]) <= 1e-6, f"{vec_id} b0 mismatch"
        assert abs(coeffs.b1 - expected_coeffs["b1"]) <= 1e-6, f"{vec_id} b1 mismatch"
        assert abs(coeffs.b2 - expected_coeffs["b2"]) <= 1e-6, f"{vec_id} b2 mismatch"
        assert abs(coeffs.a1 - expected_coeffs["a1"]) <= 1e-6, f"{vec_id} a1 mismatch"
        assert abs(coeffs.a2 - expected_coeffs["a2"]) <= 1e-6, f"{vec_id} a2 mismatch"

        # 2. Process unit impulse through BiquadNode and verify impulse response
        node = BiquadNode(
            filter_type=ftype,
            frequency=f0,
            q=q,
            shelf_slope=s,
            gain_db=gain_db,
        )
        node.configure(sample_rate=fs, channels=1)

        impulse_in = np.zeros((1, 16), dtype=np.float32)
        impulse_in[0, 0] = 1.0
        blk_in = PCMBlock.from_array(impulse_in, sample_rate=fs)

        blk_out = node.process(blk_in)
        y_out = blk_out.samples[0]

        # Numerical tolerance threshold: |y_runtime - y_ref| <= 1.0e-5
        np.testing.assert_allclose(
            y_out,
            expected_impulse,
            atol=1e-5,
            rtol=1e-5,
            err_msg=f"Golden Vector {vec_id} ({gv['description']}) failed impulse response verification",
        )


# ==============================================================================
# P. Edge Conditions (Step 16)
# ==============================================================================

def test_extreme_edge_parameters() -> None:
    """Test extreme valid frequencies, Q, S, and gains."""
    fs = 48000

    # 1. f0 close to zero (1 Hz)
    c_low = calculate_biquad_coefficients(FilterType.LOW_PASS, fs, frequency=1.0, q=0.707107)
    assert c_low.is_stable()

    # 2. f0 close to Nyquist (23990 Hz)
    c_high = calculate_biquad_coefficients(FilterType.HIGH_PASS, fs, frequency=23990.0, q=0.707107)
    assert c_high.is_stable()

    # 3. Q near lower bound (0.05) and upper bound (100.0)
    c_q_low = calculate_biquad_coefficients(FilterType.PEAKING, fs, frequency=1000.0, q=0.05, gain_db=6.0)
    assert c_q_low.is_stable()
    c_q_high = calculate_biquad_coefficients(FilterType.PEAKING, fs, frequency=1000.0, q=100.0, gain_db=6.0)
    assert c_q_high.is_stable()

    # 4. Shelf slope near bounds (0.1 and 2.0)
    c_s_low = calculate_biquad_coefficients(FilterType.LOW_SHELF, fs, frequency=200.0, shelf_slope=0.1, gain_db=6.0)
    assert c_s_low.is_stable()
    c_s_high = calculate_biquad_coefficients(FilterType.HIGH_SHELF, fs, frequency=5000.0, shelf_slope=2.0, gain_db=-6.0)
    assert c_s_high.is_stable()

    # 5. Gain near bounds (-80.0 dB and +40.0 dB)
    c_g_neg = calculate_biquad_coefficients(FilterType.PEAKING, fs, frequency=1000.0, q=1.0, gain_db=-80.0)
    assert c_g_neg.is_stable()
    c_g_pos = calculate_biquad_coefficients(FilterType.PEAKING, fs, frequency=1000.0, q=1.0, gain_db=40.0)
    assert c_g_pos.is_stable()

    # 6. Zero gain for peaking / shelf (unity pass-through)
    c_g_zero = calculate_biquad_coefficients(FilterType.PEAKING, fs, frequency=1000.0, q=1.0, gain_db=0.0)
    assert c_g_zero.is_stable()
    assert abs(c_g_zero.b0 - 1.0) < 1e-12
    assert abs(c_g_zero.b1 - c_g_zero.a1) < 1e-12
    assert abs(c_g_zero.b2 - c_g_zero.a2) < 1e-12
