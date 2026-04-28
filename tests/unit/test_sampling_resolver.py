"""Tests for SamplingResolver (LLM-driven intent resolution via MCP sampling).

All LLM round-trips are mocked via AsyncMock -- no real API calls.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from psim_mcp.intent.resolver import IntentResolver
from psim_mcp.intent.sampling_resolver import (
    INTENT_EXTRACTION_SYSTEM_PROMPT,
    SamplingExtractionError,
    SamplingResolver,
    UnknownTopologyError,
)
from psim_mcp.intent.sampling_schema import ExtractedIntent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(json_text: str) -> MagicMock:
    """Build a MagicMock Context whose session.create_message returns json_text."""
    ctx = MagicMock()
    ctx.session.create_message = AsyncMock(
        return_value=MagicMock(content=MagicMock(text=json_text))
    )
    return ctx


_BUCK_PAYLOAD: dict = {
    "input_domain": "dc",
    "output_domain": "dc",
    "isolation": False,
    "conversion_goal": "step_down",
    "use_case": "power_supply",
    "bidirectional": False,
    "values": {
        "vin": 12.0,
        "vout_target": 5.0,
        "iout": 2.0,
        "fsw": 100000.0,
        "power": 10.0,
    },
    "topology_hint": "buck",
    "confidence": "high",
    "rationale": "12V -> 5V step-down without isolation maps cleanly to a buck converter.",
}


# ---------------------------------------------------------------------------
# 1. Inheritance contract
# ---------------------------------------------------------------------------


def test_sampling_resolver_inherits_from_intent_resolver():
    """SamplingResolver must implement the IntentResolver ABC."""
    resolver = SamplingResolver()
    assert isinstance(resolver, IntentResolver)


# ---------------------------------------------------------------------------
# 2. Missing context
# ---------------------------------------------------------------------------


async def test_resolve_without_ctx_raises_runtime_error():
    """Sampling requires a Context; calling without one is a hard programmer error."""
    resolver = SamplingResolver()
    with pytest.raises(RuntimeError, match="Context"):
        await resolver.resolve("12V to 5V step-down", ctx=None)


# ---------------------------------------------------------------------------
# 3. Happy path
# ---------------------------------------------------------------------------


async def test_resolve_happy_path_returns_buck():
    """Valid LLM JSON -> topology=buck and a well-formed legacy dict."""
    ctx = _make_ctx(json.dumps(_BUCK_PAYLOAD))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V step-down", ctx=ctx)

    assert result["topology"] == "buck"
    assert result["confidence"] == "high"
    assert result["use_case"] == "power_supply"
    assert result["specs"]["vin"] == 12.0
    assert result["specs"]["vout_target"] == 5.0
    assert result["resolution_version"] == "v3-sampling"


# ---------------------------------------------------------------------------
# 4. Malformed JSON
# ---------------------------------------------------------------------------


async def test_resolve_malformed_json_raises_extraction_error():
    """Non-JSON LLM output must surface as SamplingExtractionError."""
    ctx = _make_ctx("this is not json {")
    resolver = SamplingResolver()

    with pytest.raises(SamplingExtractionError):
        await resolver.resolve("anything", ctx=ctx)


# ---------------------------------------------------------------------------
# 5. Unknown topology hint
# ---------------------------------------------------------------------------


async def test_resolve_unknown_topology_hint_raises():
    """LLM-emitted topology_hint not in TOPOLOGY_METADATA must be rejected."""
    payload = dict(_BUCK_PAYLOAD)
    payload["topology_hint"] = "warp_drive_converter"
    ctx = _make_ctx(json.dumps(payload))
    resolver = SamplingResolver()

    with pytest.raises(UnknownTopologyError, match="warp_drive_converter"):
        await resolver.resolve("12V to 5V step-down", ctx=ctx)


# ---------------------------------------------------------------------------
# 6. No topology hint -> fall back to ranker top-1
# ---------------------------------------------------------------------------


async def test_resolve_with_null_topology_hint_uses_ranker_top1():
    """When topology_hint is null, the ranker's top-1 candidate is used."""
    payload = dict(_BUCK_PAYLOAD)
    payload["topology_hint"] = None
    ctx = _make_ctx(json.dumps(payload))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V step-down", ctx=ctx)

    # With these constraints the ranker selects buck deterministically.
    assert result["topology"] == "buck"
    assert "buck" in result["topology_candidates"]


# ---------------------------------------------------------------------------
# 7. Topology hint not in top-3 -> fall back to ranker top-1
# ---------------------------------------------------------------------------


async def test_resolve_with_hint_outside_top3_uses_ranker_top1():
    """If LLM hint is a valid topology but the ranker disagrees, ranker wins."""
    # Ask for a clear DC->DC step-down (favors buck) but the LLM hints at
    # induction_motor_vf, which is dc->ac and will not appear in the top-3.
    payload = dict(_BUCK_PAYLOAD)
    payload["topology_hint"] = "induction_motor_vf"
    ctx = _make_ctx(json.dumps(payload))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V step-down", ctx=ctx)

    # The induction_motor_vf hint is rejected because it conflicts with
    # input_domain=dc / output_domain=dc / step_down constraints.
    assert result["topology"] != "induction_motor_vf"
    assert result["topology"] == "buck"


# ---------------------------------------------------------------------------
# 8. Topology hint in top-3 -> trust the LLM
# ---------------------------------------------------------------------------


async def test_resolve_with_hint_in_top3_uses_hint():
    """If the LLM hint is a real topology and ranks in top-3, trust it.

    For dc->dc step-down constraints, the ranker top-3 typically contains
    {buck, buck_boost, cc_cv_charger, ...}. Hinting buck_boost should be
    honored even if buck has the highest score.
    """
    payload = dict(_BUCK_PAYLOAD)
    payload["topology_hint"] = "buck_boost"
    ctx = _make_ctx(json.dumps(payload))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V step-down", ctx=ctx)

    assert result["topology"] == "buck_boost"


# ---------------------------------------------------------------------------
# 9. Legacy dict shape
# ---------------------------------------------------------------------------


async def test_resolve_returns_all_12_legacy_keys():
    """The returned dict must satisfy the 12-key legacy contract."""
    ctx = _make_ctx(json.dumps(_BUCK_PAYLOAD))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V step-down", ctx=ctx)

    expected_keys = {
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
    }
    assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 10. Confidence propagation
# ---------------------------------------------------------------------------


async def test_resolve_propagates_low_confidence():
    """LLM-reported confidence must propagate verbatim into the result."""
    payload = dict(_BUCK_PAYLOAD)
    payload["confidence"] = "low"
    ctx = _make_ctx(json.dumps(payload))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V", ctx=ctx)

    assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# 11. Missing fields populated
# ---------------------------------------------------------------------------


async def test_resolve_populates_missing_fields_when_required_absent():
    """When required values are absent, missing_fields should reflect that."""
    payload = dict(_BUCK_PAYLOAD)
    payload["values"] = {
        "vin": 12.0,
        "vout_target": None,  # required for buck
        "iout": None,
        "fsw": None,
        "power": None,
    }
    ctx = _make_ctx(json.dumps(payload))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V buck", ctx=ctx)

    assert "vout_target" in result["missing_fields"]


# ---------------------------------------------------------------------------
# 12. system_prompt wiring
# ---------------------------------------------------------------------------


async def test_resolve_passes_system_prompt():
    """ctx.session.create_message must be called with the canonical system prompt."""
    ctx = _make_ctx(json.dumps(_BUCK_PAYLOAD))
    resolver = SamplingResolver()

    await resolver.resolve("12V to 5V step-down", ctx=ctx)

    assert ctx.session.create_message.await_count == 1
    kwargs = ctx.session.create_message.await_args.kwargs
    assert kwargs["system_prompt"] == INTENT_EXTRACTION_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# 13. Temperature wiring
# ---------------------------------------------------------------------------


async def test_resolve_passes_low_temperature():
    """Default temperature (0.1) must reach the sampling call for determinism."""
    ctx = _make_ctx(json.dumps(_BUCK_PAYLOAD))
    resolver = SamplingResolver()

    await resolver.resolve("12V to 5V step-down", ctx=ctx)

    kwargs = ctx.session.create_message.await_args.kwargs
    assert kwargs["temperature"] == 0.1


# ---------------------------------------------------------------------------
# 14. Pydantic enum rejection
# ---------------------------------------------------------------------------


def test_extracted_intent_rejects_invalid_input_domain():
    """Pydantic must reject an out-of-enum input_domain value."""
    with pytest.raises(ValidationError):
        ExtractedIntent.model_validate({"input_domain": "nuclear"})


# ---------------------------------------------------------------------------
# 15. resolution_version stamp
# ---------------------------------------------------------------------------


async def test_resolve_stamps_v3_sampling_resolution_version():
    """Result must carry resolution_version='v3-sampling' to distinguish from regex (v2)."""
    ctx = _make_ctx(json.dumps(_BUCK_PAYLOAD))
    resolver = SamplingResolver()

    result = await resolver.resolve("12V to 5V step-down", ctx=ctx)

    assert result["resolution_version"] == "v3-sampling"
