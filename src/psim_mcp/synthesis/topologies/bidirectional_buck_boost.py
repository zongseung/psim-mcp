"""Bidirectional buck-boost converter synthesizer — creates CircuitGraph from requirements.

Non-isolated half-bridge bidirectional DC-DC converter. NO position/direction/ports.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_bidirectional_buck_boost(requirements: dict) -> CircuitGraph:
    """Synthesize a bidirectional buck-boost CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", requirements.get("switching_frequency", 50_000)))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    if vin >= vout:
        duty = vout / vin if vin else 0.5
        operating_mode = "buck"
    else:
        duty = 1 - vin / vout if vout else 0.5
        operating_mode = "boost"
    duty = max(0.05, min(duty, 0.95))

    d_buck = vout / vin if vin else 0.5
    d_buck = max(0.05, min(d_buck, 0.95))
    delta_i_buck = ripple_ratio * iout
    l_buck = vout * (1 - d_buck) / (fsw * delta_i_buck) if (fsw and delta_i_buck) else 1e-3

    d_boost = 1 - vin / vout if (vout and vout > vin) else 0.1
    d_boost = max(0.05, min(d_boost, 0.95))
    iin_boost = iout * vout / vin if vin else iout
    delta_i_boost = ripple_ratio * iin_boost
    l_boost = vin * d_boost / (fsw * delta_i_boost) if (fsw and delta_i_boost) else 1e-3

    inductance = max(l_buck, l_boost, 1e-9)

    vripple = vripple_ratio * vout
    c_buck = delta_i_buck / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
    c_boost = iout * d_boost / (fsw * vripple) if (fsw and vripple) else 100e-6
    capacitance = max(c_buck, c_boost, 1e-12)

    r_load = vout / iout if iout else 10.0

    components = [
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": vin},
            block_ids=["high_side"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["high_side"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="high_side_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["switch_stage"],
        ),
        make_component(
            "SW2", "MOSFET",
            role="low_side_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["switch_stage"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive_high",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" 0 {int(duty * 360)}.",
            },
            block_ids=["switch_stage"],
        ),
        make_component(
            "G2", "PWM_Generator",
            role="gate_drive_low",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" {int(duty * 360)} 360.",
            },
            block_ids=["switch_stage"],
        ),
        make_component(
            "L1", "Inductor",
            role="inductor",
            parameters={"inductance": round(inductance, 9)},
            block_ids=["low_side"],
        ),
        make_component(
            "C_in", "Capacitor",
            role="capacitor_high",
            parameters={"capacitance": round(capacitance, 9)},
            block_ids=["high_side"],
        ),
        make_component(
            "C1", "Capacitor",
            role="capacitor_low",
            parameters={"capacitance": round(capacitance, 9)},
            block_ids=["low_side"],
        ),
        make_component(
            "Vout", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["low_side"],
        ),
    ]

    nets = [
        make_net("net_vin_sw1", ["V1.positive", "SW1.drain", "C_in.positive"], role="high_side_positive"),
        make_net("net_sw_node", ["L1.pin1", "SW1.source", "SW2.drain"], role="switch_node"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_high"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_low"),
        make_net("net_l_out", ["L1.pin2", "C1.positive", "Vout.pin1"], role="low_side_positive"),
        make_net(
            "net_gnd",
            ["V1.negative", "GND1.pin1", "SW2.source", "C_in.negative", "C1.negative", "Vout.pin2"],
            role="ground",
        ),
    ]

    blocks = [
        make_block("high_side", "input", role="high_voltage_side", component_ids=["V1", "GND1", "C_in"]),
        make_block("switch_stage", "switching", role="switching", component_ids=["SW1", "SW2", "G1", "G2"]),
        make_block("low_side", "output", role="low_voltage_side", component_ids=["L1", "C1", "Vout"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6), rationale=f"D for {operating_mode} mode"),
        make_trace("design_formula", "operating_mode", operating_mode),
        make_trace("design_formula", "inductance", round(inductance, 9)),
    ]

    return CircuitGraph(
        topology="bidirectional_buck_boost",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "operating_mode": operating_mode,
            "duty": round(duty, 6),
            "inductance": round(inductance, 9),
            "capacitance": round(capacitance, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(50 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Bidirectional Buck-Boost Converter",
            "description": (
                f"Bidirectional buck-boost: {vin}V <-> {vout}V @ {iout}A, "
                f"fsw={fsw / 1e3:.1f}kHz, mode={operating_mode}, D={duty:.3f}"
            ),
        },
    )
