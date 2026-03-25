"""Generator resolution helpers for circuit design.

Extracted from ``circuit_design_service.py`` to reduce module size.
Re-exported from ``circuit_design_service`` so existing imports are unaffected.
"""

from __future__ import annotations

import logging

from psim_mcp.generators import get_generator
from psim_mcp.generators.constraints import validate_design_constraints

logger = logging.getLogger(__name__)


def try_generate(
    circuit_type: str,
    specs: dict | None,
    components: list[dict] | None,
) -> tuple[
    list[dict] | None,
    list[dict],
    list[dict],
    str,
    str | None,
    dict | None,
    dict | None,
    dict | None,
]:
    """Attempt to resolve components via generator.

    Returns an 8-tuple:
    (
        components,
        connections,
        nets,
        generation_mode,
        note,
        constraint_validation,
        psim_template,
        simulation_settings,
    ).
    """
    if components:
        return None, [], [], "template", None, None, None, None

    try:
        generator = get_generator(circuit_type.lower())
    except (KeyError, Exception):
        return None, [], [], "template_fallback", None, None, None, None

    req = specs or {}
    if generator.missing_fields(req):
        return None, [], [], "template_fallback", None, None, None, None

    try:
        gen_result = generator.generate(req)

        constraint_check = validate_design_constraints(circuit_type, req, gen_result)
        constraint_validation = {
            "is_feasible": constraint_check.is_feasible,
            "issues": [
                {
                    "severity": i.severity,
                    "code": i.code,
                    "message": i.message,
                    "parameter": i.parameter,
                    "suggestion": i.suggestion,
                }
                for i in constraint_check.issues
            ],
        }

        return (
            gen_result["components"],
            [],
            gen_result.get("nets", []),
            "generator",
            None,
            constraint_validation,
            gen_result.get("psim_template"),
            gen_result.get("simulation"),
        )
    except Exception as exc:
        logger.warning("Generator failed for '%s': %s", circuit_type, exc)
        return (
            None,
            [],
            [],
            "template_fallback",
            "Generator not available for this topology. Using template with default values.",
            None,
            None,
            None,
        )
