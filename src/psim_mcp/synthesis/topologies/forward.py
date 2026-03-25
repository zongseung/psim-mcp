"""Forward converter synthesizer — creates CircuitGraph from requirements.

Isolated DC-DC with transformer + output LC filter + RCD demagnetization clamp.
NO position/direction/ports.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_forward(requirements: dict) -> CircuitGraph:
    """Synthesize a forward converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
    fsw = float(requirements.get("fsw", requirements.get("switching_frequency", 100_000)))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))
    rectifier_drop = float(requirements.get("rectifier_diode_drop", 0.7))
    freewheel_drop = float(requirements.get("freewheel_diode_drop", 0.7))

    # Turns ratio Ns/Np
    if requirements.get("n_ratio"):
        n = float(requirements["n_ratio"])
    else:
        d_target = 0.45
        n = (vout + freewheel_drop + d_target * (rectifier_drop - freewheel_drop)) / (vin * d_target) if (vin and d_target) else 1.0
    n = max(0.05, min(n, 10.0))

    # Duty cycle from volt-second balance
    duty_denom = vin * n - rectifier_drop + freewheel_drop
    duty = (vout + freewheel_drop) / duty_denom if duty_denom else 0.5
    duty = max(0.05, min(duty, 0.95))

    switching_points = f" 0 {int(round(duty * 360))}."

    # Output inductor
    delta_i = ripple_ratio * iout
    inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    inductance = max(inductance, 1e-9)

    # Output capacitor
    vripple = vripple_ratio * vout
    capacitance = delta_i / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
    capacitance = max(capacitance, 1e-12)

    r_load = vout / iout if iout else 10.0

    # Magnetizing inductance
    i_reflected = max(iout * n, 0.01)
    lm = vin * duty / (fsw * 0.1 * i_reflected) if (fsw and i_reflected) else 1e-3
    lm = max(lm, 1e-6)

    # RCD clamp
    i_mag_peak = vin * duty / (lm * fsw) if (lm and fsw) else 0.1
    p_clamp = max(0.5 * lm * i_mag_peak**2 * fsw, 0.1)
    r_clamp = max(1000, min(vin**2 / p_clamp, 200_000))
    c_clamp = max(20 / (fsw * r_clamp) if (fsw and r_clamp) else 100e-9, 1e-9)

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
                "Switching_Points": switching_points,
            },
            block_ids=["switch_primary"],
        ),
        # RCD clamp components
        make_component(
            "D_clamp", "Diode",
            role="clamp_diode",
            parameters={"forward_voltage": 0.01},
            block_ids=["switch_primary"],
        ),
        make_component(
            "R_clamp", "Resistor",
            role="clamp_resistor",
            parameters={"resistance": round(r_clamp, 1)},
            block_ids=["switch_primary"],
        ),
        make_component(
            "C_clamp", "Capacitor",
            role="clamp_capacitor",
            parameters={"capacitance": round(c_clamp, 12)},
            block_ids=["switch_primary"],
        ),
        make_component(
            "D1", "Diode",
            role="secondary_rectifier",
            parameters={"forward_voltage": rectifier_drop},
            block_ids=["secondary_rectifier"],
        ),
        make_component(
            "D2", "Diode",
            role="freewheel_diode",
            parameters={"forward_voltage": freewheel_drop},
            block_ids=["secondary_rectifier"],
        ),
        make_component(
            "L1", "Inductor",
            role="output_inductor",
            parameters={"inductance": round(inductance, 9)},
            block_ids=["output_filter"],
        ),
        make_component(
            "Cout", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(capacitance, 9)},
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
        make_net("net_vin_p1", ["V1.positive", "T1.primary1", "R_clamp.pin2", "C_clamp.negative"], role="input_positive"),
        make_net("net_p2_sw", ["T1.primary2", "SW1.drain", "D_clamp.anode"], role="primary_switch_node"),
        make_net("net_clamp", ["D_clamp.cathode", "R_clamp.pin1", "C_clamp.positive"], role="clamp_node"),
        make_net("net_gate", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_sec2_d1", ["T1.secondary2", "D1.anode"], role="secondary_ac"),
        make_net("net_d1_d2_l", ["D1.cathode", "D2.cathode", "L1.pin1"], role="secondary_positive"),
        make_net("net_out", ["L1.pin2", "Cout.positive", "Vout.pin1"], role="output_positive"),
        make_net("net_sec_gnd", ["T1.secondary1", "D2.anode", "Cout.negative", "Vout.pin2"], role="secondary_ground"),
        make_net("net_pri_gnd", ["SW1.source", "V1.negative", "GND1.pin1"], role="primary_ground"),
    ]

    blocks = [
        make_block("primary_input", "input", role="primary_source", component_ids=["V1", "GND1"]),
        make_block("switch_primary", "switching", role="primary_switch", component_ids=["SW1", "G1", "D_clamp", "R_clamp", "C_clamp"]),
        make_block("magnetic_transfer", "transformer", role="isolation", component_ids=["T1"]),
        make_block("secondary_rectifier", "rectifier", role="rectification", component_ids=["D1", "D2"]),
        make_block("output_filter", "filter", role="output", component_ids=["L1", "Cout", "Vout"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6)),
        make_trace("design_formula", "turns_ratio", round(n, 6)),
        make_trace("design_formula", "inductance", round(inductance, 9)),
    ]

    return CircuitGraph(
        topology="forward",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "duty": round(duty, 6),
            "turns_ratio": round(n, 6),
            "inductance": round(inductance, 9),
            "capacitance": round(capacitance, 9),
            "magnetizing_inductance": round(lm, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(500 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Forward Converter",
            "description": (
                f"Forward DC-DC: {vin}V -> {vout}V @ {iout}A, "
                f"fsw={fsw / 1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}"
            ),
        },
    )
