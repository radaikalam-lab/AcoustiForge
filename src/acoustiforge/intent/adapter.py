"""AcoustiForge AI Design-Intent Adapter & Validation Firewall.

Implements the strict, deterministic translation boundary from untrusted DesignIntent
proposals into canonical Core OptimizationSpecifications.

Normative Authority:
- docs/architecture/PHASE_5_0_ADAPTIVE_ACOUSTIC_ARCHITECTURE_DISCOVERY.md
- docs/architecture/PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md
- docs/contracts/MULTIWAY_OPTIMIZATION_CONTRACT.md
"""

from __future__ import annotations

import math
from typing import Optional, Sequence, Union

from ..contracts.validation import (
    InvalidParameterError,
)
from ..domain.validation import InvalidSpecificationError
from ..domain.specifications import (
    AcousticTargetCurve,
    CrossoverFamily,
    OptimizationSpecification,
)
from ..extensions.spatial_optimization import (
    MultiPositionOptimizationSpecification,
    SpatialMeasurementPosition,
)
from .contracts import (
    DesignIntent,
    IntentTranslationRecord,
    IntentValidationError,
    UnsupportedIntentError,
)


class DesignIntentAdapter:
    """Deterministic validation firewall and compiler for DesignIntent proposals."""

    DEFAULT_FREQ_RANGE: tuple[float, float] = (20.0, 20000.0)
    DEFAULT_CROSSOVER_BOUNDS: tuple[float, float] = (1000.0, 4000.0)
    DEFAULT_GAIN_BOUNDS: tuple[float, float] = (-12.0, 12.0)
    DEFAULT_DELAY_BOUNDS: tuple[float, float] = (0.0, 0.005)

    @classmethod
    def compile(
        cls,
        intent: DesignIntent,
        spatial_positions: Optional[Sequence[SpatialMeasurementPosition]] = None,
    ) -> tuple[Union[OptimizationSpecification, MultiPositionOptimizationSpecification], IntentTranslationRecord]:
        """Validate an untrusted DesignIntent and compile it into an authoritative Core specification.

        Args:
            intent: High-level DesignIntent proposal object.
            spatial_positions: Optional spatial measurement positions when spatial intent is active.

        Returns:
            Tuple of (Compiled Core Specification, IntentTranslationRecord audit log).

        Raises:
            IntentValidationError: If intent fails schema, semantic, or acoustic constraint validation.
            UnsupportedIntentError: If intent requests unsupported presets or algorithms.
        """
        if not isinstance(intent, DesignIntent):
            raise IntentValidationError(f"Expected DesignIntent instance, got {type(intent)!r}.")

        accepted_items: list[str] = []
        rejected_items: list[str] = []
        rejection_reasons: list[str] = []

        # ----------------------------------------------------------------------
        # Stage 1: Frequency Range & Constraints Resolution
        # ----------------------------------------------------------------------
        f_range = intent.constraints.frequency_range_hz or cls.DEFAULT_FREQ_RANGE
        f_min, f_max = float(f_range[0]), float(f_range[1])
        if f_min <= 0.0 or f_max <= f_min or not math.isfinite(f_min) or not math.isfinite(f_max):
            raise IntentValidationError(f"Invalid frequency range: ({f_min}, {f_max}). Must be 0 < f_min < f_max.")
        accepted_items.append(f"frequency_range_hz: ({f_min:.1f}, {f_max:.1f})")

        # Gain & Delay bounds
        gain_bounds = intent.constraints.gain_bounds_db or cls.DEFAULT_GAIN_BOUNDS
        delay_bounds = intent.constraints.delay_bounds_seconds or cls.DEFAULT_DELAY_BOUNDS
        ripple_weight = float(intent.constraints.ripple_weight or 0.0)
        delay_weight = float(intent.constraints.delay_weight or 0.0)
        max_iterations = int(intent.constraints.max_iterations or 50)
        convergence_tol = float(intent.constraints.convergence_tolerance_db or 1e-5)

        # ----------------------------------------------------------------------
        # Stage 2: Target Curve Synthesis & Tonal Modifiers
        # ----------------------------------------------------------------------
        target_curve = cls._synthesize_target_curve(
            intent=intent,
            f_min=f_min,
            f_max=f_max,
            accepted_items=accepted_items,
            rejected_items=rejected_items,
            rejection_reasons=rejection_reasons,
        )

        # ----------------------------------------------------------------------
        # Stage 3: Crossover Specification Resolution
        # ----------------------------------------------------------------------
        family = intent.crossover.family or CrossoverFamily.LINKWITZ_RILEY
        order = intent.crossover.order or 4

        if order not in (2, 4, 8):
            raise IntentValidationError(f"Unsupported crossover order: {order}. Must be 2, 4, or 8.")
        if family == CrossoverFamily.LINKWITZ_RILEY and order % 2 != 0:
            raise IntentValidationError("Linkwitz-Riley crossover order must be even.")

        if intent.crossover.search_band_hz is not None:
            c_bounds = intent.crossover.search_band_hz
        elif intent.crossover.target_frequency_hz is not None:
            fc = intent.crossover.target_frequency_hz
            c_bounds = (max(f_min, fc * 0.7), min(f_max, fc * 1.4))
        else:
            c_bounds = cls.DEFAULT_CROSSOVER_BOUNDS

        # Verify crossover search bounds lie within global frequency range
        fc_min, fc_max = float(c_bounds[0]), float(c_bounds[1])
        if fc_min < f_min or fc_max > f_max or fc_max <= fc_min:
            raise IntentValidationError(
                f"Crossover bounds ({fc_min}, {fc_max}) must lie strictly within frequency range ({f_min}, {f_max})."
            )
        accepted_items.append(f"crossover: {family.value} order={order} bounds=({fc_min:.1f}, {fc_max:.1f})")

        # ----------------------------------------------------------------------
        # Stage 4: Spatial (Track C) vs Single-Position Compilation
        # ----------------------------------------------------------------------
        spec: Union[OptimizationSpecification, MultiPositionOptimizationSpecification]
        is_spatial = (
            intent.spatial.profile_name not in ("single_position", "")
            or intent.spatial.positions is not None
            or spatial_positions is not None
        )

        if is_spatial:
            positions_to_use = intent.spatial.positions or (tuple(spatial_positions) if spatial_positions else None)
            if not positions_to_use:
                # If spatial intent was requested but no positions provided, fallback to standard spec
                rejected_items.append("spatial_intent")
                rejection_reasons.append("Spatial intent requested without measurement positions; compiled as single-position.")
                spec = OptimizationSpecification(
                    target_curve=target_curve,
                    crossover_family=family,
                    crossover_order=order,
                    frequency_range_hz=(f_min, f_max),
                    crossover_bounds_hz=(fc_min, fc_max),
                    gain_bounds_db=gain_bounds,
                    delay_bounds_seconds=delay_bounds,
                    ripple_weight=ripple_weight,
                    delay_weight=delay_weight,
                    max_iterations=max_iterations,
                    convergence_tolerance_db=convergence_tol,
                )
            else:
                # Calculate normalized weights based on profile intent
                weights = cls._resolve_spatial_weights(intent.spatial.profile_name, positions_to_use, intent.spatial.weights)
                spec = MultiPositionOptimizationSpecification(
                    target_curve=target_curve,
                    crossover_family=family,
                    crossover_order=order,
                    frequency_range_hz=(f_min, f_max),
                    crossover_bounds_hz=(fc_min, fc_max),
                    gain_bounds_db=gain_bounds,
                    delay_bounds_seconds=delay_bounds,
                    ripple_weight=ripple_weight,
                    delay_weight=delay_weight,
                    max_iterations=max_iterations,
                    convergence_tolerance_db=convergence_tol,
                    positions=positions_to_use,
                    spatial_weights=weights,
                )
                accepted_items.append(f"spatial_profile: {intent.spatial.profile_name} (positions={len(positions_to_use)})")
        else:
            spec = OptimizationSpecification(
                target_curve=target_curve,
                crossover_family=family,
                crossover_order=order,
                frequency_range_hz=(f_min, f_max),
                crossover_bounds_hz=(fc_min, fc_max),
                gain_bounds_db=gain_bounds,
                delay_bounds_seconds=delay_bounds,
                ripple_weight=ripple_weight,
                delay_weight=delay_weight,
                max_iterations=max_iterations,
                convergence_tolerance_db=convergence_tol,
            )

        status = "MODIFIED" if rejected_items else "ACCEPTED"
        record = IntentTranslationRecord(
            intent_id=intent.intent_id,
            query_text=intent.query_text,
            validation_status=status,
            accepted_items=tuple(accepted_items),
            rejected_items=tuple(rejected_items),
            rejection_reasons=tuple(rejection_reasons),
            specification=spec,
        )
        return spec, record

    @classmethod
    def _synthesize_target_curve(
        cls,
        intent: DesignIntent,
        f_min: float,
        f_max: float,
        accepted_items: list[str],
        rejected_items: list[str],
        rejection_reasons: list[str],
    ) -> AcousticTargetCurve:
        """Synthesize a canonical AcousticTargetCurve applying tonal modifiers deterministically."""
        preset = intent.target_curve.preset_name
        base_spl = intent.target_curve.target_spl_db

        if intent.target_curve.points is not None:
            base_points = intent.target_curve.points
            accepted_items.append(f"custom_target_points ({len(base_points)} points)")
        elif preset in ("flat", None):
            # Generate flat response anchor points across f_min to f_max
            base_points = ((f_min, base_spl), (f_max, base_spl))
            accepted_items.append(f"flat_target_spl: {base_spl:.1f} dB")
        else:
            # Unsupported preset requested
            raise UnsupportedIntentError(
                f"Unsupported target curve preset: {preset!r}. Core supports 'flat' or custom anchor points."
            )

        # Apply Tonal Balance modifiers deterministically
        tonal = intent.tonal_balance
        has_tonal = any([
            tonal.warmth_db != 0.0,
            tonal.brightness_db != 0.0,
            tonal.low_shelf_db != 0.0,
            tonal.high_shelf_db != 0.0,
            tonal.tilt_db_per_octave != 0.0,
        ])

        if not has_tonal:
            return AcousticTargetCurve(name=f"Target_{intent.intent_id}", points=base_points)

        # Create high-density frequency grid to accurately represent tonal modifications
        num_anchors = max(16, len(base_points) * 2)
        grid_freqs = [f_min * ((f_max / f_min) ** (i / (num_anchors - 1))) for i in range(num_anchors)]

        # Linear interpolation of base points
        base_curve = AcousticTargetCurve("BaseTarget", base_points)
        modified_points: list[tuple[float, float]] = []

        ref_f = 1000.0  # Reference 1 kHz anchor for tilt
        for f in grid_freqs:
            # Base magnitude from target curve
            mag = base_curve.points[0][1] if len(base_curve.points) == 1 else base_spl
            for idx in range(len(base_curve.points) - 1):
                f1, m1 = base_curve.points[idx]
                f2, m2 = base_curve.points[idx + 1]
                if f1 <= f <= f2:
                    t = (math.log10(f) - math.log10(f1)) / (math.log10(f2) - math.log10(f1) + 1e-12)
                    mag = m1 + t * (m2 - m1)
                    break

            # 1. Low shelf (< 200 Hz)
            if tonal.low_shelf_db != 0.0 and f < 200.0:
                mag += tonal.low_shelf_db * (1.0 - (f / 200.0))

            # 2. Warmth (< 500 Hz)
            if tonal.warmth_db != 0.0 and f < 500.0:
                mag += tonal.warmth_db * (1.0 - (f / 500.0))

            # 3. High shelf (> 4000 Hz)
            if tonal.high_shelf_db != 0.0 and f > 4000.0:
                mag += tonal.high_shelf_db * min(1.0, (f - 4000.0) / 6000.0)

            # 4. Brightness (> 3000 Hz)
            if tonal.brightness_db != 0.0 and f > 3000.0:
                mag += tonal.brightness_db * min(1.0, (f - 3000.0) / 7000.0)

            # 5. Spectral tilt (dB / octave relative to 1 kHz)
            if tonal.tilt_db_per_octave != 0.0:
                octaves_from_ref = math.log2(f / ref_f)
                mag += tonal.tilt_db_per_octave * octaves_from_ref

            modified_points.append((f, round(mag, 4)))

        accepted_items.append(f"tonal_modifiers (warmth={tonal.warmth_db}, tilt={tonal.tilt_db_per_octave})")
        return AcousticTargetCurve(name=f"TonalTarget_{intent.intent_id}", points=tuple(modified_points))

    @classmethod
    def _resolve_spatial_weights(
        cls,
        profile_name: str,
        positions: Sequence[SpatialMeasurementPosition],
        custom_weights: Optional[Sequence[float]],
    ) -> tuple[float, ...]:
        """Resolve and normalize spatial position weights based on spatial profile intent."""
        n = len(positions)
        if custom_weights is not None and len(custom_weights) == n:
            raw_weights = [float(w) for w in custom_weights]
        elif profile_name == "primary_seat_weighted":
            # Primary position receives 70% weight; remaining positions share 30%
            if n == 1:
                raw_weights = [1.0]
            else:
                primary_weight = 0.70
                secondary_weight = 0.30 / (n - 1)
                primary_idx = 0
                for idx, pos in enumerate(positions):
                    if "center" in pos.name.lower() or "primary" in pos.name.lower():
                        primary_idx = idx
                        break
                raw_weights = [primary_weight if idx == primary_idx else secondary_weight for idx in range(n)]
        elif profile_name in ("wide_couch_even", "party_even"):
            # Uniform weighting across all positions
            raw_weights = [1.0 / n] * n
        else:
            raw_weights = [1.0 / n] * n

        # Strictly normalize weights to sum to exactly 1.0
        total = sum(raw_weights)
        if total <= 0.0:
            raise IntentValidationError("Spatial weights sum to 0 or negative value.")
        normalized = tuple(w / total for w in raw_weights)
        return normalized
