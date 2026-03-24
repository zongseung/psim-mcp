"""Buck converter synthesizer — creates CircuitGraph from requirements.

Extracts sizing parameters and creates components with roles, nets with
roles, and functional blocks. NO position/direction/ports.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_buck(requirements: dict) -> CircuitGraph:
    """Synthesize a buck converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", 50_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    duty = vout / vin
    delta_i = ripple_ratio * iout
    inductance = vout * (1 - duty) / (fsw * delta_i) if delta_i else 1e-3
    capacitance = delta_i / (8 * fsw * vripple_ratio * vout) if vout else 100e-6
    r_load = vout / iout if iout else 10.0

    components = [
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": vin},
            block_ids=["input_stage"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["input_stage"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="main_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["switch_stage"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f"0,{int(duty * 360)}",
            },
            block_ids=["switch_stage"],
        ),
        make_component(
            "D1", "Diode",
            role="freewheel_diode",
            parameters={"forward_voltage": 0.7},
            block_ids=["switch_stage"],
        ),
        make_component(
            "L1", "Inductor",
            role="output_inductor",
            parameters={"inductance": round(inductance, 9), "CurrentFlag": 1},
            block_ids=["output_filter"],
        ),
        make_component(
            "C1", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(capacitance, 9)},
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
        make_net("net_vin_sw", ["V1.positive", "SW1.drain"], role="input_positive"),
        make_net("net_sw_junc", ["SW1.source", "D1.cathode", "L1.pin1"], role="switch_node"),
        make_net("net_gate", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_out", ["L1.pin2", "C1.positive", "R1.pin1"], role="output_positive"),
        make_net(
            "net_gnd",
            ["V1.negative", "GND1.pin1", "D1.anode", "C1.negative", "R1.pin2"],
            role="ground",
        ),
    ]

    blocks = [
        make_block("input_stage", "input", role="input", component_ids=["V1", "GND1"]),
        make_block("switch_stage", "switching", role="switching", component_ids=["SW1", "D1", "G1"]),
        make_block("output_filter", "filter", role="output", component_ids=["L1", "C1", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6), rationale="D = Vout / Vin"),
        make_trace("design_formula", "inductance", round(inductance, 9), rationale="L = Vout*(1-D)/(fsw*dI)"),
        make_trace("design_formula", "capacitance", round(capacitance, 9), rationale="C = dI/(8*fsw*dVr*Vout)"),
    ]

    return CircuitGraph(
        topology="buck",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
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
            "name": "Buck Converter",
            "description": (
                f"Buck DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                f"fsw={fsw / 1e3:.1f}kHz, D={duty:.3f}"
            ),
        },
    )
