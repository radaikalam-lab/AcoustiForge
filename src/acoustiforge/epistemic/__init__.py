"""AcoustiForge Epistemic Subsystem.

Provides scientific model criticism, assumption inventories, unknown-state registries,
shadow execution tournaments, and theory transition ledgers with explicit epistemic provenance.

Governing Law: Epistemic Novelty != Production Authority
"""

from .assumptions import (
    AssumptionRegistry,
    EpistemicAssumption,
)
from .challenges import (
    ChallengeRegistry,
    EpistemicChallenge,
)
from .competition import (
    ModelComparison,
    ModelCompetitionRegistry,
    ModelEvidenceProfile,
)
from .falsification import (
    ApplicabilityStatus,
    FalsificationAssessment,
    FalsificationEvidence,
    FalsificationRegistry,
    FalsificationReview,
)
from .models import (
    EpistemicModel,
    ModelRegistry,
)
from .objectives import (
    EpistemicObjective,
    ObjectiveChallengeAssessment,
    ObjectiveComparison,
    ObjectiveRegistry,
)
from .representation import (
    RepresentationChallengeAssessment,
    RepresentationComparison,
    RepresentationDefinition,
    RepresentationGap,
    RepresentationRegistry,
)
from .residuals import (
    ModelResidual,
    ResidualAssessment,
    ResidualRegistry,
)
from .transitions import (
    TheoryTransitionRecord,
    TheoryTransitionRegistry,
)
from .unknowns import (
    EpistemicUnknown,
    UnknownRegistry,
)
from .vocabulary import (
    ChallengeStatus,
    EpistemicClass,
    EpistemicEvidenceLink,
    EpistemicEvidenceType,
    EpistemicStatus,
    EpistemicZone,
    EvidenceRelation,
    ResidualClassificationType,
    ZoneHChallengeType,
)

__all__ = [
    "ApplicabilityStatus",
    "AssumptionRegistry",
    "ChallengeRegistry",
    "ChallengeStatus",
    "EpistemicAssumption",
    "EpistemicChallenge",
    "EpistemicClass",
    "EpistemicEvidenceLink",
    "EpistemicEvidenceType",
    "EpistemicModel",
    "EpistemicObjective",
    "EpistemicStatus",
    "EpistemicUnknown",
    "EpistemicZone",
    "EvidenceRelation",
    "FalsificationAssessment",
    "FalsificationEvidence",
    "FalsificationRegistry",
    "FalsificationReview",
    "ModelComparison",
    "ModelCompetitionRegistry",
    "ModelEvidenceProfile",
    "ModelRegistry",
    "ModelResidual",
    "ObjectiveChallengeAssessment",
    "ObjectiveComparison",
    "ObjectiveRegistry",
    "RepresentationChallengeAssessment",
    "RepresentationComparison",
    "RepresentationDefinition",
    "RepresentationGap",
    "RepresentationRegistry",
    "ResidualAssessment",
    "ResidualClassificationType",
    "ResidualRegistry",
    "TheoryTransitionRecord",
    "TheoryTransitionRegistry",
    "UnknownRegistry",
    "ZoneHChallengeType",
]

