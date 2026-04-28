"""MCP elicitation helpers for missing intent fields."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from psim_mcp.data.topology_metadata import get_required_fields, get_topology_metadata

from .field_schemas import schema_for_field
from .models import ClarificationNeed


class ElicitationUnavailableError(RuntimeError):
    """Raised when the connected MCP client does not expose elicitation."""


class UserCanceledElicitationError(RuntimeError):
    """Raised when the user declines or cancels an elicitation request."""


@dataclass
class ElicitationRequest:
    """A standardized MCP elicitation request derived from clarification needs."""

    topology: str
    missing_fields: list[str]
    requested_schema: dict
    message: str
    fallback_questions: list[str] = field(default_factory=list)


def build_schema_for_topology(topology: str, missing: list[str]) -> dict:
    """Build a JSON Schema object for missing topology fields."""
    meta = get_topology_metadata(topology) or {}
    required_known = set(meta.get("required_fields") or get_required_fields(topology))
    properties = {field: schema_for_field(field) for field in missing}
    required = [field for field in missing if field in required_known]
    if not required:
        required = list(missing)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def build_elicitation_request(
    topology: str,
    missing: list[str],
    clarification_needs: list[ClarificationNeed] | None = None,
) -> ElicitationRequest | None:
    """Create an elicitation request from missing fields and legacy questions."""
    if not missing:
        return None
    questions = [
        need.message
        for need in clarification_needs or []
        if need.kind == "missing_field" and need.message
    ]
    return ElicitationRequest(
        topology=topology,
        missing_fields=list(missing),
        requested_schema=build_schema_for_topology(topology, missing),
        message=f"Additional parameters are required to generate a {topology} circuit.",
        fallback_questions=questions,
    )


async def elicit_missing_fields(
    topology: str,
    missing: list[str],
    ctx: Any | None,
) -> dict[str, float]:
    """Request missing fields using MCP elicitation."""
    session = getattr(ctx, "session", None)
    elicit = getattr(session, "elicit", None)
    if elicit is None:
        raise ElicitationUnavailableError("MCP elicitation is not available on this context")

    request = build_elicitation_request(topology, missing)
    if request is None:
        return {}

    result = await elicit(
        message=request.message,
        requested_schema=request.requested_schema,
    )
    action = getattr(result, "action", None)
    if isinstance(result, dict):
        action = result.get("action", action)
    if action != "accept":
        raise UserCanceledElicitationError(f"User declined elicitation: {action}")

    content = getattr(result, "content", None)
    if isinstance(result, dict):
        content = result.get("content", content)
    return _coerce_numeric_content(content or {})


def _coerce_numeric_content(content: dict[str, Any]) -> dict[str, float]:
    values: dict[str, float] = {}
    if not isinstance(content, dict):
        return values
    for key, value in content.items():
        if isinstance(value, bool) or value is None:
            continue
        try:
            values[key] = float(value)
        except (TypeError, ValueError):
            continue
    return values
