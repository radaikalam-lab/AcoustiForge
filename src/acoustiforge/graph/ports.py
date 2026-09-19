"""AcoustiForge Typed Compute Graph Port Model.

Normative Authority:
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/phases/PHASE_2A_1_TYPED_COMPUTE_GRAPH_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..contracts.pcm import ChannelLayout
from ..contracts.validation import validate_metadata


class PortDirection(str, Enum):
    """Directional flow of a compute graph port."""
    INPUT = "input"
    OUTPUT = "output"


class PortType(str, Enum):
    """Semantic payload domain type of a port."""
    PCM = "pcm"


@dataclass(frozen=True, slots=True)
class PortShape:
    """Lightweight runtime-neutral shape contract for a port.

    Decouples semantic Type from computational layout and representation.
    """
    channels: int
    sample_rate: int
    layout: ChannelLayout = ChannelLayout.MONO
    dtype: str = "float32"

    def __post_init__(self) -> None:
        validate_metadata(self.sample_rate, self.channels)
        # Ensure layout matches channels if default layout was used
        expected_layout = ChannelLayout.MONO if self.channels == 1 else ChannelLayout.STEREO
        if self.layout != expected_layout:
            object.__setattr__(self, "layout", expected_layout)


@dataclass(slots=True)
class Port:
    """Explicit structural port on a node within a compute graph."""
    node_id: str
    port_id: str
    direction: PortDirection
    port_type: PortType = PortType.PCM
    shape: Optional[PortShape] = None
    is_required: bool = True

    @property
    def full_id(self) -> str:
        """Fully-qualified compound port identifier (node_id.port_id)."""
        return f"{self.node_id}.{self.port_id}"

    def __repr__(self) -> str:
        req_str = "required" if self.is_required else "optional"
        return (
            f"Port({self.full_id!r}, direction={self.direction.value}, "
            f"type={self.port_type.value}, shape={self.shape}, {req_str})"
        )
