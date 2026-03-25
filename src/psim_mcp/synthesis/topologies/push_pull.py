"""Push-pull converter synthesizer — creates CircuitGraph from requirements.

Center-tap transformer with two primary switches and full-wave secondary rectifier.
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


def synthesize_push_pull(requirements: dict) -> CircuitGraph:
    """Synthesize a push-pull converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", 1.0))
    fsw = float(requirements.get("fsw", 100_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    if requirements.get("n_ratio"):
        n = float(requirements["n_ratio"])
    else:
        d_target = 0.4
        n = d_target * vin / vout if vout else 1.0
        n = max(0.1, min(n, 10.0))

    duty = n * vout / vin if vin else 0.5
    duty = max(0.05, min(duty, 0.48))

    delta_i = ripple_ratio * iout
    inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    inductance = max(inductance, 1e-9)
    vripple = vripple_ratio * vout
    capacitance = iout * duty / (fsw * vripple) if (fsw and vripple) else 100e-6
    capacitance = max(capacitance, 1e-12)
    r_load = vout / iout if iout else 10.0

    components = [
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": round(vin, 4)},
            block_ids=["primary_input"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["primary_input"],
        ),
        make_component(
            "T1", "Center_Tap_Transformer",
            role="center_tap_transformer",
            parameters={"turns_ratio": round(1.0 / n, 6)},
            block_ids=["magnetic_transfer"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="primary_switch_a",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["switch_primary"],
        ),
        make_component(
            "SW2", "MOSFET",
            role="primary_switch_b",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["switch_primary"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive_a",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" 0 {int(duty * 360)}.",
            },
            block_ids=["switch_primary"],
        ),
        make_component(
            "G2", "PWM_Generator",
            role="gate_drive_b",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" 180 {180 + int(duty * 360)}.",
            },
            block_ids=["switch_primary"],
        ),
        make_component(
            "D1", "Diode",
            role="secondary_rectifier",
            parameters={"forward_voltage": 0.5},
            block_ids=["secondary_rectifier"],
        ),
        make_component(
            "D2", "Diode",
            role="secondary_rectifier",
            parameters={"forward_voltage": 0.5},
            block_ids=["secondary_rectifier"],
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
        make_net("net_vin_ct", ["V1.positive", "T1.primary_center"], role="input_positive"),
        make_net("net_ptop_sw1", ["T1.primary_top", "SW1.drain"], role="primary_top"),
        make_net("net_pbot_sw2", ["T1.primary_bottom", "SW2.drain"], role="primary_bottom"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_signal_a"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_signal_b"),
        make_net("net_gnd_pri", ["SW1.source", "SW2.source", "V1.negative", "GND1.pin1"], role="primary_ground"),
        make_net("net_stop_d1", ["T1.secondary_top", "D1.anode"], role="secondary_top"),
        make_net("net_sbot_d2", ["T1.secondary_bottom", "D2.anode"], role="secondary_bottom"),
        make_net("net_rect_l", ["D1.cathode", "D2.cathode", "L1.pin1"], role="secondary_positive"),
        make_net("net_out", ["L1.pin2", "C1.positive", "R1.pin1"], role="dc_output"),
        make_net("net_sec_gnd", ["T1.secondary_center", "C1.negative", "R1.pin2"], role="secondary_ground"),
    ]

    blocks = [
        make_block("primary_input", "input", role="dc_input", component_ids=["V1", "GND1"]),
        make_block("push_pull_switches", "switching", role="primary_switches", component_ids=["SW1", "SW2", "G1", "G2"]),
        make_block("magnetic_transfer", "transformer", role="isolation", component_ids=["T1"]),
        make_block("secondary_rectifier", "rectifier", role="secondary_rect", component_ids=["D1", "D2"]),
        make_block("output_filter", "filter", role="output", component_ids=["L1", "C1", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6)),
        make_trace("design_formula", "turns_ratio_NsNp", round(n, 6)),
    ]

    return CircuitGraph(
        topology="push_pull",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "duty": round(duty, 6),
            "turns_ratio": round(n, 6),
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
            "name": "Push-Pull Converter",
            "description": (
                f"Push-pull DC-DC: {vin}V -> {vout}V @ {iout}A, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
