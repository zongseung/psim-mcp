"""Circuit creation tools: generate PSIM schematics from descriptions."""

from __future__ import annotations

import copy
import json
import os
import platform
import subprocess
import tempfile

from psim_mcp.tools import tool_handler
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg


# ---------------------------------------------------------------------------
# Pre-defined circuit templates
# ---------------------------------------------------------------------------

_TEMPLATES: dict[str, dict] = {
    "buck": {
        "description": "DC-DC Buck (step-down) converter",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 120}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000, "on_resistance": 0.01}, "position": {"x": 180, "y": 50}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 190}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}, "position": {"x": 340, "y": 50}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 500, "y": 190}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 500, "y": 50}},
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
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 12.0}, "position": {"x": 40, "y": 120}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 180, "y": 50}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000, "on_resistance": 0.01}, "position": {"x": 340, "y": 190}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 340, "y": 50}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 47e-6}, "position": {"x": 500, "y": 190}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 50.0}, "position": {"x": 500, "y": 50}},
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
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 120}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 220, "y": 50}},
            {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 220, "y": 190}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 400, "y": 120}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 560, "y": 120}},
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
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 150}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 220, "y": 50}},
            {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 220, "y": 250}},
            {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 540, "y": 50}},
            {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 20000, "on_resistance": 0.05}, "position": {"x": 540, "y": 250}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 380, "y": 100}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 380, "y": 200}},
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

# ---------------------------------------------------------------------------
# Specs → template parameter mapping
# ---------------------------------------------------------------------------

# Maps spec keys to (component_type, parameter_name) so that high-level
# specifications like {"V_in": 48} get applied to the right component.
_SPEC_MAP: dict[str, list[tuple[str, str]]] = {
    "V_in": [("DC_Source", "voltage")],
    "v_in": [("DC_Source", "voltage")],
    "voltage": [("DC_Source", "voltage")],
    "R_load": [("Resistor", "resistance")],
    "r_load": [("Resistor", "resistance")],
    "resistance": [("Resistor", "resistance")],
    "load": [("Resistor", "resistance")],
    "switching_frequency": [("MOSFET", "switching_frequency")],
    "frequency": [("MOSFET", "switching_frequency")],
    "freq": [("MOSFET", "switching_frequency")],
    "inductance": [("Inductor", "inductance")],
    "L": [("Inductor", "inductance")],
    "capacitance": [("Capacitor", "capacitance")],
    "C": [("Capacitor", "capacitance")],
    "forward_voltage": [("Diode", "forward_voltage")],
    "on_resistance": [("MOSFET", "on_resistance")],
}


def _apply_specs(components: list[dict], specs: dict) -> None:
    """Apply high-level specs to template components in-place.

    Handles both mapped keys (V_in → DC_Source.voltage) and derived
    values (V_out + I_load → R_load).
    """
    # Derive R_load from V_out and I_load if not explicitly given
    v_out = specs.get("V_out") or specs.get("v_out")
    i_load = specs.get("I_load") or specs.get("i_load")
    if v_out and i_load and "R_load" not in specs and "r_load" not in specs:
        specs["R_load"] = v_out / i_load

    for key, value in specs.items():
        targets = _SPEC_MAP.get(key)
        if not targets:
            continue
        for comp_type, param_name in targets:
            for comp in components:
                if comp.get("type") == comp_type:
                    comp.setdefault("parameters", {})[param_name] = value
                    break  # apply to first matching component only


# ---------------------------------------------------------------------------
# Pending preview storage (in-memory, per server session)
# ---------------------------------------------------------------------------
_pending_preview: dict | None = None


def register_tools(mcp, service=None):
    """Register circuit creation tools on the given MCP instance."""

    def _get_service():
        from psim_mcp.server import mcp as _mcp
        return _mcp._psim_service

    @mcp.tool(
        description=(
            "회로도를 SVG 미리보기로 생성합니다. "
            "Mac/Windows 모두 가능. 확인 후 confirm_circuit으로 실제 생성합니다. "
            "specs로 사양(입력전압, 출력전압, 부하 등)을 지정하면 템플릿에 자동 반영됩니다."
        ),
    )
    @tool_handler("preview_circuit")
    async def preview_circuit(
        circuit_type: str,
        specs: dict | None = None,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> str:
        """Generate an SVG preview of the circuit diagram.

        Args:
            circuit_type: Template name (buck, boost, half_bridge, full_bridge) or "custom".
            specs: High-level specifications to apply to the template. Example:
                {"V_in": 48, "V_out": 12, "I_load": 5, "R_load": 2.4,
                 "switching_frequency": 100000, "inductance": 22e-6}
            components: Explicit component list (overrides template).
            connections: Explicit connection list (overrides template).
            simulation_settings: Optional simulation parameters.
        """
        global _pending_preview

        # Resolve template
        template = _TEMPLATES.get(circuit_type.lower())
        if template and not components:
            resolved_components = copy.deepcopy(template["components"])
            resolved_connections = connections or copy.deepcopy(template["connections"])

            # Apply specs to template components
            if specs:
                _apply_specs(resolved_components, specs)

        elif components and isinstance(components, list):
            resolved_components = copy.deepcopy(components)
            resolved_connections = connections or []
        else:
            # Fallback: if components was passed as a dict (specs), treat it as specs
            if components and isinstance(components, dict):
                specs = components
                template = _TEMPLATES.get(circuit_type.lower())
                if template:
                    resolved_components = copy.deepcopy(template["components"])
                    resolved_connections = connections or copy.deepcopy(template["connections"])
                    _apply_specs(resolved_components, specs)
                else:
                    return {
                        "success": False,
                        "error": {
                            "code": "NO_TEMPLATE",
                            "message": f"'{circuit_type}' 템플릿을 찾을 수 없습니다.",
                            "suggestion": "list_circuit_templates로 사용 가능한 템플릿을 확인하세요.",
                        },
                    }
            else:
                return {
                    "success": False,
                    "error": {
                        "code": "NO_COMPONENTS",
                        "message": "components를 지정하거나 유효한 circuit_type 템플릿을 사용하세요.",
                        "suggestion": "list_circuit_templates로 사용 가능한 템플릿을 확인하세요.",
                    },
                }

        if resolved_connections is None:
            resolved_connections = []

        # Render ASCII diagram for inline chat display
        ascii_diagram = render_circuit_ascii(
            circuit_type=circuit_type,
            components=resolved_components,
            connections=resolved_connections,
        )

        # Render SVG
        svg_content = render_circuit_svg(
            circuit_type=circuit_type,
            components=resolved_components,
            connections=resolved_connections,
        )

        # Save SVG to temp file
        svg_dir = tempfile.gettempdir()
        svg_path = os.path.join(svg_dir, f"psim_preview_{circuit_type}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        # Auto-open SVG in browser
        try:
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", svg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif system == "Windows":
                os.startfile(svg_path)
            elif system == "Linux":
                subprocess.Popen(["xdg-open", svg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass  # Non-critical: user can still open manually

        # Store pending preview for confirm_circuit
        _pending_preview = {
            "circuit_type": circuit_type,
            "components": resolved_components,
            "connections": resolved_connections,
            "simulation_settings": simulation_settings,
            "svg_path": svg_path,
        }

        return {
            "success": True,
            "data": {
                "ascii_diagram": ascii_diagram,
                "svg_path": svg_path,
                "circuit_type": circuit_type,
                "component_count": len(resolved_components),
                "connection_count": len(resolved_connections),
                "components": [
                    {"id": c.get("id", "?"), "type": c.get("type", "?"), "parameters": c.get("parameters", {})}
                    for c in resolved_components
                ],
            },
            "message": (
                f"'{circuit_type}' 회로 미리보기:\n\n"
                f"```\n{ascii_diagram}\n```\n\n"
                f"SVG 파일이 브라우저에서 자동으로 열립니다: {svg_path}\n"
                f"확정하려면 confirm_circuit을, 수정하려면 preview_circuit을 다시 호출하세요."
            ),
        }

    @mcp.tool(
        description=(
            "미리보기로 확인한 회로를 확정하여 실제 .psimsch 파일을 생성합니다. "
            "preview_circuit 호출 후 사용합니다."
        ),
    )
    @tool_handler("confirm_circuit")
    async def confirm_circuit(
        save_path: str,
        modifications: dict | None = None,
    ) -> str:
        """Confirm the previewed circuit and generate the actual .psimsch file.

        Args:
            save_path: Path to save the .psimsch file.
            modifications: Optional dict to override parameters before creation.
                Example: {"V1": {"voltage": 24.0}, "R1": {"resistance": 50.0}}
        """
        global _pending_preview
        svc = service or _get_service()

        if _pending_preview is None:
            return {
                "success": False,
                "error": {
                    "code": "NO_PREVIEW",
                    "message": "확정할 미리보기가 없습니다.",
                    "suggestion": "먼저 preview_circuit을 호출하여 회로를 미리보기하세요.",
                },
            }

        components = copy.deepcopy(_pending_preview["components"])
        connections = _pending_preview["connections"]
        circuit_type = _pending_preview["circuit_type"]
        simulation_settings = _pending_preview["simulation_settings"]

        # Apply modifications if provided
        if modifications:
            for comp in components:
                if comp["id"] in modifications:
                    comp["parameters"].update(modifications[comp["id"]])

        result = await svc.create_circuit(
            circuit_type=circuit_type,
            components=components,
            connections=connections,
            save_path=save_path,
            simulation_settings=simulation_settings,
        )

        # Clear pending preview after successful creation
        if isinstance(result, dict) and result.get("success"):
            _pending_preview = None

        return result

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
        """Create a new PSIM circuit schematic directly (without preview)."""
        svc = service or _get_service()

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
