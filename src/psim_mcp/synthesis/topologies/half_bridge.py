"""Half-bridge inverter synthesizer — creates CircuitGraph from requirements.

Two-switch half-bridge with split DC-bus capacitors and output LC filter.
NO position/direction/ports.
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


def synthesize_half_bridge(requirements: dict) -> CircuitGraph:
    """Synthesize a half-bridge inverter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    fsw = float(requirements.get("fsw", 20_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))

    vout_peak = vin / 2
    vout_target = float(requirements.get("vout_target", vout_peak))

    if requirements.get("load_resistance"):
        r_load = float(requirements["load_resistance"])
        iout = vout_target / r_load if r_load else 1.0
    elif requirements.get("iout"):
        iout = float(requirements["iout"])
        r_load = vout_target / iout if iout else 10.0
    else:
        iout = 1.0
        r_load = vout_target / iout if iout else 10.0
    r_load = max(r_load, 0.1)

    vin_ripple = 0.01 * vin
    c_split = iout / (2 * fsw * vin_ripple) if (fsw and vin_ripple) else 100e-6
    c_split = max(c_split, 1e-12)

    delta_i = ripple_ratio * iout
    lf = vout_peak / (8 * fsw * delta_i) if (fsw and delta_i) else 1e-3
    lf = max(lf, 1e-9)

    f_cutoff = fsw / 10
    cf = 1 / ((2 * math.pi * f_cutoff) ** 2 * lf) if (f_cutoff and lf) else 10e-6
    cf = max(cf, 1e-12)

    components = [
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": vin},
            block_ids=["dc_bus"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["dc_bus"],
        ),
        make_component(
            "C1", "Capacitor",
            role="dc_bus_cap_high",
            parameters={"capacitance": round(c_split, 9)},
            block_ids=["dc_bus"],
        ),
        make_component(
            "C2", "Capacitor",
            role="dc_bus_cap_low",
            parameters={"capacitance": round(c_split, 9)},
            block_ids=["dc_bus"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="high_side_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["half_bridge_leg"],
        ),
        make_component(
            "SW2", "MOSFET",
            role="low_side_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["half_bridge_leg"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive_high",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["half_bridge_leg"],
        ),
        make_component(
            "G2", "PWM_Generator",
            role="gate_drive_low",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["half_bridge_leg"],
        ),
        make_component(
            "Lf", "Inductor",
            role="output_filter_inductor",
            parameters={"inductance": round(lf, 9)},
            block_ids=["output_filter"],
        ),
        make_component(
            "Cf", "Capacitor",
            role="output_filter_capacitor",
            parameters={"capacitance": round(cf, 9)},
            block_ids=["output_filter"],
        ),
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["output_filter"],
        ),
    ]

    nets = [
        make_net("net_vdc_pos", ["V1.positive", "C1.positive", "SW1.drain"], role="dc_bus_positive"),
        make_net("net_cap_mid", ["C1.negative", "C2.positive"], role="cap_midpoint"),
        make_net("net_bridge_mid", ["Lf.pin1", "SW1.source", "SW2.drain"], role="bridge_midpoint"),
        make_net("net_lf_out", ["Lf.pin2", "Cf.positive", "R1.pin1"], role="output_ac"),
        make_net("net_gnd", ["V1.negative", "GND1.pin1", "C2.negative", "SW2.source", "Cf.negative", "R1.pin2"], role="ground"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_high"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_low"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="dc_source", component_ids=["V1", "GND1", "C1", "C2"]),
        make_block("half_bridge_leg", "switching", role="half_bridge", component_ids=["SW1", "SW2", "G1", "G2"]),
        make_block("output_filter", "filter", role="output", component_ids=["Lf", "Cf", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "vout_peak", round(vout_peak, 4)),
        make_trace("design_formula", "filter_inductance", round(lf, 9)),
    ]

    return CircuitGraph(
        topology="half_bridge",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vout_peak": round(vout_peak, 4),
            "c_split": round(c_split, 9),
            "filter_inductance": round(lf, 9),
            "filter_capacitance": round(cf, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(100 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Half-Bridge Inverter",
            "description": (
                f"Half-bridge inverter: {vin}V DC -> {vout_target:.1f}V peak, "
                f"fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
