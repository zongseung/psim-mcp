"""Template-level validation tests."""

from __future__ import annotations

from psim_mcp.data.circuit_templates import TEMPLATES
from psim_mcp.validators import validate_circuit


def test_all_templates_have_valid_connection_endpoints():
    failures: list[str] = []

    for name, template in TEMPLATES.items():
        result = validate_circuit({
            "components": template["components"],
            "connections": template["connections"],
            "nets": [],
        })
        errors = [issue for issue in result.errors if issue.code.startswith("CONN_")]
        if errors:
            failures.append(
                f"{name}: " + "; ".join(f"{issue.code} {issue.message}" for issue in errors)
            )

    assert not failures, "\n".join(failures)


def test_forward_template_matches_current_generator_contract():
    template = TEMPLATES["forward"]
    component_ids = {component["id"] for component in template["components"]}
    connections = template["connections"]

    assert {"D_clamp", "R_clamp", "C_clamp", "Cout", "Vout"}.issubset(component_ids)
    assert "R1" not in component_ids
    assert "C1" not in component_ids
    assert {"from": "D_clamp.cathode", "to": "R_clamp.input"} in connections
    assert {"from": "L1.output", "to": "Vout.input"} in connections
