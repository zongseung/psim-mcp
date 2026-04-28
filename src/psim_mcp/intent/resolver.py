"""Intent resolver strategy interface and regex-backed implementation.

Phase 0 of the LLM-native intent layer migration. The :class:`IntentResolver`
abstract base class defines a common contract for natural-language → legacy
intent dict resolution. :class:`RegexResolver` wraps the existing deterministic
regex pipeline (``extract_intent`` → ``rank_topologies`` → ``build_canonical_spec``
→ ``analyze_clarification_needs``) without any behavior change.

Future phases will introduce :class:`SamplingResolver` (LLM-driven) and
``HybridResolver`` (LLM with regex fallback) sharing the same contract.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from .clarification import analyze_clarification_needs
from .extractors import extract_intent
from .ranker import rank_topologies
from .spec_builder import build_canonical_spec

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from mcp.server.fastmcp import Context

logger = logging.getLogger(__name__)


# Keys guaranteed to be present in every resolver result. The contract is
# load-bearing: ``CircuitDesignService.design_circuit`` indexes into the dict
# directly with these keys (see ``intent["topology"]``, ``intent["specs"]`` …)
# so any deviation breaks downstream behavior.
RESOLVER_RESULT_KEYS: tuple[str, ...] = (
    "topology",
    "topology_candidates",
    "specs",
    "normalized_specs",
    "missing_fields",
    "questions",
    "confidence",
    "use_case",
    "constraints",
    "candidate_scores",
    "decision_trace",
    "resolution_version",
)


class IntentResolver(ABC):
    """Strategy interface for natural-language → legacy intent dict resolution.

    Concrete implementations must return a dict with the keys listed in
    :data:`RESOLVER_RESULT_KEYS`. The async signature is required for parity
    with future LLM-based resolvers (Phase 1+); regex resolvers may run
    synchronously inside ``resolve``.
    """

    @abstractmethod
    async def resolve(
        self,
        description: str,
        ctx: Optional["Context"] = None,
    ) -> dict:
        """Resolve natural language → legacy-compatible intent dict.

        Returns dict with keys: topology, topology_candidates, specs,
        normalized_specs, missing_fields, questions, confidence,
        use_case, constraints, candidate_scores, decision_trace,
        resolution_version.
        """


# ---------------------------------------------------------------------------
# Helpers shared with RegexResolver. Kept module-private so we can evolve the
# legacy dict shape in lock-step with the service consumer.
# ---------------------------------------------------------------------------


def _determine_confidence(intent, top, spec) -> str:
    """Mirror of ``CircuitDesignService._determine_confidence_v2``.

    Keeping a private copy here avoids an import cycle with the service layer
    while preserving identical behavior. If the formula evolves, both sites
    must stay in sync.
    """
    missing = getattr(spec, "missing_fields", [])
    score = getattr(top, "score", 0)
    mapping_conf = getattr(intent, "mapping_confidence", "high")

    if not missing and score >= 8:
        confidence = "high"
    elif not missing:
        confidence = "medium"
    else:
        confidence = "low"

    if mapping_conf == "low":
        confidence = "low"
    elif mapping_conf == "medium" and confidence == "high":
        confidence = "medium"

    return confidence


def _empty_result(intent_model) -> dict:
    """Build the no-candidate result branch of the legacy ``_resolve_intent_v2``."""
    return {
        "topology": None,
        "topology_candidates": [],
        "specs": dict(intent_model.values),
        "normalized_specs": dict(intent_model.values),
        "missing_fields": [],
        "questions": [],
        "confidence": "low",
        "use_case": intent_model.use_case,
        "constraints": intent_model.constraints,
        "candidate_scores": [],
        "decision_trace": [],
        "resolution_version": "v2",
    }


class RegexResolver(IntentResolver):
    """Deterministic regex-backed resolver — wraps the existing pipeline.

    Behavior is byte-for-byte identical to the prior inline implementation in
    ``CircuitDesignService._resolve_intent_v2`` (lines 263-310 prior to Phase 0).
    Tests rely on this contract; do not introduce drift.
    """

    async def resolve(
        self,
        description: str,
        ctx: Optional["Context"] = None,
    ) -> dict:
        # ctx is accepted for interface parity but ignored: regex resolution is
        # fully local and never needs an MCP sampling round-trip.
        del ctx

        intent_model = extract_intent(description)
        candidates = rank_topologies(intent_model)
        if not candidates:
            return _empty_result(intent_model)

        top = candidates[0]
        spec = build_canonical_spec(intent_model, top)
        # Computed for confidence calculation only — the legacy contract leaves
        # ``questions`` empty in the resolved dict, so we mirror that exactly.
        _clarifications = analyze_clarification_needs(intent_model, candidates)
        confidence = _determine_confidence(intent_model, top, spec)

        return {
            "topology": top.topology,
            "topology_candidates": [c.topology for c in candidates[:5]],
            "specs": dict(intent_model.values),
            "normalized_specs": dict(spec.requirements),
            "missing_fields": spec.missing_fields,
            "questions": [],
            "confidence": confidence,
            "use_case": intent_model.use_case,
            "constraints": intent_model.constraints,
            "candidate_scores": [
                {"topology": c.topology, "score": c.score, "reasons": c.reasons}
                for c in candidates[:5]
            ],
            "decision_trace": spec.decision_trace,
            "resolution_version": "v2",
        }


def get_resolver(mode: str) -> IntentResolver:
    """Resolver factory keyed on the requested mode.

    - ``"regex"`` → :class:`RegexResolver` (deterministic, default)
    - ``"sampling"`` → :class:`SamplingResolver` (LLM via MCP sampling)
    - Unknown modes fall back to ``RegexResolver`` with a debug log entry.

    ``"hybrid"`` is reserved for Phase 2 and currently maps to regex.
    """
    normalized = (mode or "regex").lower()
    if normalized == "sampling":
        from .sampling_resolver import SamplingResolver

        return SamplingResolver()
    if normalized != "regex":
        logger.debug(
            "Resolver mode %r not yet implemented; falling back to RegexResolver",
            mode,
        )
    return RegexResolver()
