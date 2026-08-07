from __future__ import annotations

import json
from pathlib import Path

import pytest

import psim_mcp.services.optimization_service as service_module
from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.models.optimization import OptimizationRequest
from psim_mcp.services.optimization_service import OptimizationService
from psim_mcp.services.validators import ValidationResult


def _request(source: Path) -> OptimizationRequest:
    return OptimizationRequest.model_validate(
        {
            "source_project_path": str(source),
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
                    "name": "vout",
                    "signal": "V(Vout)",
                    "function": "mean",
                    "window": {
                        "start_fraction": 0.5,
                        "end_fraction": 1.0,
                        "min_samples": 20,
                    },
                }
            ],
            "objective": [{"measurement": "vout", "target": 12.0}],
            "constraints": [
                {
                    "measurement": "vout",
                    "operator": ">=",
                    "limit": 1.0,
                    "scale": 1.0,
                }
            ],
            "n_trials": 1,
            "time_budget_seconds": 30,
        }
    )


async def test_source_disappearing_after_validation_returns_terminal_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    source = tmp_path / "source.psimsch"
    source.write_text("source", encoding="utf-8")
    original_validate = service_module.validate_project_path

    def validate_then_remove(path: str, allowed_dirs: list[str] | None) -> ValidationResult:
        result = original_validate(path, allowed_dirs)
        Path(path).unlink()
        return result

    monkeypatch.setattr(service_module, "validate_project_path", validate_then_remove)
    service = OptimizationService(
        MockPsimAdapter(),
        AppConfig(
            psim_mode="mock",
            psim_output_dir=tmp_path / "output",
            allowed_project_dirs=[str(tmp_path)],
        ),
    )

    # When
    result = await service.optimize(_request(source))

    # Then
    assert result["state"] == "failed"
    assert result["stop_reason"] == "setup_failed"
    ledger = Path(result["ledger_path"])
    terminal = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert terminal["type"] == "terminal"
    assert terminal["stop_reason"] == "setup_failed"


async def test_output_root_failure_returns_structured_result(tmp_path: Path) -> None:
    # Given
    source = tmp_path / "source.psimsch"
    source.write_text("source", encoding="utf-8")
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")
    service = OptimizationService(
        MockPsimAdapter(),
        AppConfig(
            psim_mode="mock",
            psim_output_dir=output_file,
            allowed_project_dirs=[str(tmp_path)],
        ),
    )

    # When
    result = await service.optimize(_request(source))

    # Then
    assert result["success"] is False
    assert result["state"] == "failed"
    assert result["stop_reason"] == "setup_failed"
    assert result["ledger_path"] is None
    assert result["error"]
