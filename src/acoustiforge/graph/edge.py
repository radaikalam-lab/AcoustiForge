"""AcoustiForge Typed Compute Graph Edge Model.

Normative Authority:
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/phases/PHASE_2A_1_TYPED_COMPUTE_GRAPH_CONTRACT_RECONCILIATION.md
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Edge:
    """Immutable directed connection between a producer output port and consumer input port.

    An edge carries 0 frames of latency and performs zero transformation or buffering.
    """
    source_node_id: str
    source_port_id: str
    target_node_id: str
    target_port_id: str

    @property
    def source_full_id(self) -> str:
        """Fully-qualified source port identifier (source_node_id.source_port_id)."""
        return f"{self.source_node_id}.{self.source_port_id}"

    @property
    def target_full_id(self) -> str:
        """Fully-qualified target port identifier (target_node_id.target_port_id)."""
        return f"{self.target_node_id}.{self.target_port_id}"

    def __repr__(self) -> str:
        return f"Edge({self.source_full_id} -> {self.target_full_id})"
