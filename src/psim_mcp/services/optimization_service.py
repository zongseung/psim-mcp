"""Circuit optimization service -- Bayesian optimization of component values."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter

logger = logging.getLogger(__name__)


class OptimizationService:
    """Iteratively optimizes circuit parameters using Bayesian optimization.

    Uses `Optuna <https://optuna.org/>`_ with a TPE sampler to explore the
    parameter space and minimize a cost function derived from the difference
    between computed metrics and user-supplied targets.
    """

    def __init__(self, adapter: BasePsimAdapter) -> None:
        self._adapter = adapter

    async def optimize(
        self,
        topology: str,
        targets: dict[str, float],
        tunable_params: list[dict] | None = None,
        n_trials: int = 50,
        max_time_seconds: int = 300,
    ) -> dict:
        """Run Bayesian optimization loop.

        Parameters
        ----------
        topology:
            Circuit topology name -- used to look up default tunable
            parameters and metric definitions.
        targets:
            Mapping of metric names to desired values.
        tunable_params:
            Optional list of parameter descriptors.  Each entry must have
            ``component``, ``param``, ``min``, ``max`` keys and optionally
            ``log_scale`` (default *True*).
        n_trials:
            Maximum number of optimization trials.
        max_time_seconds:
            Hard time-limit (currently informational).

        Returns
        -------
        dict
            Keys: ``success``, ``best_params``, ``best_cost``,
            ``trials_completed``, ``history``.
        """
        try:
            import optuna

            optuna.logging.set_verbosity(optuna.logging.WARNING)
        except ImportError:
            return {
                "success": False,
                "error": "optuna not installed. Run: uv add optuna",
            }

        from psim_mcp.data.topology_metrics import (
            get_default_tunable_params,
            get_topology_metrics,
        )

        # Get tunable params
        if not tunable_params:
            tunable_params = get_default_tunable_params(topology)
        if not tunable_params:
            return {
                "success": False,
                "error": f"No tunable parameters defined for topology '{topology}'",
            }

        # Get metrics spec
        topo_metrics = get_topology_metrics(topology) or {}
        metrics_spec = topo_metrics.get("metrics", [])
        skip_ratio = topo_metrics.get("steady_state_skip", 0.5)

        best_cost = float("inf")
        best_params: dict = {}
        trial_history: list[dict] = []

        study = optuna.create_study(
            sampler=optuna.samplers.TPESampler(
                n_startup_trials=max(5, n_trials // 4),
                multivariate=True,
            ),
            direction="minimize",
        )

        for trial_idx in range(n_trials):
            trial = study.ask()

            # Suggest parameter values
            param_values: dict[str, float] = {}
            for p in tunable_params:
                key = f"{p['component']}.{p['param']}"
                param_values[key] = trial.suggest_float(
                    key,
                    float(p["min"]),
                    float(p["max"]),
                    log=p.get("log_scale", True),
                )

            # Set parameters on the adapter
            for p in tunable_params:
                key = f"{p['component']}.{p['param']}"
                try:
                    await self._adapter.set_parameter(
                        p["component"],
                        p["param"],
                        param_values[key],
                    )
                except Exception:
                    study.tell(trial, float("inf"))
                    continue

            # Run simulation (headless)
            try:
                sim_result = await self._adapter.run_simulation({"simview": 0})
                if not isinstance(sim_result, dict) or sim_result.get("status") != "completed":
                    study.tell(trial, float("inf"))
                    continue
            except Exception:
                study.tell(trial, float("inf"))
                continue

            # Compute metrics
            try:
                metrics_result = await self._adapter.compute_metrics(
                    metrics_spec=metrics_spec,
                    skip_ratio=skip_ratio,
                )
                computed = metrics_result.get("metrics", {})
            except Exception:
                study.tell(trial, float("inf"))
                continue

            # Compute cost (normalised squared error)
            cost = 0.0
            for metric_name, target_val in targets.items():
                actual = computed.get(metric_name)
                if actual is None or isinstance(actual, dict):
                    cost += 100.0
                    continue
                if target_val != 0:
                    cost += ((actual - target_val) / target_val) ** 2
                else:
                    cost += actual**2

            study.tell(trial, cost)
            trial_history.append(
                {
                    "trial": trial_idx,
                    "cost": round(cost, 6),
                    "params": {k: round(v, 9) for k, v in param_values.items()},
                    "metrics": {
                        k: round(v, 6) if isinstance(v, float) else v
                        for k, v in computed.items()
                    },
                }
            )

            if cost < best_cost:
                best_cost = cost
                best_params = dict(param_values)

            logger.debug("Trial %d: cost=%.6f", trial_idx, cost)

        # Apply best parameters to the adapter
        for p in tunable_params:
            key = f"{p['component']}.{p['param']}"
            if key in best_params:
                try:
                    await self._adapter.set_parameter(
                        p["component"],
                        p["param"],
                        best_params[key],
                    )
                except Exception:
                    pass

        return {
            "success": True,
            "best_params": {k: round(v, 9) for k, v in best_params.items()},
            "best_cost": round(best_cost, 6),
            "trials_completed": len(trial_history),
            "history": trial_history[-5:],  # last 5 trials
        }
