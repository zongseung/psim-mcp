"""Intent Resolution -- structured intent extraction and topology resolution.

Replaces the monolithic parse_circuit_intent() with a pipeline:
  extract_intent() -> rank_topologies() -> analyze_clarification_needs() -> build_canonical_spec()
"""

from .clarification import analyze_clarification_needs
from .extractors import extract_intent
from .models import (
    CanonicalIntentSpec,
    ClarificationNeed,
    DesignResolutionResult,
    IntentModel,
    TopologyCandidate,
)
from .ranker import rank_topologies
from .spec_builder import build_canonical_spec

__all__ = [
    "CanonicalIntentSpec",
    "ClarificationNeed",
    "DesignResolutionResult",
    "IntentModel",
    "TopologyCandidate",
    "analyze_clarification_needs",
    "build_canonical_spec",
    "extract_intent",
    "rank_topologies",
]
