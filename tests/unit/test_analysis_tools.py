"""Tests for analysis/optimization tool wiring in mock mode."""

from __future__ import annotations

import json
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


def _optimization_request(project_path: Path) -> dict:
    return {
        "source_project_path": str(project_path),
        "variables": [
            {
                "name": "inductance",
                "min": 20e-6,
                "max": 80e-6,
                "bindings": [
                    {
                        "component_id": "L1",
                        "component_kind": "L",
                        "parameter_name": "Inductance",
                    }
                ],
            }
        ],
        "measurements": [
            {
                "name": "vout_mean",
                "signal": "V(Vout)",
                "function": "mean",
                "window": {
                    "start_fraction": 0.5,
                    "end_fraction": 1.0,
                    "min_samples": 20,
                },
            },
            {
                "name": "inductor_peak",
                "signal": "I(L1)",
                "function": "peak",
                "window": {
                    "start_fraction": 0.5,
                    "end_fraction": 1.0,
                    "min_samples": 20,
                },
            },
        ],
        "objective": [{"measurement": "vout_mean", "target": 12.0}],
        "constraints": [
            {
                "measurement": "inductor_peak",
                "operator": "<=",
                "limit": 10.0,
                "scale": 1.0,
            }
        ],
        "n_trials": 2,
        "time_budget_seconds": 30,
        "seed": 7,
    }


async def test_optimize_circuit_tool_with_dynamic_request(
    mock_config: AppConfig,
    project_path: Path,
):
    # Given
    app = create_app(mock_config)
    service = app._psim_service
    await service.open_project(str(project_path))
    request = _optimization_request(project_path)

    # When
    raw = await app._tool_manager.call_tool(
        "optimize_circuit",
        {"request": request},
        convert_result=False,
    )
    result = json.loads(raw)

    # Then
    assert result["success"] is True
    assert result["data"]["state"] == "completed"
    assert result["data"]["trials_complete"] == 2
    assert Path(result["data"]["best_project_path"]).is_file()


async def test_optimize_circuit_rejects_load_resistor(
    mock_config: AppConfig,
    project_path: Path,
) -> None:
    # Given
    app = create_app(mock_config)
    request = _optimization_request(project_path)
    request["variables"][0]["bindings"][0] = {
        "component_id": "R1",
        "component_kind": "R",
        "parameter_name": "Resistance",
        "role": "load",
    }

    # When
    rejected = json.loads(
        await app._tool_manager.call_tool(
            "optimize_circuit",
            {"request": request},
            convert_result=False,
        )
    )

    # Then
    assert rejected["success"] is False
    assert rejected["error"]["code"] == "VALIDATION_ERROR"
