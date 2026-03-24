"""Simulation analysis service -- metric extraction and comparison."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter

logger = logging.getLogger(__name__)


class AnalysisService:
    """Extracts metrics from simulation results and compares against targets."""

    def __init__(self, adapter: BasePsimAdapter) -> None:
        self._adapter = adapter

    async def analyze(
        self,
        topology: str,
        targets: dict[str, float] | None = None,
        graph_file: str | None = None,
        show_waveform: bool = False,
    ) -> dict:
        """Run analysis: extract signals, compute metrics, compare targets.

        Parameters
        ----------
        topology:
            Circuit topology name (e.g. ``"buck"``, ``"flyback"``).  Used to
            look up the appropriate metric definitions.
        targets:
            Optional dict mapping metric names to desired values.  When
            provided the service computes pass/fail status for each metric
            using a 5 % tolerance band.
        graph_file:
            Path to the simulation result file (``.smv``).
        show_waveform:
            When *True* a PNG waveform plot is generated via
            :func:`~psim_mcp.utils.waveform_renderer.render_waveforms`.

        Returns
        -------
        dict
            Keys: ``metrics``, ``comparison``, ``all_pass``,
            ``available_signals``, ``waveform_path``.
        """
        from psim_mcp.data.topology_metrics import get_topology_metrics

        topo_metrics = get_topology_metrics(topology)
        if topo_metrics is None:
            # Use generic metrics when topology is unknown
            topo_metrics = {
                "metrics": [],
                "steady_state_skip": 0.5,
                "primary_signals": [],
            }

        # 1. Compute metrics via adapter ----------------------------------
        metrics_spec = topo_metrics.get("metrics", [])
        skip_ratio = topo_metrics.get("steady_state_skip", 0.5)

        computed: dict = {}
        available_signals: list[str] = []
        if metrics_spec:
            try:
                result = await self._adapter.compute_metrics(
                    metrics_spec=metrics_spec,
                    graph_file=graph_file,
                    skip_ratio=skip_ratio,
                )
                computed = result.get("metrics", {})
                available_signals = result.get("available_signals", [])
            except Exception:
                logger.debug("compute_metrics failed", exc_info=True)

        # 2. Compare against targets --------------------------------------
        comparison: dict = {}
        all_pass = True
        if targets:
            for metric_name, target_val in targets.items():
                actual = computed.get(metric_name)
                if actual is None or isinstance(actual, dict):
                    comparison[metric_name] = {
                        "target": target_val,
                        "actual": None,
                        "pass": False,
                    }
                    all_pass = False
                    continue
                error_pct = (
                    abs(actual - target_val) / abs(target_val) * 100
                    if target_val != 0
                    else 0
                )
                passed = error_pct < 5.0  # 5 % tolerance
                comparison[metric_name] = {
                    "target": target_val,
                    "actual": round(actual, 6),
                    "error_pct": round(error_pct, 2),
                    "pass": passed,
                }
                if not passed:
                    all_pass = False

        # 3. Waveform rendering -------------------------------------------
        waveform_path = ""
        if show_waveform:
            try:
                primary = topo_metrics.get("primary_signals", [])
                signal_result = await self._adapter.extract_signals(
                    graph_file=graph_file,
                    signals=primary or None,
                    max_points=2000,
                )
                signal_data = signal_result.get("signals", {})
                if signal_data:
                    from psim_mcp.utils.waveform_renderer import render_waveforms

                    time_step_val = 1e-6  # default
                    waveform_path = render_waveforms(
                        signal_data,
                        time_step=time_step_val,
                        title=f"{topology.upper()} Simulation Results",
                    )
            except Exception:
                logger.debug("Waveform rendering failed", exc_info=True)

        return {
            "metrics": computed,
            "comparison": comparison,
            "all_pass": all_pass,
            "available_signals": available_signals,
            "waveform_path": waveform_path,
        }
