"""Tests for analysis/optimization tool wiring in mock mode."""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.server import create_app


@pytest.fixture
def analysis_test_root() -> Path:
    root = Path("output") / "analysis_tools_test"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def mock_config(analysis_test_root: Path) -> AppConfig:
    out = analysis_test_root / "output"
    out.mkdir(exist_ok=True)
    return AppConfig(
        psim_mode="mock",
        psim_project_dir=analysis_test_root / "projects",
        psim_output_dir=out,
        log_dir=analysis_test_root / "logs",
        allowed_project_dirs=[str(analysis_test_root.resolve())],
    )


@pytest.fixture
def project_path(analysis_test_root: Path) -> Path:
    path = analysis_test_root / "analysis-demo.psimsch"
    path.write_text("<psim/>")
    return path


async def test_analyze_simulation_tool_with_mock_adapter(
    mock_config: AppConfig,
    project_path: Path,
):
    """analyze_simulation should be callable through the MCP tool surface."""
    app = create_app(mock_config)
    service = app._psim_service

    await service.open_project(str(project_path))

    raw = await app._tool_manager.call_tool(
        "analyze_simulation",
        {"topology": "buck", "targets": {"output_voltage_mean": 12.0}, "show_waveform": False},
        convert_result=False,
    )
    result = json.loads(raw)

    assert result["success"] is True
    assert "metrics" in result["data"]
    assert "comparison" in result["data"]
    assert "output_voltage_mean" in result["data"]["metrics"]


async def test_optimize_circuit_tool_with_fake_optuna(
    mock_config: AppConfig,
    project_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """optimize_circuit should run end-to-end when optuna is available."""

    class FakeTrial:
        def __init__(self) -> None:
            self.params: dict[str, float] = {}

        def suggest_float(self, name: str, low: float, high: float, log: bool = True) -> float:
            _ = log
            value = (float(low) + float(high)) / 2.0
            self.params[name] = value
            return value

    class FakeStudy:
        def __init__(self) -> None:
            self.values: list[float] = []

        def ask(self) -> FakeTrial:
            return FakeTrial()

        def tell(self, trial: FakeTrial, value: float) -> None:
            _ = trial
            self.values.append(value)

    fake_optuna = types.ModuleType("optuna")
    fake_optuna.logging = types.SimpleNamespace(WARNING=0, set_verbosity=lambda level: None)
    fake_optuna.samplers = types.SimpleNamespace(TPESampler=lambda **kwargs: object())
    fake_optuna.create_study = lambda sampler, direction: FakeStudy()

    monkeypatch.setitem(sys.modules, "optuna", fake_optuna)

    app = create_app(mock_config)
    service = app._psim_service
    await service.open_project(str(project_path))

    raw = await app._tool_manager.call_tool(
        "optimize_circuit",
        {"topology": "buck", "targets": {"output_voltage_mean": 12.0}, "n_trials": 2},
        convert_result=False,
    )
    result = json.loads(raw)

    assert result["success"] is True
    assert result["data"]["trials_completed"] == 2
    assert "best_params" in result["data"]
