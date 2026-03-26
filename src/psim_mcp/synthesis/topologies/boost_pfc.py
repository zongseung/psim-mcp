"""Boost PFC synthesizer — creates CircuitGraph from requirements.

Single-stage boost PFC: VAC -> diode bridge -> boost stage. NO position/direction/ports.
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


def synthesize_boost_pfc(requirements: dict) -> CircuitGraph:
    """Synthesize a boost PFC CircuitGraph from requirements."""
    vin_rms = float(requirements["vin"])
    fsw = float(requirements.get("fsw", 65_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.02))
    f_line = float(requirements.get("frequency", 60.0))

    vin_peak = vin_rms * math.sqrt(2)
    vout = float(requirements.get("vout_target", max(vin_peak * 1.1, 380.0)))

    pout = float(requirements.get("power", 200.0))
    if requirements.get("iout"):
        iout_val = float(requirements["iout"])
        pout = vout * iout_val

    iout = pout / vout if vout else 1.0
    r_load = vout / iout if iout else 10.0
    r_load = max(r_load, 0.1)

    iin_peak = pout * math.sqrt(2) / (vin_rms * 0.95) if vin_rms else 1.0
    d_max = 1 - vin_peak / vout if vout > vin_peak else 0.1
    d_max = max(0.05, min(d_max, 0.95))

    delta_i = ripple_ratio * iin_peak
    inductance = vin_peak * d_max / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    inductance = max(inductance, 1e-9)

    vripple = vripple_ratio * vout
    cout = pout / (2 * math.pi * f_line * vout * vripple) if (f_line and vout and vripple) else 470e-6
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
            "BR1", "DiodeBridge",
            role="diode_bridge",
            parameters={"forward_voltage": 0.7},
            block_ids=["input_rectifier"],
        ),
        make_component(
            "L1", "Inductor",
            role="boost_inductor",
            parameters={"inductance": round(inductance, 9)},
            block_ids=["boost_stage"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="boost_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["boost_stage"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" 0 {int(d_max * 360)}.",
            },
            block_ids=["boost_stage"],
        ),
        make_component(
            "D1", "Diode",
            role="boost_diode",
            parameters={"forward_voltage": 0.7},
            block_ids=["boost_stage"],
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
        make_net("net_vac_pos", ["V1.positive", "BR1.ac_pos"], role="ac_input"),
        make_net("net_vac_neg", ["V1.negative", "GND1.pin1", "BR1.ac_neg"], role="ac_return"),
        make_net("net_br_pos", ["BR1.dc_pos", "L1.pin1"], role="rectified_dc"),
        make_net("net_l_sw_d", ["L1.pin2", "SW1.drain", "D1.anode"], role="boost_switch_node"),
        make_net("net_gate", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_d_out", ["D1.cathode", "Cout.positive", "R1.pin1"], role="boost_output"),
        make_net("net_gnd", ["BR1.dc_neg", "SW1.source", "Cout.negative", "R1.pin2"], role="ground"),
    ]

    blocks = [
        make_block("ac_input", "input", role="ac_source", component_ids=["V1", "GND1"]),
        make_block("input_rectifier", "rectifier", role="rectification", component_ids=["BR1"]),
        make_block("boost_stage", "switching", role="boost_converter", component_ids=["L1", "SW1", "G1", "D1"]),
        make_block("output_filter", "filter", role="output", component_ids=["Cout", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "d_max", round(d_max, 6)),
        make_trace("design_formula", "inductance", round(inductance, 9)),
    ]

    return CircuitGraph(
        topology="boost_pfc",
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
            "name": "Boost PFC",
            "description": (
                f"Boost PFC: {vin_rms}V AC -> {vout:.0f}V DC, "
                f"P={pout:.0f}W, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
