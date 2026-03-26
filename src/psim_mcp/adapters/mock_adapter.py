"""Mock PSIM adapter for development on non-Windows platforms."""

from __future__ import annotations

import copy
import math
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
        param_count = sum(len(c.get("parameters", {})) for c in components)

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

    async def shutdown(self) -> None:
        """Mock adapter는 정리할 리소스가 없으므로 no-op."""
        pass

    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
        graph_file: str = "",
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

    async def extract_signals(
        self,
        graph_file: str = "",
        signals: list[str] | None = None,
        skip_ratio: float = 0.0,
        max_points: int = 2000,
    ) -> dict:
        """Return synthetic waveform samples derived from current parameters."""
        _ = graph_file
        waveform_library = _build_mock_signals(self._current_project, self._last_simulation)
        if signals is None:
            selected = dict(waveform_library)
        else:
            selected = {name: waveform_library[name] for name in signals if name in waveform_library}

        trimmed: dict[str, list[float]] = {}
        for name, values in selected.items():
            start = int(len(values) * max(0.0, min(skip_ratio, 0.95)))
            samples = values[start:]
            if len(samples) > max_points:
                step = max(1, len(samples) // max_points)
                samples = samples[::step]
            trimmed[name] = [round(v, 9) for v in samples]

        return {
            "signals": trimmed,
            "signal_names": list(trimmed.keys()),
            "point_count": len(next(iter(trimmed.values()), [])),
            "graph_file": graph_file or (self._last_simulation or {}).get("output_path", ""),
        }

    async def compute_metrics(
        self,
        metrics_spec: list[dict],
        graph_file: str = "",
        skip_ratio: float = 0.5,
        time_step: float = 1e-6,
    ) -> dict:
        """Compute metrics from the synthetic waveform samples."""
        signal_result = await self.extract_signals(
            graph_file=graph_file,
            signals=None,
            skip_ratio=0.0,
            max_points=5000,
        )
        signal_data = signal_result.get("signals", {})

        results: dict[str, float | dict[str, str]] = {}
        for spec in metrics_spec:
            metric_name = str(spec.get("name", ""))
            signal_name = str(spec.get("signal", ""))
            function_name = str(spec.get("function", ""))
            kwargs = spec.get("kwargs", {}) or {}

            values = signal_data.get(signal_name)
            if not values:
                results[metric_name] = {"error": f"signal '{signal_name}' not found"}
                continue

            try:
                if function_name == "mean":
                    result = _metric_mean(values, skip_ratio)
                elif function_name == "ripple_pp":
                    result = _metric_ripple_pp(values, skip_ratio)
                elif function_name == "ripple_percent":
                    result = _metric_ripple_percent(values, skip_ratio)
                elif function_name == "rms":
                    result = _metric_rms(values, skip_ratio)
                elif function_name == "peak":
                    result = _metric_peak(values, skip_ratio)
                elif function_name == "overshoot_percent":
                    result = _metric_overshoot_percent(
                        values,
                        float(kwargs.get("target", 0.0)),
                        skip_ratio,
                    )
                elif function_name == "settling_time":
                    result = _metric_settling_time(
                        values,
                        time_step,
                        float(kwargs.get("target", 0.0)),
                        float(kwargs.get("band", 0.02)),
                        skip_ratio,
                    )
                else:
                    results[metric_name] = {"error": f"unknown function '{function_name}'"}
                    continue
                results[metric_name] = round(float(result), 6)
            except Exception as exc:
                results[metric_name] = {"error": str(exc)}

        return {
            "metrics": results,
            "available_signals": list(signal_data.keys()),
            "graph_file": graph_file or (self._last_simulation or {}).get("output_path", ""),
        }

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
            "parameter_count": sum(len(c.get("parameters", {})) for c in components),
        }

    async def create_circuit(
        self,
        circuit_type: str,
        components: list[dict],
        connections: list[dict],
        save_path: str,
        wire_segments: list[dict] | None = None,
        simulation_settings: dict | None = None,
        psim_template: dict | None = None,
        nets: list[dict] | None = None,
    ) -> dict:
        """Mock circuit creation — stores the circuit as the current project."""
        import copy

        self._current_project = {
            "name": _stem_from_path(save_path),
            "path": save_path,
            "components": copy.deepcopy(components),
        }
        self._last_simulation = None

        return {
            "file_path": save_path,
            "circuit_type": circuit_type,
            "component_count": len(components),
            "connection_count": len(wire_segments or connections),
            "components": components,
            "connections": connections,
            "wire_segments": wire_segments or [],
            "simulation_settings": simulation_settings or {
                "time_step": 1e-5,
                "total_time": 0.1,
            },
            "status": "created",
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


def _build_mock_signals(current_project: dict | None, last_simulation: dict | None) -> dict[str, list[float]]:
    """Build deterministic synthetic waveforms from the current mock project."""
    if current_project is None:
        raise RuntimeError("No project is currently open.")
    if last_simulation is None:
        raise RuntimeError("No simulation results available.")

    component_map = {comp["id"]: comp for comp in current_project.get("components", [])}

    def _param(component_id: str, name: str, default: float) -> float:
        comp = component_map.get(component_id)
        if not comp:
            return default
        try:
            return float(comp.get("parameters", {}).get(name, default))
        except (TypeError, ValueError):
            return default

    vin = _param("V1", "voltage", 48.0)
    load_resistance = max(_param("R1", "resistance", 10.0), 0.5)
    inductance = max(_param("L1", "inductance", 47e-6), 1e-7)
    capacitance = max(_param("C1", "capacitance", 100e-6), 1e-8)
    magnetizing = max(_param("Lm", "inductance", inductance * 2.0), 1e-7)
    resonant_l = max(_param("Lr", "inductance", inductance * 0.5), 1e-7)
    resonant_c = max(_param("Cr", "capacitance", capacitance * 0.1), 1e-10)

    samples = 800
    vout_mean = vin * 0.25
    vout_mean *= 1.0 - 0.015 * abs(math.log10(inductance / 47e-6))
    vout_mean *= 1.0 - 0.012 * abs(math.log10(capacitance / 100e-6))
    vout_mean *= 1.0 - 0.01 * abs(math.log10(load_resistance / 10.0))
    vout_mean = max(vout_mean, 0.1)

    ripple_pp = 0.18 * (47e-6 / inductance) ** 0.35 * (100e-6 / capacitance) ** 0.45
    ripple_pp *= (load_resistance / 10.0) ** 0.08
    ripple_pp = max(0.01, min(ripple_pp, vout_mean * 0.15))

    inductor_current_mean = vout_mean / load_resistance
    inductor_current_ripple = max(0.02, 0.35 * (47e-6 / inductance) ** 0.4)
    magnetizing_peak = max(0.05, 0.4 * (47e-6 / magnetizing) ** 0.35)
    resonant_rms = max(0.05, 0.7 * (47e-6 / resonant_l) ** 0.25 * (10e-9 / resonant_c) ** 0.1)

    vout: list[float] = []
    il1: list[float] = []
    ilm: list[float] = []
    ilr: list[float] = []

    for idx in range(samples):
        phase = 2.0 * math.pi * idx / samples
        transient = math.exp(-idx / 80.0)
        vout.append(
            vout_mean
            + 0.5 * ripple_pp * math.sin(phase * 18.0)
            + 0.12 * vout_mean * transient
        )
        il1.append(
            inductor_current_mean
            + 0.5 * inductor_current_ripple * math.sin(phase * 18.0 + math.pi / 6.0)
        )
        ilm.append(
            0.5 * magnetizing_peak * (1.0 + math.sin(phase * 10.0 - math.pi / 4.0))
        )
        ilr.append(
            math.sqrt(2.0) * resonant_rms * math.sin(phase * 22.0)
        )

    return {
        "V(Vout)": vout,
        "I(L1)": il1,
        "I(Lm)": ilm,
        "I(Lr)": ilr,
    }


def _skip_values(values: list[float], skip_ratio: float) -> list[float]:
    start = int(len(values) * max(0.0, min(skip_ratio, 0.95)))
    trimmed = values[start:]
    if not trimmed:
        raise ValueError("metric input is empty after applying skip_ratio")
    return trimmed


def _metric_mean(values: list[float], skip_ratio: float) -> float:
    trimmed = _skip_values(values, skip_ratio)
    return sum(trimmed) / len(trimmed)


def _metric_ripple_pp(values: list[float], skip_ratio: float) -> float:
    trimmed = _skip_values(values, skip_ratio)
    return max(trimmed) - min(trimmed)


def _metric_ripple_percent(values: list[float], skip_ratio: float) -> float:
    mean_val = _metric_mean(values, skip_ratio)
    if mean_val == 0:
        return 0.0
    return _metric_ripple_pp(values, skip_ratio) / abs(mean_val) * 100.0


def _metric_rms(values: list[float], skip_ratio: float) -> float:
    trimmed = _skip_values(values, skip_ratio)
    return math.sqrt(sum(v * v for v in trimmed) / len(trimmed))


def _metric_peak(values: list[float], skip_ratio: float) -> float:
    trimmed = _skip_values(values, skip_ratio)
    return max(abs(v) for v in trimmed)


def _metric_overshoot_percent(values: list[float], target: float, skip_ratio: float) -> float:
    trimmed = _skip_values(values, skip_ratio)
    if target == 0:
        return 0.0
    return max(0.0, (max(trimmed) - target) / abs(target) * 100.0)


def _metric_settling_time(
    values: list[float],
    time_step: float,
    target: float,
    band: float,
    skip_ratio: float,
) -> float:
    trimmed = _skip_values(values, skip_ratio)
    if target == 0:
        return 0.0
    lower = target * (1.0 - band)
    upper = target * (1.0 + band)
    for idx, value in enumerate(trimmed):
        if all(lower <= later <= upper for later in trimmed[idx:]):
            return idx * time_step
    return len(trimmed) * time_step
