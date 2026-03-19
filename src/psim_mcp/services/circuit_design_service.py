"""Circuit design pipeline service.

Consolidates circuit design logic that was previously scattered across
``tools/design.py``, ``tools/circuit.py``, and parts of ``SimulationService``.

Handles: NLP parsing -> generation -> preview -> validation -> creation.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
from typing import TYPE_CHECKING, Any

from psim_mcp.data.circuit_templates import TEMPLATES as _TEMPLATES, CATEGORIES as _CATEGORIES
from psim_mcp.data.component_library import COMPONENTS as _COMPONENTS, CATEGORIES as _COMP_CATEGORIES
from psim_mcp.data.component_library import resolve_psim_element_type
from psim_mcp.data.spec_mapping import apply_specs as _apply_specs
from psim_mcp.generators import get_generator
from psim_mcp.generators.constraints import validate_design_constraints
from psim_mcp.parsers import parse_circuit_intent
from psim_mcp.shared.audit import AuditMiddleware
from psim_mcp.shared.response import ResponseBuilder
from psim_mcp.shared.state_store import StateStore, get_state_store
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg, open_svg_in_browser
from psim_mcp.validators import validate_circuit as validate_circuit_spec

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.config import AppConfig


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers (from _preview_helpers)
# ---------------------------------------------------------------------------

def _run_validation(
    components: list[dict],
    connections: list[dict],
    nets: list[dict],
) -> tuple[list[dict], bool]:
    """Validate circuit and return (issues, has_errors)."""
    validation_input = {
        "components": components,
        "connections": connections,
        "nets": nets,
    }
    result = validate_circuit_spec(validation_input)
    issues = [
        {
            "code": issue.code,
            "message": issue.message,
            "component_id": issue.component_id,
            "suggestion": issue.suggestion,
        }
        for issue in (result.errors + result.warnings)
    ]
    return issues, bool(result.errors)


def _convert_nets_to_connections(nets: list[dict]) -> list[dict]:
    """Convert net-based wiring to point-to-point connections."""
    from psim_mcp.bridge.wiring import nets_to_connections
    return nets_to_connections(nets)


def _nets_to_connections_simple(nets: list[dict]) -> list[dict]:
    """Convert net-based representation to point-to-point connections (simple)."""
    connections = []
    for net in nets:
        pins = net.get("pins", [])
        for i in range(len(pins) - 1):
            connections.append({"from": pins[i], "to": pins[i + 1]})
    return connections


def _enrich_components_for_bridge(components: list[dict]) -> list[dict]:
    """Attach bridge-facing metadata expected by the real adapter."""
    enriched: list[dict] = []
    for component in components:
        item = dict(component)
        item_type = str(item.get("type", ""))
        item["psim_element_type"] = resolve_psim_element_type(item_type)
        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Generator resolution helper
# ---------------------------------------------------------------------------

def _try_generate(
    circuit_type: str,
    specs: dict | None,
    components: list[dict] | None,
) -> tuple[list[dict] | None, list[dict], list[dict], str, str | None, dict | None]:
    """Attempt to resolve components via generator.

    Returns (components, connections, nets, generation_mode, note, constraint_validation).
    """
    if components:
        return None, [], [], "template", None, None

    try:
        generator = get_generator(circuit_type.lower())
    except (KeyError, Exception):
        return None, [], [], "template_fallback", None, None

    req = specs or {}
    if generator.missing_fields(req):
        return None, [], [], "template_fallback", None, None

    try:
        gen_result = generator.generate(req)

        # Run constraint validation on generator output
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
        )
    except Exception as exc:
        logger.warning("Generator failed for '%s': %s", circuit_type, exc)
        return (
            None, [], [], "template_fallback",
            "Generator not available for this topology. Using template with default values.",
            None,
        )


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------

def _render_and_store(
    store: StateStore,
    circuit_type: str,
    components: list[dict],
    connections: list[dict],
    nets: list[dict],
    simulation_settings: dict | None = None,
) -> dict:
    """Render ASCII + SVG, open browser, save to store."""
    ascii_diagram = render_circuit_ascii(
        circuit_type=circuit_type,
        components=components,
        connections=connections,
    )

    svg_content = render_circuit_svg(
        circuit_type=circuit_type,
        components=components,
        connections=connections,
        nets=nets,
    )

    svg_dir = tempfile.gettempdir()
    svg_path = os.path.join(svg_dir, f"psim_preview_{circuit_type}.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    open_svg_in_browser(svg_path)

    token = store.save({
        "circuit_type": circuit_type,
        "components": components,
        "connections": connections,
        "nets": nets,
        "simulation_settings": simulation_settings,
        "svg_path": svg_path,
    })

    return {
        "ascii_diagram": ascii_diagram,
        "svg_path": svg_path,
        "preview_token": token,
    }


# ===========================================================================
# CircuitDesignService
# ===========================================================================

class CircuitDesignService:
    """Circuit design pipeline service.

    Consolidates all circuit design logic:
    - NLP parsing and topology extraction
    - Generator / template based circuit generation
    - Preview rendering (SVG/ASCII) and token management
    - Circuit validation and .psimsch file creation
    """

    def __init__(
        self,
        adapter: BasePsimAdapter,
        config: AppConfig,
        state_store: StateStore | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._store = state_store or get_state_store()
        self._logger = logging.getLogger(__name__)
        self._audit = AuditMiddleware()

    # ------------------------------------------------------------------
    # NLP → Design
    # ------------------------------------------------------------------

    async def design_circuit(self, description: str) -> dict:
        """Parse natural language and suggest/create a circuit."""
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
            session_token = self._store.save({
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
            return await self._auto_generate_preview(topology, specs, intent)

        # Case 2: Topology found but missing specs
        if topology and missing:
            session_token = self._store.save({
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

        # Case 4: Nothing matched
        return self._no_match_response(specs)

    async def continue_design(
        self,
        session_token: str,
        additional_specs: dict | None = None,
        additional_description: str | None = None,
    ) -> dict:
        """Continue a design session with additional specifications."""
        session = self._store.get(session_token)

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

        if additional_specs:
            merged_specs.update(additional_specs)

        if additional_description:
            parsed = parse_circuit_intent(additional_description)
            for k, v in parsed.get("specs", {}).items():
                if k not in merged_specs:
                    merged_specs[k] = v

        self._store.delete(session_token)

        # Try generator
        gen_components, gen_connections, gen_nets, gen_mode, gen_note, gen_constraints = (
            _try_generate(topology, merged_specs, None)
        )

        resolved_components = gen_components
        resolved_connections = gen_connections
        resolved_nets = gen_nets
        generation_mode = gen_mode

        # If generator needs more fields, ask again
        if resolved_components is None:
            generator = None
            try:
                generator = get_generator(topology)
            except (KeyError, Exception):
                pass

            if generator:
                still_missing = generator.missing_fields(merged_specs)
                if still_missing:
                    return self._build_need_specs_response(
                        topology, merged_specs, still_missing, "awaiting_specs",
                    )

        # Template fallback: check design_ready_fields
        if resolved_components is None:
            design_missing = self._check_design_readiness(topology, merged_specs)
            if design_missing:
                return self._build_need_specs_response(
                    topology, merged_specs, design_missing, "awaiting_design_specs",
                )

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

        return self._validate_and_render(
            topology=topology,
            components=resolved_components,
            connections=resolved_connections,
            nets=resolved_nets,
            specs=merged_specs,
            intent={},
            generation_mode=generation_mode,
            confidence="high",
            constraint_validation=gen_constraints,
        )

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    async def preview_circuit(
        self,
        circuit_type: str,
        specs: dict | None = None,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> dict:
        """Generate an SVG preview of the circuit diagram."""
        resolved_nets: list[dict] = []
        generation_mode = "template"

        # Try generator first
        gen_components, gen_connections, gen_nets, gen_mode, _note, _gen_constraints = _try_generate(
            circuit_type, specs, components,
        )
        if gen_components is not None:
            resolved_components = gen_components
            resolved_connections = gen_connections
            resolved_nets = gen_nets
            generation_mode = gen_mode
        else:
            template = _TEMPLATES.get(circuit_type.lower())

            if template and not components:
                resolved_components = copy.deepcopy(template["components"])
                resolved_connections = connections or copy.deepcopy(template["connections"])
                if specs:
                    _apply_specs(resolved_components, specs)

            elif components and isinstance(components, list):
                resolved_components = copy.deepcopy(components)
                resolved_connections = connections or []

            elif components and isinstance(components, dict):
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

        if resolved_nets and not resolved_connections:
            resolved_connections = _convert_nets_to_connections(resolved_nets)

        validation_issues, _has_errors = _run_validation(
            resolved_components, resolved_connections, resolved_nets,
        )

        preview = _render_and_store(
            self._store,
            circuit_type=circuit_type,
            components=resolved_components,
            connections=resolved_connections,
            nets=resolved_nets,
            simulation_settings=simulation_settings,
        )

        token = preview["preview_token"]
        ascii_diagram = preview["ascii_diagram"]
        svg_path = preview["svg_path"]

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
                "validation_warnings": validation_issues,
                "generation_mode": generation_mode,
            },
            "message": (
                f"'{circuit_type}' 회로 미리보기 (token: {token}):\n\n"
                f"```\n{ascii_diagram}\n```\n\n"
                f"SVG 파일이 브라우저에서 자동으로 열립니다: {svg_path}\n"
                f"확정하려면 confirm_circuit(preview_token='{token}')을, "
                f"수정하려면 preview_circuit을 다시 호출하세요."
            ),
        }

    # ------------------------------------------------------------------
    # Confirm & Create
    # ------------------------------------------------------------------

    async def confirm_circuit(
        self,
        save_path: str,
        preview_token: str | None = None,
        modifications: dict | None = None,
    ) -> dict:
        """Confirm the previewed circuit and create the .psimsch file."""
        preview = self._store.get(preview_token) if preview_token else None

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
        simulation_settings = preview.get("simulation_settings")

        if nets:
            connections = _convert_nets_to_connections(nets)

        if modifications:
            for comp in components:
                if comp["id"] in modifications:
                    comp["parameters"].update(modifications[comp["id"]])

        result = await self._create_in_psim(
            circuit_type=circuit_type,
            components=components,
            connections=connections,
            save_path=save_path,
            simulation_settings=simulation_settings,
            circuit_spec={"components": components, "nets": nets} if nets else None,
        )

        if isinstance(result, dict) and result.get("success"):
            self._store.delete(preview_token)

        return result

    async def create_circuit_direct(
        self,
        circuit_type: str,
        save_path: str,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> dict:
        """Create a circuit directly without preview."""
        circuit_spec: dict | None = None

        gen_components, gen_connections, gen_nets, gen_mode, _note, _gen_constraints = _try_generate(
            circuit_type, simulation_settings, components,
        )

        if gen_components is not None:
            components = gen_components
            connections = gen_connections
            circuit_spec = {
                "topology": circuit_type,
                "components": components,
                "nets": gen_nets,
                "simulation": {},
            }
        else:
            template = _TEMPLATES.get(circuit_type.lower())
            if template and not components:
                components = template["components"]
                connections = connections or template["connections"]
            elif not components:
                components = []
                connections = connections or []

        if connections is None:
            connections = []

        if circuit_spec and circuit_spec.get("nets") and not connections:
            connections = _convert_nets_to_connections(circuit_spec["nets"])

        result = await self._create_in_psim(
            circuit_type=circuit_type,
            components=components,
            connections=connections,
            save_path=save_path,
            simulation_settings=simulation_settings,
            circuit_spec=circuit_spec,
        )

        if isinstance(result, dict) and "data" in result and isinstance(result["data"], dict):
            result["data"]["generation_mode"] = gen_mode
        elif isinstance(result, dict):
            result.setdefault("data", {})["generation_mode"] = gen_mode

        return result

    # ------------------------------------------------------------------
    # Read-only queries
    # ------------------------------------------------------------------

    def get_component_library(self, category: str | None = None) -> dict:
        """Return available component types with pins and parameters."""
        result = {}
        for type_name, comp in _COMPONENTS.items():
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
                "categories": list(_COMP_CATEGORIES.keys()),
            },
            "message": (
                f"{len(result)}개 부품 타입 사용 가능. "
                "preview_circuit의 components에 이 타입명과 핀 이름을 사용하세요."
            ),
        }

    def list_templates(self, category: str | None = None) -> dict:
        """Return available circuit templates."""
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _auto_generate_preview(
        self, topology: str, specs: dict, intent: dict,
    ) -> dict:
        """High-confidence auto-generation with fallback."""
        gen_components, gen_connections, gen_nets, gen_mode, gen_note, gen_constraints = (
            _try_generate(topology, specs, None)
        )

        resolved_components = gen_components
        resolved_connections = gen_connections
        resolved_nets = gen_nets
        generation_mode = gen_mode
        generation_note = gen_note

        # Fallback to template
        if resolved_components is None:
            gen_constraints = None  # No constraint data for template fallback
            generator_was_attempted = gen_note is not None
            template = _TEMPLATES.get(topology)
            if template:
                resolved_components = copy.deepcopy(template["components"])
                resolved_connections = copy.deepcopy(template["connections"])
                if specs:
                    _apply_specs(resolved_components, specs)
                if generation_note is None and generator_was_attempted:
                    generation_note = (
                        "Generator not available for this topology. "
                        "Using template with default values."
                    )

        # If template fallback, check design_ready_fields
        if generation_mode == "template_fallback":
            design_missing = self._check_design_readiness(topology, specs)
            if design_missing:
                return self._build_need_specs_response(
                    topology, specs, design_missing, "awaiting_design_specs",
                    note="템플릿은 있지만 의미 있는 설계를 위해 추가 정보가 필요합니다.",
                )

        if resolved_components:
            return self._validate_and_render(
                topology=topology,
                components=resolved_components,
                connections=resolved_connections,
                nets=resolved_nets,
                specs=specs,
                intent=intent,
                generation_mode=generation_mode,
                confidence="high",
                generation_note=generation_note,
                constraint_validation=gen_constraints,
            )

        return self._no_match_response(specs)

    def _validate_and_render(
        self,
        topology: str,
        components: list[dict],
        connections: list[dict],
        nets: list[dict],
        specs: dict,
        intent: dict,
        generation_mode: str,
        confidence: str,
        generation_note: str | None = None,
        constraint_validation: dict | None = None,
    ) -> dict:
        """Validate circuit, render preview if valid."""
        if nets and not connections:
            connections = _convert_nets_to_connections(nets)

        validation_issues, has_errors = _run_validation(components, connections, nets)

        if has_errors:
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

        preview = _render_and_store(
            self._store,
            circuit_type=topology,
            components=components,
            connections=connections,
            nets=nets,
        )

        token = preview["preview_token"]
        ascii_diagram = preview["ascii_diagram"]
        svg_path = preview["svg_path"]

        response_data: dict[str, Any] = {
            "ascii_diagram": ascii_diagram,
            "svg_path": svg_path,
            "circuit_type": topology,
            "preview_token": token,
            "component_count": len(components),
            "specs_applied": specs,
            "intent": intent,
            "generation_mode": generation_mode,
            "confidence": confidence,
            "validation_issues": validation_issues,
        }
        if generation_note:
            response_data["generation_note"] = generation_note
        if constraint_validation:
            response_data["constraint_validation"] = constraint_validation

        # Build message with constraint warnings appended
        message = (
            f"'{topology}' 회로가 자동 설계되었습니다 (token: {token}):\n\n"
            f"```\n{ascii_diagram}\n```\n\n"
            f"SVG: {svg_path}\n"
            f"확정: confirm_circuit(preview_token='{token}', save_path='...')\n"
            f"수정: preview_circuit 또는 design_circuit을 다시 호출하세요."
        )
        if constraint_validation and constraint_validation.get("issues"):
            warnings = [
                i for i in constraint_validation["issues"]
                if i["severity"] in ("warning", "error")
            ]
            if warnings:
                message += "\n\n설계 제약 조건 검토:"
                for w in warnings:
                    severity_label = "오류" if w["severity"] == "error" else "주의"
                    message += f"\n  [{severity_label}] {w['message']}"
                    if w.get("suggestion"):
                        message += f"\n    -> {w['suggestion']}"

        return {
            "success": True,
            "data": response_data,
            "message": message,
        }

    def _build_need_specs_response(
        self,
        topology: str,
        specs: dict,
        missing_fields: list[str],
        generation_mode: str,
        note: str | None = None,
    ) -> dict:
        """Build a response asking the user for additional specs."""
        from psim_mcp.data.topology_metadata import get_slot_questions
        topo_questions = get_slot_questions(topology)
        questions = [
            topo_questions.get(f, f"{f}을(를) 지정해주세요.")
            for f in missing_fields
        ]

        session_token = self._store.save({
            "type": "design_session",
            "topology": topology,
            "specs": specs,
            "missing_fields": missing_fields,
        })

        data: dict = {
            "action": "need_specs",
            "topology": topology,
            "specs": specs,
            "missing_fields": missing_fields,
            "questions": questions,
            "confidence": "medium",
            "generation_mode": generation_mode,
            "design_session_token": session_token,
        }
        if note:
            data["generation_note"] = note

        return {
            "success": True,
            "data": data,
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

    @staticmethod
    def _check_design_readiness(topology: str, specs: dict) -> list[str] | None:
        """Check if template fallback has enough fields for meaningful design."""
        from psim_mcp.data.topology_metadata import get_design_ready_fields
        design_fields = get_design_ready_fields(topology)
        if not design_fields:
            return None
        missing = [f for f in design_fields if f not in specs]
        return missing if missing else None

    @staticmethod
    def _no_match_response(specs: dict) -> dict:
        """Build response when no topology could be matched."""
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

    async def _create_in_psim(
        self,
        circuit_type: str,
        components: list[dict],
        connections: list[dict],
        save_path: str,
        simulation_settings: dict | None = None,
        circuit_spec: dict | None = None,
    ) -> dict:
        """Validate and create circuit via adapter.

        This contains the logic previously in SimulationService.create_circuit().
        """

        async def _handler():
            nonlocal components, connections

            if not circuit_type or not isinstance(circuit_type, str):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="circuit_type은 비어 있지 않은 문자열이어야 합니다.",
                )

            if circuit_spec is not None:
                components = circuit_spec.get("components", components)
                nets = circuit_spec.get("nets", [])
                if nets:
                    connections = _nets_to_connections_simple(nets)

            if not components or not isinstance(components, list):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="components는 비어 있지 않은 리스트여야 합니다.",
                )

            if not save_path or not isinstance(save_path, str):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="save_path가 지정되지 않았습니다.",
                )

            if not save_path.endswith(".psimsch"):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="save_path는 .psimsch 확장자여야 합니다.",
                )

            validation_input = {
                "components": components,
                "nets": circuit_spec.get("nets", []) if circuit_spec else [],
            }
            validation = validate_circuit_spec(validation_input)
            if not validation.is_valid:
                error_messages = "; ".join(e.message for e in validation.errors)
                return ResponseBuilder.error(
                    code="CIRCUIT_VALIDATION_FAILED",
                    message=f"회로 검증 실패: {error_messages}",
                )

            bridge_components = _enrich_components_for_bridge(components)

            try:
                data = await self._adapter.create_circuit(
                    circuit_type=circuit_type,
                    components=bridge_components,
                    connections=connections or [],
                    save_path=save_path,
                    simulation_settings=simulation_settings,
                )
                return ResponseBuilder.success(
                    data,
                    f"'{circuit_type}' 회로가 성공적으로 생성되었습니다. "
                    f"컴포넌트 {len(components)}개, 연결 {len(connections or [])}개.",
                )
            except Exception:
                self._logger.exception("Failed to create circuit")
                return ResponseBuilder.error(
                    code="CREATE_CIRCUIT_FAILED",
                    message="회로 생성 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit(
            "create_circuit",
            {"circuit_type": circuit_type, "component_count": len(components or [])},
            _handler,
        )
