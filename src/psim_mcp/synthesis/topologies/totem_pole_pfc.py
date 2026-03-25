"""Totem-pole bridgeless PFC synthesizer — creates CircuitGraph from requirements.

VAC → boost inductor → HF MOSFET pair + LF MOSFET pair → output. NO position/direction/ports.
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


def synthesize_totem_pole_pfc(requirements: dict) -> CircuitGraph:
    """Synthesize a totem-pole PFC CircuitGraph from requirements."""
    vac_rms = float(requirements.get("vac_rms", requirements.get("vin", 220.0)))
    fsw = float(requirements.get("fsw", 65_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.02))
    f_line = float(requirements.get("frequency", 60.0))

    vin_peak = vac_rms * math.sqrt(2)
    vout = float(requirements.get("vout_target", max(vin_peak * 1.1, 400.0)))
    pout = float(requirements.get("power", 500.0))

    iout = pout / vout if vout else 1.0
    r_load = vout / iout if iout else 10.0
    r_load = max(r_load, 0.1)
    iin_peak = pout * math.sqrt(2) / (vac_rms * 0.95) if vac_rms else 1.0
    d_max = 1 - vin_peak / vout if vout > vin_peak else 0.1
    d_max = max(0.05, min(d_max, 0.95))

    delta_i = ripple_ratio * iin_peak
    inductance = vin_peak * d_max / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    inductance = max(inductance, 1e-9)
    vripple = vripple_ratio * vout
    cout = pout / (2 * f_line * vout * vripple) if (f_line and vout and vripple) else 470e-6
    cout = max(cout, 1e-12)

    components = [
        make_component(
            "V1", "AC_Source",
            role="ac_source",
            parameters={"amplitude": round(vin_peak, 4), "frequency": f_line},
            block_ids=["ac_input"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["ac_input"],
        ),
        make_component(
            "L1", "Inductor",
            role="boost_inductor",
            parameters={"inductance": round(inductance, 9), "CurrentFlag": 1},
            block_ids=["boost_stage"],
        ),
        # HF switching leg
        make_component(
            "SW_HF1", "MOSFET",
            role="high_freq_switch_a",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["hf_leg"],
        ),
        make_component(
            "SW_HF2", "MOSFET",
            role="high_freq_switch_b",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["hf_leg"],
        ),
        make_component(
            "G_HF1", "PWM_Generator",
            role="hf_gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2,
                        "Switching_Points": f" 0 {int(d_max * 360)}."},
            block_ids=["hf_leg"],
        ),
        make_component(
            "G_HF2", "PWM_Generator",
            role="hf_gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2,
                        "Switching_Points": f" {int(d_max * 360)} 360."},
            block_ids=["hf_leg"],
        ),
        # LF polarity-steering leg
        make_component(
            "SW_LF1", "MOSFET",
            role="low_freq_switch_a",
            parameters={"switching_frequency": f_line, "on_resistance": 0.01},
            block_ids=["lf_leg"],
        ),
        make_component(
            "SW_LF2", "MOSFET",
            role="low_freq_switch_b",
            parameters={"switching_frequency": f_line, "on_resistance": 0.01},
            block_ids=["lf_leg"],
        ),
        make_component(
            "G_LF1", "PWM_Generator",
            role="lf_gate_drive",
            parameters={"Frequency": f_line, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["lf_leg"],
        ),
        make_component(
            "G_LF2", "PWM_Generator",
            role="lf_gate_drive",
            parameters={"Frequency": f_line, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["lf_leg"],
        ),
        make_component(
            "Cout", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(cout, 9)},
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
        make_net("net_vac_pos_l", ["V1.positive", "L1.pin1"], role="ac_input"),
        make_net("net_l_hf_mid", ["L1.pin2", "SW_HF1.source", "SW_HF2.drain"], role="boost_node"),
        make_net("net_vac_neg_lf",
                 ["V1.negative", "GND1.pin1", "SW_LF1.source", "SW_LF2.drain"],
                 role="ac_return"),
        make_net("net_dc_pos",
                 ["SW_HF1.drain", "SW_LF1.drain", "Cout.positive", "R1.pin1"],
                 role="dc_output"),
        make_net("net_dc_neg",
                 ["SW_HF2.source", "SW_LF2.source", "Cout.negative", "R1.pin2"],
                 role="ground"),
        make_net("net_g_hf1", ["G_HF1.output", "SW_HF1.gate"], role="drive_signal"),
        make_net("net_g_hf2", ["G_HF2.output", "SW_HF2.gate"], role="drive_signal"),
        make_net("net_g_lf1", ["G_LF1.output", "SW_LF1.gate"], role="drive_signal"),
        make_net("net_g_lf2", ["G_LF2.output", "SW_LF2.gate"], role="drive_signal"),
    ]

    blocks = [
        make_block("ac_input", "input", role="ac_source", component_ids=["V1", "GND1"]),
        make_block("totem_pole_bridge", "switching", role="totem_pole",
                   component_ids=["L1", "SW_HF1", "SW_HF2", "G_HF1", "G_HF2",
                                  "SW_LF1", "SW_LF2", "G_LF1", "G_LF2"]),
        make_block("output_filter", "output", role="dc_output", component_ids=["Cout", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "d_max", round(d_max, 6)),
        make_trace("design_formula", "inductance", round(inductance, 9)),
    ]

    return CircuitGraph(
        topology="totem_pole_pfc",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "d_max": round(d_max, 6),
            "vin_peak": round(vin_peak, 4),
            "inductance": round(inductance, 9),
            "capacitance": round(cout, 9),
            "r_load": round(r_load, 4),
            "power": round(pout, 2),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(3 / f_line, 6),
        },
        traces=traces,
        metadata={
            "name": "Totem-Pole Bridgeless PFC",
            "description": (
                f"Totem-pole PFC: {vac_rms}V AC -> {vout:.0f}V DC, P={pout:.0f}W"
            ),
        },
    )
