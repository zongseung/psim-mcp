"""Circuit design pipeline service.

Consolidates circuit design logic that was previously scattered across
``tools/design.py``, ``tools/circuit.py``, and parts of ``SimulationService``.

Handles: NLP parsing -> generation -> preview -> validation -> creation.

Implementation is split across three private helper modules to keep each
file focused on a single responsibility:

* ``_circuit_pipeline.py``   — synthesis / layout / routing pipeline
* ``_circuit_render.py``     — rendering and validation helpers
* ``_circuit_generators.py`` — generator resolution helper
"""

from __future__ import annotations

import copy
import json
import logging
import os
from typing import TYPE_CHECKING, Any

from psim_mcp.data.circuit_templates import TEMPLATES as _TEMPLATES, CATEGORIES as _CATEGORIES
from psim_mcp.data.component_library import COMPONENTS as _COMPONENTS, CATEGORIES as _COMP_CATEGORIES
from psim_mcp.data.spec_mapping import apply_specs as _apply_specs
from psim_mcp.parsers import parse_circuit_intent
from psim_mcp.shared.audit import AuditMiddleware
from psim_mcp.shared.response import ResponseBuilder
from psim_mcp.shared.state_store import StateStore, get_state_store
from psim_mcp.validators import validate_circuit as validate_circuit_spec
from psim_mcp.services.validators import validate_save_path

# Helper sub-modules
from psim_mcp.services._circuit_pipeline import (
    SYNTHESIS_PIPELINE_AVAILABLE,
    PREVIEW_PAYLOAD_KIND,
    PREVIEW_PAYLOAD_VERSION,
    DESIGN_SESSION_KIND,
    DESIGN_SESSION_VERSION,
    try_synthesize_and_layout as _try_synthesize_and_layout,
    normalize_preview_payload as _normalize_preview_payload,
    normalize_design_session_payload as _normalize_design_session_payload,
    load_graph_layout_routing as _load_graph_layout_routing,
    make_design_session_payload as _make_design_session_payload,
)
from psim_mcp.services._circuit_render import (
    run_validation as _run_validation,
    convert_nets_to_connections as _convert_nets_to_connections,
    nets_to_connections_simple as _nets_to_connections_simple,
    enrich_components_for_bridge as _enrich_components_for_bridge,
    render_and_store as _render_and_store,
)
from psim_mcp.services._circuit_generators import try_generate as _try_generate

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.config import AppConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backward-compatibility aliases (tests import these from this module)
# ---------------------------------------------------------------------------

# Synthesis pipeline availability flags (referenced by several test modules)
_SYNTHESIS_PIPELINE_AVAILABLE = SYNTHESIS_PIPELINE_AVAILABLE
_LAYOUT_ENGINE_AVAILABLE = SYNTHESIS_PIPELINE_AVAILABLE
_ROUTING_ENGINE_AVAILABLE = SYNTHESIS_PIPELINE_AVAILABLE

# Payload kind / version constants (referenced by test_build_need_specs_versioned)
_PREVIEW_PAYLOAD_KIND = PREVIEW_PAYLOAD_KIND
_PREVIEW_PAYLOAD_VERSION = PREVIEW_PAYLOAD_VERSION
_DESIGN_SESSION_KIND = DESIGN_SESSION_KIND
_DESIGN_SESSION_VERSION = DESIGN_SESSION_VERSION

# ---------------------------------------------------------------------------
# Optional V2 intent pipeline
# ---------------------------------------------------------------------------

try:
    from psim_mcp.intent import IntentResolver, get_resolver

    _INTENT_V2_AVAILABLE = True
except ImportError:
    IntentResolver = None  # type: ignore[assignment,misc]
    get_resolver = None  # type: ignore[assignment]
    _INTENT_V2_AVAILABLE = False


# ---------------------------------------------------------------------------
# Utility: open .psimsch file in PSIM GUI
# ---------------------------------------------------------------------------


def _open_in_psim(file_path: str) -> None:
    """Open a .psimsch file in PSIM GUI if available.

    Non-blocking: launches PSIM as a detached subprocess.
    Silently does nothing if PSIM is not installed or path is invalid.
    """
    import subprocess

    psim_path = os.environ.get("PSIM_PATH", "")
    if not psim_path:
        return
    psim_exe = os.path.join(psim_path, "PSIM.exe")
    if not os.path.isfile(psim_exe):
        return
    if not file_path or not os.path.isfile(file_path):
        return
    try:
        subprocess.Popen(
            [psim_exe, file_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0),
        )
    except Exception:
        logger.debug("Failed to open PSIM GUI for %s", file_path, exc_info=True)


def _merge_simulation_settings(
    generated: dict | None,
    overrides: dict | None,
) -> dict | None:
    """Merge user overrides on top of generator-provided simulation settings."""
    if generated is None and overrides is None:
        return None
    merged: dict[str, Any] = {}
    if generated:
        merged.update(generated)
    if overrides:
        merged.update(overrides)
    return merged


def _get_allowed_save_dirs(config: AppConfig | None) -> list[str] | None:
    """Resolve allowed output roots for new schematic files.

    Only restricts when ``allowed_project_dirs`` is explicitly configured.
    In real mode without an explicit whitelist, saves are unrestricted so
    that users can save to any valid path (e.g. Documents, Desktop).
    """
    if config is None:
        return None
    if config.allowed_project_dirs:
        return config.allowed_project_dirs
    return None


def _build_save_path_suggestion(
    config: AppConfig | None,
    topology: str = "circuit",
) -> str:
    """Describe valid save roots and provide a safe example path."""
    allowed_dirs = _get_allowed_save_dirs(config)
    if not allowed_dirs:
        return "Use a valid .psimsch path."

    example_root = allowed_dirs[-1]
    example_path = os.path.join(example_root, f"{topology}.psimsch")
    roots = ", ".join(allowed_dirs)
    return (
        f"Use a .psimsch path under one of the configured save roots: {roots}. "
        f"Example: {example_path}"
    )


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
        intent_resolver: IntentResolver | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._store = state_store or get_state_store()
        self._logger = logging.getLogger(__name__)
        self._audit = AuditMiddleware()

        # Intent resolution is delegated to a strategy object so Phase 1+ can
        # swap in LLM-driven resolvers without touching this service. When the
        # intent module is unavailable (legacy installs), ``_intent_resolver``
        # stays ``None`` and ``_resolve_intent_v2`` short-circuits to None
        # which triggers the legacy ``parse_circuit_intent`` fallback.
        if intent_resolver is not None:
            self._intent_resolver = intent_resolver
        elif _INTENT_V2_AVAILABLE and get_resolver is not None:
            mode = getattr(config, "intent_resolver_mode", "regex")
            self._intent_resolver = get_resolver(mode)
        else:
            self._intent_resolver = None

    # ------------------------------------------------------------------
    # Feature flag helpers
    # ------------------------------------------------------------------

    def _is_intent_v2_enabled(self) -> bool:
        return _INTENT_V2_AVAILABLE and bool(self._config.psim_intent_pipeline_v2)

    def _is_synthesis_enabled_for_topology(
        self,
        topology: str,
        stage: str = "synthesize",
    ) -> bool:
        from psim_mcp.data.capability_matrix import is_supported as _capability_is_supported

        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            return False
        if not _capability_is_supported(topology, stage):
            return False
        enabled = [item.lower() for item in self._config.psim_synthesis_enabled_topologies]
        if not enabled or "*" in enabled or "all" in enabled:
            return True
        return topology.lower() in enabled

    def _try_synthesis_for_topology(
        self,
        topology: str,
        specs: dict | None,
        stage: str = "synthesize",
    ) -> dict | None:
        if not self._is_synthesis_enabled_for_topology(topology, stage=stage):
            return None
        return _try_synthesize_and_layout(topology, specs, config=self._config)

    # ------------------------------------------------------------------
    # NLP -> Design
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_confidence_v2(
        intent: object,
        top: object,
        spec: object,
        clarification_needs: list,
    ) -> str:
        """Determine confidence level for V2 pipeline result."""
        missing = getattr(spec, "missing_fields", [])
        score = getattr(top, "score", 0)
        mapping_conf = getattr(intent, "mapping_confidence", "high")

        if not missing and score >= 8:
            confidence = "high"
        elif not missing:
            confidence = "medium"
        else:
            confidence = "low"

        if mapping_conf == "low":
            confidence = "low"
        elif mapping_conf == "medium" and confidence == "high":
            confidence = "medium"

        return confidence

    async def _resolve_intent_v2(self, description: str, ctx=None) -> dict | None:
        """V2 intent pipeline. Returns legacy-compatible parsed dict, or None.

        Delegates to the configured :class:`IntentResolver` strategy. ``ctx``
        is forwarded to the resolver so Phase 1+ LLM-backed resolvers can
        invoke MCP sampling on the client. The regex resolver ignores it.
        """
        if not self._is_intent_v2_enabled():
            return None
        if self._intent_resolver is None:
            return None
        try:
            return await self._intent_resolver.resolve(description, ctx=ctx)
        except Exception:
            logger.debug("V2 intent resolution failed, falling back to legacy", exc_info=True)
            return None

    async def design_circuit(self, description: str, ctx=None) -> dict:
        """Parse natural language and suggest/create a circuit.

        Tries V2 intent pipeline first, falls back to legacy on failure.
        ``ctx`` is the FastMCP tool Context, forwarded to LLM-backed
        resolvers (Phase 1+); ignored by the regex resolver.
        """
        try:
            intent = await self._resolve_intent_v2(description, ctx=ctx)
        except Exception:
            logger.debug("V2 intent resolution raised, falling back to legacy", exc_info=True)
            intent = None
        if intent is None:
            intent = parse_circuit_intent(description)

        topology = intent["topology"]
        specs = intent.get("normalized_specs", intent["specs"])
        candidates = intent["topology_candidates"]
        missing = intent["missing_fields"]
        questions = intent["questions"]
        confidence = intent["confidence"]
        use_case = intent["use_case"]

        candidate_scores = intent.get("candidate_scores")
        decision_trace = intent.get("decision_trace")

        # Case 1b: Medium confidence — show intent, ask for confirmation
        if topology and confidence == "medium":
            session_token = self._store.save(
                _make_design_session_payload(topology, specs, missing),
            )
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
                    **({"candidate_scores": candidate_scores} if candidate_scores is not None else {}),
                    **({"decision_trace": decision_trace} if decision_trace is not None else {}),
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
            session_token = self._store.save(
                _make_design_session_payload(topology, specs, missing),
            )
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
                    **({"candidate_scores": candidate_scores} if candidate_scores is not None else {}),
                    **({"decision_trace": decision_trace} if decision_trace is not None else {}),
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
        if session:
            session = _normalize_design_session_payload(session)

        if not session or session.get("type") != _DESIGN_SESSION_KIND:
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

        gen_components, gen_connections, gen_nets, gen_mode, gen_note, gen_constraints, gen_template, gen_simulation = (
            _try_generate(topology, merged_specs, None)
        )

        resolved_components = gen_components
        resolved_connections = gen_connections
        resolved_nets = gen_nets
        generation_mode = gen_mode

        if resolved_components is None:
            generator = None
            try:
                from psim_mcp.generators import get_generator

                generator = get_generator(topology)
            except (KeyError, Exception):
                pass

            if generator:
                still_missing = generator.missing_fields(merged_specs)
                if still_missing:
                    return self._build_need_specs_response(
                        topology, merged_specs, still_missing, "awaiting_specs",
                    )

        if resolved_components is None:
            design_missing = self._check_design_readiness(topology, merged_specs)
            if design_missing:
                return self._build_need_specs_response(
                    topology, merged_specs, design_missing, "awaiting_design_specs",
                )

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
            psim_template=gen_template,
            simulation_settings=gen_simulation,
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
        wire_segments: list[dict] = []
        synth_graph = None
        synth_layout = None
        synth_routing = None

        synth_result = None
        if not components and specs:
            synth_result = self._try_synthesis_for_topology(circuit_type, specs, stage="preview_generator")

        gen_components, gen_connections, gen_nets, gen_mode, _note, _gen_constraints, _gen_template, gen_simulation = _try_generate(
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

        if synth_result is not None:
            # Always capture graph/layout/routing from synthesis for
            # the preview payload (needed by confirm_circuit for
            # materialization and by tests asserting canonical path).
            synth_graph = synth_result["graph"]
            synth_layout = synth_result["layout"]
            synth_routing = synth_result.get("wire_routing")

            # Use synthesis output (components with layout positions,
            # nets from graph, and wire_segments from routing engine).
            # The bridge supplements wire_segments with pin-based wiring
            # from nets to fill any routing gaps.
            resolved_components = synth_result["components"]
            resolved_nets = synth_result["nets"]
            resolved_connections = []
            if synth_routing is not None:
                wire_segments = synth_routing.to_legacy_segments()

            generation_mode = "generator"
            # Reset legacy template so confirm_circuit uses the graph
            # materialization path instead of the template fast path.
            _gen_template = None

        if resolved_connections is None:
            resolved_connections = []

        if resolved_nets and not resolved_connections:
            resolved_connections = _convert_nets_to_connections(resolved_nets)

        validation_issues, has_errors = _run_validation(
            resolved_components, resolved_connections, resolved_nets,
        )

        if has_errors:
            return {
                "success": False,
                "error": {
                    "code": "CIRCUIT_VALIDATION_FAILED",
                    "message": "Preview blocked because the circuit spec contains validation errors.",
                    "details": validation_issues,
                    "suggestion": (
                        "Fix invalid component.pin references or adjust the template/spec "
                        "before requesting a preview."
                    ),
                },
            }

        effective_simulation_settings = _merge_simulation_settings(gen_simulation, simulation_settings)

        preview = _render_and_store(
            self._store,
            circuit_type=circuit_type,
            components=resolved_components,
            connections=resolved_connections,
            nets=resolved_nets,
            wire_segments=wire_segments,
            simulation_settings=effective_simulation_settings,
            psim_template=_gen_template,
            graph=synth_graph,
            layout=synth_layout,
            wire_routing=synth_routing,
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

        preview = _normalize_preview_payload(preview)
        graph, layout, routing = _load_graph_layout_routing(preview)

        components = copy.deepcopy(preview["components"])
        connections = preview.get("connections", [])
        nets = preview.get("nets", [])
        circuit_type = preview["circuit_type"]
        simulation_settings = preview.get("simulation_settings")
        psim_template = preview.get("psim_template")

        if psim_template:
            try:
                data = await self._adapter.create_circuit(
                    circuit_type=circuit_type,
                    components=[],
                    connections=[],
                    save_path=save_path,
                    simulation_settings=simulation_settings,
                    psim_template=psim_template,
                )
                return ResponseBuilder.success(
                    data,
                    f"'{circuit_type}' 회로가 템플릿 기반으로 생성되었습니다.",
                )
            except Exception:
                self._logger.exception("Failed to create template circuit")
                return ResponseBuilder.error(
                    code="TEMPLATE_CREATE_FAILED",
                    message="템플릿 기반 회로 생성 중 오류가 발생했습니다.",
                )

        if graph is not None and layout is not None:
            # Skip materialization when preview components already have
            # ports (from the generator path).  Materialized components
            # may produce positions that don't match the routing engine's
            # wire segment coordinates.
            has_ports = any(c.get("ports") for c in components)
            if not has_ports:
                try:
                    from psim_mcp.layout.materialize import materialize_to_legacy

                    components, nets = materialize_to_legacy(graph, layout)
                    connections = []
                except Exception:
                    logger.debug("Failed to materialize graph/layout during confirm", exc_info=True)

        if routing is not None and not preview.get("wire_segments"):
            try:
                preview["wire_segments"] = routing.to_legacy_segments()
            except Exception:
                logger.debug("Failed to derive wire segments from routing during confirm", exc_info=True)

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
            circuit_spec={
                "components": components,
                "nets": nets,
                "wire_segments": preview.get("wire_segments", []),
                "graph": preview.get("graph"),
                "layout": preview.get("layout"),
                "routing": preview.get("routing"),
            } if nets or preview.get("wire_segments") or preview.get("graph") or preview.get("layout") else None,
        )

        if isinstance(result, dict) and result.get("success"):
            svg_path = preview.get("svg_path")
            if svg_path:
                try:
                    os.remove(svg_path)
                except OSError:
                    pass
            self._store.delete(preview_token)
            _open_in_psim(save_path)

        return result

    async def create_circuit_direct(
        self,
        circuit_type: str,
        save_path: str,
        specs: dict | None = None,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> dict:
        """Create a circuit directly without preview."""
        circuit_spec: dict | None = None
        gen_mode = "template"

        synth_result = None
        if not components and specs:
            synth_result = self._try_synthesis_for_topology(circuit_type, specs, stage="create_direct")

        if synth_result is not None:
            components = synth_result["components"]
            connections = []
            circuit_spec = {
                "topology": circuit_type,
                "components": components,
                "nets": synth_result["nets"],
                "wire_segments": synth_result.get("wire_segments", []),
                "graph": synth_result["graph"].to_dict() if hasattr(synth_result["graph"], "to_dict") else synth_result["graph"],
                "layout": synth_result["layout"].to_dict() if hasattr(synth_result["layout"], "to_dict") else synth_result["layout"],
                "routing": synth_result["wire_routing"].to_dict() if synth_result.get("wire_routing") and hasattr(synth_result["wire_routing"], "to_dict") else synth_result.get("wire_routing"),
                "simulation": {},
            }
            gen_mode = "generator"
        else:
            gen_components, gen_connections, gen_nets, gen_mode, _note, _gen_constraints, _gen_template, gen_simulation = _try_generate(
                circuit_type, specs, components,
            )

            if gen_components is not None:
                components = gen_components
                connections = gen_connections
                simulation_settings = _merge_simulation_settings(gen_simulation, simulation_settings)
                circuit_spec = {
                    "topology": circuit_type,
                    "components": components,
                    "nets": gen_nets,
                    "simulation": simulation_settings or {},
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

        if isinstance(result, dict) and result.get("success"):
            _open_in_psim(save_path)

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
        synth_result = self._try_synthesis_for_topology(topology, specs, stage="design_circuit")
        if synth_result is not None:
            return self._validate_and_render(
                topology=topology,
                components=synth_result["components"],
                connections=[],
                nets=synth_result["nets"],
                specs=specs,
                intent=intent,
                generation_mode="generator",
                confidence="high",
                graph=synth_result["graph"],
                layout=synth_result["layout"],
                wire_routing=synth_result.get("wire_routing"),
                wire_segments=synth_result.get("wire_segments"),
            )

        gen_components, gen_connections, gen_nets, gen_mode, gen_note, gen_constraints, gen_template, gen_simulation = (
            _try_generate(topology, specs, None)
        )

        resolved_components = gen_components
        resolved_connections = gen_connections
        resolved_nets = gen_nets
        generation_mode = gen_mode
        generation_note = gen_note

        if resolved_components is None:
            gen_constraints = None
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
                psim_template=gen_template,
                simulation_settings=gen_simulation,
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
        psim_template: dict | None = None,
        simulation_settings: dict | None = None,
        graph: object | None = None,
        layout: object | None = None,
        wire_routing: object | None = None,
        wire_segments: list[dict] | None = None,
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
            simulation_settings=simulation_settings,
            psim_template=psim_template,
            wire_segments=wire_segments,
            graph=graph,
            layout=layout,
            wire_routing=wire_routing,
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

        save_path_hint = _build_save_path_suggestion(self._config, topology)
        message = (
            f"'{topology}' 회로가 자동 설계되었습니다 (token: {token}):\n\n"
            f"```\n{ascii_diagram}\n```\n\n"
            f"SVG: {svg_path}\n"
            f"확정: confirm_circuit(preview_token='{token}', save_path='...')\n"
            f"권장 save_path: {save_path_hint}\n"
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

        session_token = self._store.save(
            _make_design_session_payload(topology, specs, missing_fields),
        )

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
        """Validate and create circuit via adapter."""

        async def _handler():
            nonlocal components, connections
            wire_segments = []

            if not circuit_type or not isinstance(circuit_type, str):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="circuit_type은 비어 있지 않은 문자열이어야 합니다.",
                )

            if circuit_spec is not None:
                components = circuit_spec.get("components", components)
                nets = circuit_spec.get("nets", [])
                wire_segments = circuit_spec.get("wire_segments", [])
                if nets:
                    try:
                        connections = _convert_nets_to_connections(nets)
                    except Exception:
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

            save_path_validation = validate_save_path(
                save_path,
                allowed_dirs=_get_allowed_save_dirs(self._config),
            )
            if not save_path_validation.is_valid:
                return ResponseBuilder.error(
                    code=save_path_validation.error_code or "VALIDATION_ERROR",
                    message=save_path_validation.error_message or "Invalid save_path.",
                    suggestion=_build_save_path_suggestion(self._config, circuit_type),
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
                # Pass nets alongside connections so the bridge can use
                # star routing directly from the original net data.
                raw_nets = (
                    circuit_spec.get("nets", []) if circuit_spec else []
                )
                data = await self._adapter.create_circuit(
                    circuit_type=circuit_type,
                    components=bridge_components,
                    connections=connections or [],
                    wire_segments=wire_segments or None,
                    save_path=save_path,
                    simulation_settings=simulation_settings,
                    nets=raw_nets or None,
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
