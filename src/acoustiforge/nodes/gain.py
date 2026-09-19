"""AcoustiForge Gain Node Implementation.

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


class GainNode(BaseProcessingNode):
    """Stateless scalar linear gain processing node.

    Mathematical definition:
        y[n] = G * x[n]
    where:
        G = 10^(gain_db / 20)
    """

    def __init__(
        self,
        gain_db: float = 0.0,
        sample_rate: Optional[int] = None,
        channels: Optional[int] = None,
        name: Optional[str] = None,
    ) -> None:
        """Initialize GainNode with gain in dB and optional stream configuration."""
        super().__init__(name=name)

        self._validate_gain(gain_db)
        self._gain_db: float = float(gain_db)
        self._gain_linear: float = math.pow(10.0, self._gain_db / 20.0)

        if sample_rate is not None and channels is not None:
            self.configure(sample_rate, channels)

    @staticmethod
    def _validate_gain(gain_db: Union[int, float]) -> None:
        """Validate that gain parameter is a finite number."""
        if isinstance(gain_db, bool) or not isinstance(gain_db, (int, float)):
            raise InvalidParameterError(f"Gain must be a numeric value in dB, got {gain_db!r}.")
        if not math.isfinite(gain_db):
            raise NonFiniteValueError(f"Gain must be finite, got {gain_db!r}.")

    @property
    def latency_frames(self) -> int:
        """Algorithmic latency in frames (GainNode has zero algorithmic latency)."""
        return 0

    @property
    def gain_db(self) -> float:
        """Active gain in decibels (dB)."""
        return self._gain_db

    @property
    def gain_linear(self) -> float:
        """Active derived linear gain scalar."""
        return self._gain_linear

    def set_parameters(self, gain_db: float) -> None:
        """Atomically update gain parameter in dB.

        If validation fails, active configuration remains unmodified.
        """
        self._validate_gain(gain_db)
        cand_db = float(gain_db)
        cand_linear = math.pow(10.0, cand_db / 20.0)

        # Atomic commit
        self._gain_db = cand_db
        self._gain_linear = cand_linear

    def reset(self) -> None:
        """Reset internal node state (stateless no-op; preserves active configuration)."""
        pass

    def process(self, block: PCMBlock) -> PCMBlock:
        """Process an input PCM block by applying linear scalar gain.

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

        # Gain application in float32 PCM domain
        g = np.float32(self._gain_linear)
        y = block.samples * g

        return PCMBlock(
            samples=y,
            metadata=block.metadata,
        )
