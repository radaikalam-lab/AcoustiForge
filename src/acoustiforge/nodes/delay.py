"""AcoustiForge Delay Node Implementation.

Normative Authority:
- prompts/MASTER_PROMPT.md
- docs/contracts/PCM_CONTRACT.md
- docs/phases/PHASE_1A_1_DSP_NODE_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

import math
from typing import Optional, Union
import numpy as np

from ..contracts.pcm import PCMBlock
from ..contracts.validation import (
    IncompatibleNodeError,
    InvalidParameterError,
    NonFiniteValueError,
    validate_metadata,
)
from .base import BaseProcessingNode


class DelayNode(BaseProcessingNode):
    """Stateful integer-frame delay processing node.

    Mathematical definition:
        y[n] = x[n - D]
    where:
        D = delay_frames (integer >= 0)
        Initial state prior to input stream is zero.
    """

    def __init__(
        self,
        delay_frames: int = 0,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize DelayNode with integer frame delay and optional stream configuration."""
        super().__init__(name=name)

        self._validate_delay_frames(delay_frames)
        self._delay_frames: int = int(delay_frames)
        self._buffer: Optional[np.ndarray] = None

        if sample_rate is not None and channels is not None:
            self.configure(sample_rate, channels)

    @staticmethod
    def _validate_delay_frames(delay_frames: Union[int, float]) -> None:
        """Validate that delay_frames is an integer >= 0."""
        if isinstance(delay_frames, bool) or not isinstance(delay_frames, int):
            if isinstance(delay_frames, float):
                if not math.isfinite(delay_frames):
                    raise NonFiniteValueError(f"Delay frames must be finite, got {delay_frames!r}.")
                raise InvalidParameterError(
                    f"Delay frames must be an integer, got non-integer float: {delay_frames!r}."
                )
            raise InvalidParameterError(
                f"Delay frames must be an integer >= 0, got {delay_frames!r}."
            )
        if delay_frames < 0:
            raise InvalidParameterError(
                f"Delay frames must be >= 0 (causal constraint), got {delay_frames}."
            )

    @property
    def latency_frames(self) -> int:
        """Algorithmic latency in frames introduced by this node (equal to delay_frames)."""
        return self._delay_frames

    @property
    def delay_frames(self) -> int:
        """Active delay length in integer frames."""
        return self._delay_frames

    def configure(self, sample_rate: int, channels: int) -> None:
        """Configure node with expected sample rate and channel count and allocate state."""
        validate_metadata(sample_rate, channels)
        super().configure(sample_rate, channels)

        # Allocate or re-allocate delay ring buffer initialized to silence
        if self._delay_frames > 0:
            self._buffer = np.zeros((channels, self._delay_frames), dtype=np.float32)
        else:
            self._buffer = None

    def set_parameters(self, delay_frames: int) -> None:
        """Atomically update delay length in frames.

        Note: Per Phase 1D policy, delay reconfiguration intentionally resets delay state
        to silence for the new delay length. If validation fails, active configuration remains unmodified.
        """
        self._validate_delay_frames(delay_frames)
        cand_delay = int(delay_frames)

        # Atomic commit
        self._delay_frames = cand_delay
        if self._channels is not None and self._delay_frames > 0:
            self._buffer = np.zeros((self._channels, self._delay_frames), dtype=np.float32)
        else:
            self._buffer = None

    def reset(self) -> None:
        """Reset internal delay buffer history to silence while preserving configuration."""
        if self._buffer is not None:
            self._buffer.fill(0.0)

    def process(self, block: PCMBlock) -> PCMBlock:
        """Process an input PCM block by delaying the signal by D frames.

        Args:
            block: Valid canonical input PCMBlock.

        Returns:
            Valid canonical output PCMBlock.
        """
        if self._sample_rate is None or self._channels is None:
            self.configure(block.sample_rate, block.channels)
        else:
            if block.sample_rate != self._sample_rate:
                raise IncompatibleNodeError(
                    f"Sample rate mismatch: Node configured for {self._sample_rate} Hz, "
                    f"block has {block.sample_rate} Hz."
                )
            if block.channels != self._channels:
                raise IncompatibleNodeError(
                    f"Channel count mismatch: Node configured for {self._channels} channels, "
                    f"block has {block.channels} channels."
                )

        # Bypass / Inactive pass-through
        if not self._is_active:
            return block.copy()

        # Exact identity for zero delay
        if self._delay_frames == 0:
            return block.copy()

        channels, frames = block.shape
        d = self._delay_frames

        if self._buffer is None or self._buffer.shape != (channels, d):
            self._buffer = np.zeros((channels, d), dtype=np.float32)

        x = block.samples
        y = np.empty((channels, frames), dtype=np.float32)

        if frames >= d:
            # Output first d samples from internal buffer, remaining (frames - d) from current input
            y[:, :d] = self._buffer
            y[:, d:] = x[:, : frames - d]
            # Internal buffer receives the last d samples of current input
            self._buffer[:, :] = x[:, frames - d :]
        else:
            # Block is smaller than delay buffer: output first 'frames' samples from buffer
            y[:, :] = self._buffer[:, :frames]
            # Shift buffer left by 'frames' and append current input at end
            self._buffer[:, : d - frames] = self._buffer[:, frames:]
            self._buffer[:, d - frames :] = x

        return PCMBlock(
            samples=y,
            metadata=block.metadata,
        )
