"""AcoustiForge canonical PassThrough processing node.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6E, 6F)
"""

from __future__ import annotations
from typing import Optional

from ..contracts.pcm import PCMBlock
from ..contracts.validation import MalformedBufferError
from .base import BaseProcessingNode


class PassThroughNode(BaseProcessingNode):
    """Canonical identity processing node.

    Guarantees:
    - Bit-exact sample preservation
    - Zero algorithmic latency (0 frames)
    - Metadata preservation
    - Stateless execution
    - Zero signal transformation
    """

    def __init__(self, name: Optional[str] = "PassThrough") -> None:
        super().__init__(name=name)

    @property
    def latency_frames(self) -> int:
        """Pass-through introduces zero algorithmic latency."""
        return 0

    def process(self, block: PCMBlock) -> PCMBlock:
        """Process an input PCM block and return an identical output block.

        Args:
            block: Valid canonical input PCMBlock.

        Returns:
            Bit-exact canonical output PCMBlock.

        Raises:
            MalformedBufferError: If block is not a valid PCMBlock instance.
        """
        if not isinstance(block, PCMBlock):
            raise MalformedBufferError(
                f"PassThroughNode.process expected PCMBlock, got {type(block)!r}."
            )

        # Return a copy to ensure caller immutability invariant
        return block.copy()

    def reset(self) -> None:
        """Pass-through is stateless; reset is a deterministic no-op."""
        pass
