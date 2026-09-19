"""AcoustiForge Driver Acoustic Time Alignment Mathematics.

Pure deterministic calculations for driver time-of-flight alignment and delay compensation.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..domain.profiles import DriverProfile

# Explicit reference speed of sound in dry air at 20°C (101.325 kPa)
DEFAULT_SPEED_OF_SOUND_MPS: float = 343.2


@dataclass(frozen=True, slots=True)
class DriverAlignmentResult:
    """Immutable result container for acoustic driver time-of-flight alignment."""
    driver_name: str
    physical_delay_seconds: float
    requested_delay_frames: float
    applied_delay_frames: int
    depth_offset_mm: float
    reference_depth_mm: float
    sample_rate: int
    speed_of_sound_mps: float


def calculate_driver_alignment(
    driver_depth_mm: float,
    reference_depth_mm: float,
    sample_rate: int,
    speed_of_sound_mps: float = DEFAULT_SPEED_OF_SOUND_MPS,
    driver_name: str = "",
) -> DriverAlignmentResult:
    """Calculate relative time-of-flight acoustic delay for a single driver against a reference depth.

    Under the non-negative delay policy, acoustic drivers positioned forward of the reference plane
    (smaller depth offset) require positive delay to align their acoustic centers with the furthest back driver.

    Args:
        driver_depth_mm: Acoustic center depth offset of the driver in millimeters.
        reference_depth_mm: Acoustic center depth offset of the reference driver in millimeters.
        sample_rate: Audio sampling rate in Hz (must be positive integer).
        speed_of_sound_mps: Speed of sound in meters per second (default: 343.2 m/s).
        driver_name: Optional identifier for the driver.

    Returns:
        DriverAlignmentResult with exact physical delay in seconds, exact requested frames,
        and applied integer delay frames rounded to nearest sample.

    Raises:
        InvalidSampleRateError: If sample_rate is non-positive or invalid.
        InvalidParameterError: If speed_of_sound_mps is non-positive, or if depth offsets produce negative delay.
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    if not isinstance(speed_of_sound_mps, (int, float)) or isinstance(speed_of_sound_mps, bool) or speed_of_sound_mps <= 0.0 or not math.isfinite(speed_of_sound_mps):
        raise InvalidParameterError(f"speed_of_sound_mps must be a positive finite float, got {speed_of_sound_mps!r}.")

    for name, val in [("driver_depth_mm", driver_depth_mm), ("reference_depth_mm", reference_depth_mm)]:
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
            raise InvalidParameterError(f"{name} must be a finite float, got {val!r}.")

    delta_depth_mm = float(reference_depth_mm) - float(driver_depth_mm)
    if delta_depth_mm < -1e-9:
        raise InvalidParameterError(
            f"Driver depth ({driver_depth_mm} mm) is greater than reference depth ({reference_depth_mm} mm). "
            f"Under the non-negative delay policy, reference depth must be >= driver depth."
        )

    # Clean small floating-point residuals near zero
    if abs(delta_depth_mm) < 1e-9:
        delta_depth_mm = 0.0

    delta_depth_meters = delta_depth_mm * 1e-3
    physical_delay_seconds = delta_depth_meters / float(speed_of_sound_mps)
    requested_delay_frames = physical_delay_seconds * float(sample_rate)
    applied_delay_frames = int(round(requested_delay_frames))

    return DriverAlignmentResult(
        driver_name=driver_name,
        physical_delay_seconds=physical_delay_seconds,
        requested_delay_frames=requested_delay_frames,
        applied_delay_frames=applied_delay_frames,
        depth_offset_mm=float(driver_depth_mm),
        reference_depth_mm=float(reference_depth_mm),
        sample_rate=sample_rate,
        speed_of_sound_mps=float(speed_of_sound_mps),
    )


def calculate_system_alignments(
    drivers: Sequence[DriverProfile],
    sample_rate: int,
    speed_of_sound_mps: float = DEFAULT_SPEED_OF_SOUND_MPS,
) -> dict[str, DriverAlignmentResult]:
    """Calculate non-negative relative acoustic alignments for a collection of driver profiles.

    Establishes the acoustically furthest back driver (maximum depth_offset_mm) as the common reference,
    ensuring all applied delays are strictly non-negative.

    Args:
        drivers: Sequence of DriverProfile objects.
        sample_rate: Audio sampling rate in Hz.
        speed_of_sound_mps: Speed of sound in meters per second (default: 343.2 m/s).

    Returns:
        Dictionary mapping driver name to DriverAlignmentResult.

    Raises:
        InvalidParameterError: If drivers sequence is empty.
    """
    if not drivers:
        raise InvalidParameterError("Cannot calculate alignments for empty drivers list.")

    reference_depth_mm = max(d.depth_offset_mm for d in drivers)

    results: dict[str, DriverAlignmentResult] = {}
    for d in drivers:
        results[d.name] = calculate_driver_alignment(
            driver_depth_mm=d.depth_offset_mm,
            reference_depth_mm=reference_depth_mm,
            sample_rate=sample_rate,
            speed_of_sound_mps=speed_of_sound_mps,
            driver_name=d.name,
        )
    return results
