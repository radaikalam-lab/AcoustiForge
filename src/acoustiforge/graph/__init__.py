"""AcoustiForge Typed Compute Graph Package.

Normative Authority:
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/phases/PHASE_2A_1_TYPED_COMPUTE_GRAPH_CONTRACT_RECONCILIATION.md
"""

from .compute_graph import ComputeGraph, GraphLifecycle
from .edge import Edge
from .ports import Port, PortDirection, PortShape, PortType

__all__ = [
    "ComputeGraph",
    "GraphLifecycle",
    "Port",
    "PortDirection",
    "PortType",
    "PortShape",
    "Edge",
]
