"""Determinism and repeatability tests for AcoustiForge Phase 0.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6F)
"""

import hashlib
import numpy as np

from acoustiforge.contracts.pcm import PCMBlock
from acoustiforge.nodes.passthrough import PassThroughNode
from acoustiforge.engine.pipeline import ReferencePipeline


class TestDeterminism:
    """Multi-iteration determinism test suite."""

    def test_multi_iteration_pass_through_determinism(self) -> None:
        """Run 1,000 randomized block passes and verify bitwise output equality."""
        node = PassThroughNode()
        rng = np.random.default_rng(12345)

        for _ in range(1000):
            channels = int(rng.choice([1, 2]))
            frames = int(rng.integers(1, 1024))
            data = rng.uniform(-2.0, 2.0, (channels, frames)).astype(np.float32)

            input_block = PCMBlock.from_array(data, sample_rate=48000)
            output_block = node.process(input_block)

            assert np.array_equal(output_block.samples, input_block.samples)

    def test_pipeline_hash_determinism(self) -> None:
        """Verify that identical input streams through ReferencePipeline yield identical sha256 digests."""
        rng_seed = 99999
        num_blocks = 50
        block_size = 256

        def run_stream_hash() -> str:
            pipeline = ReferencePipeline([PassThroughNode(), PassThroughNode()])
            rng = np.random.default_rng(rng_seed)
            hasher = hashlib.sha256()

            for _ in range(num_blocks):
                data = rng.uniform(-1.0, 1.0, (2, block_size)).astype(np.float32)
                block = PCMBlock.from_array(data, sample_rate=48000)
                out = pipeline.process(block)
                hasher.update(out.samples.tobytes())

            return hasher.hexdigest()

        hash_1 = run_stream_hash()
        hash_2 = run_stream_hash()
        hash_3 = run_stream_hash()

        assert hash_1 == hash_2 == hash_3
