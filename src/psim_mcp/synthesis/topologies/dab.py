"""Dual Active Bridge (DAB) synthesizer — creates CircuitGraph from requirements.

Two full H-bridges linked by series inductor and ideal transformer.
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


def synthesize_dab(requirements: dict) -> CircuitGraph:
    """Synthesize a DAB converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    iout = float(requirements.get("iout", 1.0))
    pout = float(requirements.get("power", vout * iout))
    fsw = float(requirements.get("fsw", 100_000))
    phi_deg = float(requirements.get("phase_shift_deg", 30.0))
    phi_deg = max(5.0, min(phi_deg, 85.0))
    phi = math.radians(phi_deg)

    n = vout / vin if vin else 1.0
    n = max(0.1, min(n, 20.0))
    ls = vin * vout * phi * (math.pi - phi) / (2 * math.pi**2 * fsw * pout) if (fsw and pout) else 10e-6
    ls = max(ls, 1e-9)
    r_load = vout**2 / pout if pout else 10.0
    r_load = max(r_load, 0.1)

    # Output capacitor (not in legacy generator but required by topology_metadata)
    c_out = pout / (2 * math.pi * 1000 * vout * 0.02 * vout) if vout else 10e-6
    c_out = max(c_out, 1e-12)

    b2_on = round(phi_deg, 1)
    b2_off = round(phi_deg + 180, 1)
    b2_comp_on = round(phi_deg + 180, 1)
    b2_comp_off = round(phi_deg + 360, 1)

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
        # Primary bridge — left leg
        make_component(
            "SW1", "MOSFET",
            role="primary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["primary_bridge"],
        ),
        make_component(
            "SW3", "MOSFET",
            role="primary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["primary_bridge"],
        ),
        # Primary bridge — right leg
        make_component(
            "SW2", "MOSFET",
            role="primary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["primary_bridge"],
        ),
        make_component(
            "SW4", "MOSFET",
            role="primary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["primary_bridge"],
        ),
        make_component("G1", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
                       block_ids=["primary_bridge"]),
        make_component("G2", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
                       block_ids=["primary_bridge"]),
        make_component("G3", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
                       block_ids=["primary_bridge"]),
        make_component("G4", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
                       block_ids=["primary_bridge"]),
        # Series inductor + ideal transformer
        make_component(
            "Ls", "Inductor",
            role="series_inductor",
            parameters={"inductance": round(ls, 9), "CurrentFlag": 1},
            block_ids=["magnetic_transfer"],
        ),
        make_component(
            "T1", "IdealTransformer",
            role="isolation_transformer",
            parameters={"np_turns": 1, "ns_turns": round(n, 6)},
            block_ids=["magnetic_transfer"],
        ),
        # Secondary bridge — left leg
        make_component(
            "SW5", "MOSFET",
            role="secondary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["secondary_bridge"],
        ),
        make_component(
            "SW7", "MOSFET",
            role="secondary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["secondary_bridge"],
        ),
        # Secondary bridge — right leg
        make_component(
            "SW6", "MOSFET",
            role="secondary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["secondary_bridge"],
        ),
        make_component(
            "SW8", "MOSFET",
            role="secondary_bridge_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["secondary_bridge"],
        ),
        make_component("G5", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2,
                                   "Switching_Points": f" {b2_on} {b2_off}."},
                       block_ids=["secondary_bridge"]),
        make_component("G6", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2,
                                   "Switching_Points": f" {b2_comp_on} {b2_comp_off}."},
                       block_ids=["secondary_bridge"]),
        make_component("G7", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2,
                                   "Switching_Points": f" {b2_comp_on} {b2_comp_off}."},
                       block_ids=["secondary_bridge"]),
        make_component("G8", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2,
                                   "Switching_Points": f" {b2_on} {b2_off}."},
                       block_ids=["secondary_bridge"]),
        # Output
        make_component(
            "C1", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(c_out, 9)},
            block_ids=["secondary_output"],
        ),
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["secondary_output"],
        ),
        make_component(
            "GND2", "Ground",
            role="secondary_gnd_ref",
            block_ids=["secondary_output"],
        ),
    ]

    nets = [
        make_net("net_vdc_pos", ["V1.positive", "SW1.drain", "SW2.drain"], role="input_positive"),
        make_net("net_gnd_pri", ["V1.negative", "GND1.pin1", "SW3.source", "SW4.source"], role="primary_ground"),
        make_net("net_b1_left_mid", ["SW1.source", "SW3.drain", "Ls.pin1"], role="primary_left_mid"),
        make_net("net_ls_tf", ["Ls.pin2", "T1.primary1"], role="primary_xfmr"),
        make_net("net_b1_right_mid", ["SW2.source", "SW4.drain", "T1.primary2"], role="primary_right_mid"),
        make_net("net_gate_g1", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_gate_g2", ["G2.output", "SW2.gate"], role="drive_signal"),
        make_net("net_gate_g3", ["G3.output", "SW3.gate"], role="drive_signal"),
        make_net("net_gate_g4", ["G4.output", "SW4.gate"], role="drive_signal"),
        make_net("net_sec_pos",
                 ["T1.secondary1", "SW5.drain", "SW6.drain", "C1.positive", "R1.pin1"],
                 role="secondary_positive"),
        make_net("net_gnd_sec",
                 ["T1.secondary2", "GND2.pin1", "SW7.source", "SW8.source", "C1.negative", "R1.pin2"],
                 role="secondary_ground"),
        make_net("net_b2_left_mid", ["SW5.source", "SW7.drain"], role="secondary_left_mid"),
        make_net("net_b2_right_mid", ["SW6.source", "SW8.drain"], role="secondary_right_mid"),
        make_net("net_gate_g5", ["G5.output", "SW5.gate"], role="drive_signal"),
        make_net("net_gate_g6", ["G6.output", "SW6.gate"], role="drive_signal"),
        make_net("net_gate_g7", ["G7.output", "SW7.gate"], role="drive_signal"),
        make_net("net_gate_g8", ["G8.output", "SW8.gate"], role="drive_signal"),
    ]

    blocks = [
        make_block("primary_input", "input", role="dc_input", component_ids=["V1", "GND1"]),
        make_block("primary_bridge", "switching", role="primary_h_bridge",
                   component_ids=["SW1", "SW2", "SW3", "SW4", "G1", "G2", "G3", "G4"]),
        make_block("transformer_stage", "transformer", role="isolation", component_ids=["Ls", "T1"]),
        make_block("secondary_bridge", "switching", role="secondary_h_bridge",
                   component_ids=["SW5", "SW6", "SW7", "SW8", "G5", "G6", "G7", "G8"]),
        make_block("secondary_output", "output", role="dc_output", component_ids=["C1", "R1", "GND2"]),
    ]

    traces = [
        make_trace("design_formula", "phase_shift_deg", round(phi_deg, 2)),
        make_trace("design_formula", "series_inductance", round(ls, 9)),
    ]

    return CircuitGraph(
        topology="dab",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "turns_ratio": round(n, 6),
            "phase_shift_deg": round(phi_deg, 2),
            "series_inductance": round(ls, 9),
            "r_load": round(r_load, 4),
            "power": round(pout, 2),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(50 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Dual Active Bridge",
            "description": (
                f"DAB: {vin}V -> {vout}V, P={pout}W, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
