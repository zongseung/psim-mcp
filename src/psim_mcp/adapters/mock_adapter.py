"""Mock PSIM adapter for development on non-Windows platforms."""

from __future__ import annotations

import copy
import time
from pathlib import PurePosixPath, PureWindowsPath

from psim_mcp.adapters.base import BasePsimAdapter


def _stem_from_path(path: str) -> str:
    """Extract the file stem regardless of OS path style."""
    # Try Windows-style first (contains backslash), then POSIX.
    if "\\" in path:
        return PureWindowsPath(path).stem
    return PurePosixPath(path).stem


# Default component catalogue used by the mock adapter.
_DEFAULT_COMPONENTS: list[dict] = [
    {
        "id": "V1",
        "type": "DC_Source",
        "parameters": {"voltage": 48.0},
    },
    {
        "id": "SW1",
        "type": "MOSFET",
        "parameters": {
            "switching_frequency": 50000,
            "on_resistance": 0.01,
        },
    },
    {
        "id": "L1",
        "type": "Inductor",
        "parameters": {"inductance": 47e-6},
    },
    {
        "id": "C1",
        "type": "Capacitor",
        "parameters": {"capacitance": 100e-6},
    },
    {
        "id": "R1",
        "type": "Resistor",
        "parameters": {"resistance": 10.0},
    },
    {
        "id": "D1",
        "type": "Diode",
        "parameters": {"forward_voltage": 0.7},
    },
]


class MockPsimAdapter(BasePsimAdapter):
    """In-memory mock that emulates PSIM responses for local development."""

    def __init__(self) -> None:
        self._current_project: dict | None = None
        self._last_simulation: dict | None = None

    # ------------------------------------------------------------------
    # BasePsimAdapter interface
    # ------------------------------------------------------------------

    @property
    def is_project_open(self) -> bool:
        return self._current_project is not None

    async def open_project(self, path: str) -> dict:
        """Store a dummy project with pre-defined components."""
        components = copy.deepcopy(_DEFAULT_COMPONENTS)
        param_count = sum(len(c["parameters"]) for c in components)

        self._current_project = {
            "name": _stem_from_path(path),
            "path": path,
            "components": components,
        }
        # Reset last simulation when opening a new project.
        self._last_simulation = None

        return {
            "name": self._current_project["name"],
            "path": path,
            "components": components,
            "component_count": len(components),
            "parameter_count": param_count,
        }

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Update a parameter on a mock component."""
        if self._current_project is None:
            raise RuntimeError("No project is currently open.")

        for comp in self._current_project["components"]:
            if comp["id"] == component_id:
                params = comp["parameters"]
                if parameter_name not in params:
                    raise ValueError(
                        f"Parameter '{parameter_name}' not found on component '{component_id}'. "
                        f"Available parameters: {list(params.keys())}"
                    )
                previous = params[parameter_name]
                params[parameter_name] = value
                return {
                    "component_id": component_id,
                    "parameter_name": parameter_name,
                    "previous_value": previous,
                    "new_value": value,
                    "unit": _infer_unit(parameter_name),
                }

        available = [c["id"] for c in self._current_project["components"]]
        raise ValueError(
            f"Component '{component_id}' not found. "
            f"Available components: {available}"
        )

    async def run_simulation(self, options: dict | None = None) -> dict:
        """Return a pre-built successful simulation result."""
        if self._current_project is None:
            raise RuntimeError("No project is currently open.")

        start = time.monotonic()
        # Simulate a tiny processing delay (synchronous, no real work).
        elapsed = round(time.monotonic() - start + 1.23, 2)

        result = {
            "status": "completed",
            "duration_seconds": elapsed,
            "result_file": "/tmp/mock_result.smv",
            "summary": {
                "output_voltage_avg": 12.01,
                "output_voltage_ripple": 0.15,
                "efficiency": 95.3,
                "warnings": [],
            },
        }
        self._last_simulation = result
        return result

    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> dict:
        """Return a mock list of exported files."""
        if self._last_simulation is None:
            raise RuntimeError("No simulation results to export.")

        exported_signals = signals or [
            "output_voltage",
            "output_current",
            "inductor_current",
        ]
        files = [
            {
                "path": f"{output_dir}/results.{format}",
                "format": format,
                "size_bytes": 524288,
                "signals_exported": exported_signals,
                "data_points": 10000,
            }
        ]
        return {"exported_files": files}

    async def get_status(self) -> dict:
        """Return current mock adapter status."""
        project_info: dict | None = None
        if self._current_project is not None:
            project_info = {
                "name": self._current_project["name"],
                "path": self._current_project["path"],
            }

        simulation_info: dict | None = None
        if self._last_simulation is not None:
            simulation_info = {
                "status": self._last_simulation["status"],
                "duration_seconds": self._last_simulation["duration_seconds"],
            }

        return {
            "mode": "mock",
            "psim_connected": False,
            "psim_version": None,
            "current_project": project_info,
            "last_simulation": simulation_info,
            "server": {
                "uptime_seconds": 0,
                "version": "0.1.0",
            },
        }

    async def get_project_info(self) -> dict:
        """Return detailed project information."""
        if self._current_project is None:
            raise RuntimeError("No project is currently open.")

        components = self._current_project["components"]
        return {
            "name": self._current_project["name"],
            "path": self._current_project["path"],
            "components": components,
            "component_count": len(components),
            "parameter_count": sum(len(c["parameters"]) for c in components),
        }


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_UNIT_MAP: dict[str, str] = {
    "voltage": "V",
    "resistance": "ohm",
    "on_resistance": "ohm",
    "inductance": "H",
    "capacitance": "F",
    "switching_frequency": "Hz",
    "forward_voltage": "V",
}


def _infer_unit(parameter_name: str) -> str:
    """Return a plausible unit string for a known parameter name."""
    return _UNIT_MAP.get(parameter_name, "")
