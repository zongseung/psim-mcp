"""One sequential Optuna study over a leased PSIM adapter session."""

from __future__ import annotations

import json
import math
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import optuna
from optuna.trial import TrialState

from psim_mcp.models.optimization import ConstraintOperator, OptimizationRequest

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter, SessionToken


class _InvalidMeasurement(ValueError):
    pass


class _OptimizationExecutionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StudyFiles:
    source_copy: Path
    working: Path
    study_dir: Path
    ledger: Path


def append_ledger(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


class OptimizationStudy:
    def __init__(self, adapter: BasePsimAdapter, request: OptimizationRequest) -> None:
        self._adapter = adapter
        self._request = request

    async def run(  # noqa: ANN401  # noqa: DICT_OK
        self,
        token: SessionToken,
        files: StudyFiles,
        started: float,
    ) -> dict:
        paths: list[str] = []
        await self._adapter.open_project(str(files.working), lease_token=token)
        await self._instrument(token)
        baseline_path = files.study_dir / "baseline.smv"
        paths.append(str(baseline_path))
        await self._measure(baseline_path, token)

        sampler = optuna.samplers.TPESampler(
            seed=self._request.seed,
            constraints_func=lambda trial: trial.user_attrs["constraint_residuals"],
        )
        study = optuna.create_study(direction="minimize", sampler=sampler)
        deadline = started + self._request.time_budget_seconds
        complete = 0
        failed = 0
        best: tuple[float, dict[str, float], dict[str, float], list[float]] | None = None
        stop_reason = "trials_exhausted"

        for index in range(self._request.n_trials):
            if time.monotonic() >= deadline:
                stop_reason = "time_budget_reached"
                break
            trial = study.ask()
            params = {
                variable.name: trial.suggest_float(
                    variable.name,
                    variable.minimum,
                    variable.maximum,
                    log=variable.log_scale,
                )
                for variable in self._request.variables
            }
            trial_path = files.study_dir / f"trial-{index:04d}.smv"
            paths.append(str(trial_path))
            try:
                await self._apply(params, token)
                metrics = await self._measure(trial_path, token)
            except _InvalidMeasurement as exc:
                study.tell(trial, state=TrialState.FAIL)
                failed += 1
                append_ledger(
                    files.ledger,
                    {"type": "trial", "trial": index, "state": "failed", "error": str(exc)},
                )
                continue
            except Exception:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
                study.tell(trial, state=TrialState.FAIL)
                raise

            cost = self._cost(metrics)
            residuals = self._residuals(metrics)
            trial.set_user_attr("constraint_residuals", residuals)
            study.tell(trial, cost)
            complete += 1
            append_ledger(
                files.ledger,
                {
                    "type": "trial",
                    "trial": index,
                    "state": "complete",
                    "cost": cost,
                    "params": params,
                    "metrics": metrics,
                    "constraint_residuals": residuals,
                    "result_path": str(trial_path),
                },
            )
            if all(residual <= 0.0 for residual in residuals) and (best is None or cost < best[0]):
                best = (cost, params, metrics, residuals)

        common = {
            "trials_complete": complete,
            "trials_failed": failed,
            "stop_reason": stop_reason,
            "result_paths": paths,
        }
        if best is None:
            return {
                **common,
                "success": False,
                "state": "no_feasible_trial",
                "best_params": None,
            }

        best_path = files.study_dir / "best.psimsch"
        best_result_path = files.study_dir / "best.smv"
        shutil.copy2(files.source_copy, best_path)
        await self._adapter.open_project(str(best_path), lease_token=token)
        await self._instrument(token)
        await self._apply(best[1], token)
        paths.append(str(best_result_path))
        best_metrics = await self._measure(best_result_path, token)
        best_residuals = self._residuals(best_metrics)
        if any(residual > 0.0 for residual in best_residuals):
            raise _OptimizationExecutionError("best candidate failed final constraint validation")
        return {
            **common,
            "success": True,
            "state": "time_budget_reached" if stop_reason == "time_budget_reached" else "completed",
            "best_params": best[1],
            "best_cost": self._cost(best_metrics),
            "best_metrics": best_metrics,
            "constraint_residuals": best_residuals,
            "best_project_path": str(best_path),
        }

    async def _instrument(self, token: SessionToken) -> None:
        components = {
            measurement.signal[2:-1]
            for measurement in self._request.measurements
            if measurement.signal.startswith("I(") and measurement.signal.endswith(")")
        }
        for component in sorted(components):
            await self._adapter.set_parameter(component, "CurrentFlag", 1, lease_token=token)

    async def _apply(self, params: dict[str, float], token: SessionToken) -> None:
        for variable in self._request.variables:
            for binding in variable.bindings:
                await self._adapter.set_parameter(
                    binding.component_id,
                    binding.parameter_name,
                    params[variable.name],
                    lease_token=token,
                )

    async def _measure(
        self,
        output_path: Path,
        token: SessionToken,
    ) -> dict[str, float]:
        simulation = await self._adapter.run_simulation(
            {"simview": 0},
            str(output_path),
            lease_token=token,
        )
        if simulation.get("status") != "completed":
            raise _OptimizationExecutionError("PSIM simulation did not complete")
        measured = await self._adapter.compute_metrics(
            [measurement.to_metric_spec() for measurement in self._request.measurements],
            graph_file=str(output_path),
            skip_ratio=0.0,
            lease_token=token,
        )
        metrics = measured.get("metrics", {})
        windows = measured.get("windows", {})
        values: dict[str, float] = {}
        for measurement in self._request.measurements:
            value = metrics.get(measurement.name)
            evidence = windows.get(measurement.name, {})
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or evidence.get("point_count", 0) < measurement.window.min_samples
            ):
                raise _InvalidMeasurement(f"invalid measurement: {measurement.name}")
            values[measurement.name] = float(value)
        return values

    def _cost(self, metrics: dict[str, float]) -> float:
        return sum(
            term.weight
            * ((metrics[term.measurement] - term.target) / term.normalization_scale) ** 2
            for term in self._request.objective
        )

    def _residuals(self, metrics: dict[str, float]) -> list[float]:
        return [
            (
                metrics[constraint.measurement] - constraint.limit
                if constraint.operator is ConstraintOperator.UPPER
                else constraint.limit - metrics[constraint.measurement]
            )
            / constraint.scale
            for constraint in self._request.constraints
        ]
