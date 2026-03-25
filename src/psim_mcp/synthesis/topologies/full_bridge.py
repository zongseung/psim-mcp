"""Full-bridge inverter synthesizer — creates CircuitGraph from requirements.

Four-switch H-bridge for DC-AC or DC-DC conversion. NO position/direction/ports.
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


def synthesize_full_bridge(requirements: dict) -> CircuitGraph:
    """Synthesize a full-bridge inverter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    fsw = float(requirements.get("fsw", 20_000))
    m = float(requirements.get("modulation_index", 0.8))
    m = max(0.1, min(m, 1.0))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))

    vout_rms = m * vin / 2
    vout_target = float(requirements.get("vout_target", vout_rms))

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

    delta_i = ripple_ratio * iout
    lf = vin / (8 * fsw * delta_i) if (fsw and delta_i) else 1e-3
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
        # Left leg
        make_component(
            "SW1", "MOSFET",
            role="switch_leg_a_high",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["full_bridge_legs"],
        ),
        make_component(
            "SW3", "MOSFET",
            role="switch_leg_a_low",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["full_bridge_legs"],
        ),
        # Right leg
        make_component(
            "SW2", "MOSFET",
            role="switch_leg_b_high",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["full_bridge_legs"],
        ),
        make_component(
            "SW4", "MOSFET",
            role="switch_leg_b_low",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["full_bridge_legs"],
        ),
        # Gate drives: diagonal pairs SW1+SW4 = "0,180"; SW2+SW3 = "180,360"
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive_leg_a_high",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["full_bridge_legs"],
        ),
        make_component(
            "G3", "PWM_Generator",
            role="gate_drive_leg_a_low",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["full_bridge_legs"],
        ),
        make_component(
            "G2", "PWM_Generator",
            role="gate_drive_leg_b_high",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["full_bridge_legs"],
        ),
        make_component(
            "G4", "PWM_Generator",
            role="gate_drive_leg_b_low",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["full_bridge_legs"],
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
        make_net("net_vdc_high", ["V1.positive", "SW1.drain", "SW2.drain"], role="dc_bus_positive"),
        make_net("net_left_mid", ["Lf.pin1", "SW1.source", "SW3.drain"], role="output_ac"),
        make_net("net_right_mid", ["R1.pin1", "SW2.source", "SW4.drain"], role="output_return"),
        make_net("net_lf_out", ["Lf.pin2", "Cf.positive"], role="filter_output"),
        make_net("net_load_return", ["Cf.negative", "R1.pin2"], role="load_return"),
        make_net("net_gnd", ["V1.negative", "GND1.pin1", "SW3.source", "SW4.source"], role="ground"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_leg_a_high"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_leg_b_high"),
        make_net("net_gate3", ["G3.output", "SW3.gate"], role="drive_leg_a_low"),
        make_net("net_gate4", ["G4.output", "SW4.gate"], role="drive_leg_b_low"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="dc_source", component_ids=["V1", "GND1"]),
        make_block("full_bridge_legs", "switching", role="h_bridge", component_ids=["SW1", "SW2", "SW3", "SW4", "G1", "G2", "G3", "G4"]),
        make_block("output_filter", "filter", role="output", component_ids=["Lf", "Cf", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "modulation_index", round(m, 4)),
        make_trace("design_formula", "vout_rms", round(vout_rms, 4)),
        make_trace("design_formula", "filter_inductance", round(lf, 9)),
    ]

    return CircuitGraph(
        topology="full_bridge",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "modulation_index": round(m, 4),
            "vout_rms": round(vout_rms, 4),
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
            "name": "Full-Bridge Inverter",
            "description": (
                f"Full-bridge inverter: {vin}V DC -> {vout_target:.1f}V RMS, "
                f"fsw={fsw / 1e3:.1f}kHz, m={m:.2f}"
            ),
        },
    )
