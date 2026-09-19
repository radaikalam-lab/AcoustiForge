"""AcoustiForge Optional Extensions Package.

Extensions provide higher-level workflows, multi-position spatial optimization,
and system adapters without mutating the frozen deterministic Core.
"""

from __future__ import annotations

from .spatial_optimization import (
    MultiPositionOptimizationResult,
    MultiPositionOptimizationSpecification,
    SpatialMeasurementPosition,
    build_multi_position_objective,
    optimize_multi_position,
)

__all__ = [
    "SpatialMeasurementPosition",
    "MultiPositionOptimizationSpecification",
    "MultiPositionOptimizationResult",
    "build_multi_position_objective",
    "optimize_multi_position",
]
