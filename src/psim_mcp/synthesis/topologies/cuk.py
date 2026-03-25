"""Cuk converter synthesizer — creates CircuitGraph from requirements.

Non-isolated inverting DC-DC converter with coupling capacitor. NO position/direction/ports.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_cuk(requirements: dict) -> CircuitGraph:
    """Synthesize a Cuk converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", requirements.get("switching_frequency", 50_000)))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    denom = vin + vout
    duty = vout / denom if denom else 0.5
    duty = max(0.05, min(duty, 0.95))

    iin = iout * duty / (1 - duty) if duty < 1 else iout
    delta_il1 = ripple_ratio * iin
    l1 = vin * duty / (fsw * delta_il1) if (fsw and delta_il1) else 1e-3
    l1 = max(l1, 1e-9)

    delta_il2 = ripple_ratio * iout
    l2 = vout * (1 - duty) / (fsw * delta_il2) if (fsw and delta_il2) else 1e-3
    l2 = max(l2, 1e-9)

    vc1_ripple = 0.05 * denom
    c_coupling = iout * duty / (fsw * vc1_ripple) if (fsw and vc1_ripple) else 10e-6
    c_coupling = max(c_coupling, 1e-12)

    vripple = vripple_ratio * vout
    c_out = delta_il2 / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
    c_out = max(c_out, 1e-12)

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
            "L1", "Inductor",
            role="input_inductor",
            parameters={"inductance": round(l1, 9)},
            block_ids=["switch_stage"],
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
                "Switching_Points": f" 0 {int(duty * 360)}.",
            },
            block_ids=["switch_stage"],
        ),
        make_component(
            "Cc", "Capacitor",
            role="coupling_capacitor",
            parameters={"capacitance": round(c_coupling, 9)},
            block_ids=["coupling_capacitor"],
        ),
        make_component(
            "D1", "Diode",
            role="output_diode",
            parameters={"forward_voltage": 0.7},
            block_ids=["coupling_capacitor"],
        ),
        make_component(
            "L2", "Inductor",
            role="output_inductor",
            parameters={"inductance": round(l2, 9)},
            block_ids=["output_filter"],
        ),
        make_component(
            "C2", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(c_out, 9)},
            block_ids=["output_filter"],
        ),
        make_component(
            "Vout", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["output_filter"],
        ),
    ]

    nets = [
        make_net("net_vin_l1", ["V1.positive", "L1.pin1"], role="input_positive"),
        make_net("net_l1_sw_cc", ["L1.pin2", "SW1.drain", "Cc.positive"], role="switch_node"),
        make_net("net_gate", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_cc_d_l2", ["Cc.negative", "D1.cathode", "L2.pin1"], role="coupling_node"),
        make_net("net_l2_out", ["L2.pin2", "C2.positive", "Vout.pin1"], role="output_positive"),
        make_net(
            "net_gnd",
            ["V1.negative", "GND1.pin1", "SW1.source", "D1.anode", "C2.negative", "Vout.pin2"],
            role="ground",
        ),
    ]

    blocks = [
        make_block("input_stage", "input", role="input", component_ids=["V1", "GND1"]),
        make_block("switch_stage", "switching", role="switching", component_ids=["L1", "SW1", "G1"]),
        make_block("coupling_capacitor", "coupling", role="coupling", component_ids=["Cc", "D1"]),
        make_block("output_filter", "filter", role="output", component_ids=["L2", "C2", "Vout"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6), rationale="D = Vout/(Vin+Vout)"),
        make_trace("design_formula", "l1_inductance", round(l1, 9), rationale="L1 = Vin*D/(fsw*dIL1)"),
        make_trace("design_formula", "l2_inductance", round(l2, 9), rationale="L2 = Vout*(1-D)/(fsw*dIL2)"),
        make_trace("design_formula", "c_coupling", round(c_coupling, 9)),
    ]

    return CircuitGraph(
        topology="cuk",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "duty": round(duty, 6),
            "l1_inductance": round(l1, 9),
            "l2_inductance": round(l2, 9),
            "c_coupling": round(c_coupling, 9),
            "c_output": round(c_out, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(50 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Cuk Converter",
            "description": (
                f"Cuk DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                f"fsw={fsw / 1e3:.1f}kHz, D={duty:.3f}"
            ),
        },
    )
