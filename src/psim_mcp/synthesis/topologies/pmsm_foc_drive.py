"""PMSM FOC drive synthesizer — creates CircuitGraph from requirements.

Three-phase IGBT bridge + PMSM motor with FOC controller placeholder.
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


def synthesize_pmsm_foc_drive(requirements: dict) -> CircuitGraph:
    """Synthesize a PMSM FOC drive CircuitGraph from requirements."""
    vdc = float(requirements.get("vdc", requirements.get("vin", 48.0)))
    motor_power = float(requirements.get("motor_power", 1000.0))
    speed_rpm = float(requirements.get("speed", 3000.0))
    fsw = float(requirements.get("fsw", 10_000))

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
            "Q_AH", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "Q_AL", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_AH", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 0 180."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_AL", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 180 360."},
            block_ids=["three_phase_inverter"],
        ),
        # Phase B
        make_component(
            "Q_BH", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "Q_BL", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_BH", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 120 300."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_BL", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 300 480."},
            block_ids=["three_phase_inverter"],
        ),
        # Phase C
        make_component(
            "Q_CH", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "Q_CL", "IGBT",
            role="inverter_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_CH", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 240 420."},
            block_ids=["three_phase_inverter"],
        ),
        make_component(
            "G_CL", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": f_elec, "NoOfPoints": 2, "Switching_Points": " 60 240."},
            block_ids=["three_phase_inverter"],
        ),
        # PMSM motor
        make_component(
            "M1", "PMSM",
            role="pmsm_motor",
            parameters={"poles": poles, "Rs": 0.1, "Ld": 1e-3, "Lq": 1e-3,
                        "flux": 0.05, "J": 0.01},
            block_ids=["pmsm_motor"],
        ),
        # FOC controller placeholder
        make_component(
            "FOC1", "PI_Controller",
            role="foc_controller",
            parameters={},
            block_ids=["foc_controller"],
        ),
    ]

    nets = [
        make_net("net_vdc_pos",
                 ["V1.positive", "Q_AH.collector", "Q_BH.collector", "Q_CH.collector"],
                 role="dc_bus_positive"),
        make_net("net_gnd",
                 ["V1.negative", "GND1.pin1",
                  "Q_AL.emitter", "Q_BL.emitter", "Q_CL.emitter"],
                 role="ground"),
        make_net("net_phase_a", ["Q_AH.emitter", "Q_AL.collector", "M1.phase_a"], role="phase_a"),
        make_net("net_phase_b", ["Q_BH.emitter", "Q_BL.collector", "M1.phase_b"], role="phase_b"),
        make_net("net_phase_c", ["Q_CH.emitter", "Q_CL.collector", "M1.phase_c"], role="phase_c"),
        make_net("net_g_ah", ["G_AH.output", "Q_AH.gate"], role="drive_signal"),
        make_net("net_g_al", ["G_AL.output", "Q_AL.gate"], role="drive_signal"),
        make_net("net_g_bh", ["G_BH.output", "Q_BH.gate"], role="drive_signal"),
        make_net("net_g_bl", ["G_BL.output", "Q_BL.gate"], role="drive_signal"),
        make_net("net_g_ch", ["G_CH.output", "Q_CH.gate"], role="drive_signal"),
        make_net("net_g_cl", ["G_CL.output", "Q_CL.gate"], role="drive_signal"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="dc_source", component_ids=["V1", "GND1"]),
        make_block("three_phase_inverter", "switching", role="three_phase_bridge",
                   component_ids=["Q_AH", "Q_AL", "G_AH", "G_AL",
                                  "Q_BH", "Q_BL", "G_BH", "G_BL",
                                  "Q_CH", "Q_CL", "G_CH", "G_CL"]),
        make_block("pmsm_motor", "load", role="pmsm_motor", component_ids=["M1"]),
        make_block("foc_controller", "control", role="foc", component_ids=["FOC1"]),
    ]

    traces = [
        make_trace("design_formula", "f_electrical_hz", round(f_elec, 2)),
        make_trace("design_formula", "poles", poles),
    ]

    return CircuitGraph(
        topology="pmsm_foc_drive",
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
            "name": "PMSM FOC Drive",
            "description": (
                f"PMSM drive: Vdc={vdc}V, speed={speed_rpm}rpm, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
