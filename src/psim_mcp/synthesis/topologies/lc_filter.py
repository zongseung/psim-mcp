"""LC low-pass filter synthesizer — creates CircuitGraph from requirements.

AC source → series inductor → shunt capacitor → resistive load. NO position/direction/ports.
"""

from __future__ import annotations

import math

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_lc_filter(requirements: dict) -> CircuitGraph:
    """Synthesize an LC low-pass filter CircuitGraph from requirements."""
    vin = float(requirements.get("vin", 10.0))
    freq = float(requirements.get("freq", 1000.0))
    r_load = float(requirements.get("load_resistance", requirements.get("vout_target", vin * 0.5) /
                                    max(float(requirements.get("iout", 1.0)), 1e-6)))
    r_load = max(r_load, 0.1)

    if requirements.get("inductance") and requirements.get("capacitance"):
        inductance = float(requirements["inductance"])
        capacitance = float(requirements["capacitance"])
        fc = 1 / (2 * math.pi * math.sqrt(inductance * capacitance))
    elif requirements.get("cutoff_freq"):
        fc = float(requirements["cutoff_freq"])
        z0 = r_load
        inductance = z0 / (2 * math.pi * fc)
        capacitance = 1 / (2 * math.pi * fc * z0)
    else:
        fc = freq * 10
        z0 = r_load
        inductance = z0 / (2 * math.pi * fc)
        capacitance = 1 / (2 * math.pi * fc * z0)

    inductance = max(inductance, 1e-9)
    capacitance = max(capacitance, 1e-12)

    components = [
        make_component(
            "V1", "AC_Source",
            role="input_source",
            parameters={"amplitude": round(vin * math.sqrt(2), 4), "frequency": freq},
            block_ids=["input"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["input"],
        ),
        make_component(
            "L1", "Inductor",
            role="inductor",
            parameters={"inductance": round(inductance, 9), "CurrentFlag": 1},
            block_ids=["lc_section"],
        ),
        make_component(
            "C1", "Capacitor",
            role="capacitor",
            parameters={"capacitance": round(capacitance, 9)},
            block_ids=["lc_section"],
        ),
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["output"],
        ),
    ]

    nets = [
        make_net("net_vin", ["V1.positive", "L1.pin1"], role="input_signal"),
        make_net("net_lc", ["L1.pin2", "C1.positive", "R1.pin1"], role="output_signal"),
        make_net("net_gnd", ["V1.negative", "GND1.pin1", "C1.negative", "R1.pin2"], role="ground"),
    ]

    blocks = [
        make_block("input", "input", role="signal_source", component_ids=["V1", "GND1"]),
        make_block("lc_section", "filter", role="lc_filter", component_ids=["L1", "C1"]),
        make_block("output", "output", role="load", component_ids=["R1"]),
    ]

    traces = [
        make_trace("design_formula", "cutoff_freq_hz", round(fc, 2)),
        make_trace("design_formula", "inductance", round(inductance, 9)),
    ]

    sim_period = 1 / freq if freq else 1e-3
    return CircuitGraph(
        topology="lc_filter",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "cutoff_freq": round(fc, 2),
            "inductance": round(inductance, 9),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(sim_period / 500, 9),
            "total_time": round(sim_period * 20, 6),
        },
        traces=traces,
        metadata={
            "name": "LC Low-Pass Filter",
            "description": (
                f"LC filter: fc={fc:.1f}Hz, vin={vin}V"
            ),
        },
    )
