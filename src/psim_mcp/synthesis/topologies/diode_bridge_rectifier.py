"""Diode bridge rectifier synthesizer — creates CircuitGraph from requirements.

Full-wave bridge rectifier with capacitive filter. NO position/direction/ports.
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


def synthesize_diode_bridge_rectifier(requirements: dict) -> CircuitGraph:
    """Synthesize a diode bridge rectifier CircuitGraph from requirements."""
    # Accept vin as AC RMS voltage (alias for vac_rms)
    vac_rms = float(requirements.get("vac_rms", requirements.get("vin", 220.0)))
    f_line = float(requirements.get("f_line", 60.0))
    r_load = float(requirements.get("load_resistance", requirements.get("iout") and
                   (float(requirements.get("vout_target", 300.0)) / float(requirements["iout"]))
                   if requirements.get("iout") else 100.0))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.05))

    v_peak = vac_rms * math.sqrt(2)
    vdc = v_peak - 1.4  # two diode drops
    iout = vdc / r_load if r_load else 0.1

    v_ripple = ripple_ratio * vdc
    capacitance = iout / (2 * f_line * v_ripple) if (f_line and v_ripple) else 100e-6
    capacitance = max(capacitance, 1e-12)

    components = [
        make_component(
            "V1", "AC_Source",
            role="ac_source",
            parameters={"amplitude": round(vac_rms * math.sqrt(2), 4), "frequency": f_line},
            block_ids=["ac_source"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["ac_source"],
        ),
        make_component(
            "BR1", "DiodeBridge",
            role="diode_bridge",
            parameters={"forward_voltage": 0.7},
            block_ids=["diode_bridge"],
        ),
        make_component(
            "C1", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(capacitance, 9)},
            block_ids=["dc_output"],
        ),
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["dc_output"],
        ),
    ]

    nets = [
        make_net("net_ac_pos", ["V1.positive", "BR1.ac_pos"], role="ac_input"),
        make_net("net_ac_neg", ["V1.negative", "GND1.pin1", "BR1.ac_neg"], role="ac_return"),
        make_net("net_dc_pos", ["BR1.dc_pos", "C1.positive", "R1.pin1"], role="dc_output"),
        make_net("net_dc_neg", ["BR1.dc_neg", "C1.negative", "R1.pin2"], role="ground"),
    ]

    blocks = [
        make_block("ac_source", "input", role="ac_input", component_ids=["V1", "GND1"]),
        make_block("diode_bridge", "rectifier", role="rectification", component_ids=["BR1"]),
        make_block("dc_output", "output", role="dc_output", component_ids=["C1", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "vdc", round(vdc, 4)),
        make_trace("design_formula", "capacitance", round(capacitance, 9)),
    ]

    sim_period = 1 / f_line if f_line else 1 / 60
    return CircuitGraph(
        topology="diode_bridge_rectifier",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vdc_output": round(vdc, 4),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(sim_period / 500, 9),
            "total_time": round(sim_period * 20, 6),
        },
        traces=traces,
        metadata={
            "name": "Diode Bridge Rectifier",
            "description": (
                f"Bridge rectifier: {vac_rms}Vrms @ {f_line}Hz -> "
                f"{vdc:.1f}Vdc, C={capacitance * 1e6:.1f}uF"
            ),
        },
    )
