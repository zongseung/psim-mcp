"""Flyback converter synthesizer — creates CircuitGraph from requirements.

Isolated DC-DC converter with transformer for energy storage and
voltage transformation. NO position/direction/ports.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_flyback(requirements: dict) -> CircuitGraph:
    """Synthesize a flyback converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", 100_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    # Turns ratio Ns/Np
    if requirements.get("n_ratio"):
        n = float(requirements["n_ratio"])
    else:
        d_target = 0.45
        n = d_target * vin / (vout * (1 - d_target)) if vout else 1.0
        n = max(0.1, min(n, 10.0))

    denom = vin + vout * n
    duty = (vout * n) / denom if denom else 0.5
    duty = max(0.05, min(duty, 0.95))

    pout = vout * iout
    iin = pout / (vin * duty) if (vin and duty) else iout
    delta_i = ripple_ratio * iin
    lm = vin * duty / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    lm = max(lm, 1e-9)

    vripple = vripple_ratio * vout
    cout = iout * duty / (fsw * vripple) if (fsw and vripple) else 100e-6
    cout = max(cout, 1e-12)
    r_load = vout / iout if iout else 10.0

    components = [
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": vin},
            block_ids=["primary_input"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["primary_input"],
        ),
        make_component(
            "T1", "Transformer",
            role="isolation_transformer",
            parameters={
                "np_turns": 1,
                "ns_turns": round(n, 6),
                "magnetizing_inductance": round(lm, 9),
            },
            block_ids=["magnetic_transfer"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="primary_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["switch_primary"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" 0 {int(duty * 360)}.",
            },
            block_ids=["switch_primary"],
        ),
        make_component(
            "D1", "Diode",
            role="secondary_rectifier",
            parameters={"forward_voltage": 0.7},
            block_ids=["secondary_rectifier_block"],
        ),
        make_component(
            "C1", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(cout, 9)},
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
        make_net("net_vin_pri1", ["V1.positive", "T1.primary1"], role="input_positive"),
        make_net("net_pri2_sw", ["T1.primary2", "SW1.drain"], role="primary_switch_node"),
        make_net("net_gate", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_sw_gnd", ["SW1.source", "V1.negative", "GND1.pin1"], role="primary_ground"),
        make_net("net_sec2_d", ["T1.secondary2", "D1.anode"], role="secondary_ac"),
        make_net("net_d_out", ["D1.cathode", "C1.positive", "Vout.pin1"], role="output_positive"),
        make_net("net_sec_gnd", ["T1.secondary1", "C1.negative", "Vout.pin2"], role="secondary_ground"),
    ]

    blocks = [
        make_block("primary_input", "input", role="input", component_ids=["V1", "GND1"]),
        make_block("switch_primary", "switching", role="primary_switch", component_ids=["SW1", "G1"]),
        make_block("magnetic_transfer", "transformer", role="isolation", component_ids=["T1"]),
        make_block("secondary_rectifier_block", "rectifier", role="rectification", component_ids=["D1"]),
        make_block("output_filter", "filter", role="output", component_ids=["C1", "Vout"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6), rationale="D = (Vout*n)/(Vin + Vout*n)"),
        make_trace("design_formula", "turns_ratio", round(n, 6), rationale="n chosen for D~0.45"),
        make_trace("design_formula", "magnetizing_inductance", round(lm, 9)),
    ]

    return CircuitGraph(
        topology="flyback",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "duty": round(duty, 6),
            "turns_ratio": round(n, 6),
            "magnetizing_inductance": round(lm, 9),
            "capacitance": round(cout, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(50 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Flyback Converter",
            "description": (
                f"Flyback DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                f"fsw={fsw / 1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}"
            ),
        },
    )
