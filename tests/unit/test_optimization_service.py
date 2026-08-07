from __future__ import annotations

import asyncio  # noqa: F401  # noqa: ANYIO_OK
import json
from pathlib import Path

import pytest

from psim_mcp.adapters.base import SessionToken
from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.models.optimization import OptimizationRequest
from psim_mcp.services.optimization_service import OptimizationService


def _request(source: Path, *, limit: float = 10.0) -> OptimizationRequest:
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
                    "limit": limit,
                    "scale": 1.0,
                }
            ],
            "n_trials": 2,
            "time_budget_seconds": 30,
            "seed": 7,
        }
    )


async def test_preserves_source_restores_project_and_uses_unique_results(
    tmp_path: Path,
) -> None:
    # Given
    previous = tmp_path / "previous.psimsch"
    source = tmp_path / "source.psimsch"
    previous.write_text("previous", encoding="utf-8")
    source.write_text("source", encoding="utf-8")
    source_before = source.read_bytes()
    output = tmp_path / "output"
    adapter = MockPsimAdapter()
    await adapter.open_project(str(previous))
    service = OptimizationService(
        adapter,
        AppConfig(
            psim_mode="mock",
            psim_output_dir=output,
            allowed_project_dirs=[str(tmp_path)],
        ),
    )

    # When
    result = await service.optimize(_request(source))

    # Then
    assert result["success"] is True
    assert result["state"] == "completed"
    assert result["trials_complete"] == 2
    assert source.read_bytes() == source_before
    assert result["source_hash_before"] == result["source_hash_after"]
    assert adapter.current_project_path == str(previous.resolve())
    assert result["restoration_status"] == "restored"
    assert Path(result["best_project_path"]).is_file()
    result_paths = [Path(path) for path in result["result_paths"]]
    assert len(result_paths) == len(set(result_paths)) == 4
    assert all(path.is_file() for path in result_paths)
    ledger = Path(result["ledger_path"])
    assert json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])["state"] == "completed"


async def test_all_infeasible_trials_return_truthful_failure(tmp_path: Path) -> None:
    # Given
    source = tmp_path / "source.psimsch"
    source.write_text("source", encoding="utf-8")
    service = OptimizationService(
        MockPsimAdapter(),
        AppConfig(
            psim_mode="mock",
            psim_output_dir=tmp_path / "output",
            allowed_project_dirs=[str(tmp_path)],
        ),
    )

    # When
    result = await service.optimize(_request(source, limit=0.1))

    # Then
    assert result["success"] is False
    assert result["state"] == "no_feasible_trial"
    assert result["best_params"] is None
    assert result["best_project_path"] is None
    assert result["restoration_status"] == "no_previous_project"


class _CancellableMockAdapter(MockPsimAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.baseline_started = asyncio.Event()

    async def run_simulation(
        self,
        options: dict | None = None,
        output_path: str = "",
        lease_token: SessionToken | None = None,
    ) -> dict:
        if Path(output_path).name == "baseline.smv":
            self.baseline_started.set()
            await asyncio.Event().wait()
        return await super().run_simulation(options, output_path, lease_token)


async def test_cancellation_restores_project_and_records_cancelled_state(
    tmp_path: Path,
) -> None:
    # Given
    previous = tmp_path / "previous.psimsch"
    source = tmp_path / "source.psimsch"
    previous.write_text("previous", encoding="utf-8")
    source.write_text("source", encoding="utf-8")
    output = tmp_path / "output"
    adapter = _CancellableMockAdapter()
    await adapter.open_project(str(previous))
    service = OptimizationService(
        adapter,
        AppConfig(
            psim_mode="mock",
            psim_output_dir=output,
            allowed_project_dirs=[str(tmp_path)],
        ),
    )

    # When
    task = asyncio.create_task(service.optimize(_request(source)))
    await adapter.baseline_started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Then
    assert adapter.current_project_path == str(previous.resolve())
    ledger = next(output.glob("optuna-*/study.jsonl"))
    terminal = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert terminal["state"] == "cancelled"
    assert terminal["restoration_status"] == "restored"


class _SafetyMockAdapter(MockPsimAdapter):
    def __init__(
        self,
        *,
        fail_component: str | None = None,
        fail_restore: bool = False,
    ) -> None:
        super().__init__()
        self.fail_component = fail_component
        self.fail_restore = fail_restore
        self.inductance_writes: list[tuple[str, float]] = []
        self.simulation_count = 0

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
        lease_token: SessionToken | None = None,
    ) -> dict:
        if parameter_name == "Inductance":
            self.inductance_writes.append((component_id, float(value)))
            if component_id == self.fail_component:
                raise RuntimeError("injected parameter failure")
            if component_id in {"L2", "L3"}:
                return {"component_id": component_id, "new_value": value}
        return await super().set_parameter(
            component_id,
            parameter_name,
            value,
            lease_token,
        )

    async def run_simulation(
        self,
        options: dict | None = None,
        output_path: str = "",
        lease_token: SessionToken | None = None,
    ) -> dict:
        self.simulation_count += 1
        return await super().run_simulation(options, output_path, lease_token)

    async def reset_session(self, token: SessionToken) -> None:
        if self.fail_restore:
            raise OSError("injected restoration failure")
        await super().reset_session(token)


def _tied_request(source: Path) -> OptimizationRequest:
    request = _request(source).model_dump(mode="json", by_alias=True)
    request["variables"][0]["bindings"].extend(
        [
            {
                "component_id": component,
                "component_kind": "L",
                "parameter_name": "Inductance",
            }
            for component in ("L2", "L3")
        ]
    )
    return OptimizationRequest.model_validate(request)


async def test_tied_variable_writes_the_same_value_to_each_phase(tmp_path: Path) -> None:
    # Given
    source = tmp_path / "source.psimsch"
    source.write_text("source", encoding="utf-8")
    adapter = _SafetyMockAdapter()
    service = OptimizationService(
        adapter,
        AppConfig(psim_output_dir=tmp_path / "output", allowed_project_dirs=[str(tmp_path)]),
    )

    # When
    result = await service.optimize(_tied_request(source))

    # Then
    assert result["state"] == "completed"
    groups = [adapter.inductance_writes[index : index + 3] for index in range(0, 9, 3)]
    assert all([component for component, _ in group] == ["L1", "L2", "L3"] for group in groups)
    assert all(len({value for _, value in group}) == 1 for group in groups)


async def test_partial_parameter_failure_does_not_run_trial(tmp_path: Path) -> None:
    # Given
    source = tmp_path / "source.psimsch"
    source.write_text("source", encoding="utf-8")
    adapter = _SafetyMockAdapter(fail_component="L2")
    service = OptimizationService(
        adapter,
        AppConfig(psim_output_dir=tmp_path / "output", allowed_project_dirs=[str(tmp_path)]),
    )

    # When
    result = await service.optimize(_tied_request(source))

    # Then
    assert result["state"] == "failed"
    assert adapter.simulation_count == 1


async def test_restoration_failure_overrides_optimization_success(tmp_path: Path) -> None:
    # Given
    source = tmp_path / "source.psimsch"
    source.write_text("source", encoding="utf-8")
    adapter = _SafetyMockAdapter(fail_restore=True)
    service = OptimizationService(
        adapter,
        AppConfig(psim_output_dir=tmp_path / "output", allowed_project_dirs=[str(tmp_path)]),
    )

    # When
    result = await service.optimize(_request(source))

    # Then
    assert result["success"] is False
    assert result["state"] == "failed"
    assert result["stop_reason"] == "restoration_failed"
    assert result["restoration_status"].startswith("failed")
