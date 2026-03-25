"""Induction motor V/f drive synthesizer — creates CircuitGraph from requirements.

Three-phase IGBT bridge driving an induction motor with V/f open-loop control.
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


def synthesize_induction_motor_vf(requirements: dict) -> CircuitGraph:
    """Synthesize an induction motor V/f drive CircuitGraph from requirements."""
    vdc = float(requirements.get("vdc", requirements.get("vin", 48.0)))
    fsw = float(requirements.get("fsw", 5_000))
    f_motor = float(requirements.get("f_motor", 60.0))
    poles = int(requirements.get("poles", 4))

    rs = float(requirements.get("Rs", 0.5))
    rr = float(requirements.get("Rr", 0.4))
    ls = float(requirements.get("Ls", 0.08))
    lr = float(requirements.get("Lr", 0.08))
    lm = float(requirements.get("Lm", 0.075))
    j_inertia = float(requirements.get("J", 0.1))

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
            "SW1", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "SW2", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G2", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["three_phase_inverter"],
        ),
        # Phase B
        make_component(
            "SW3", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "SW4", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G3", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 120 300."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G4", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 300 480."},
            block_ids=["three_phase_inverter"],
        ),
        # Phase C
        make_component(
            "SW5", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "SW6", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G5", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 240 420."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G6", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 60 240."},
            block_ids=["three_phase_inverter"],
        ),
        # Induction motor
        make_component(
            "M1", "Induction_Motor",
            role="induction_motor",
            parameters={
                "poles": poles, "Rs": rs, "Rr": rr,
                "Ls": ls, "Lr": lr, "Lm": lm, "J": j_inertia,
            },
            block_ids=["induction_motor"],
        ),
    ]

    nets = [
        make_net("net_vdc_pos",
                 ["V1.positive", "SW1.collector", "SW3.collector", "SW5.collector"],
                 role="dc_bus_positive"),
        make_net("net_gnd",
                 ["V1.negative", "GND1.pin1",
                  "SW2.emitter", "SW4.emitter", "SW6.emitter"],
                 role="ground"),
        make_net("net_phase_a", ["SW1.emitter", "SW2.collector", "M1.phase_a"], role="phase_a"),
        make_net("net_phase_b", ["SW3.emitter", "SW4.collector", "M1.phase_b"], role="phase_b"),
        make_net("net_phase_c", ["SW5.emitter", "SW6.collector", "M1.phase_c"], role="phase_c"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_signal"),
        make_net("net_gate3", ["G3.output", "SW3.gate"], role="drive_signal"),
        make_net("net_gate4", ["G4.output", "SW4.gate"], role="drive_signal"),
        make_net("net_gate5", ["G5.output", "SW5.gate"], role="drive_signal"),
        make_net("net_gate6", ["G6.output", "SW6.gate"], role="drive_signal"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="dc_source", component_ids=["V1", "GND1"]),
        make_block("three_phase_inverter", "switching", role="three_phase_bridge",
                   component_ids=["SW1", "SW2", "G1", "G2",
                                  "SW3", "SW4", "G3", "G4",
                                  "SW5", "SW6", "G5", "G6"]),
        make_block("induction_motor", "load", role="induction_motor", component_ids=["M1"]),
    ]

    traces = [
        make_trace("design_formula", "f_motor_hz", round(f_motor, 2)),
        make_trace("design_formula", "poles", poles),
    ]

    ns = 120 * f_motor / poles
    return CircuitGraph(
        topology="induction_motor_vf",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vdc": round(vdc, 4),
            "f_motor": round(f_motor, 4),
            "poles": poles,
            "synchronous_speed_rpm": round(ns, 2),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(5 / f_motor, 6),
        },
        traces=traces,
        metadata={
            "name": "Induction Motor V/f Drive",
            "description": (
                f"V/f IM drive: Vdc={vdc}V, fsw={fsw / 1e3:.1f}kHz, f={f_motor}Hz"
            ),
        },
    )
