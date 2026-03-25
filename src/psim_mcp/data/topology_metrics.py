"""Topology-specific metric definitions for simulation analysis.

Each topology maps to:
- metrics: list of metric specs the bridge can compute
- steady_state_skip: fraction of simulation to skip for steady-state analysis
- primary_signals: signal names to extract for waveform rendering
- tunable_params: default parameter ranges for Bayesian optimization
- acceptance_criteria: pass/fail thresholds for simulation result validation
"""

from __future__ import annotations

_TOPOLOGY_METRICS: dict[str, dict] = {
    "buck": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pp", "signal": "V(Vout)", "function": "ripple_pp"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
            {"name": "inductor_current_mean", "signal": "I(L1)", "function": "mean"},
            {"name": "inductor_current_ripple_pp", "signal": "I(L1)", "function": "ripple_pp"},
        ],
        "steady_state_skip": 0.5,
        "primary_signals": ["V(Vout)", "I(L1)"],
        "tunable_params": [
            {"component": "L1", "param": "inductance", "min": 1e-6, "max": 1e-3, "log_scale": True},
            {"component": "C1", "param": "capacitance", "min": 1e-6, "max": 1e-3, "log_scale": True},
            {"component": "R1", "param": "resistance", "min": 1.0, "max": 100.0, "log_scale": False},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 5.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 10.0},
        },
    },
    "boost": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pp", "signal": "V(Vout)", "function": "ripple_pp"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
            {"name": "inductor_current_mean", "signal": "I(L1)", "function": "mean"},
        ],
        "steady_state_skip": 0.5,
        "primary_signals": ["V(Vout)", "I(L1)"],
        "tunable_params": [
            {"component": "L1", "param": "inductance", "min": 10e-6, "max": 5e-3, "log_scale": True},
            {"component": "C1", "param": "capacitance", "min": 10e-6, "max": 2e-3, "log_scale": True},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 5.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 10.0},
        },
    },
    "buck_boost": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
            {"name": "inductor_current_mean", "signal": "I(L1)", "function": "mean"},
        ],
        "steady_state_skip": 0.5,
        "primary_signals": ["V(Vout)", "I(L1)"],
        "tunable_params": [
            {"component": "L1", "param": "inductance", "min": 10e-6, "max": 2e-3, "log_scale": True},
            {"component": "C1", "param": "capacitance", "min": 10e-6, "max": 1e-3, "log_scale": True},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 5.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 10.0},
        },
    },
    "flyback": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
            {"name": "magnetizing_current_peak", "signal": "I(Lm)", "function": "peak"},
        ],
        "steady_state_skip": 0.6,
        "primary_signals": ["V(Vout)", "I(Lm)"],
        "tunable_params": [
            {"component": "Lm", "param": "inductance", "min": 10e-6, "max": 1e-3, "log_scale": True},
            {"component": "C1", "param": "capacitance", "min": 10e-6, "max": 1e-3, "log_scale": True},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 10.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 15.0},
        },
    },
    "llc": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
            {"name": "resonant_current_rms", "signal": "I(Lr)", "function": "rms"},
        ],
        "steady_state_skip": 0.6,
        "primary_signals": ["V(Vout)", "I(Lr)"],
        "tunable_params": [
            {"component": "Lr", "param": "inductance", "min": 1e-6, "max": 500e-6, "log_scale": True},
            {"component": "Cr", "param": "capacitance", "min": 1e-9, "max": 100e-9, "log_scale": True},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 10.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 15.0},
            "resonant_current_rms": {"min_absolute": 0.01},
        },
    },
    "forward": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pp", "signal": "V(Vout)", "function": "ripple_pp"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
            {"name": "inductor_current_mean", "signal": "I(L1)", "function": "mean"},
            {"name": "inductor_current_ripple_pp", "signal": "I(L1)", "function": "ripple_pp"},
        ],
        "steady_state_skip": 0.6,
        "primary_signals": ["V(Vout)", "I(L1)"],
        "tunable_params": [
            {"component": "L1", "param": "inductance", "min": 10e-6, "max": 2e-3, "log_scale": True},
            {"component": "Cout", "param": "capacitance", "min": 1e-6, "max": 500e-6, "log_scale": True},
            {"component": "Vout", "param": "resistance", "min": 1.0, "max": 100.0, "log_scale": False},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 10.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 15.0},
        },
    },
    "cuk": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
        ],
        "steady_state_skip": 0.5,
        "primary_signals": ["V(Vout)"],
        "tunable_params": [
            {"component": "L1", "param": "inductance", "min": 10e-6, "max": 2e-3, "log_scale": True},
            {"component": "C1", "param": "capacitance", "min": 10e-6, "max": 1e-3, "log_scale": True},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 5.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 10.0},
        },
    },
    "sepic": {
        "metrics": [
            {"name": "output_voltage_mean", "signal": "V(Vout)", "function": "mean"},
            {"name": "output_voltage_ripple_pct", "signal": "V(Vout)", "function": "ripple_percent"},
        ],
        "steady_state_skip": 0.5,
        "primary_signals": ["V(Vout)"],
        "tunable_params": [
            {"component": "L1", "param": "inductance", "min": 10e-6, "max": 2e-3, "log_scale": True},
            {"component": "C1", "param": "capacitance", "min": 10e-6, "max": 1e-3, "log_scale": True},
        ],
        "acceptance_criteria": {
            "output_voltage_mean": {"tolerance_pct": 5.0, "min_absolute": 0.5},
            "output_voltage_ripple_pct": {"max": 10.0},
        },
    },
}


def get_topology_metrics(topology: str) -> dict | None:
    """Return metric definitions for a topology, or None if unknown."""
    return _TOPOLOGY_METRICS.get(topology)


def get_default_tunable_params(topology: str) -> list[dict] | None:
    """Return default tunable parameter ranges for a topology."""
    entry = _TOPOLOGY_METRICS.get(topology)
    if entry is None:
        return None
    return entry.get("tunable_params")


def get_acceptance_criteria(topology: str) -> dict | None:
    """Return acceptance criteria for a topology, or None if undefined."""
    entry = _TOPOLOGY_METRICS.get(topology)
    if entry is None:
        return None
    return entry.get("acceptance_criteria")


def evaluate_acceptance(
    topology: str,
    metrics: dict[str, float],
    targets: dict[str, float] | None = None,
) -> dict:
    """Evaluate simulation metrics against acceptance criteria.

    Args:
        topology: Topology name (e.g. "buck").
        metrics: Measured metric values from simulation.
        targets: Optional design targets (e.g. {"output_voltage_mean": 12.0}).

    Returns:
        Dict with ``passed`` (bool), ``results`` (per-metric detail), and
        ``summary`` (human-readable).
    """
    criteria = get_acceptance_criteria(topology)
    if criteria is None:
        return {"passed": True, "results": {}, "summary": "No criteria defined."}

    results: dict[str, dict] = {}
    all_passed = True

    for metric_name, rules in criteria.items():
        measured = metrics.get(metric_name)
        if measured is None or isinstance(measured, dict):
            results[metric_name] = {"status": "skipped", "reason": "metric not available"}
            continue

        entry: dict = {"measured": measured, "status": "pass"}

        # Check minimum absolute value (detects 0V output)
        min_abs = rules.get("min_absolute")
        if min_abs is not None and abs(measured) < min_abs:
            entry["status"] = "fail"
            entry["reason"] = f"|{measured:.4f}| < min_absolute {min_abs}"
            all_passed = False
            results[metric_name] = entry
            continue

        # Check maximum threshold (e.g. ripple_pct < 10%)
        max_val = rules.get("max")
        if max_val is not None and measured > max_val:
            entry["status"] = "fail"
            entry["reason"] = f"{measured:.4f} > max {max_val}"
            all_passed = False
            results[metric_name] = entry
            continue

        # Check tolerance against target (e.g. Vout within ±5% of target)
        tol_pct = rules.get("tolerance_pct")
        if tol_pct is not None and targets:
            target_val = targets.get(metric_name)
            if target_val is not None and target_val != 0:
                error_pct = abs(measured - target_val) / abs(target_val) * 100
                entry["target"] = target_val
                entry["error_pct"] = round(error_pct, 2)
                if error_pct > tol_pct:
                    entry["status"] = "fail"
                    entry["reason"] = f"error {error_pct:.1f}% > tolerance {tol_pct}%"
                    all_passed = False

        results[metric_name] = entry

    failed = [k for k, v in results.items() if v.get("status") == "fail"]
    if failed:
        summary = f"FAIL: {', '.join(failed)}"
    else:
        summary = "All acceptance criteria passed."

    return {"passed": all_passed, "results": results, "summary": summary}
