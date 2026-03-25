"""LCL filter synthesizer — creates CircuitGraph from requirements.

Grid-connected inverter LCL filter: L1 → shunt C → L2 → load. NO position/direction/ports.
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


def synthesize_lcl_filter(requirements: dict) -> CircuitGraph:
    """Synthesize an LCL filter CircuitGraph from requirements."""
    vin = float(requirements.get("vin", 220.0))
    f_line = float(requirements.get("f_line", 60.0))
    fsw = float(requirements.get("fsw", 10_000.0))
    r_load = float(requirements.get("load_resistance",
                                    float(requirements.get("vout_target", vin * 0.5)) /
                                    max(float(requirements.get("iout", 1.0)), 1e-6)))
    r_load = max(r_load, 0.1)
    vdc = float(requirements.get("vdc", vin * math.sqrt(2)))
    delta_i_ratio = float(requirements.get("delta_i_ratio", 0.15))

    i_rated = vin / r_load if r_load else 1.0
    delta_i = delta_i_ratio * i_rated * math.sqrt(2)
    delta_i = max(delta_i, 1e-6)
    l1 = vdc / (delta_i * fsw) if fsw else 1e-3
    l1 = max(l1, 1e-9)
    l2 = max(l1 / 3, 1e-9)
    f_res = fsw / 7
    capacitance = 1 / (4 * math.pi**2 * f_res**2 * l1) if (f_res and l1) else 10e-6
    capacitance = max(capacitance, 1e-12)

    components = [
        make_component(
            "V1", "AC_Source",
            role="input_source",
            parameters={"amplitude": round(vin * math.sqrt(2), 4), "frequency": f_line},
            block_ids=["input"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["input"],
        ),
        make_component(
            "L1", "Inductor",
            role="inductor_1",
            parameters={"inductance": round(l1, 9), "CurrentFlag": 1},
            block_ids=["lcl_section"],
        ),
        make_component(
            "C1", "Capacitor",
            role="capacitor",
            parameters={"capacitance": round(capacitance, 9)},
            block_ids=["lcl_section"],
        ),
        make_component(
            "L2", "Inductor",
            role="inductor_2",
            parameters={"inductance": round(l2, 9)},
            block_ids=["lcl_section"],
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
        make_net("net_l1_c", ["L1.pin2", "C1.positive", "L2.pin1"], role="filter_node"),
        make_net("net_l2_out", ["L2.pin2", "R1.pin1"], role="output_signal"),
        make_net("net_gnd", ["V1.negative", "GND1.pin1", "C1.negative", "R1.pin2"], role="ground"),
    ]

    blocks = [
        make_block("input", "input", role="signal_source", component_ids=["V1", "GND1"]),
        make_block("lcl_section", "filter", role="lcl_filter", component_ids=["L1", "C1", "L2"]),
        make_block("output", "output", role="load", component_ids=["R1"]),
    ]

    traces = [
        make_trace("design_formula", "l1", round(l1, 9)),
        make_trace("design_formula", "l2", round(l2, 9)),
    ]

    sim_period = 1 / f_line if f_line else 1e-3
    return CircuitGraph(
        topology="lcl_filter",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "l1": round(l1, 9),
            "l2": round(l2, 9),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(sim_period * 10, 6),
        },
        traces=traces,
        metadata={
            "name": "LCL Filter",
            "description": (
                f"LCL filter: fsw={fsw / 1e3:.1f}kHz, f_line={f_line}Hz"
            ),
        },
    )
