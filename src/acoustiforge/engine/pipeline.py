"""AcoustiForge sequential reference processing pipeline.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6E, 6F)
"""

from __future__ import annotations
from typing import Sequence, Optional, Iterator
from ..contracts.pcm import PCMBlock
from ..contracts.validation import MalformedBufferError, validate_pipeline_link
from ..nodes.base import BaseProcessingNode


class ReferencePipeline:
    """Sequential audio processing execution engine."""

    def __init__(self, nodes: Optional[Sequence[BaseProcessingNode]] = None) -> None:
        self._nodes: list[BaseProcessingNode] = list(nodes) if nodes is not None else []

    @property
    def nodes(self) -> list[BaseProcessingNode]:
        """List of processing nodes in this pipeline."""
        return self._nodes

    def add_node(self, node: BaseProcessingNode) -> ReferencePipeline:
        """Append a processing node to the pipeline."""
        if not isinstance(node, BaseProcessingNode):
            raise TypeError(f"Expected BaseProcessingNode instance, got {type(node)!r}.")
        self._nodes.append(node)
        return self

    @property
    def total_latency_frames(self) -> int:
        """Total latency in frames accumulated across all active nodes."""
        return sum(node.latency_frames for node in self._nodes if node.is_active)

    def process(self, block: PCMBlock) -> PCMBlock:
        """Process a single PCM block through all active pipeline nodes.

        Args:
            block: Valid canonical input PCMBlock.

        Returns:
            Processed output PCMBlock.
        """
        if not isinstance(block, PCMBlock):
            raise MalformedBufferError(f"ReferencePipeline.process expected PCMBlock, got {type(block)!r}.")

        current = block
        for node in self._nodes:
            if node.is_active:
                current = node.process(current)
        return current

    def process_stream(self, stream: Iterator[PCMBlock]) -> Iterator[PCMBlock]:
        """Process an iterator of PCM blocks through the pipeline."""
        for block in stream:
            yield self.process(block)

    def reset(self) -> None:
        """Reset all nodes in the pipeline."""
        for node in self._nodes:
            node.reset()
