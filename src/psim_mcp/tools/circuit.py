"""Circuit creation tools: generate PSIM schematics from descriptions."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


# ---------------------------------------------------------------------------
# Pre-defined circuit templates
# ---------------------------------------------------------------------------
# Each template provides a complete component + connection list so the user
# can simply say "Buck 컨버터 만들어줘" without specifying every detail.

_TEMPLATES: dict[str, dict] = {
    "buck": {
        "description": "DC-DC Buck (step-down) converter",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 100, "y": 200}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000, "on_resistance": 0.01}, "position": {"x": 250, "y": 100}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 250, "y": 300}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}, "position": {"x": 400, "y": 200}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 550, "y": 300}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 550, "y": 200}},
        ],
        "connections": [
            {"from": "V1.positive", "to": "SW1.drain"},
            {"from": "SW1.source", "to": "L1.input"},
            {"from": "SW1.source", "to": "D1.cathode"},
            {"from": "D1.anode", "to": "V1.negative"},
            {"from": "L1.output", "to": "R1.input"},
            {"from": "L1.output", "to": "C1.positive"},
            {"from": "R1.output", "to": "V1.negative"},
            {"from": "C1.negative", "to": "V1.negative"},
        ],
    },
    "boost": {
        "description": "DC-DC Boost (step-up) converter",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 12.0}, "position": {"x": 100, "y": 200}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 250, "y": 200}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000, "on_resistance": 0.01}, "position": {"x": 400, "y": 300}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 400, "y": 100}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 47e-6}, "position": {"x": 550, "y": 300}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 50.0}, "position": {"x": 550, "y": 200}},
        ],
        "connections": [
            {"from": "V1.positive", "to": "L1.input"},
            {"from": "L1.output", "to": "SW1.drain"},
            {"from": "L1.output", "to": "D1.anode"},
            {"from": "SW1.source", "to": "V1.negative"},
            {"from": "D1.cathode", "to": "R1.input"},
            {"from": "D1.cathode", "to": "C1.positive"},
            {"from": "R1.output", "to": "V1.negative"},
            {"from": "C1.negative", "to": "V1.negative"},
        ],
    },
    "half_bridge": {
        "description": "Half-bridge inverter",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 100, "y": 200}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 300, "y": 100}},
            {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 300, "y": 300}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 500, "y": 200}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 650, "y": 200}},
        ],
        "connections": [
            {"from": "V1.positive", "to": "SW1.drain"},
            {"from": "SW1.source", "to": "SW2.drain"},
            {"from": "SW2.source", "to": "V1.negative"},
            {"from": "SW1.source", "to": "L1.input"},
            {"from": "L1.output", "to": "R1.input"},
            {"from": "R1.output", "to": "V1.negative"},
        ],
    },
    "full_bridge": {
        "description": "Full-bridge (H-bridge) inverter",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 100, "y": 250}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 300, "y": 100}},
            {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 300, "y": 400}},
            {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 600, "y": 100}},
            {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 600, "y": 400}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 450, "y": 250}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 450, "y": 150}},
        ],
        "connections": [
            {"from": "V1.positive", "to": "SW1.drain"},
            {"from": "V1.positive", "to": "SW3.drain"},
            {"from": "SW1.source", "to": "SW2.drain"},
            {"from": "SW3.source", "to": "SW4.drain"},
            {"from": "SW2.source", "to": "V1.negative"},
            {"from": "SW4.source", "to": "V1.negative"},
            {"from": "SW1.source", "to": "L1.input"},
            {"from": "L1.output", "to": "R1.input"},
            {"from": "R1.output", "to": "SW3.source"},
        ],
    },
}


def register_tools(mcp, service=None):
    """Register circuit creation tools on the given MCP instance."""

    def _get_service():
        from psim_mcp.server import mcp as _mcp
        return _mcp._psim_service

    @mcp.tool(
        description=(
            "PSIM 회로를 자동으로 생성합니다. "
            "템플릿(buck, boost, half_bridge, full_bridge) 또는 커스텀 회로를 지원합니다."
        ),
    )
    @tool_handler("create_circuit")
    async def create_circuit(
        circuit_type: str,
        save_path: str,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> str:
        """Create a new PSIM circuit schematic.

        If circuit_type matches a known template (buck, boost, half_bridge,
        full_bridge), default components and connections are used unless
        explicitly overridden.  For custom circuits, provide components and
        connections directly.
        """
        svc = service or _get_service()

        # Use template if available and no custom components provided
        template = _TEMPLATES.get(circuit_type.lower())
        if template and not components:
            components = template["components"]
            connections = connections or template["connections"]
        elif not components:
            components = []
            connections = connections or []

        if connections is None:
            connections = []

        return await svc.create_circuit(
            circuit_type=circuit_type,
            components=components,
            connections=connections,
            save_path=save_path,
            simulation_settings=simulation_settings,
        )

    @mcp.tool(
        description="사용 가능한 회로 템플릿 목록을 반환합니다.",
    )
    @tool_handler("list_circuit_templates")
    async def list_circuit_templates() -> str:
        """Return a list of available pre-defined circuit templates."""
        templates = []
        for name, tmpl in _TEMPLATES.items():
            templates.append({
                "name": name,
                "description": tmpl["description"],
                "component_count": len(tmpl["components"]),
                "components": [
                    {"id": c["id"], "type": c["type"]}
                    for c in tmpl["components"]
                ],
            })
        return {"success": True, "data": {"templates": templates}, "message": f"{len(templates)}개 템플릿 사용 가능."}
