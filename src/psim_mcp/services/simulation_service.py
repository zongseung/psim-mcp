"""Simulation service -- orchestrates validation, adapter calls, and response formatting."""

from __future__ import annotations

import logging
import time
from typing import Any

from psim_mcp.adapters.base import BasePsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.services.response import ResponseBuilder
from psim_mcp.utils.logging import SecurityAuditLogger, hash_input
from psim_mcp.utils.sanitize import sanitize_for_llm_context, sanitize_path_for_display
from psim_mcp.validators import validate_circuit as validate_circuit_spec
from psim_mcp.services.validators import (
    validate_component_id,
    validate_output_dir,
    validate_output_format,
    validate_parameter_name,
    validate_parameter_value,
    validate_project_path,
    validate_signals_list,
    validate_simulation_options,
    validate_string_length,
)


class SimulationService:
    """High-level service that mediates between the tool layer and adapters.

    Responsibilities:
    - Input validation and path security
    - Delegation to the injected :class:`BasePsimAdapter`
    - Consistent success / error response formatting
    """

    def __init__(self, adapter: BasePsimAdapter, config: AppConfig) -> None:
        self._adapter = adapter
        self._config = config
        self._logger = logging.getLogger(__name__)
        self._audit = SecurityAuditLogger()
        self._last_simulation: dict | None = None

    # ------------------------------------------------------------------
    # Audit helper
    # ------------------------------------------------------------------

    async def _execute_with_audit(
        self, tool_name: str, input_summary: dict, handler
    ) -> dict:
        """Execute *handler* with timing and audit logging."""
        start = time.monotonic()
        success = False
        try:
            result = await handler()
            success = result.get("success", False)
            return result
        finally:
            duration = (time.monotonic() - start) * 1000
            self._audit.log_tool_call(tool_name, input_summary, duration, success)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def open_project(self, path: str) -> dict:
        """Validate and open a PSIM project file.

        Returns:
            Formatted success/error dict.
        """

        async def _handler():
            vr = validate_project_path(path, self._config.allowed_project_dirs or None)
            if not vr.is_valid:
                self._audit.log_path_blocked(path, vr.error_code or "VALIDATION_ERROR")
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
                return ResponseBuilder.error(
                    code="OPEN_PROJECT_FAILED",
                    message="프로젝트를 여는 중 오류가 발생했습니다.",
                )

        return await self._execute_with_audit(
            "open_project", {"path_hash": hash_input(path)}, _handler,
        )

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Validate inputs and set a component parameter."""

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

        return await self._execute_with_audit(
            "set_parameter",
            {"component_id": component_id, "parameter_name": parameter_name},
            _handler,
        )

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
                return ResponseBuilder.error(code="SIMULATION_FAILED", message="시뮬레이션 실행 중 오류가 발생했습니다.")

        return await self._execute_with_audit("run_simulation", {}, _handler)

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

            # Fallback to config output dir when not specified
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

            try:
                data = await self._adapter.export_results(output_dir, format, signals)
                return ResponseBuilder.success(data, "결과가 성공적으로 내보내졌습니다.")
            except Exception:
                self._logger.exception("Export failed")
                return ResponseBuilder.error(code="EXPORT_FAILED", message="결과 내보내기 중 오류가 발생했습니다.")

        return await self._execute_with_audit(
            "export_results", {"output_dir_hash": hash_input(output_dir or "")}, _handler,
        )

    async def get_project_info(self) -> dict:
        """Return detailed structural information about the currently open project."""

        async def _handler():
            if not self._is_project_open:
                return ResponseBuilder.error(
                    code="NO_PROJECT",
                    message="No project is currently open.",
                    suggestion="Use open_project to load a .psimsch file first.",
                )

            try:
                data = await self._adapter.get_project_info()
                return ResponseBuilder.success(data, "프로젝트 정보를 조회했습니다.")
            except Exception:
                self._logger.exception("Failed to get project info")
                return ResponseBuilder.error(
                    code="PROJECT_INFO_FAILED",
                    message="프로젝트 정보 조회 중 오류가 발생했습니다.",
                )

        return await self._execute_with_audit("get_project_info", {}, _handler)

    async def get_status(self) -> dict:
        """Return current adapter and server status."""

        async def _handler():
            try:
                data = await self._adapter.get_status()
                return ResponseBuilder.success(data, "Status retrieved.")
            except Exception:
                self._logger.exception("Status check failed")
                return ResponseBuilder.error(code="STATUS_FAILED", message="상태 확인 중 오류가 발생했습니다.")

        return await self._execute_with_audit("get_status", {}, _handler)

    async def create_circuit(
        self,
        circuit_type: str,
        components: list[dict],
        connections: list[dict],
        save_path: str,
        simulation_settings: dict | None = None,
    ) -> dict:
        """Validate inputs and create a new PSIM circuit."""

        async def _handler():
            if not circuit_type or not isinstance(circuit_type, str):
                return ResponseBuilder.error(
                    code="VALIDATION_ERROR",
                    message="circuit_type은 비어 있지 않은 문자열이어야 합니다.",
                )

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

            # Validate circuit spec (blocking — reject invalid circuits)
            validation_input = {"components": components, "nets": []}
            validation = validate_circuit_spec(validation_input)
            if not validation.is_valid:
                error_messages = "; ".join(e.message for e in validation.errors)
                return ResponseBuilder.error(
                    code="CIRCUIT_VALIDATION_FAILED",
                    message=f"회로 검증 실패: {error_messages}",
                )

            try:
                data = await self._adapter.create_circuit(
                    circuit_type=circuit_type,
                    components=components,
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

        return await self._execute_with_audit(
            "create_circuit",
            {"circuit_type": circuit_type, "component_count": len(components)},
            _handler,
        )

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @property
    def _is_project_open(self) -> bool:
        """Check if a project is currently open via the adapter interface."""
        return self._adapter.is_project_open

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> None:
        """Ensure *value* is a valid identifier (letters, digits, underscores; 1-64 chars).

        Raises:
            ValueError: If validation fails.
        """
        if not value:
            raise ValueError(f"{field_name} must not be empty.")
        validator = validate_component_id  # same regex for both
        if not validator(value):
            raise ValueError(
                f"Invalid {field_name}: '{value}'. "
                "Must start with a letter, contain only letters/digits/underscores, "
                "and be at most 64 characters."
            )
