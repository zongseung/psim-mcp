"""Parameter management service.

Handles component parameter reads/writes and sweep configuration.
Extracted from the original monolithic ``SimulationService``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psim_mcp.shared.audit import AuditMiddleware
from psim_mcp.shared.response import ResponseBuilder
from psim_mcp.services.validators import (
    validate_component_id,
    validate_parameter_value,
    validate_string_length,
)

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.config import AppConfig
    from psim_mcp.shared.protocols import ProjectServiceProtocol


class ParameterService:
    """Parameter management service.

    Responsibilities:
    - Parameter input validation (identifier, value, length)
    - Delegating parameter operations to the adapter
    - Sweep parameter validation
    """

    def __init__(
        self,
        adapter: BasePsimAdapter,
        config: AppConfig,
        project_service: ProjectServiceProtocol,
    ) -> None:
        self._adapter = adapter
        self._config = config
        self._project = project_service
        self._logger = logging.getLogger(__name__)
        self._audit = AuditMiddleware()

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Validate inputs and set a component parameter."""

        async def _handler():
            if not self._project.is_project_open:
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
                return ResponseBuilder.error(
                    code="COMPONENT_NOT_FOUND",
                    message="지정된 컴포넌트를 찾을 수 없습니다.",
                )
            except Exception:
                self._logger.exception("Failed to set parameter")
                return ResponseBuilder.error(
                    code="SET_PARAMETER_FAILED",
                    message="파라미터 설정 중 오류가 발생했습니다.",
                )

        return await self._audit.execute_with_audit(
            "set_parameter",
            {"component_id": component_id, "parameter_name": parameter_name},
            _handler,
        )

    @staticmethod
    def _validate_identifier(value: str, field_name: str) -> None:
        """Ensure *value* is a valid identifier.

        Raises:
            ValueError: If validation fails.
        """
        if not value:
            raise ValueError(f"{field_name} must not be empty.")
        if not validate_component_id(value):
            raise ValueError(
                f"Invalid {field_name}: '{value}'. "
                "Must start with a letter, contain only letters/digits/underscores, "
                "and be at most 64 characters."
            )
