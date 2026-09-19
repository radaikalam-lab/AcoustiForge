"""AcoustiForge Infrasonic Driver Protection Filter Mathematics.

Deterministic synthesis of high-pass protective biquad filter sections.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from ..contracts.validation import InvalidParameterError, InvalidSampleRateError
from ..domain.profiles import DriverProfile, EnclosureProfile, EnclosureType
from ..domain.specifications import CrossoverFamily, CrossoverSpecification
from ..nodes.biquad import BiquadCoefficients
from .crossover import synthesize_crossover_biquads


@dataclass(frozen=True, slots=True)
class ProtectionFilterResult:
    """Immutable result container for infrasonic driver excursion protection filter design."""
    cutoff_frequency_hz: float
    order: int
    sample_rate: int
    sections: Tuple[BiquadCoefficients, ...]
    driver_name: Optional[str] = None


def design_infrasonic_protection_filter(
    cutoff_frequency_hz: float,
    sample_rate: int,
    order: int = 2,
    driver_name: Optional[str] = None,
) -> ProtectionFilterResult:
    """Deterministically synthesize a high-pass Butterworth protection filter stage.

    Protects low-frequency acoustic transducers from excessive mechanical displacement (excursion)
    below enclosure unloading frequency.

    Args:
        cutoff_frequency_hz: -3 dB high-pass cutoff frequency in Hz.
        sample_rate: Audio sampling rate in Hz.
        order: Filter order (2 or 4).
        driver_name: Optional identifier for target driver.

    Returns:
        ProtectionFilterResult containing high-pass biquad filter coefficient sections.

    Raises:
        InvalidSampleRateError: If sample_rate is non-positive.
        InvalidParameterError: If cutoff_frequency_hz or order is invalid.
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise InvalidSampleRateError(f"sample_rate must be a positive integer, got {sample_rate!r}.")

    if not isinstance(cutoff_frequency_hz, (int, float)) or isinstance(cutoff_frequency_hz, bool) or not math.isfinite(cutoff_frequency_hz) or cutoff_frequency_hz <= 0.0:
        raise InvalidParameterError(f"cutoff_frequency_hz must be a positive finite float, got {cutoff_frequency_hz!r}.")

    if order not in (2, 4):
        raise InvalidParameterError(f"Protection filter order must be 2 or 4, got {order!r}.")

    spec = CrossoverSpecification(
        family=CrossoverFamily.BUTTERWORTH,
        order=order,
        frequency_hz=float(cutoff_frequency_hz),
    )
    synth_result = synthesize_crossover_biquads(spec, sample_rate)

    return ProtectionFilterResult(
        cutoff_frequency_hz=float(cutoff_frequency_hz),
        order=order,
        sample_rate=sample_rate,
        sections=synth_result.high_pass_sections,
        driver_name=driver_name,
    )


def derive_protection_filter_for_driver(
    driver: DriverProfile,
    enclosure: Optional[EnclosureProfile],
    sample_rate: int,
    order: int = 2,
    explicit_cutoff_hz: Optional[float] = None,
    vented_scale_factor: float = 0.8,
    sealed_scale_factor: float = 0.7,
    min_sealed_cutoff_hz: float = 15.0,
) -> ProtectionFilterResult:
    """Derive an infrasonic protection filter using explicit overrides or deterministic engineering heuristics.

    IMPORTANT POLICY CONSTRAINTS (Normative):
    The default derivation formulas implemented here:
      1. Vented / Bandpass / Passive Radiator: cutoff = vented_scale_factor * enclosure.tuning_frequency_hz (default: 0.8 * Fb)
      2. Sealed / Free Air: cutoff = max(min_sealed_cutoff_hz, sealed_scale_factor * driver.limits.f_s_hz) (default: max(15 Hz, 0.7 * Fs))
    are CONFIGURABLE DEFAULT ENGINEERING HEURISTICS. They are NOT universal acoustic laws,
    fundamental physical derivations, or substitutes for validated nonlinear excursion/thermal modeling.

    Args:
        driver: DriverProfile value object.
        enclosure: Optional EnclosureProfile value object.
        sample_rate: Audio sampling rate in Hz.
        order: Filter order (2 or 4).
        explicit_cutoff_hz: Optional explicit cutoff frequency in Hz (bypasses heuristics).
        vented_scale_factor: Heuristic scaling factor applied to enclosure tuning frequency (default: 0.8).
        sealed_scale_factor: Heuristic scaling factor applied to driver resonance frequency (default: 0.7).
        min_sealed_cutoff_hz: Minimum infrasonic clamp frequency in Hz for sealed alignments (default: 15.0 Hz).

    Returns:
        ProtectionFilterResult containing synthesized high-pass biquad coefficient sections.

    Raises:
        InvalidParameterError: If insufficient physical data is available to derive a cutoff frequency.
    """
    cutoff_hz: Optional[float] = None

    if explicit_cutoff_hz is not None:
        if not isinstance(explicit_cutoff_hz, (int, float)) or isinstance(explicit_cutoff_hz, bool) or not math.isfinite(explicit_cutoff_hz) or explicit_cutoff_hz <= 0.0:
            raise InvalidParameterError(f"explicit_cutoff_hz must be a positive finite float, got {explicit_cutoff_hz!r}.")
        cutoff_hz = float(explicit_cutoff_hz)

    elif enclosure is not None and enclosure.enclosure_type in (
        EnclosureType.VENTED,
        EnclosureType.BANDPASS,
        EnclosureType.PASSIVE_RADIATOR,
    ):
        if enclosure.tuning_frequency_hz is not None:
            cutoff_hz = float(vented_scale_factor) * enclosure.tuning_frequency_hz

    elif driver.limits is not None:
        cutoff_hz = max(float(min_sealed_cutoff_hz), float(sealed_scale_factor) * driver.limits.f_s_hz)

    if cutoff_hz is None:
        raise InvalidParameterError(
            f"Cannot derive protection filter for driver '{driver.name}': "
            "Enclosure tuning frequency and driver resonance limits are both absent."
        )

    return design_infrasonic_protection_filter(
        cutoff_frequency_hz=cutoff_hz,
        sample_rate=sample_rate,
        order=order,
        driver_name=driver.name,
    )
