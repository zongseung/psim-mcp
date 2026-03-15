"""Simulation service -- orchestrates validation, adapter calls, and response formatting."""

from __future__ import annotations

import logging
from typing import Any

from psim_mcp.adapters.base import BasePsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.services.validators import (
    validate_component_id,
    validate_output_format,
    validate_parameter_name,
    validate_parameter_value,
    validate_project_path,
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
        self._last_simulation: dict | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def open_project(self, path: str) -> dict:
        """Validate and open a PSIM project file.

        Returns:
            Formatted success/error dict.
        """
        vr = validate_project_path(path, self._config.allowed_project_dirs or None)
        if not vr.is_valid:
            return self._format_error(
                code=vr.error_code or "VALIDATION_ERROR",
                message=vr.error_message or "Invalid project path.",
                suggestion="Provide an absolute path to a .psimsch file.",
            )

        try:
            data = await self._adapter.open_project(path)
            return self._format_success(data, f"Project '{data.get('name', path)}' opened successfully.")
        except Exception as exc:
            self._logger.exception("Failed to open project: %s", path)
            return self._format_error(
                code="OPEN_PROJECT_FAILED",
                message=str(exc),
            )

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Validate inputs and set a component parameter."""
        if not self._is_project_open:
            return self._format_error(
                code="NO_PROJECT",
                message="No project is currently open.",
                suggestion="Use open_project to load a .psimsch file first.",
            )

        try:
            self._validate_identifier(component_id, "component_id")
            self._validate_identifier(parameter_name, "parameter_name")
        except ValueError as exc:
            return self._format_error(code="VALIDATION_ERROR", message=str(exc))

        if not validate_parameter_value(value):
            return self._format_error(
                code="VALIDATION_ERROR",
                message=f"Invalid parameter value: {value!r}. Must be int, float, or str.",
            )

        try:
            data = await self._adapter.set_parameter(component_id, parameter_name, value)
            return self._format_success(
                data,
                f"Parameter '{parameter_name}' on '{component_id}' set to {value}.",
            )
        except ValueError as exc:
            return self._format_error(code="COMPONENT_NOT_FOUND", message=str(exc))
        except Exception as exc:
            self._logger.exception("Failed to set parameter")
            return self._format_error(code="SET_PARAMETER_FAILED", message=str(exc))

    async def run_simulation(self, options: dict | None = None) -> dict:
        """Run a simulation on the currently open project."""
        if not self._is_project_open:
            return self._format_error(
                code="NO_PROJECT",
                message="No project is currently open.",
                suggestion="Use open_project to load a .psimsch file first.",
            )

        try:
            data = await self._adapter.run_simulation(options)
            self._last_simulation = data
            return self._format_success(data, "Simulation completed.")
        except Exception as exc:
            self._logger.exception("Simulation failed")
            return self._format_error(code="SIMULATION_FAILED", message=str(exc))

    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> dict:
        """Export the most recent simulation results."""
        if self._last_simulation is None:
            return self._format_error(
                code="NO_SIMULATION",
                message="No simulation results available to export.",
                suggestion="Run a simulation first using run_simulation.",
            )

        if not validate_output_format(format):
            return self._format_error(
                code="INVALID_FORMAT",
                message=f"Unsupported export format: '{format}'. Supported: json, csv.",
            )

        try:
            data = await self._adapter.export_results(output_dir, format, signals)
            return self._format_success(data, f"Results exported to {output_dir}.")
        except Exception as exc:
            self._logger.exception("Export failed")
            return self._format_error(code="EXPORT_FAILED", message=str(exc))

    async def get_status(self) -> dict:
        """Return current adapter and server status."""
        try:
            data = await self._adapter.get_status()
            return self._format_success(data, "Status retrieved.")
        except Exception as exc:
            self._logger.exception("Status check failed")
            return self._format_error(code="STATUS_FAILED", message=str(exc))

    # ------------------------------------------------------------------
    # Response helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_success(data: Any, message: str) -> dict:
        """Wrap *data* in a standard success envelope."""
        return {"success": True, "data": data, "message": message}

    @staticmethod
    def _format_error(
        code: str,
        message: str,
        suggestion: str | None = None,
    ) -> dict:
        """Wrap an error in a standard error envelope."""
        return {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "suggestion": suggestion,
            },
        }

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @property
    def _is_project_open(self) -> bool:
        """Heuristic check -- delegates to the adapter's internal state."""
        adapter = self._adapter
        # MockPsimAdapter exposes _current_project; for others fall back to
        # optimistic True (the adapter itself will raise if nothing is open).
        if hasattr(adapter, "_current_project"):
            return adapter._current_project is not None  # type: ignore[attr-defined]
        return True

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
