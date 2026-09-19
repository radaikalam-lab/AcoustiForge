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
from .optimization import (
    calculate_acoustic_complex_summation,
    calculate_branch_complex_response,
    complex_response_to_frequency_response_data,
    coordinate_descent_search,
    driver_response_to_complex,
    evaluate_acoustic_target_loss,
    evaluate_biquad_complex_response,
    generate_crossover_candidate_grid,
    generate_delay_candidate_grid,
    golden_section_line_search,
    is_candidate_better,
    validate_frequency_grid_matching,
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
    "calculate_acoustic_complex_summation",
    "calculate_branch_complex_response",
    "calculate_driver_alignment",
    "calculate_response_metrics",
    "calculate_sensitivity_gain",
    "calculate_system_alignments",
    "calculate_system_sensitivity_gains",
    "complex_response_to_frequency_response_data",
    "coordinate_descent_search",
    "derive_protection_filter_for_driver",
    "design_infrasonic_protection_filter",
    "driver_response_to_complex",
    "evaluate_acoustic_target_loss",
    "evaluate_biquad_complex_response",
    "evaluate_measurement_quality",
    "evaluate_target_curve",
    "generate_crossover_candidate_grid",
    "generate_delay_candidate_grid",
    "generate_window",
    "golden_section_line_search",
    "is_candidate_better",
    "smooth_frequency_response",
    "synthesize_crossover_biquads",
    "synthesize_parametric_eq",
    "transform_impulse_to_frequency_response",
    "validate_frequency_grid_matching",
]
