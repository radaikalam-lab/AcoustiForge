"""Numerical and contract pass-through test suite for AcoustiForge.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6B, 6F)
"""

import numpy as np

from acoustiforge.contracts.pcm import PCMBlock, AudioMetadata
from acoustiforge.nodes.passthrough import PassThroughNode
from acoustiforge.engine.pipeline import ReferencePipeline


class TestPassThroughNode:
    """PassThroughNode numerical verification."""

    def test_bit_exact_mono_passthrough(self) -> None:
        node = PassThroughNode()
        frames = 512
        # Deterministic pseudo-random float32 data in [-1.0, 1.0]
        rng = np.random.default_rng(42)
        raw_samples = rng.uniform(-1.0, 1.0, (1, frames)).astype(np.float32)
        input_block = PCMBlock.from_array(raw_samples, sample_rate=48000)

        output_block = node.process(input_block)

        assert np.array_equal(output_block.samples, input_block.samples)
        assert output_block.shape == input_block.shape
        assert output_block.sample_rate == input_block.sample_rate
        assert output_block.channels == input_block.channels
        assert output_block.metadata == input_block.metadata
        assert node.latency_frames == 0

    def test_bit_exact_stereo_passthrough(self) -> None:
        node = PassThroughNode()
        frames = 256
        t = np.linspace(0, 1, frames, endpoint=False, dtype=np.float32)
        left = np.sin(2 * np.pi * 440 * t, dtype=np.float32)
        right = np.cos(2 * np.pi * 880 * t, dtype=np.float32)
        raw_samples = np.vstack([left, right])
        input_block = PCMBlock.from_array(raw_samples, sample_rate=44100)

        output_block = node.process(input_block)

        assert np.array_equal(output_block.samples, input_block.samples)
        assert np.array_equal(output_block.channel(0), left)
        assert np.array_equal(output_block.channel(1), right)

    def test_dynamic_range_and_headroom_preservation(self) -> None:
        node = PassThroughNode()
        # Test digital silence (0.0), full-scale (+-1.0), subnormals (1e-6), and unclipped headroom (+-5.0)
        test_values = np.array([
            [0.0, 1.0, -1.0, 0.5, -0.5, 1e-6, -1e-6, 2.5, -5.0, 10.0],
            [0.0, -1.0, 1.0, -0.5, 0.5, -1e-6, 1e-6, -2.5, 5.0, -10.0],
        ], dtype=np.float32)

        input_block = PCMBlock.from_array(test_values, sample_rate=48000)
        output_block = node.process(input_block)

        assert np.array_equal(output_block.samples, test_values)
        assert np.array_equal(output_block.samples, input_block.samples)

    def test_caller_immutability_and_isolation(self) -> None:
        node = PassThroughNode()
        data = np.ones((2, 64), dtype=np.float32)
        input_block = PCMBlock.from_array(data, sample_rate=48000)

        output_block = node.process(input_block)

        # Mutate the source array backing input_block
        data[0, 0] = 999.0

        # output_block must retain original values
        assert output_block.samples[0, 0] == 1.0

    def test_reset_is_deterministic_noop(self) -> None:
        node = PassThroughNode()
        node.reset()
        assert node.latency_frames == 0
        data = np.zeros((1, 32), dtype=np.float32)
        block = PCMBlock.from_array(data, sample_rate=48000)
        output = node.process(block)
        assert np.array_equal(output.samples, data)


class TestReferencePipeline:
    """ReferencePipeline execution engine verification."""

    def test_single_node_pipeline(self) -> None:
        pipeline = ReferencePipeline()
        node = PassThroughNode(name="PT1")
        pipeline.add_node(node)

        assert len(pipeline.nodes) == 1
        assert pipeline.total_latency_frames == 0

        data = np.ones((2, 128), dtype=np.float32) * 0.75
        input_block = PCMBlock.from_array(data, sample_rate=96000)

        output_block = pipeline.process(input_block)
        assert np.array_equal(output_block.samples, input_block.samples)

    def test_multi_node_passthrough_chain(self) -> None:
        pipeline = ReferencePipeline([
            PassThroughNode("PT1"),
            PassThroughNode("PT2"),
            PassThroughNode("PT3"),
        ])

        assert len(pipeline.nodes) == 3
        assert pipeline.total_latency_frames == 0

        rng = np.random.default_rng(100)
        data = rng.uniform(-1.0, 1.0, (2, 256)).astype(np.float32)
        input_block = PCMBlock.from_array(data, sample_rate=48000)

        output_block = pipeline.process(input_block)
        assert np.array_equal(output_block.samples, input_block.samples)

    def test_inactive_node_bypass(self) -> None:
        pt1 = PassThroughNode("PT1")
        pt2 = PassThroughNode("PT2")
        pt2.is_active = False

        pipeline = ReferencePipeline([pt1, pt2])
        assert pipeline.total_latency_frames == 0

        data = np.ones((1, 64), dtype=np.float32)
        block = PCMBlock.from_array(data, sample_rate=48000)
        out = pipeline.process(block)
        assert np.array_equal(out.samples, data)

    def test_stream_processing(self) -> None:
        pipeline = ReferencePipeline([PassThroughNode()])
        num_blocks = 20
        block_size = 128
        rng = np.random.default_rng(200)

        stream_in = [
            PCMBlock.from_array(
                rng.uniform(-0.8, 0.8, (2, block_size)).astype(np.float32),
                sample_rate=48000,
            )
            for _ in range(num_blocks)
        ]

        stream_out = list(pipeline.process_stream(iter(stream_in)))

        assert len(stream_out) == num_blocks
        for in_blk, out_blk in zip(stream_in, stream_out):
            assert np.array_equal(out_blk.samples, in_blk.samples)
            assert out_blk.metadata == in_blk.metadata
