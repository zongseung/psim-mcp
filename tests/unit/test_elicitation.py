"""Tests for MCP elicitation helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from psim_mcp.intent.elicitation import (
    build_elicitation_request,
    build_schema_for_topology,
    elicit_missing_fields,
)
from psim_mcp.intent.models import ClarificationNeed


def test_build_schema_for_topology_uses_required_fields():
    schema = build_schema_for_topology("buck", ["vin", "vout_target"])

    assert schema["type"] == "object"
    assert set(schema["required"]) == {"vin", "vout_target"}
    assert schema["properties"]["vin"]["type"] == "number"


def test_build_elicitation_request_keeps_fallback_questions():
    request = build_elicitation_request(
        "buck",
        ["vout_target"],
        [
            ClarificationNeed(
                kind="missing_field",
                field="vout_target",
                message="Target output voltage?",
            ),
        ],
    )

    assert request is not None
    assert request.topology == "buck"
    assert request.fallback_questions == ["Target output voltage?"]


async def test_elicit_missing_fields_accepts_content():
    ctx = SimpleNamespace()
    ctx.session = SimpleNamespace()
    ctx.session.elicit = AsyncMock(
        return_value=SimpleNamespace(
            action="accept",
            content={"vin": "48", "vout_target": 12},
        ),
    )

    values = await elicit_missing_fields("buck", ["vin", "vout_target"], ctx)

    assert values == {"vin": 48.0, "vout_target": 12.0}
    ctx.session.elicit.assert_awaited_once()


async def test_service_merges_elicited_fields():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    from psim_mcp.config import AppConfig
    from psim_mcp.services.circuit_design_service import CircuitDesignService

    ctx = SimpleNamespace()
    ctx.session = SimpleNamespace()
    ctx.session.elicit = AsyncMock(
        return_value=SimpleNamespace(
            action="accept",
            content={"vout_target": 12},
        ),
    )
    service = CircuitDesignService(
        adapter=MockPsimAdapter(),
        config=AppConfig(psim_mode="mock"),
    )

    intent, specs, missing, questions, confidence = await service._maybe_elicit_missing_fields(
        intent={
            "specs": {"vin": 48.0},
            "normalized_specs": {"vin": 48.0},
            "missing_fields": ["vout_target"],
            "questions": ["Target output voltage?"],
            "confidence": "low",
        },
        topology="buck",
        specs={"vin": 48.0},
        missing=["vout_target"],
        questions=["Target output voltage?"],
        confidence="low",
        ctx=ctx,
    )

    assert specs == {"vin": 48.0, "vout_target": 12.0}
    assert missing == []
    assert questions == []
    assert confidence == "high"
    assert intent["elicitation"]["used"] is True
