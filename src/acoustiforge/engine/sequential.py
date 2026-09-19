"""AcoustiForge Immutable Sequential Processing Pipeline.

Normative Authority:
- docs/contracts/NODE_COMPOSITION_CONTRACT.md
- docs/phases/PHASE_1E_NODE_COMPOSITION_CONTRACT_DISCOVERY.md
"""

from __future__ import annotations

from typing import Iterator, Optional, Sequence
from ..contracts.pcm import PCMBlock
from ..contracts.validation import (
    IncompatibleNodeError,
    InvalidParameterError,
    MalformedBufferError,
    validate_metadata,
)
from ..nodes.base import BaseProcessingNode


class SequentialPipeline(BaseProcessingNode):
    """Immutable linear execution pipeline composing compatible ACE processing nodes.

    Conforms to the Phase 1E Node Composition Contract (CONTRACT-COMPOSITION-01).
    """

    def __init__(
        self,
        nodes: Sequence[BaseProcessingNode],
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize SequentialPipeline with an immutable sequence of processing nodes."""
        super().__init__(name=name)

        if not isinstance(nodes, (list, tuple)) or len(nodes) == 0:
            raise InvalidParameterError("SequentialPipeline requires a non-empty sequence of nodes.")

        for i, node in enumerate(nodes):
            if not isinstance(node, BaseProcessingNode):
                raise TypeError(
                    f"Node at index {i} must be a BaseProcessingNode instance, got {type(node)!r}."
                )

        # Fix topology as an immutable tuple
        self._nodes: tuple[BaseProcessingNode, ...] = tuple(nodes)

        if sample_rate is not None and channels is not None:
            self.configure(sample_rate, channels)

    @property
    def nodes(self) -> tuple[BaseProcessingNode, ...]:
        """Immutable tuple of processing nodes in this pipeline."""
        return self._nodes

    @property
    def latency_frames(self) -> int:
        """Total cumulative algorithmic latency in frames across all active nodes."""
        if not self._is_active:
            return 0
        return sum(node.latency_frames for node in self._nodes if node.is_active)

    @property
    def total_latency_frames(self) -> int:
        """Alias for latency_frames."""
        return self.latency_frames

    def __len__(self) -> int:
        """Return the number of nodes in this pipeline."""
        return len(self._nodes)

    def __getitem__(self, index: int) -> BaseProcessingNode:
        """Get node at specified index."""
        return self._nodes[index]

    def configure(self, sample_rate: int, channels: int) -> None:
        """Configure pipeline and all child nodes in forward declaration order."""
        validate_metadata(sample_rate, channels)
        super().configure(sample_rate, channels)

        for node in self._nodes:
            node.configure(sample_rate, channels)

    def reset(self) -> None:
        """Reset all child nodes in forward declaration order."""
        for node in self._nodes:
            node.reset()

    def process(self, block: PCMBlock) -> PCMBlock:
        """Process an input PCM block through all active pipeline stages sequentially.

        Args:
            block: Valid canonical input PCMBlock.

        Returns:
            Processed output PCMBlock.
        """
        if not isinstance(block, PCMBlock):
            raise MalformedBufferError(f"Expected PCMBlock, got {type(block)!r}.")

        # Auto-configure if unconfigured
        if self._sample_rate is None or self._channels is None:
            self.configure(block.sample_rate, block.channels)
        else:
            if block.sample_rate != self._sample_rate:
                raise IncompatibleNodeError(
                    f"Sample rate mismatch: Pipeline configured for {self._sample_rate} Hz, "
                    f"block has {block.sample_rate} Hz."
                )
            if block.channels != self._channels:
                raise IncompatibleNodeError(
                    f"Channel count mismatch: Pipeline configured for {self._channels} channels, "
                    f"block has {block.channels} channels."
                )

        if not self._is_active:
            return block.copy()

        current = block
        for node in self._nodes:
            if node.is_active:
                current = node.process(current)

        return current

    def process_stream(self, stream: Iterator[PCMBlock]) -> Iterator[PCMBlock]:
        """Process an iterator of PCM blocks sequentially through the pipeline."""
        for block in stream:
            yield self.process(block)
