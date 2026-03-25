"""Three-phase inverter synthesizer — creates CircuitGraph from requirements.

Six-switch two-level inverter with 120-degree phase-shifted gating.
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


def synthesize_three_phase_inverter(requirements: dict) -> CircuitGraph:
    """Synthesize a three-phase inverter CircuitGraph from requirements."""
    vdc = float(requirements.get("vdc", requirements.get("vin", 48.0)))
    r_load = float(requirements.get("load_resistance",
                                    float(requirements.get("vout_target", vdc * 0.5)) /
                                    max(float(requirements.get("iout", 1.0)), 1e-6)))
    r_load = max(r_load, 0.1)
    fsw = float(requirements.get("fsw", 10_000))

    components = [
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": round(vdc, 4)},
            block_ids=["dc_bus"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["dc_bus"],
        ),
        # Phase A
        make_component(
            "SW1", "MOSFET",
            role="switch_a_high",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["phase_a_leg"],
        ),
        make_component(
            "SW2", "MOSFET",
            role="switch_a_low",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["phase_a_leg"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["phase_a_leg"],
        ),
        make_component(
            "G2", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["phase_a_leg"],
        ),
        # Phase B
        make_component(
            "SW3", "MOSFET",
            role="switch_b_high",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["phase_b_leg"],
        ),
        make_component(
            "SW4", "MOSFET",
            role="switch_b_low",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["phase_b_leg"],
        ),
        make_component(
            "G3", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 120 300."},
            block_ids=["phase_b_leg"],
        ),
        make_component(
            "G4", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 300 480."},
            block_ids=["phase_b_leg"],
        ),
        # Phase C
        make_component(
            "SW5", "MOSFET",
            role="switch_c_high",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["phase_c_leg"],
        ),
        make_component(
            "SW6", "MOSFET",
            role="switch_c_low",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["phase_c_leg"],
        ),
        make_component(
            "G5", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 240 420."},
            block_ids=["phase_c_leg"],
        ),
        make_component(
            "G6", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 60 240."},
            block_ids=["phase_c_leg"],
        ),
        # Loads (star-connected)
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["load"],
        ),
        make_component(
            "R2", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4)},
            block_ids=["load"],
        ),
        make_component(
            "R3", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4)},
            block_ids=["load"],
        ),
    ]

    nets = [
        make_net("net_vdc_pos", ["V1.positive", "SW1.drain", "SW3.drain", "SW5.drain"],
                 role="dc_bus_positive"),
        make_net("net_gnd", ["V1.negative", "GND1.pin1", "SW2.source", "SW4.source", "SW6.source"],
                 role="ground"),
        make_net("net_phase_a", ["SW1.source", "SW2.drain", "R1.pin1"], role="phase_a"),
        make_net("net_phase_b", ["SW3.source", "SW4.drain", "R2.pin1"], role="phase_b"),
        make_net("net_phase_c", ["SW5.source", "SW6.drain", "R3.pin1"], role="phase_c"),
        make_net("net_star", ["R1.pin2", "R2.pin2", "R3.pin2"], role="star_point"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_signal"),
        make_net("net_gate3", ["G3.output", "SW3.gate"], role="drive_signal"),
        make_net("net_gate4", ["G4.output", "SW4.gate"], role="drive_signal"),
        make_net("net_gate5", ["G5.output", "SW5.gate"], role="drive_signal"),
        make_net("net_gate6", ["G6.output", "SW6.gate"], role="drive_signal"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="dc_source", component_ids=["V1", "GND1"]),
        make_block("leg_a", "switching", role="phase_a",
                   component_ids=["SW1", "SW2", "G1", "G2"]),
        make_block("leg_b", "switching", role="phase_b",
                   component_ids=["SW3", "SW4", "G3", "G4"]),
        make_block("leg_c", "switching", role="phase_c",
                   component_ids=["SW5", "SW6", "G5", "G6"]),
        make_block("load", "output", role="ac_load", component_ids=["R1", "R2", "R3"]),
    ]

    traces = [
        make_trace("design_formula", "vdc", round(vdc, 4)),
        make_trace("design_formula", "fsw", fsw),
    ]

    return CircuitGraph(
        topology="three_phase_inverter",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vdc": round(vdc, 4),
            "r_load": round(r_load, 4),
            "fsw": round(fsw, 2),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(100 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Three-Phase Inverter",
            "description": (
                f"3-phase inverter: Vdc={vdc}V, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
