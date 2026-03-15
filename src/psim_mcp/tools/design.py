"""Design tool: natural language circuit design interface."""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

from psim_mcp.data.circuit_templates import TEMPLATES as _TEMPLATES
from psim_mcp.data.spec_mapping import SPEC_MAP as _SPEC_MAP, apply_specs as _apply_specs
from psim_mcp.generators import get_generator
from psim_mcp.parsers import parse_circuit_intent
from psim_mcp.services.preview_store import get_preview_store
from psim_mcp.tools import tool_handler
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg, open_svg_in_browser
from psim_mcp.validators import validate_circuit


def register_tools(mcp, service=None):
    """Register design_circuit and continue_design tools on *mcp*."""

    @mcp.tool(
        description=(
            "자연어 입력을 분석하여 회로 토폴로지와 사양을 추출합니다. "
            "확신도가 높으면 자동 미리보기를 생성하고, 낮으면 해석 결과를 반환합니다.\n\n"
            "지원 자동 계산: buck, boost, buck_boost (설계 공식 기반).\n"
            "다른 토폴로지: 템플릿 기반 fallback.\n"
            "커스텀/복잡한 회로: get_component_library() + preview_circuit()을 직접 사용하세요.\n\n"
            "참고: 이 도구는 자연어 파싱 기반이므로 복잡한 요청은 "
            "preview_circuit()에 components/connections를 직접 전달하는 것이 더 정확합니다."
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
        specs = intent.get("normalized_specs", intent["specs"])
        candidates = intent["topology_candidates"]
        missing = intent["missing_fields"]
        questions = intent["questions"]
        confidence = intent["confidence"]
        use_case = intent["use_case"]

        # Case 1b: Medium confidence — show intent, ask for confirmation
        if topology and confidence == "medium":
            store = get_preview_store()
            session_token = store.save({
                "type": "design_session",
                "topology": topology,
                "specs": specs,
                "missing_fields": missing,
            })
            return {
                "success": True,
                "data": {
                    "action": "confirm_intent",
                    "topology": topology,
                    "topology_candidates": candidates,
                    "specs": specs,
                    "missing_fields": missing,
                    "confidence": confidence,
                    "generation_mode": "pending_confirmation",
                    "design_session_token": session_token,
                },
                "message": (
                    f"'{topology}' 토폴로지로 해석했습니다.\n"
                    f"스펙: {json.dumps(specs, ensure_ascii=False)}\n"
                    + (f"누락 정보: {', '.join(missing)}\n" if missing else "")
                    + f"\n이 해석이 맞다면 다음 명령으로 미리보기를 생성하세요:\n"
                    f"  preview_circuit(circuit_type='{topology}', specs={json.dumps(specs, ensure_ascii=False)})\n"
                    + (f"\n다른 후보: {', '.join(candidates[:5])}" if len(candidates) > 1 else "")
                    + f"\n\n또는 continue_design(design_session_token='{session_token}', ...)으로 추가 정보를 전달하세요."
                    + "\n\n직접 설계하려면 get_component_library()로 부품을 확인 후 "
                    "preview_circuit()에 components/connections를 전달하세요."
                ),
            }

        # Case 1: High confidence — auto-generate preview
        if topology and confidence == "high":
            # Try generator first
            generator = None
            try:
                generator = get_generator(topology)
            except (KeyError, Exception):
                pass

            resolved_components = None
            resolved_connections = []
            resolved_nets = []
            generation_mode = "template_fallback"
            generation_note = None

            if generator and not generator.missing_fields(specs):
                try:
                    gen_result = generator.generate(specs)
                    resolved_components = gen_result["components"]
                    resolved_nets = gen_result.get("nets", [])
                    generation_mode = "generator"
                except Exception as exc:
                    logger.warning(
                        "Generator failed for topology '%s': %s. "
                        "Falling back to template.",
                        topology,
                        exc,
                    )
                    generation_note = (
                        "Generator not available for this topology. "
                        "Using template with default values."
                    )

            # Fallback to template
            if resolved_components is None:
                template = _TEMPLATES.get(topology)
                if template:
                    resolved_components = copy.deepcopy(template["components"])
                    resolved_connections = copy.deepcopy(template["connections"])
                    if specs:
                        _apply_specs(resolved_components, specs)
                    if generation_note is None and generator is not None:
                        generation_note = (
                            "Generator not available for this topology. "
                            "Using template with default values."
                        )

            # If template fallback, check design_ready_fields
            if generation_mode == "template_fallback":
                from psim_mcp.data.topology_metadata import get_design_ready_fields
                design_fields = get_design_ready_fields(topology)
                if design_fields:
                    design_missing = [f for f in design_fields if f not in specs]
                    if design_missing:
                        # Not enough info for meaningful design — ask instead
                        from psim_mcp.data.topology_metadata import get_slot_questions
                        topo_questions = get_slot_questions(topology)
                        questions = [topo_questions.get(f, f"{f}을(를) 지정해주세요.") for f in design_missing]
                        store = get_preview_store()
                        session_token = store.save({
                            "type": "design_session",
                            "topology": topology,
                            "specs": specs,
                            "missing_fields": design_missing,
                        })
                        return {
                            "success": True,
                            "data": {
                                "action": "need_specs",
                                "topology": topology,
                                "specs": specs,
                                "missing_fields": design_missing,
                                "questions": questions,
                                "confidence": "medium",
                                "generation_mode": "awaiting_design_specs",
                                "generation_note": "템플릿은 있지만 의미 있는 설계를 위해 추가 정보가 필요합니다.",
                                "design_session_token": session_token,
                            },
                            "message": (
                                f"'{topology}' 토폴로지가 선택되었습니다.\n"
                                f"현재 스펙: {json.dumps(specs, ensure_ascii=False)}\n"
                                f"더 정확한 설계를 위해 다음 정보가 필요합니다:\n"
                                + "\n".join(f"  - {q}" for q in questions)
                                + f"\n\ncontinue_design(design_session_token='{session_token}', ...)으로 추가 정보를 전달하세요."
                                + "\n\n정보 없이 기본값으로 진행하려면 "
                                f"preview_circuit(circuit_type='{topology}')을 호출하세요."
                            ),
                        }

            if resolved_components:
                # If we have nets but no connections, convert for rendering
                if resolved_nets and not resolved_connections:
                    from psim_mcp.bridge.wiring import nets_to_connections
                    resolved_connections = nets_to_connections(resolved_nets)

                validation_input = {
                    "components": resolved_components,
                    "connections": resolved_connections,
                    "nets": resolved_nets,
                }
                validation_result = validate_circuit(validation_input)
                validation_issues = [
                    {
                        "code": issue.code,
                        "message": issue.message,
                        "component_id": issue.component_id,
                        "suggestion": issue.suggestion,
                    }
                    for issue in (validation_result.errors + validation_result.warnings)
                ]

                if validation_result.errors:
                    return {
                        "success": False,
                        "error": {
                            "code": "CIRCUIT_VALIDATION_FAILED",
                            "message": "자동 설계 결과가 유효한 회로 검증을 통과하지 못했습니다.",
                            "suggestion": "입력 조건을 더 구체화하거나 preview_circuit에 components/connections를 직접 전달해 수정하세요.",
                        },
                        "data": {
                            "topology": topology,
                            "specs_applied": specs,
                            "intent": intent,
                            "generation_mode": generation_mode,
                            "validation_issues": validation_issues,
                        },
                    }

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
                open_svg_in_browser(svg_path)

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

                response_data = {
                        "ascii_diagram": ascii_diagram,
                        "svg_path": svg_path,
                        "circuit_type": topology,
                        "preview_token": token,
                        "component_count": len(resolved_components),
                        "specs_applied": specs,
                        "intent": intent,
                        "generation_mode": generation_mode,
                        "confidence": confidence,
                        "validation_issues": validation_issues,
                    }
                if generation_note:
                    response_data["generation_note"] = generation_note

                return {
                    "success": True,
                    "data": response_data,
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
            store = get_preview_store()
            session_token = store.save({
                "type": "design_session",
                "topology": topology,
                "specs": specs,
                "missing_fields": missing,
            })
            return {
                "success": True,
                "data": {
                    "action": "need_specs",
                    "topology": topology,
                    "specs": specs,
                    "missing_fields": missing,
                    "questions": questions,
                    "confidence": confidence,
                    "generation_mode": "awaiting_specs",
                    "design_session_token": session_token,
                },
                "message": (
                    f"'{topology}' 토폴로지가 선택되었습니다.\n"
                    f"현재 스펙: {json.dumps(specs, ensure_ascii=False)}\n"
                    f"다음 정보가 필요합니다:\n"
                    + "\n".join(f"  - {q}" for q in questions)
                    + f"\n\ncontinue_design(design_session_token='{session_token}', ...)으로 답변하세요."
                ),
            }

        # Case 3: No topology match but use-case found
        if use_case and candidates:
            candidate_info = []
            for c in candidates:
                tmpl = _TEMPLATES.get(c)
                desc = tmpl["description"] if tmpl else c
                candidate_info.append(f"  - {c}: {desc}")

            return {
                "success": True,
                "data": {
                    "action": "suggest_candidates",
                    "use_case": use_case,
                    "candidates": candidates,
                    "specs": specs,
                    "confidence": confidence,
                    "generation_mode": "awaiting_selection",
                },
                "message": (
                    f"'{use_case}' 용도에 적합한 토폴로지:\n"
                    + "\n".join(candidate_info)
                    + "\n\n원하는 토폴로지를 선택해주세요.\n"
                    "직접 설계하려면 get_component_library()로 부품을 확인 후 "
                    "preview_circuit()에 components/connections를 전달하세요."
                ),
            }

        # Case 4: Nothing matched -- provide helpful guidance
        available = sorted(_TEMPLATES.keys())

        # Try to extract any useful context
        has_voltage = bool(specs.get("vin") or specs.get("vout_target"))
        suggestions = []
        if has_voltage:
            suggestions.append("전압 정보가 감지되었습니다. 토폴로지를 지정해주세요.")
            suggestions.append("예: 'buck 컨버터', 'flyback', 'LLC 공진 컨버터'")
        else:
            suggestions.append("회로 종류와 전압/전류 조건을 함께 알려주세요.")
            suggestions.append("예: 'Buck 컨버터 48V 입력 12V 출력 5A'")
            suggestions.append("예: '태양광 MPPT 회로 Voc 40V Isc 10A'")
            suggestions.append("예: 'flyback 310V 입력 5V 출력 2A'")

        suggestions.append("")
        suggestions.append("또는 get_component_library()로 부품을 확인한 후")
        suggestions.append("preview_circuit()에 components/connections를 직접 전달하세요.")

        return {
            "success": False,
            "error": {
                "code": "NO_MATCH",
                "message": "입력에서 회로 토폴로지를 식별할 수 없습니다.",
                "suggestion": "\n".join(suggestions),
            },
            "data": {
                "specs_extracted": specs,
                "confidence": "low",
                "generation_mode": "no_match",
                "available_categories": [
                    "DC-DC: buck, boost, flyback, llc, dab",
                    "인버터: half_bridge, full_bridge, three_phase_inverter",
                    "정류: diode_bridge_rectifier",
                    "PFC: boost_pfc, totem_pole_pfc",
                    "모터: bldc_drive, pmsm_foc_drive",
                    "충전: cc_cv_charger, ev_obc",
                    "태양광: pv_mppt_boost, pv_grid_tied",
                ],
            },
        }

    @mcp.tool(
        description=(
            "이전 design_circuit 세션을 이어서 진행합니다. "
            "design_circuit이 추가 정보를 요청했을 때, "
            "design_session_token과 추가 정보를 전달하여 설계를 계속합니다."
        ),
    )
    @tool_handler("continue_design")
    async def continue_design(
        design_session_token: str,
        additional_specs: dict | None = None,
        additional_description: str | None = None,
    ) -> str:
        """Continue a design session with additional specifications.

        Args:
            design_session_token: Token from previous design_circuit response.
            additional_specs: Dict of additional specs, e.g. {"vin": 48, "vout_target": 12}
            additional_description: Natural language with additional info, e.g. "입력 48V 출력 12V"
        """
        store = get_preview_store()
        session = store.get(design_session_token)

        if not session or session.get("type") != "design_session":
            return {
                "success": False,
                "error": {
                    "code": "INVALID_SESSION",
                    "message": "유효하지 않거나 만료된 설계 세션입니다.",
                    "suggestion": "design_circuit을 다시 호출하세요.",
                },
            }

        topology = session["topology"]
        merged_specs = dict(session.get("specs", {}))

        # Merge additional specs (explicit values take priority)
        if additional_specs:
            merged_specs.update(additional_specs)

        # Parse additional description for values
        if additional_description:
            parsed = parse_circuit_intent(additional_description)
            # Merge parsed specs (don't override explicit additional_specs)
            for k, v in parsed.get("specs", {}).items():
                if k not in merged_specs:
                    merged_specs[k] = v

        # Delete the old session
        store.delete(design_session_token)

        # Try generator first
        generator = None
        try:
            generator = get_generator(topology)
        except (KeyError, Exception):
            pass

        resolved_components = None
        resolved_connections = []
        resolved_nets = []
        generation_mode = "template_fallback"

        if generator:
            still_missing = generator.missing_fields(merged_specs)
            if not still_missing:
                try:
                    gen_result = generator.generate(merged_specs)
                    resolved_components = gen_result["components"]
                    resolved_nets = gen_result.get("nets", [])
                    generation_mode = "generator"
                except Exception as exc:
                    logger.warning(
                        "Generator failed for topology '%s' in continue_design: %s",
                        topology,
                        exc,
                    )
            else:
                # Still missing fields -- save a new session and ask again
                from psim_mcp.data.topology_metadata import get_slot_questions
                topo_questions = get_slot_questions(topology)
                questions = [
                    topo_questions.get(f, f"{f}을(를) 지정해주세요.")
                    for f in still_missing
                ]
                new_token = store.save({
                    "type": "design_session",
                    "topology": topology,
                    "specs": merged_specs,
                    "missing_fields": still_missing,
                })
                return {
                    "success": True,
                    "data": {
                        "action": "need_specs",
                        "topology": topology,
                        "specs": merged_specs,
                        "missing_fields": still_missing,
                        "questions": questions,
                        "confidence": "medium",
                        "generation_mode": "awaiting_specs",
                        "design_session_token": new_token,
                    },
                    "message": (
                        f"스펙이 업데이트되었지만 아직 추가 정보가 필요합니다.\n"
                        f"현재 스펙: {json.dumps(merged_specs, ensure_ascii=False)}\n"
                        f"다음 정보가 필요합니다:\n"
                        + "\n".join(f"  - {q}" for q in questions)
                        + f"\n\ncontinue_design(design_session_token='{new_token}', ...)으로 답변하세요."
                    ),
                }

        # Template fallback still needs enough information for a meaningful design.
        if resolved_components is None:
            from psim_mcp.data.topology_metadata import get_design_ready_fields, get_slot_questions

            design_fields = get_design_ready_fields(topology)
            design_missing = [f for f in design_fields if f not in merged_specs]
            if design_missing:
                topo_questions = get_slot_questions(topology)
                questions = [
                    topo_questions.get(f, f"{f}을(를) 지정해주세요.")
                    for f in design_missing
                ]
                new_token = store.save({
                    "type": "design_session",
                    "topology": topology,
                    "specs": merged_specs,
                    "missing_fields": design_missing,
                })
                return {
                    "success": True,
                    "data": {
                        "action": "need_specs",
                        "topology": topology,
                        "specs": merged_specs,
                        "missing_fields": design_missing,
                        "questions": questions,
                        "confidence": "medium",
                        "generation_mode": "awaiting_design_specs",
                        "design_session_token": new_token,
                    },
                    "message": (
                        f"추가 스펙 없이는 '{topology}' 회로를 의미 있게 생성할 수 없습니다.\n"
                        f"현재 스펙: {json.dumps(merged_specs, ensure_ascii=False)}\n"
                        f"다음 정보가 더 필요합니다:\n"
                        + "\n".join(f"  - {q}" for q in questions)
                        + f"\n\ncontinue_design(design_session_token='{new_token}', ...)으로 답변하세요."
                    ),
                }

        # Fallback to template
        if resolved_components is None:
            template = _TEMPLATES.get(topology)
            if template:
                resolved_components = copy.deepcopy(template["components"])
                resolved_connections = copy.deepcopy(template["connections"])
                if merged_specs:
                    _apply_specs(resolved_components, merged_specs)

        if not resolved_components:
            return {
                "success": False,
                "error": {
                    "code": "DESIGN_FAILED",
                    "message": "회로를 생성할 수 없습니다.",
                    "suggestion": "design_circuit을 다시 호출하세요.",
                },
            }

        # Convert nets to connections for rendering
        if resolved_nets and not resolved_connections:
            from psim_mcp.bridge.wiring import nets_to_connections
            resolved_connections = nets_to_connections(resolved_nets)

        # Validate
        validation_input = {
            "components": resolved_components,
            "connections": resolved_connections,
            "nets": resolved_nets,
        }
        validation_result = validate_circuit(validation_input)
        validation_issues = [
            {
                "code": issue.code,
                "message": issue.message,
                "component_id": issue.component_id,
                "suggestion": issue.suggestion,
            }
            for issue in (validation_result.errors + validation_result.warnings)
        ]

        if validation_result.errors:
            return {
                "success": False,
                "error": {
                    "code": "CIRCUIT_VALIDATION_FAILED",
                    "message": "설계 결과가 회로 검증을 통과하지 못했습니다.",
                    "suggestion": "입력 조건을 수정하거나 preview_circuit에 직접 전달하세요.",
                },
                "data": {
                    "topology": topology,
                    "specs_applied": merged_specs,
                    "generation_mode": generation_mode,
                    "validation_issues": validation_issues,
                },
            }

        # Render
        ascii_diagram = render_circuit_ascii(
            topology, resolved_components, resolved_connections
        )
        svg_content = render_circuit_svg(
            topology, resolved_components, resolved_connections
        )
        svg_dir = tempfile.gettempdir()
        svg_path = os.path.join(svg_dir, f"psim_preview_{topology}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_content)

        open_svg_in_browser(svg_path)

        # Save preview
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
                "specs_applied": merged_specs,
                "generation_mode": generation_mode,
                "validation_issues": validation_issues,
            },
            "message": (
                f"'{topology}' 회로가 설계되었습니다 (token: {token}):\n\n"
                f"```\n{ascii_diagram}\n```\n\n"
                f"SVG: {svg_path}\n"
                f"확정: confirm_circuit(preview_token='{token}', save_path='...')\n"
                f"수정: design_circuit 또는 preview_circuit을 다시 호출하세요."
            ),
        }
