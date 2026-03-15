"""Design tool: natural language circuit design interface."""

from __future__ import annotations

import copy
import json
import os
import platform
import subprocess
import tempfile

from psim_mcp.data.circuit_templates import TEMPLATES
from psim_mcp.generators import get_generator
from psim_mcp.parsers import parse_circuit_intent
from psim_mcp.services.preview_store import get_preview_store
from psim_mcp.tools import tool_handler
from psim_mcp.tools.circuit import _TEMPLATES, _apply_specs, _SPEC_MAP
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg


def register_tools(mcp, service=None):
    """Register the design_circuit tool on *mcp*."""

    @mcp.tool(
        description=(
            "자연어로 회로를 설계합니다. "
            "예: 'Buck 컨버터 48V 입력 12V 출력 5A 부하', "
            "'태양광 MPPT 회로', 'BLDC 모터 드라이브 48V'"
        ),
    )
    @tool_handler("design_circuit")
    async def design_circuit(description: str) -> str:
        """Parse natural language and suggest/create a circuit.

        Args:
            description: Natural language circuit description in Korean or English.
        """
        intent = parse_circuit_intent(description)

        topology = intent["topology"]
        specs = intent["specs"]
        candidates = intent["topology_candidates"]
        missing = intent["missing_fields"]
        questions = intent["questions"]
        confidence = intent["confidence"]
        use_case = intent["use_case"]

        # Case 1: High/medium confidence — auto-generate preview
        if topology and confidence in ("high", "medium"):
            # Try generator first
            generator = None
            try:
                generator = get_generator(topology)
            except (KeyError, Exception):
                pass

            resolved_components = None
            resolved_connections = []
            resolved_nets = []

            if generator and not generator.missing_fields(specs):
                try:
                    gen_result = generator.generate(specs)
                    resolved_components = gen_result["components"]
                    resolved_nets = gen_result.get("nets", [])
                except Exception:
                    pass

            # Fallback to template
            if resolved_components is None:
                template = _TEMPLATES.get(topology)
                if template:
                    resolved_components = copy.deepcopy(template["components"])
                    resolved_connections = copy.deepcopy(template["connections"])
                    if specs:
                        _apply_specs(resolved_components, specs)

            if resolved_components:
                # Render ASCII
                ascii_diagram = render_circuit_ascii(
                    topology, resolved_components, resolved_connections
                )

                # Render SVG
                svg_content = render_circuit_svg(
                    topology, resolved_components, resolved_connections
                )
                svg_dir = tempfile.gettempdir()
                svg_path = os.path.join(svg_dir, f"psim_preview_{topology}.svg")
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(svg_content)

                # Auto-open SVG
                try:
                    system = platform.system()
                    if system == "Darwin":
                        subprocess.Popen(
                            ["open", svg_path],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    elif system == "Windows":
                        os.startfile(svg_path)
                except Exception:
                    pass

                # Save to preview store
                store = get_preview_store()
                token = store.save({
                    "circuit_type": topology,
                    "components": resolved_components,
                    "connections": resolved_connections,
                    "nets": resolved_nets,
                    "simulation_settings": None,
                    "svg_path": svg_path,
                })

                return {
                    "success": True,
                    "data": {
                        "ascii_diagram": ascii_diagram,
                        "svg_path": svg_path,
                        "circuit_type": topology,
                        "preview_token": token,
                        "component_count": len(resolved_components),
                        "specs_applied": specs,
                        "intent": intent,
                    },
                    "message": (
                        f"'{topology}' 회로가 자동 설계되었습니다 (token: {token}):\n\n"
                        f"```\n{ascii_diagram}\n```\n\n"
                        f"SVG: {svg_path}\n"
                        f"확정: confirm_circuit(preview_token='{token}', save_path='...')\n"
                        f"수정: preview_circuit 또는 design_circuit을 다시 호출하세요."
                    ),
                }

        # Case 2: Topology found but missing specs
        if topology and missing:
            return {
                "success": True,
                "data": {
                    "action": "need_specs",
                    "topology": topology,
                    "specs": specs,
                    "missing_fields": missing,
                    "questions": questions,
                    "confidence": confidence,
                },
                "message": (
                    f"'{topology}' 토폴로지가 선택되었습니다.\n"
                    f"현재 스펙: {json.dumps(specs, ensure_ascii=False)}\n"
                    f"다음 정보가 필요합니다:\n"
                    + "\n".join(f"  - {q}" for q in questions)
                ),
            }

        # Case 3: No topology match but use-case found
        if use_case and candidates:
            candidate_info = []
            for c in candidates:
                tmpl = TEMPLATES.get(c)
                desc = tmpl["description"] if tmpl else c
                candidate_info.append(f"  - {c}: {desc}")

            return {
                "success": True,
                "data": {
                    "action": "suggest_candidates",
                    "use_case": use_case,
                    "candidates": candidates,
                    "specs": specs,
                },
                "message": (
                    f"'{use_case}' 용도에 적합한 토폴로지:\n"
                    + "\n".join(candidate_info)
                    + "\n\n원하는 토폴로지를 선택해주세요."
                ),
            }

        # Case 4: Nothing matched
        available = sorted(TEMPLATES.keys())
        return {
            "success": False,
            "error": {
                "code": "NO_MATCH",
                "message": (
                    "입력에서 회로 토폴로지를 식별할 수 없습니다.\n"
                    "예시: 'Buck 컨버터 48V→12V 5A', '태양광 MPPT 회로'\n"
                    f"사용 가능한 템플릿 ({len(available)}개): "
                    + ", ".join(available[:10])
                    + ("..." if len(available) > 10 else "")
                ),
                "suggestion": "list_circuit_templates로 전체 목록을 확인하세요.",
            },
        }
