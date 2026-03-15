"""Circuit creation tools: generate PSIM schematics from descriptions."""

from __future__ import annotations

import copy
import json
import os
import tempfile

from psim_mcp.data.circuit_templates import TEMPLATES as _ALL_TEMPLATES, CATEGORIES as _CATEGORIES
from psim_mcp.data.spec_mapping import SPEC_MAP as _SPEC_MAP, apply_specs as _apply_specs
from psim_mcp.generators import get_generator
from psim_mcp.services.preview_store import get_preview_store
from psim_mcp.tools import tool_handler
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg, open_svg_in_browser
from psim_mcp.validators import validate_circuit


# ---------------------------------------------------------------------------
# Templates — imported from comprehensive data module
# ---------------------------------------------------------------------------
_TEMPLATES = _ALL_TEMPLATES



# ---------------------------------------------------------------------------
# Preview storage — token-based (supports concurrent previews)
# ---------------------------------------------------------------------------


def register_tools(mcp, service=None):
    """Register circuit creation tools on the given MCP instance."""

    def _get_service():
        from psim_mcp.server import mcp as _mcp
        return _mcp._psim_service

    @mcp.tool(
        description=(
            "PSIM 부품 라이브러리를 반환합니다. "
            "회로를 직접 설계할 때 사용 가능한 부품 타입, 핀 이름, 기본 파라미터를 확인할 수 있습니다. "
            "preview_circuit에 커스텀 components/connections를 전달하기 전에 이 도구로 부품 정보를 확인하세요."
        ),
    )
    @tool_handler("get_component_library")
    async def get_component_library(category: str | None = None) -> str:
        """Return available component types with pins and parameters."""
        from psim_mcp.data.component_library import COMPONENTS, CATEGORIES

        result = {}
        for type_name, comp in COMPONENTS.items():
            if category and comp["category"] != category.lower():
                continue
            result[type_name] = {
                "category": comp["category"],
                "pins": comp.get("pins", []),
                "default_parameters": comp.get("default_parameters", {}),
            }

        return {
            "success": True,
            "data": {
                "components": result,
                "total": len(result),
                "categories": list(CATEGORIES.keys()),
            },
            "message": (
                f"{len(result)}개 부품 타입 사용 가능. "
                "preview_circuit의 components에 이 타입명과 핀 이름을 사용하세요."
            ),
        }

    @mcp.tool(
        description=(
            "회로도 SVG 미리보기를 생성합니다. 두 가지 모드:\n\n"
            "모드 1 (템플릿): circuit_type='buck' + specs={'V_in': 48, 'V_out': 12} 형태로 간편 생성.\n\n"
            "모드 2 (커스텀 설계): 임의 회로를 직접 설계. components와 connections를 직접 전달.\n"
            "get_component_library()로 부품 타입과 핀 이름을 먼저 확인하세요.\n"
            "components: [{\"id\": \"V1\", \"type\": \"DC_Source\", \"parameters\": {\"voltage\": 310}, \"position\": {\"x\": 0, \"y\": 0}}, ...]\n"
            "connections: [{\"from\": \"V1.positive\", \"to\": \"SW1.drain\"}, ...]\n\n"
            "검증 결과가 응답에 포함됩니다. 핀 이름 오류 시 올바른 핀 목록이 제안됩니다.\n"
            "확정하려면 confirm_circuit(preview_token=..., save_path=...)을 호출하세요."
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
        store = get_preview_store()
        resolved_nets: list[dict] = []
        circuit_spec: dict | None = None

        # Try generator first
        _generator_resolved = False
        _generation_mode = "template"
        try:
            generator = get_generator(circuit_type.lower())
        except KeyError:
            generator = None

        if generator and not components:
            req = specs or {}
            missing = generator.missing_fields(req)
            if not missing:
                try:
                    gen_result = generator.generate(req)
                    # Build spec dict for downstream
                    circuit_spec = {
                        "topology": circuit_type,
                        "components": gen_result["components"],
                        "nets": gen_result.get("nets", []),
                        "simulation": gen_result.get("simulation", {}),
                    }
                    resolved_components = gen_result["components"]
                    resolved_connections = []  # generator uses nets
                    resolved_nets = gen_result.get("nets", [])
                    _generator_resolved = True
                    _generation_mode = "generator"
                except Exception:
                    pass  # generator failed, fall back to template

        # Resolve template (fallback if generator didn't resolve)
        if not _generator_resolved:
            template = _TEMPLATES.get(circuit_type.lower())

        if not _generator_resolved and template and not components:
            resolved_components = copy.deepcopy(template["components"])
            resolved_connections = connections or copy.deepcopy(template["connections"])

            # Apply specs to template components
            if specs:
                _apply_specs(resolved_components, specs)

        elif not _generator_resolved and components and isinstance(components, list):
            resolved_components = copy.deepcopy(components)
            resolved_connections = connections or []
        elif not _generator_resolved:
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

        # If we have nets but no connections, convert for rendering
        if resolved_nets and not resolved_connections:
            from psim_mcp.bridge.wiring import nets_to_connections
            resolved_connections = nets_to_connections(resolved_nets)

        # Run validation (non-blocking for preview, just include warnings in response)
        validation_input = {
            "components": resolved_components,
            "connections": resolved_connections,
            "nets": resolved_nets,
        }
        validation_result = validate_circuit(validation_input)
        validation_warnings = [
            {"code": w.code, "message": w.message, "component_id": w.component_id, "suggestion": w.suggestion}
            for w in (validation_result.errors + validation_result.warnings)
        ]

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
        open_svg_in_browser(svg_path)

        # Store pending preview for confirm_circuit (token-based)
        token = store.save({
            "circuit_type": circuit_type,
            "components": resolved_components,
            "connections": resolved_connections,
            "nets": resolved_nets,
            "simulation_settings": simulation_settings,
            "svg_path": svg_path,
        })

        return {
            "success": True,
            "data": {
                "ascii_diagram": ascii_diagram,
                "svg_path": svg_path,
                "circuit_type": circuit_type,
                "preview_token": token,
                "component_count": len(resolved_components),
                "connection_count": len(resolved_connections),
                "components": [
                    {"id": c.get("id", "?"), "type": c.get("type", "?"), "parameters": c.get("parameters", {})}
                    for c in resolved_components
                ],
                "validation_warnings": validation_warnings,
                "generation_mode": _generation_mode,
            },
            "message": (
                f"'{circuit_type}' 회로 미리보기 (token: {token}):\n\n"
                f"```\n{ascii_diagram}\n```\n\n"
                f"SVG 파일이 브라우저에서 자동으로 열립니다: {svg_path}\n"
                f"확정하려면 confirm_circuit(preview_token='{token}')을, "
                f"수정하려면 preview_circuit을 다시 호출하세요."
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
        preview_token: str | None = None,
        modifications: dict | None = None,
    ) -> str:
        """Confirm the previewed circuit and generate the actual .psimsch file.

        Args:
            save_path: Path to save the .psimsch file.
            preview_token: Token returned by preview_circuit to identify which preview to confirm.
            modifications: Optional dict to override parameters before creation.
                Example: {"V1": {"voltage": 24.0}, "R1": {"resistance": 50.0}}
        """
        svc = service or _get_service()
        store = get_preview_store()

        # Retrieve preview data by token
        preview = None
        if preview_token:
            preview = store.get(preview_token)

        if preview is None:
            return {
                "success": False,
                "error": {
                    "code": "NO_PREVIEW",
                    "message": "확정할 미리보기가 없습니다.",
                    "suggestion": (
                        "먼저 preview_circuit을 호출하여 회로를 미리보기하고, "
                        "반환된 preview_token을 전달하세요."
                    ),
                },
            }

        components = copy.deepcopy(preview["components"])
        connections = preview.get("connections", [])
        nets = preview.get("nets", [])
        circuit_type = preview["circuit_type"]
        simulation_settings = preview["simulation_settings"]

        # If nets are available, convert them to connections for the adapter
        if nets:
            from psim_mcp.bridge.wiring import nets_to_connections
            connections = nets_to_connections(nets)

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

        # Clear preview after successful creation
        if isinstance(result, dict) and result.get("success"):
            store.delete(preview_token)

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
        circuit_spec: dict | None = None

        # Try generator first
        _generator_resolved = False
        _generation_mode = "template"
        try:
            generator = get_generator(circuit_type.lower())
        except KeyError:
            generator = None

        if generator and not components:
            req = simulation_settings or {}
            missing = generator.missing_fields(req)
            if not missing:
                try:
                    gen_result = generator.generate(req)
                    # Build spec dict for downstream
                    circuit_spec = {
                        "topology": circuit_type,
                        "components": gen_result["components"],
                        "nets": gen_result.get("nets", []),
                        "simulation": gen_result.get("simulation", {}),
                    }
                    components = gen_result["components"]
                    connections = []  # generator uses nets
                    _generator_resolved = True
                    _generation_mode = "generator"
                except Exception:
                    pass  # generator failed, fall back to template

        if not _generator_resolved:
            template = _TEMPLATES.get(circuit_type.lower())
            if template and not components:
                components = template["components"]
                connections = connections or template["connections"]
            elif not components:
                components = []
                connections = connections or []

        if connections is None:
            connections = []

        # If we have nets but no connections, convert for rendering/adapter
        if circuit_spec and circuit_spec.get("nets") and not connections:
            from psim_mcp.bridge.wiring import nets_to_connections
            connections = nets_to_connections(circuit_spec["nets"])

        result = await svc.create_circuit(
            circuit_type=circuit_type,
            components=components,
            connections=connections,
            save_path=save_path,
            simulation_settings=simulation_settings,
            circuit_spec=circuit_spec if circuit_spec else None,
        )

        # Annotate result with generation mode
        if isinstance(result, dict) and "data" in result and isinstance(result["data"], dict):
            result["data"]["generation_mode"] = _generation_mode
        elif isinstance(result, dict):
            result.setdefault("data", {})["generation_mode"] = _generation_mode

        return result

    @mcp.tool(
        description=(
            "사용 가능한 회로 템플릿 목록을 반환합니다. "
            "카테고리(dc_dc, dc_ac, ac_dc, pfc, renewable, motor_drive, battery, filter)로 필터링 가능."
        ),
    )
    @tool_handler("list_circuit_templates")
    async def list_circuit_templates(category: str | None = None) -> str:
        """Return available circuit templates, optionally filtered by category."""
        by_category: dict[str, list] = {}
        for name, tmpl in _TEMPLATES.items():
            cat = tmpl.get("category", "other")
            if category and cat != category.lower():
                continue
            cat_label = _CATEGORIES.get(cat, cat)
            by_category.setdefault(cat_label, []).append({
                "name": name,
                "description": tmpl["description"],
                "component_count": len(tmpl["components"]),
            })

        total = sum(len(v) for v in by_category.values())
        return {
            "success": True,
            "data": {
                "categories": by_category,
                "total_templates": total,
                "available_categories": list(_CATEGORIES.keys()),
            },
            "message": f"{total}개 템플릿 사용 가능 ({len(by_category)}개 카테고리).",
        }
