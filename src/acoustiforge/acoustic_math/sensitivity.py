"""AcoustiForge Acoustic Driver Sensitivity Matching Mathematics.

Pure deterministic calculations for driver sensitivity matching and gain pad design.

Normative Authority:
- docs/phases/PHASE_3C_3D_ACOUSTIC_MATHEMATICS_AND_GRAPH_BUILDERS_IMPLEMENTATION_AND_VERIFICATION.md
- docs/phases/PHASE_3A_ACOUSTIC_DOMAIN_MODEL_DISCOVERY.md
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..contracts.validation import InvalidParameterError
from ..domain.profiles import DriverProfile


@dataclass(frozen=True, slots=True)
class GainDesignResult:
    """Immutable result container for acoustic sensitivity matching and polarity configuration."""
    driver_name: str
    sensitivity_db: float
    reference_sensitivity_db: float
    gain_db: float
    gain_linear: float
    polarity_inverted: bool


def calculate_sensitivity_gain(
    sensitivity_db: float,
    reference_sensitivity_db: float,
    polarity_inverted: bool = False,
    driver_name: str = "",
) -> GainDesignResult:
    """Calculate the trimming attenuation and linear gain required to match a reference sensitivity.

    Under the headroom preservation convention:
    - reference_sensitivity_db is the target SPL (typically lowest sensitivity among drivers).
    - gain_db = reference_sensitivity_db - sensitivity_db <= 0 dB (attenuation only).
    - gain_linear = 10^(gain_db / 20.0) * (-1.0 if polarity_inverted else +1.0).

    Args:
        sensitivity_db: Measured 1W/1m sensitivity of the driver in dB SPL.
        reference_sensitivity_db: Target reference sensitivity in dB SPL.
        polarity_inverted: Whether acoustic polarity is inverted (reverses sign of gain_linear).
        driver_name: Optional identifier for the driver.

    Returns:
        GainDesignResult with gain_db, gain_linear, and polarity state.

    Raises:
        InvalidParameterError: If sensitivities are non-finite or gain_db would exceed 0 dB (boost).
    """
    for name, val in [("sensitivity_db", sensitivity_db), ("reference_sensitivity_db", reference_sensitivity_db)]:
        if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(val):
            raise InvalidParameterError(f"{name} must be a finite float, got {val!r}.")

    gain_db = float(reference_sensitivity_db) - float(sensitivity_db)
    # Numerical guard for tiny positive floating errors
    if 0.0 < gain_db < 1e-9:
        gain_db = 0.0

    if gain_db > 1e-6:
        raise InvalidParameterError(
            f"Calculated gain is positive ({gain_db:+.3f} dB). "
            f"Sensitivity matching requires attenuation only (reference sensitivity {reference_sensitivity_db} dB SPL <= driver sensitivity {sensitivity_db} dB SPL)."
        )

    gain_linear_magnitude = math.pow(10.0, gain_db / 20.0)
    gain_linear = -gain_linear_magnitude if polarity_inverted else gain_linear_magnitude

    return GainDesignResult(
        driver_name=driver_name,
        sensitivity_db=float(sensitivity_db),
        reference_sensitivity_db=float(reference_sensitivity_db),
        gain_db=gain_db,
        gain_linear=gain_linear,
        polarity_inverted=bool(polarity_inverted),
    )


def calculate_system_sensitivity_gains(
    drivers: Sequence[DriverProfile],
) -> dict[str, GainDesignResult]:
    """Calculate deterministic attenuation gains for a system of drivers to match the least sensitive driver.

    Args:
        drivers: Sequence of DriverProfile objects.

    Returns:
        Dictionary mapping driver name to GainDesignResult.

    Raises:
        InvalidParameterError: If drivers sequence is empty.
    """
    if not drivers:
        raise InvalidParameterError("Cannot calculate sensitivity gains for empty drivers list.")

    reference_sensitivity_db = min(d.sensitivity_db for d in drivers)

    results: dict[str, GainDesignResult] = {}
    for d in drivers:
        results[d.name] = calculate_sensitivity_gain(
            sensitivity_db=d.sensitivity_db,
            reference_sensitivity_db=reference_sensitivity_db,
            polarity_inverted=d.polarity_inverted,
            driver_name=d.name,
        )
    return results
