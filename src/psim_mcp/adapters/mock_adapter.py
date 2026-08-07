"""Mock PSIM adapter for development on non-Windows platforms."""

from __future__ import annotations

import asyncio  # noqa: F401  # noqa: ANYIO_OK
import copy
import math
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath, PureWindowsPath

from psim_mcp.adapters.base import BasePsimAdapter, SessionToken


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


# Canned PsimConvertToPython output for convert_to_python (buck-like RLC).
# Format mirrors real PSIM 2026 converter output so the importer pipeline
# can be exercised end-to-end in mock mode.
_MOCK_CONVERTED_SCRIPT = """
p1.PsimSetElmValue(sch, None, "TIMESTEP", "1E-06")
p1.PsimSetElmValue(sch, None, "TOTALTIME", "0.05")
nCreatedIndex = p1.PsimCreateNewElement(sch, "SIMCONTROL", "", DIRECTION = 0, AREA = [0, 0, 40, 40], PAGE=0, XFLIP=0, _OPTIONS_=0)
nCreatedIndex = p1.PsimCreateNewElement(sch, "VDC", "V1", AREA = [90, 100, 110, 150], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[100, 100, 100, 150], Amplitude = "48")
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_INDUCTOR", "L1", SubType="Level 1", AREA = [150, 90, 200, 110], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[150, 100, 200, 100], Inductance = "47u")
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_CAPACITOR", "C1", SubType="Level 1", AREA = [240, 100, 260, 150], DIRECTION = 90, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[250, 100, 250, 150], Capacitance = "100u")
nCreatedIndex = p1.PsimCreateNewElement(sch, "MULTI_RESISTOR", "R1", SubType="Level 1", AREA = [290, 100, 310, 150], DIRECTION = 90, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[300, 100, 300, 150], Resistance = "10")
nCreatedIndex = p1.PsimCreateNewElement(sch, "Ground", "Ground", AREA = [90, 150, 110, 170], DIRECTION = 0, PAGE=0, XFLIP=0, _OPTIONS_=16, PORTS=[100, 150])
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="100", Y1="100", X2="150", Y2="100")
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="200", Y1="100", X2="250", Y2="100")
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="250", Y1="100", X2="300", Y2="100")
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="100", Y1="150", X2="250", Y2="150")
nCreatedIndex = p1.PsimCreateNewElement(sch, "WIRE", "", PAGE=0, X1="250", Y1="150", X2="300", Y2="150")
nCreatedIndex = p1.PsimCreateNewElement(sch, "LABEL", "Vout", DIRECTION = 0, PORTS=[250, 100], PAGE=0, XFLIP=0, _OPTIONS_=16)
"""


class MockPsimAdapter(BasePsimAdapter):
    """In-memory mock that emulates PSIM responses for local development."""

    def __init__(self) -> None:
        self._current_project: dict | None = None
        self._last_simulation: dict | None = None
        self._session_lock = asyncio.Lock()
        self._session_token: SessionToken | None = None

    # ------------------------------------------------------------------
    # BasePsimAdapter interface
    # ------------------------------------------------------------------

    @property
    def is_project_open(self) -> bool:
        return self._current_project is not None

    @property
    def current_project_path(self) -> str | None:
        if self._current_project is None:
            return None
        return str(Path(self._current_project["path"]).resolve())

    @asynccontextmanager
    async def session_lease(self, study_dir: str) -> AsyncIterator[SessionToken]:
        _ = study_dir
        async with self._session_lock:
            token = SessionToken(secrets.token_hex(16))
            self._session_token = token
            try:
                yield token
            finally:
                self._session_token = None

    async def reset_session(self, token: SessionToken) -> None:
        self._check_session(token)
        self._current_project = None
        self._last_simulation = None

    def _check_session(self, token: SessionToken | None) -> None:
        if self._session_token is not None and token is not self._session_token:
            raise RuntimeError("SESSION_BUSY: PSIM session is reserved by an optimization")

    async def open_project(
        self,
        path: str,
        lease_token: SessionToken | None = None,
    ) -> dict:
        """Store a dummy project with pre-defined components."""
        self._check_session(lease_token)
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
        lease_token: SessionToken | None = None,
    ) -> dict:
        """Update a parameter on a mock component."""
        self._check_session(lease_token)
        if self._current_project is None:
            raise RuntimeError("No project is currently open.")

        for comp in self._current_project["components"]:
            if comp["id"] == component_id:
                params = comp["parameters"]
                parameter_key = {
                    "Inductance": "inductance",
                    "Capacitance": "capacitance",
                    "Resistance": "resistance",
                    "CurrentFlag": "CurrentFlag",
                }.get(parameter_name, parameter_name)
                if parameter_key not in params and parameter_key != "CurrentFlag":
                    raise ValueError(
                        f"Parameter '{parameter_name}' not found on component '{component_id}'. "
                        f"Available parameters: {list(params.keys())}"
                    )
                previous = params.get(parameter_key, 0)
                params[parameter_key] = value
                return {
                    "component_id": component_id,
                    "parameter_name": parameter_name,
                    "previous_value": previous,
                    "new_value": value,
                    "unit": _infer_unit(parameter_key),
                }

        available = [c["id"] for c in self._current_project["components"]]
        raise ValueError(f"Component '{component_id}' not found. Available components: {available}")

    async def run_simulation(
        self,
        options: dict | None = None,
        output_path: str = "",
        lease_token: SessionToken | None = None,
    ) -> dict:
        """Return a pre-built successful simulation result."""
        self._check_session(lease_token)
        if self._current_project is None:
            raise RuntimeError("No project is currently open.")

        start = time.monotonic()
        # Simulate a tiny processing delay (synchronous, no real work).
        elapsed = round(time.monotonic() - start + 1.23, 2)

        resolved_output = output_path or "/tmp/mock_result.smv"
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("mock simulation result", encoding="utf-8")

        result = {
            "status": "completed",
            "duration_seconds": elapsed,
            "result_file": resolved_output,
            "output_path": resolved_output,
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
        self._check_session(None)
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
        lease_token: SessionToken | None = None,
    ) -> dict:
        """Return synthetic waveform samples derived from current parameters."""
        self._check_session(lease_token)
        _ = graph_file
        waveform_library = _build_mock_signals(self._current_project, self._last_simulation)
        if signals is None:
            selected = dict(waveform_library)
        else:
            selected = {
                name: waveform_library[name] for name in signals if name in waveform_library
            }

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
        lease_token: SessionToken | None = None,
    ) -> dict:
        """Compute metrics from the synthetic waveform samples."""
        self._check_session(lease_token)
        signal_result = await self.extract_signals(
            graph_file=graph_file,
            signals=None,
            skip_ratio=0.0,
            max_points=5000,
            lease_token=lease_token,
        )
        signal_data = signal_result.get("signals", {})

        results: dict[str, float | dict[str, str]] = {}
        windows: dict[str, dict[str, int]] = {}
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
                metric_values = values
                metric_skip = skip_ratio
                window = spec.get("window")
                if window:
                    start_index = math.floor(len(values) * float(window["start_fraction"]))
                    end_index = math.ceil(len(values) * float(window["end_fraction"]))
                    metric_values = values[start_index:end_index]
                    minimum = int(window["min_samples"])
                    if len(metric_values) < minimum:
                        raise ValueError(
                            f"metric window has {len(metric_values)} samples; requires {minimum}"
                        )
                    windows[metric_name] = {
                        "start_index": start_index,
                        "end_index": end_index,
                        "point_count": len(metric_values),
                    }
                    metric_skip = 0.0

                if function_name == "mean":
                    result = _metric_mean(metric_values, metric_skip)
                elif function_name == "ripple_pp":
                    result = _metric_ripple_pp(metric_values, metric_skip)
                elif function_name == "ripple_percent":
                    result = _metric_ripple_percent(metric_values, metric_skip)
                elif function_name == "rms":
                    result = _metric_rms(metric_values, metric_skip)
                elif function_name == "peak":
                    result = _metric_peak(metric_values, metric_skip)
                elif function_name == "overshoot_percent":
                    result = _metric_overshoot_percent(
                        metric_values,
                        float(kwargs.get("target", 0.0)),
                        metric_skip,
                    )
                elif function_name == "settling_time":
                    result = _metric_settling_time(
                        metric_values,
                        time_step,
                        float(kwargs.get("target", 0.0)),
                        float(kwargs.get("band", 0.02)),
                        metric_skip,
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
            "windows": windows,
        }

    async def get_status(self) -> dict:
        """Return current mock adapter status."""
        self._check_session(None)
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
        self._check_session(None)
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

    async def convert_to_python(self, path: str, output_path: str = "") -> dict:
        """Return a canned converted script (buck-like RLC) for testing.

        Mirrors the real bridge response shape:
        ``{"success": True, "data": {"script_path", "script_text", ...}}``.
        """
        self._check_session(None)
        script_text = _MOCK_CONVERTED_SCRIPT
        return {
            "success": True,
            "data": {
                "source_path": path,
                "script_path": output_path or f"{path}.converted.py",
                "script_text": script_text,
                "size": len(script_text),
            },
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


def _build_mock_signals(
    current_project: dict | None, last_simulation: dict | None
) -> dict[str, list[float]]:
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
            vout_mean + 0.5 * ripple_pp * math.sin(phase * 18.0) + 0.12 * vout_mean * transient
        )
        il1.append(
            inductor_current_mean
            + 0.5 * inductor_current_ripple * math.sin(phase * 18.0 + math.pi / 6.0)
        )
        ilm.append(0.5 * magnetizing_peak * (1.0 + math.sin(phase * 10.0 - math.pi / 4.0)))
        ilr.append(math.sqrt(2.0) * resonant_rms * math.sin(phase * 22.0))

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
