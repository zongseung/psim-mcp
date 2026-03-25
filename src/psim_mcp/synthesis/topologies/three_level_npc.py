"""Three-level NPC inverter synthesizer — creates CircuitGraph from requirements.

Split DC bus → 4-IGBT NPC bridge + 2 clamping diodes → LC filter → load.
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


def synthesize_three_level_npc(requirements: dict) -> CircuitGraph:
    """Synthesize a three-level NPC inverter CircuitGraph from requirements."""
    vdc_total = float(requirements.get("vdc_total", requirements.get("vin", 48.0)))
    vdc_half = vdc_total / 2.0
    fsw = float(requirements.get("fsw", 10_000))
    m = float(requirements.get("modulation_index", 0.8))
    m = max(0.1, min(m, 1.0))
    r_load = float(requirements.get("load_resistance",
                                    float(requirements.get("vout_target", vdc_total * 0.5)) /
                                    max(float(requirements.get("iout", 1.0)), 1e-6)))
    r_load = max(r_load, 0.1)

    vout_rms = m * vdc_half / math.sqrt(2)
    iout_rms = vout_rms / r_load
    delta_i = 0.3 * iout_rms if iout_rms > 0 else 1.0
    lf = vdc_half / (8 * fsw * delta_i) if (fsw and delta_i) else 2e-3
    lf = max(lf, 1e-9)

    components = [
        # Top DC source
        make_component(
            "V1", "DC_Source",
            role="input_source",
            parameters={"voltage": round(vdc_half, 4)},
            block_ids=["dc_bus"],
        ),
        # Bottom DC source
        make_component(
            "V2", "DC_Source",
            role="dc_bus_lower",
            parameters={"voltage": round(vdc_half, 4)},
            block_ids=["dc_bus"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["dc_bus"],
        ),
        # 4-IGBT NPC stack
        make_component(
            "SW1", "IGBT",
            role="npc_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["npc_bridge"],
        ),
        make_component(
            "SW2", "IGBT",
            role="npc_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["npc_bridge"],
        ),
        make_component(
            "SW3", "IGBT",
            role="npc_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["npc_bridge"],
        ),
        make_component(
            "SW4", "IGBT",
            role="npc_switches",
            parameters={"switching_frequency": fsw, "on_resistance": 0.02},
            block_ids=["npc_bridge"],
        ),
        make_component("G1", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 90."},
                       block_ids=["npc_bridge"]),
        make_component("G2", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
                       block_ids=["npc_bridge"]),
        make_component("G3", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
                       block_ids=["npc_bridge"]),
        make_component("G4", "PWM_Generator", role="gate_drive",
                       parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 90 270."},
                       block_ids=["npc_bridge"]),
        # Clamping diodes
        make_component(
            "D1", "Diode",
            role="clamping_diodes",
            parameters={"forward_voltage": 1.5},
            block_ids=["clamping"],
        ),
        make_component(
            "D2", "Diode",
            role="clamping_diodes",
            parameters={"forward_voltage": 1.5},
            block_ids=["clamping"],
        ),
        # Output filter
        make_component(
            "L1", "Inductor",
            role="output_inductor",
            parameters={"inductance": round(lf, 9), "CurrentFlag": 1},
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
        make_net("net_vdc_top", ["V1.positive", "SW1.collector"], role="dc_bus_positive"),
        make_net("net_midpoint",
                 ["V1.negative", "V2.positive", "D1.anode", "D2.cathode"],
                 role="dc_bus_neutral"),
        make_net("net_vdc_bot", ["V2.negative", "GND1.pin1", "SW4.emitter"], role="ground"),
        make_net("net_sw1_sw2", ["SW1.emitter", "SW2.collector", "D1.cathode"],
                 role="npc_upper_clamp"),
        make_net("net_sw2_sw3", ["SW2.emitter", "SW3.collector", "L1.pin1"], role="output_ac"),
        make_net("net_sw3_sw4", ["SW3.emitter", "SW4.collector", "D2.anode"],
                 role="npc_lower_clamp"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="drive_signal"),
        make_net("net_gate3", ["G3.output", "SW3.gate"], role="drive_signal"),
        make_net("net_gate4", ["G4.output", "SW4.gate"], role="drive_signal"),
        make_net("net_lf_out", ["L1.pin2", "R1.pin1"], role="filtered_output"),
        make_net("net_load_return", ["R1.pin2", "V1.negative"], role="load_return"),
    ]

    blocks = [
        make_block("dc_bus", "input", role="split_dc_source", component_ids=["V1", "V2", "GND1"]),
        make_block("npc_legs", "switching", role="npc_inverter",
                   component_ids=["SW1", "SW2", "SW3", "SW4", "G1", "G2", "G3", "G4", "D1", "D2"]),
        make_block("output_filter", "filter", role="output", component_ids=["L1", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "vdc_half", round(vdc_half, 4)),
        make_trace("design_formula", "modulation_index", round(m, 4)),
    ]

    return CircuitGraph(
        topology="three_level_npc",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vdc_half": round(vdc_half, 4),
            "modulation_index": round(m, 4),
            "vout_rms": round(vout_rms, 4),
            "filter_inductance": round(lf, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(100 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "Three-Level NPC Inverter",
            "description": (
                f"3-level NPC: Vdc={vdc_total}V, fsw={fsw / 1e3:.1f}kHz, m={m:.2f}"
            ),
        },
    )
