"""AcoustiForge AI Design-Intent Provider Interface & Deterministic Mocks.

Defines the protocol for external natural language/AI systems proposing design intents,
and provides a deterministic, zero-dependency mock provider for offline execution and testing.

Normative Authority:
- docs/architecture/PHASE_5_0_ADAPTIVE_ACOUSTIC_ARCHITECTURE_DISCOVERY.md
- docs/architecture/PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from ..domain.specifications import CrossoverFamily
from .contracts import (
    ConstraintIntent,
    CrossoverIntent,
    DesignIntent,
    SpatialIntent,
    TargetCurveIntent,
    TonalBalanceIntent,
    UnsupportedIntentError,
)


@runtime_checkable
class IDesignIntentProvider(Protocol):
    """Protocol defining the external AI / NLP intent proposal boundary."""

    def propose_intent(
        self,
        query: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> DesignIntent:
        """Translate a natural-language query and optional context into a structured DesignIntent.

        Args:
            query: User natural language request.
            context: Optional contextual parameters (e.g., driver specs, measurement metadata).

        Returns:
            Structured DesignIntent proposal.
        """
        ...


class MockDesignIntentProvider:
    """Deterministic, rule-based mock provider for offline testing and verification.

    Parses controlled semantic keywords without external API dependencies or nondeterminism.
    """

    def __init__(self, default_intent_id_prefix: str = "intent-mock") -> None:
        self._prefix: str = default_intent_id_prefix
        self._counter: int = 0

    def propose_intent(
        self,
        query: str,
        context: Optional[Mapping[str, Any]] = None,
    ) -> DesignIntent:
        """Parse natural language keywords into a structured DesignIntent proposal."""
        if not isinstance(query, str) or not query.strip():
            raise UnsupportedIntentError("Query string must be non-empty.")

        self._counter += 1
        intent_id = f"{self._prefix}-{self._counter:04d}"
        q_lower = query.strip().lower()

        target_curve = TargetCurveIntent()
        tonal = TonalBalanceIntent()
        crossover = CrossoverIntent()
        spatial = SpatialIntent()
        constraints = ConstraintIntent()

        # 1. Target Curve & Tonal Intents
        if "warm" in q_lower or "warmth" in q_lower:
            tonal = TonalBalanceIntent(warmth_db=1.5, low_shelf_db=1.0, tilt_db_per_octave=-0.5)
        elif "bright" in q_lower or "clarity" in q_lower:
            tonal = TonalBalanceIntent(brightness_db=1.5, high_shelf_db=1.0, tilt_db_per_octave=0.5)
        elif "low shelf" in q_lower:
            match = re.search(r"low\s+shelf\s*([+-]?\d+(?:\.\d+)?)", q_lower)
            shelf_val = float(match.group(1)) if match else 2.0
            tonal = TonalBalanceIntent(low_shelf_db=shelf_val)

        # 2. Crossover Intents
        if "crossover" in q_lower or "cross" in q_lower:
            freq_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hz|khz)", q_lower)
            if freq_match:
                raw_f = float(freq_match.group(1))
                if "khz" in freq_match.group(0):
                    raw_f *= 1000.0
                crossover = CrossoverIntent(
                    family=CrossoverFamily.LINKWITZ_RILEY,
                    order=4,
                    target_frequency_hz=raw_f,
                    search_band_hz=(max(20.0, raw_f * 0.7), raw_f * 1.4),
                )
            else:
                crossover = CrossoverIntent(
                    family=CrossoverFamily.LINKWITZ_RILEY,
                    order=4,
                    target_frequency_hz=2000.0,
                    search_band_hz=(1400.0, 2800.0),
                )

        if "butterworth" in q_lower:
            crossover = CrossoverIntent(
                family=CrossoverFamily.BUTTERWORTH,
                order=2,
                target_frequency_hz=crossover.target_frequency_hz or 2000.0,
                search_band_hz=crossover.search_band_hz or (1400.0, 2800.0),
            )

        # 3. Spatial Intents (Track C)
        if "primary listening position" in q_lower or "sweet spot" in q_lower:
            spatial = SpatialIntent(profile_name="primary_seat_weighted")
        elif "wide" in q_lower or "couch" in q_lower or "even coverage" in q_lower:
            spatial = SpatialIntent(profile_name="wide_couch_even")

        # 4. Fallback for completely unrecognized queries (fail closed or provide clean flat intent)
        if "flat" in q_lower or "neutral" in q_lower or "reference" in q_lower:
            target_curve = TargetCurveIntent(preset_name="flat")

        return DesignIntent(
            intent_id=intent_id,
            query_text=query,
            target_curve=target_curve,
            tonal_balance=tonal,
            crossover=crossover,
            spatial=spatial,
            constraints=constraints,
            metadata={"mock_provider": "deterministic_keyword_matcher", "counter": self._counter},
        )
