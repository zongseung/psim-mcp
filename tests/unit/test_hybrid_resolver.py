"""Tests for HybridResolver sampling-first behavior."""

from __future__ import annotations

from psim_mcp.intent.hybrid_resolver import HybridResolver
from psim_mcp.intent.resolver import IntentResolver, RegexResolver


class SuccessfulResolver(IntentResolver):
    async def resolve(self, text: str, ctx=None):
        return {
            "topology": "buck",
            "topology_candidates": ["buck"],
            "specs": {"vin": 48.0, "vout_target": 12.0},
            "normalized_specs": {"vin": 48.0, "vout_target": 12.0},
            "missing_fields": [],
            "questions": [],
            "confidence": "high",
            "use_case": None,
            "constraints": {},
            "candidate_scores": [],
            "decision_trace": [],
            "resolution_version": "v2_sampling",
        }


class FailingResolver(IntentResolver):
    async def resolve(self, text: str, ctx=None):
        raise ValueError("bad sampling")


async def test_hybrid_uses_sampling_when_successful():
    resolver = HybridResolver(
        sampling_resolver=SuccessfulResolver(),
        fallback_resolver=RegexResolver(),
    )

    result = await resolver.resolve("48V to 12V buck")

    assert result["topology"] == "buck"
    assert result["resolution_version"] == "v2_hybrid"
    assert result["intent_resolution_fallback"] is False


async def test_hybrid_falls_back_to_regex_on_sampling_failure():
    resolver = HybridResolver(
        sampling_resolver=FailingResolver(),
        fallback_resolver=RegexResolver(),
    )

    result = await resolver.resolve("buck converter 48V input 12V output")

    assert result["topology"] == "buck"
    assert result["resolution_version"] == "v2_hybrid_regex_fallback"
    assert result["intent_resolution_fallback"] is True
    assert result["fallback_reason"] == "ValueError"
