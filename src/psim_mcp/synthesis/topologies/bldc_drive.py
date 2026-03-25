"""BLDC motor drive synthesizer — creates CircuitGraph from requirements.

Three-phase H-bridge driving a BLDC motor with 6-step commutation.
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


def synthesize_bldc_drive(requirements: dict) -> CircuitGraph:
    """Synthesize a BLDC drive CircuitGraph from requirements."""
    vdc = float(requirements.get("vdc", requirements.get("vin", 48.0)))
    motor_power = float(requirements.get("motor_power", 500.0))
    speed_rpm = float(requirements.get("speed", 3000.0))
    fsw = float(requirements.get("fsw", 20_000))

    poles = 8
    f_elec = poles * speed_rpm / (2 * 60)
    f_elec = max(f_elec, 1.0)

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
            "SW_AH", "MOSFET",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "SW_AL", "MOSFET",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_AH", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 0 120."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_AL", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 180 300."},
            block_ids=["three_phase_inverter"],
        ),
        # Phase B
        make_component(
            "SW_BH", "MOSFET",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "SW_BL", "MOSFET",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_BH", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 120 240."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_BL", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 300 420."},
            block_ids=["three_phase_inverter"],
        ),
        # Phase C
        make_component(
            "SW_CH", "MOSFET",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "SW_CL", "MOSFET",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_CH", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 240 360."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_CL", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 60 180."},
            block_ids=["three_phase_inverter"],
        ),
        # BLDC Motor
        make_component(
            "M1", "BLDC_Motor",
            role="bldc_motor",
            parameters={"poles": poles, "Rs": 0.1, "Ls": 1e-3, "Ke": 0.01, "J": 0.005},
            block_ids=["bldc_motor"],
        ),
    ]

    nets = [
        make_net("net_vdc_pos",
                 ["V1.positive", "SW_AH.drain", "SW_BH.drain", "SW_CH.drain"],
                 role="dc_bus_positive"),
        make_net("net_gnd",
                 ["V1.negative", "GND1.pin1", "SW_AL.source", "SW_BL.source", "SW_CL.source"],
                 role="ground"),
        make_net("net_phase_a", ["SW_AH.source", "SW_AL.drain", "M1.phase_a"], role="phase_a"),
        make_net("net_phase_b", ["SW_BH.source", "SW_BL.drain", "M1.phase_b"], role="phase_b"),
        make_net("net_phase_c", ["SW_CH.source", "SW_CL.drain", "M1.phase_c"], role="phase_c"),
        make_net("net_g_ah", ["G_AH.output", "SW_AH.gate"], role="drive_signal"),
        make_net("net_g_al", ["G_AL.output", "SW_AL.gate"], role="drive_signal"),
        make_net("net_g_bh", ["G_BH.output", "SW_BH.gate"], role="drive_signal"),
        make_net("net_g_bl", ["G_BL.output", "SW_BL.gate"], role="drive_signal"),
        make_net("net_g_ch", ["G_CH.output", "SW_CH.gate"], role="drive_signal"),
        make_net("net_g_cl", ["G_CL.output", "SW_CL.gate"], role="drive_signal"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="dc_source", component_ids=["V1", "GND1"]),
        make_block("three_phase_inverter", "switching", role="three_phase_bridge",
                   component_ids=["SW_AH", "SW_AL", "G_AH", "G_AL",
                                  "SW_BH", "SW_BL", "G_BH", "G_BL",
                                  "SW_CH", "SW_CL", "G_CH", "G_CL"]),
        make_block("bldc_motor", "load", role="bldc_motor", component_ids=["M1"]),
    ]

    traces = [
        make_trace("design_formula", "f_electrical_hz", round(f_elec, 2)),
        make_trace("design_formula", "poles", poles),
    ]

    return CircuitGraph(
        topology="bldc_drive",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vdc": round(vdc, 2),
            "motor_power": round(motor_power, 2),
            "speed_rpm": round(speed_rpm, 1),
            "poles": poles,
            "f_electrical": round(f_elec, 2),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(10 / f_elec, 6),
        },
        traces=traces,
        metadata={
            "name": "BLDC Motor Drive",
            "description": (
                f"BLDC 6-step drive: Vdc={vdc}V, speed={speed_rpm}rpm"
            ),
        },
    )
