"""Design tool: natural language circuit design interface."""

from __future__ import annotations

import json

from psim_mcp.data.circuit_templates import TEMPLATES
from psim_mcp.parsers import parse_circuit_intent
from psim_mcp.tools import tool_handler


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

        # Case 1: High confidence — topology found, all specs present
        if topology and confidence == "high":
            # Try to generate a preview automatically
            try:
                from psim_mcp.generators import get_generator

                gen = get_generator(topology)
                gen_result = gen.generate(specs)
                return {
                    "success": True,
                    "data": {
                        "action": "auto_preview",
                        "topology": topology,
                        "specs": specs,
                        "design": gen_result.get("metadata", {}).get("design", {}),
                        "component_count": len(gen_result.get("components", [])),
                        "description": gen_result.get("metadata", {}).get("description", ""),
                    },
                    "message": (
                        f"'{topology}' 회로가 자동 설계되었습니다.\n"
                        f"스펙: {json.dumps(specs, ensure_ascii=False)}\n"
                        f"preview_circuit(circuit_type='{topology}', specs={json.dumps(specs, ensure_ascii=False)})로 "
                        f"미리보기를 확인하세요."
                    ),
                }
            except (KeyError, ValueError):
                # No generator available; fall back to template suggestion
                pass

            # Fall back to template
            if topology in TEMPLATES:
                return {
                    "success": True,
                    "data": {
                        "action": "suggest_template",
                        "topology": topology,
                        "specs": specs,
                        "template_available": True,
                    },
                    "message": (
                        f"'{topology}' 템플릿을 사용할 수 있습니다.\n"
                        f"preview_circuit(circuit_type='{topology}', specs={json.dumps(specs, ensure_ascii=False)})로 "
                        f"미리보기를 확인하세요."
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
