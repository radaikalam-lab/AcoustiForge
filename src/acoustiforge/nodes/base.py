"""AcoustiForge abstract processing node base class.

Normative Authority: prompts/MASTER_PROMPT.md (Section 6E)
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional

from ..contracts.pcm import PCMBlock
from ..contracts.validation import validate_metadata, MalformedBufferError


class BaseProcessingNode(ABC):
    """Abstract base class for all AcoustiForge processing nodes."""

    def __init__(self, name: Optional[str] = None) -> None:
        self._name: str = name if name is not None else self.__class__.__name__
        self._is_active: bool = True
        self._sample_rate: Optional[int] = None
        self._channels: Optional[int] = None

    @property
    def name(self) -> str:
        """Human-readable identifier of this node."""
        return self._name

    @property
    def is_active(self) -> bool:
        """Whether this node is currently active in processing."""
        return self._is_active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self._is_active = bool(value)

    @property
    @abstractmethod
    def latency_frames(self) -> int:
        """Algorithmic latency in frames introduced by this node."""
        pass

    def configure(self, sample_rate: int, channels: int) -> None:
        """Configure node with expected sample rate and channel count."""
        validate_metadata(sample_rate, channels)
        self._sample_rate = sample_rate
        self._channels = channels

    @abstractmethod
    def process(self, block: PCMBlock) -> PCMBlock:
        """Process an input PCM block and produce an output PCM block.

        Args:
            block: Valid canonical input PCMBlock.

        Returns:
            Valid canonical output PCMBlock.
        """
        pass

    def reset(self) -> None:
        """Reset internal filter states and buffers to initial silence."""
        pass
