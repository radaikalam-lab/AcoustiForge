"""AcoustiForge Acoustic Mathematics Package.

Pure deterministic mathematical operations for acoustic filter synthesis,
driver alignment, sensitivity matching, target curve evaluation, protection,
reflection gating, and diagnostics.

Normative Authority:
- Phase 3C/3D Implementation Specification
- docs/contracts/TYPED_COMPUTE_GRAPH_CONTRACT.md
- docs/contracts/REFLECTION_GATING_CONTRACT.md
- docs/contracts/MEASUREMENT_DIAGNOSTICS_CONTRACT.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
"""

from .alignment import DriverAlignmentResult, calculate_driver_alignment, calculate_system_alignments
from .calibration import (
    CalibrationBoundaryPolicy,
    CalibrationOutOfRangeError,
    apply_microphone_calibration,
)
from .crossover import CrossoverSynthesisResult, synthesize_crossover_biquads
from .diagnostics import (
    DiagnosticFlag,
    MeasurementDiagnosticReport,
    evaluate_measurement_quality,
)
from .equalizer import EQSynthesisResult, synthesize_parametric_eq
from .gating import (
    GateSpecification,
    GatedImpulseResult,
    WindowType,
    apply_reflection_gate,
    generate_window,
    transform_impulse_to_frequency_response,
)
from .metrics import (
    AcousticMetricsResult,
    SmoothingMode,
    calculate_response_metrics,
    smooth_frequency_response,
)
from .protection import (
    ProtectionFilterResult,
    derive_protection_filter_for_driver,
    design_infrasonic_protection_filter,
)
from .sensitivity import GainDesignResult, calculate_sensitivity_gain, calculate_system_sensitivity_gains
from .target_curve import evaluate_target_curve

__all__ = [
    "AcousticMetricsResult",
    "CalibrationBoundaryPolicy",
    "CalibrationOutOfRangeError",
    "CrossoverSynthesisResult",
    "DiagnosticFlag",
    "DriverAlignmentResult",
    "EQSynthesisResult",
    "GainDesignResult",
    "GateSpecification",
    "GatedImpulseResult",
    "MeasurementDiagnosticReport",
    "ProtectionFilterResult",
    "SmoothingMode",
    "WindowType",
    "apply_microphone_calibration",
    "apply_reflection_gate",
    "calculate_driver_alignment",
    "calculate_response_metrics",
    "calculate_sensitivity_gain",
    "calculate_system_alignments",
    "calculate_system_sensitivity_gains",
    "derive_protection_filter_for_driver",
    "design_infrasonic_protection_filter",
    "evaluate_measurement_quality",
    "evaluate_target_curve",
    "generate_window",
    "smooth_frequency_response",
    "synthesize_crossover_biquads",
    "synthesize_parametric_eq",
    "transform_impulse_to_frequency_response",
]
