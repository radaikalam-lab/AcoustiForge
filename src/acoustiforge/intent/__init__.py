"""AcoustiForge AI Design-Intent Package.

Provides high-level intent value objects, provider protocols, validation firewalls,
and adapters compiling user/AI intent proposals into authoritative Core specifications.

Normative Authority:
- docs/architecture/PHASE_5_0_ADAPTIVE_ACOUSTIC_ARCHITECTURE_DISCOVERY.md
- docs/architecture/PHASE_5_5_AI_DESIGN_INTENT_INTEGRATION.md
"""

from __future__ import annotations

from .adapter import DesignIntentAdapter
from .contracts import (
    ConstraintIntent,
    CrossoverIntent,
    DesignIntent,
    IntentTranslationRecord,
    IntentValidationError,
    SpatialIntent,
    TargetCurveIntent,
    TonalBalanceIntent,
    UnsupportedIntentError,
)
from .provider import (
    IDesignIntentProvider,
    MockDesignIntentProvider,
)

__all__ = [
    "ConstraintIntent",
    "CrossoverIntent",
    "DesignIntent",
    "DesignIntentAdapter",
    "IDesignIntentProvider",
    "IntentTranslationRecord",
    "IntentValidationError",
    "MockDesignIntentProvider",
    "SpatialIntent",
    "TargetCurveIntent",
    "TonalBalanceIntent",
    "UnsupportedIntentError",
]
