"""Topology candidate ranking -- scores topologies against extracted intent.

Uses domain compatibility, isolation, conversion goal, use case,
power range, and bidirectional support to rank candidates.
"""

from __future__ import annotations

from .models import IntentModel, TopologyCandidate


def rank_topologies(intent: IntentModel) -> list[TopologyCandidate]:
    """Rank all known topologies against the extracted intent.

    Returns sorted list (highest score first) of TopologyCandidate.
    Only includes candidates with score > 0.
    """
    from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA
    from psim_mcp.parsers.keyword_map import TOPOLOGY_KEYWORDS, USE_CASE_MAP

    candidates = []

    # 1. Keyword-based candidates
    keyword_matches = _keyword_match(intent.raw_text)

    # 2. Use-case candidates
    use_case_matches = _use_case_match(intent.raw_text)

    # 3. Constraint-based scoring for ALL topologies
    for name, meta in TOPOLOGY_METADATA.items():
        score = 0.0
        reasons: list[str] = []
        conflicts: list[str] = []

        # Keyword match bonus
        if name in keyword_matches:
            score += 5.0
            reasons.append(f"keyword_match: {keyword_matches[name]}")

        # Domain matching
        if intent.input_domain:
            if meta.get("input_domain") == intent.input_domain:
                score += 3.0
                reasons.append(f"input_domain={intent.input_domain}")
            else:
                score -= 2.0
                conflicts.append(
                    f"input_domain mismatch: want={intent.input_domain}, have={meta.get('input_domain')}"
                )

        if intent.output_domain:
            if meta.get("output_domain") == intent.output_domain:
                score += 3.0
                reasons.append(f"output_domain={intent.output_domain}")
            else:
                score -= 2.0
                conflicts.append("output_domain mismatch")

        # Isolation matching
        if intent.isolation is not None:
            if meta.get("isolated") == intent.isolation:
                score += 3.0
                reasons.append(f"isolation={'isolated' if intent.isolation else 'non-isolated'}")
            else:
                score -= 3.0
                conflicts.append("isolation mismatch")

        # Conversion goal
        goal = intent.conversion_goal
        if goal == "step_down" and meta.get("supports_step_down"):
            score += 3.0
            reasons.append("supports_step_down")
        elif goal == "step_up" and meta.get("supports_step_up"):
            score += 3.0
            reasons.append("supports_step_up")
        elif goal == "rectification" and meta.get("conversion_type") == "ac_dc":
            score += 3.0
            reasons.append("rectification")
        elif goal == "inversion" and meta.get("conversion_type") in ("dc_ac", "drive"):
            score += 3.0
            reasons.append("inversion")
        elif goal:
            score -= 1.0

        # Use case
        if intent.use_case:
            if intent.use_case in meta.get("typical_use_cases", []):
                score += 2.0
                reasons.append(f"use_case={intent.use_case}")
            if name in use_case_matches:
                score += 1.0
                reasons.append("use_case_map_match")

        # Bidirectional
        if intent.bidirectional:
            if meta.get("supports_bidirectional"):
                score += 2.0
                reasons.append("bidirectional")
            else:
                score -= 2.0
                conflicts.append("no_bidirectional")

        # Missing fields analysis
        required = meta.get("required_fields", [])
        missing = [f for f in required if f not in intent.values]

        if score > 0:
            candidates.append(
                TopologyCandidate(
                    topology=name,
                    score=score,
                    reasons=reasons,
                    missing_fields=missing,
                    conflicts=conflicts,
                )
            )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates


def _keyword_match(text: str) -> dict[str, str]:
    """Returns {topology: matched_keyword} for keyword matches in text."""
    from psim_mcp.parsers.keyword_map import TOPOLOGY_KEYWORDS

    matches: dict[str, str] = {}
    text_lower = text.lower()
    for topo, keywords in TOPOLOGY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                if topo not in matches or len(kw) > len(matches[topo]):
                    matches[topo] = kw
    return matches


def _use_case_match(text: str) -> set[str]:
    """Returns set of topology names matched via USE_CASE_MAP."""
    from psim_mcp.parsers.keyword_map import USE_CASE_MAP

    result: set[str] = set()
    text_lower = text.lower()
    for uc_key, topos in USE_CASE_MAP.items():
        if uc_key.lower() in text_lower:
            result.update(topos)
    return result
