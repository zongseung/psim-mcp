"""Topology-specific metric definitions for simulation analysis.

Each topology maps to:
- metrics: list of metric specs the bridge can compute
- steady_state_skip: fraction of simulation to skip for steady-state analysis
- primary_signals: signal names to extract for waveform rendering
- tunable_params: default parameter ranges for Bayesian optimization
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
