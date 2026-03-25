"""Simulation service -- runs simulations and manages results.

This is the slimmed-down version after MSA refactoring.  Project management,
parameter handling, and circuit creation have been extracted into dedicated
services (``ProjectService``, ``ParameterService``, ``CircuitDesignService``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psim_mcp.shared.audit import AuditMiddleware
from psim_mcp.shared.response import ResponseBuilder
from psim_mcp.utils.logging import hash_input
from psim_mcp.utils.sanitize import sanitize_for_llm_context, sanitize_path_for_display
from psim_mcp.services.validators import (
    validate_component_id,
    validate_output_dir,
    validate_output_format,
    validate_parameter_value,
    validate_project_path,
    validate_save_path,
    validate_signals_list,
    validate_simulation_options,
    validate_string_length,
)

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.config import AppConfig
    from psim_mcp.shared.protocols import ProjectServiceProtocol


def _get_allowed_save_dirs(config: AppConfig | None) -> list[str] | None:
    """Resolve allowed output roots for newly created schematics."""
    if config is None:
        return None
    if config.allowed_project_dirs:
        return config.allowed_project_dirs
    if config.psim_mode == "real" and config.psim_project_dir is not None:
        return [str(config.psim_project_dir)]
    return None


class SimulationService:
    """Simulation execution and result management.

    After MSA refactoring this service only handles:
    - Simulation execution
    - Result export
    - Result comparison (P1)

    For backward compatibility it also retains delegate methods that forward
    to the appropriate domain service when called via legacy code paths.

    Phase 1-5 boundary: This service remains a compatibility layer, but it can
    now consume enriched circuit payloads that include graph/layout/routing
    projections in addition to legacy component/connection data.
    """

    def __init__(
        self,
        adapter: BasePsimAdapter,
        config: AppConfig,
        project_service: ProjectServiceProtocol | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._project = project_service
        self._logger = logging.getLogger(__name__)
        self._audit = AuditMiddleware()
        self._last_simulation: dict | None = None

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------

    async def run_simulation(self, options: dict | None = None) -> dict:
        """Run a simulation on the currently open project."""

        async def _handler():
            if not self._is_project_open:
                return ResponseBuilder.error(
                    code="NO_PROJECT",
                    message="No project is currently open.",
                    suggestion="Use open_project to load a .psimsch file first.",
                )

            vr = validate_simulation_options(options, self._config.simulation_timeout)
            if not vr.is_valid:
                return ResponseBuilder.error(
                    code=vr.error_code or "VALIDATION_ERROR",
                    message=vr.error_message or "Invalid simulation options.",
                )

            try:
                data = await self._adapter.run_simulation(options)
                self._last_simulation = data
                return ResponseBuilder.success(data, "Simulation completed.")
            except Exception:
                self._logger.exception("Simulation failed")
                return ResponseBuilder.error(
                    code="SIMULATION_FAILED",
                    message="시뮬레이션 실행 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit("run_simulation", {}, _handler)

    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> dict:
        """Export the most recent simulation results."""

        async def _handler():
            nonlocal output_dir

            if self._last_simulation is None:
                return ResponseBuilder.error(
                    code="NO_SIMULATION",
                    message="No simulation results available to export.",
                    suggestion="Run a simulation first using run_simulation.",
                )

            if output_dir is None:
                if self._config.psim_output_dir:
                    output_dir = str(self._config.psim_output_dir)
                else:
                    return ResponseBuilder.error(
                        code="INVALID_INPUT",
                        message="출력 디렉터리가 지정되지 않았고, 기본 출력 디렉터리(PSIM_OUTPUT_DIR)도 설정되어 있지 않습니다.",
                        suggestion="output_dir를 지정하거나 .env에 PSIM_OUTPUT_DIR을 설정하세요.",
                    )

            vr = validate_output_dir(output_dir)
            if not vr.is_valid:
                return ResponseBuilder.error(
                    code=vr.error_code or "VALIDATION_ERROR",
                    message=vr.error_message or "Invalid output directory.",
                )

            vr = validate_signals_list(signals)
            if not vr.is_valid:
                return ResponseBuilder.error(
                    code=vr.error_code or "VALIDATION_ERROR",
                    message=vr.error_message or "Invalid signals list.",
                )

            if not validate_output_format(format):
                return ResponseBuilder.error(
                    code="INVALID_FORMAT",
                    message=f"Unsupported export format: '{format}'. Supported: json, csv.",
                )

            graph_file = ""
            if self._last_simulation:
                sim_data = self._last_simulation.get("data", {}) or {}
                graph_file = sim_data.get("output_path", "")

            try:
                data = await self._adapter.export_results(
                    output_dir, format, signals, graph_file=graph_file,
                )
                return ResponseBuilder.success(data, "결과가 성공적으로 내보내졌습니다.")
            except Exception:
                self._logger.exception("Export failed")
                return ResponseBuilder.error(
                    code="EXPORT_FAILED",
                    message="결과 내보내기 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit(
            "export_results",
            {"output_dir_hash": hash_input(output_dir or "")},
            _handler,
        )

    @property
    def last_simulation(self) -> dict | None:
        return self._last_simulation

    # ------------------------------------------------------------------
    # Backward-compatibility delegates
    # ------------------------------------------------------------------
    # These methods are retained so that legacy tool code and existing tests
    # that call ``service.open_project()`` etc. continue to work during the
    # transition period.  They will be removed in a future cleanup pass.

    async def open_project(self, path: str) -> dict:
        """Delegate to ProjectService (backward compat)."""
        if self._project is not None:
            return await self._project.open_project(path)
        # Inline fallback for tests that create SimulationService without project_service
        return await self._legacy_open_project(path)

    async def get_project_info(self) -> dict:
        """Delegate to ProjectService (backward compat)."""
        if self._project is not None:
            return await self._project.get_project_info()
        return await self._legacy_get_project_info()

    async def get_status(self) -> dict:
        """Delegate to ProjectService (backward compat)."""
        if self._project is not None:
            return await self._project.get_status()
        return await self._legacy_get_status()

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Backward compat: parameter setting (will be removed)."""
        async def _handler():
            if not self._is_project_open:
                return ResponseBuilder.error(
                    code="NO_PROJECT",
                    message="No project is currently open.",
                    suggestion="Use open_project to load a .psimsch file first.",
                )

            try:
                self._validate_identifier(component_id, "component_id")
                self._validate_identifier(parameter_name, "parameter_name")
            except ValueError as exc:
                self._audit.log_invalid_input(
                    "set_parameter", "component_id/parameter_name", str(exc),
                )
                return ResponseBuilder.error(code="VALIDATION_ERROR", message=str(exc))

            if not validate_parameter_value(value):
                self._audit.log_invalid_input(
                    "set_parameter", "value", f"Invalid type: {type(value).__name__}",
                )
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message=f"Invalid parameter value: {value!r}. Must be int, float, or str.",
                )

            if isinstance(value, str):
                vr = validate_string_length(value, max_length=1024, field_name="parameter value")
                if not vr.is_valid:
                    return ResponseBuilder.error(
                        code=vr.error_code or "VALIDATION_ERROR",
                        message=vr.error_message or "Invalid parameter value.",
                    )

            try:
                data = await self._adapter.set_parameter(component_id, parameter_name, value)
                return ResponseBuilder.success(
                    data,
                    f"Parameter '{parameter_name}' on '{component_id}' set to {value}.",
                )
            except ValueError:
                self._logger.warning("Component not found: %s", component_id)
                return ResponseBuilder.error(code="COMPONENT_NOT_FOUND", message="지정된 컴포넌트를 찾을 수 없습니다.")
            except Exception:
                self._logger.exception("Failed to set parameter")
                return ResponseBuilder.error(code="SET_PARAMETER_FAILED", message="파라미터 설정 중 오류가 발생했습니다.")

        return await self._audit.execute_with_audit(
            "set_parameter",
            {"component_id": component_id, "parameter_name": parameter_name},
            _handler,
        )

    async def create_circuit(
        self,
        circuit_type: str,
        components: list[dict],
        connections: list[dict],
        save_path: str,
        simulation_settings: dict | None = None,
        circuit_spec: dict | None = None,
        wire_segments: list[dict] | None = None,
    ) -> dict:
        """Backward compat: circuit creation (will be removed)."""
        from psim_mcp.bridge.wiring import nets_to_connections
        from psim_mcp.data.component_library import resolve_psim_element_type
        from psim_mcp.validators import validate_circuit as validate_circuit_spec

        def _nets_to_connections(nets: list[dict]) -> list[dict]:
            conns = []
            for net in nets:
                pins = net.get("pins", [])
                for i in range(len(pins) - 1):
                    conns.append({"from": pins[i], "to": pins[i + 1]})
            return conns

        def _enrich(comps: list[dict]) -> list[dict]:
            enriched = []
            for c in comps:
                item = dict(c)
                item["psim_element_type"] = resolve_psim_element_type(str(item.get("type", "")))
                enriched.append(item)
            return enriched

        async def _handler():
            nonlocal components, connections, wire_segments

            if not circuit_type or not isinstance(circuit_type, str):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="circuit_type은 비어 있지 않은 문자열이어야 합니다.",
                )

            if circuit_spec is not None:
                graph_data = circuit_spec.get("graph")
                layout_data = circuit_spec.get("layout")
                routing_data = circuit_spec.get("routing") or circuit_spec.get("wire_routing")

                if graph_data is not None and layout_data is not None:
                    try:
                        from psim_mcp.layout.materialize import materialize_to_legacy
                        from psim_mcp.layout.models import SchematicLayout
                        from psim_mcp.synthesis.graph import CircuitGraph

                        graph = CircuitGraph.from_dict(graph_data) if isinstance(graph_data, dict) else graph_data
                        layout = SchematicLayout.from_dict(layout_data) if isinstance(layout_data, dict) else layout_data
                        components, nets = materialize_to_legacy(graph, layout)
                    except Exception:
                        components = circuit_spec.get("components", components)
                        nets = circuit_spec.get("nets", [])
                else:
                    components = circuit_spec.get("components", components)
                    nets = circuit_spec.get("nets", [])

                wire_segments = circuit_spec.get("wire_segments", wire_segments)
                if not wire_segments and routing_data is not None:
                    try:
                        from psim_mcp.routing.models import WireRouting

                        routing = WireRouting.from_dict(routing_data) if isinstance(routing_data, dict) else routing_data
                        wire_segments = routing.to_legacy_segments()
                    except Exception:
                        pass

                if nets:
                    try:
                        connections = nets_to_connections(nets)
                    except Exception:
                        connections = _nets_to_connections(nets)

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
                    suggestion="Use a .psimsch path under the configured project root.",
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

            bridge_components = _enrich(components)

            try:
                data = await self._adapter.create_circuit(
                    circuit_type=circuit_type,
                    components=bridge_components,
                    connections=connections or [],
                    wire_segments=wire_segments,
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
            {"circuit_type": circuit_type, "component_count": len(components)},
            _handler,
        )

    # ------------------------------------------------------------------
    # Legacy internal helpers (backward compat)
    # ------------------------------------------------------------------

    @property
    def _is_project_open(self) -> bool:
        if self._project is not None:
            return self._project.is_project_open
        return self._adapter.is_project_open

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> None:
        if not value:
            raise ValueError(f"{field_name} must not be empty.")
        if not validate_component_id(value):
            raise ValueError(
                f"Invalid {field_name}: '{value}'. "
                "Must start with a letter, contain only letters/digits/underscores, "
                "and be at most 64 characters."
            )

    async def _legacy_open_project(self, path: str) -> dict:
        async def _handler():
            vr = validate_project_path(path, self._config.allowed_project_dirs or None)
            if not vr.is_valid:
                return ResponseBuilder.error(
                    code=vr.error_code or "VALIDATION_ERROR",
                    message=vr.error_message or "Invalid project path.",
                    suggestion="Provide an absolute path to a .psimsch file.",
                )
            try:
                data = await self._adapter.open_project(path)
                display_name = sanitize_for_llm_context(data.get('name', sanitize_path_for_display(path)))
                return ResponseBuilder.success(data, f"Project '{display_name}' opened successfully.")
            except Exception:
                self._logger.exception("Failed to open project: %s", path)
                return ResponseBuilder.error(code="OPEN_PROJECT_FAILED", message="프로젝트를 여는 중 오류가 발생했습니다.")
        return await self._audit.execute_with_audit("open_project", {"path_hash": hash_input(path)}, _handler)

    async def _legacy_get_project_info(self) -> dict:
        async def _handler():
            if not self._adapter.is_project_open:
                return ResponseBuilder.error(code="NO_PROJECT", message="No project is currently open.", suggestion="Use open_project to load a .psimsch file first.")
            try:
                data = await self._adapter.get_project_info()
                return ResponseBuilder.success(data, "프로젝트 정보를 조회했습니다.")
            except Exception:
                self._logger.exception("Failed to get project info")
                return ResponseBuilder.error(code="PROJECT_INFO_FAILED", message="프로젝트 정보 조회 중 오류가 발생했습니다.")
        return await self._audit.execute_with_audit("get_project_info", {}, _handler)

    async def _legacy_get_status(self) -> dict:
        async def _handler():
            try:
                data = await self._adapter.get_status()
                return ResponseBuilder.success(data, "Status retrieved.")
            except Exception:
                self._logger.exception("Status check failed")
                return ResponseBuilder.error(code="STATUS_FAILED", message="상태 확인 중 오류가 발생했습니다.")
        return await self._audit.execute_with_audit("get_status", {}, _handler)
