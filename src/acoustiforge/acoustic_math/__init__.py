"""AcoustiForge Acoustic Mathematics Package.

Pure deterministic mathematical operations for acoustic filter synthesis,
driver alignment, sensitivity matching, target curve evaluation, and protection.

Normative Authority:
- Phase 3C/3D Implementation Specification
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
"""

from .alignment import DriverAlignmentResult, calculate_driver_alignment, calculate_system_alignments
from .crossover import CrossoverSynthesisResult, synthesize_crossover_biquads
from .equalizer import EQSynthesisResult, synthesize_parametric_eq
from .protection import (
    ProtectionFilterResult,
    derive_protection_filter_for_driver,
    design_infrasonic_protection_filter,
)
from .sensitivity import GainDesignResult, calculate_sensitivity_gain, calculate_system_sensitivity_gains
from .target_curve import evaluate_target_curve

__all__ = [
    "CrossoverSynthesisResult",
    "DriverAlignmentResult",
    "EQSynthesisResult",
    "GainDesignResult",
    "ProtectionFilterResult",
    "calculate_driver_alignment",
    "calculate_sensitivity_gain",
    "calculate_system_alignments",
    "calculate_system_sensitivity_gains",
    "derive_protection_filter_for_driver",
    "design_infrasonic_protection_filter",
    "evaluate_target_curve",
    "synthesize_crossover_biquads",
    "synthesize_parametric_eq",
]
