"""Thyristor bridge rectifier synthesizer — creates CircuitGraph from requirements.

Controlled AC-DC bridge using 4 thyristors (SCRs). NO position/direction/ports.
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


def synthesize_thyristor_rectifier(requirements: dict) -> CircuitGraph:
    """Synthesize a thyristor bridge rectifier CircuitGraph from requirements."""
    vac_rms = float(requirements.get("vac_rms", requirements.get("vin", 220.0)))
    alpha_deg = float(requirements.get("firing_angle", 30.0))
    f_line = float(requirements.get("f_line", 60.0))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.1))

    alpha_rad = math.radians(alpha_deg)
    vpeak = vac_rms * math.sqrt(2)
    vdc = max(0.9 * vac_rms * math.cos(alpha_rad), 0.1)

    r_load = float(requirements.get("load_resistance", 10.0))
    r_load = max(r_load, 0.1)
    idc = vdc / r_load

    delta_i = ripple_ratio * idc if idc > 0 else 1.0
    inductance = vpeak / (2 * math.pi * f_line * delta_i) if (f_line and delta_i) else 10e-3
    inductance = max(inductance, 1e-9)

    components = [
        make_component(
            "V1", "AC_Source",
            role="ac_source",
            parameters={"amplitude": round(vpeak, 4), "frequency": f_line},
            block_ids=["ac_source"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["ac_source"],
        ),
        # Thyristor bridge: T1/T2 = top pair (cathodes to DC+), T3/T4 = bottom pair
        make_component(
            "T1", "Thyristor",
            role="thyristors",
            parameters={"firing_angle": alpha_deg},
            block_ids=["thyristor_bridge"],
        ),
        make_component(
            "T2", "Thyristor",
            role="thyristors",
            parameters={"firing_angle": alpha_deg},
            block_ids=["thyristor_bridge"],
        ),
        make_component(
            "T3", "Thyristor",
            role="thyristors",
            parameters={"firing_angle": alpha_deg},
            block_ids=["thyristor_bridge"],
        ),
        make_component(
            "T4", "Thyristor",
            role="thyristors",
            parameters={"firing_angle": alpha_deg},
            block_ids=["thyristor_bridge"],
        ),
        make_component(
            "L1", "Inductor",
            role="output_inductor",
            parameters={"inductance": round(inductance, 9), "CurrentFlag": 1},
            block_ids=["dc_output"],
        ),
        make_component(
            "C1", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(max(idc / (2 * f_line * 0.05 * vdc), 1e-12), 9)},
            block_ids=["dc_output"],
        ),
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["dc_output"],
        ),
    ]

    c_out = max(idc / (2 * f_line * 0.05 * vdc), 1e-12) if (f_line and vdc) else 100e-6

    nets = [
        make_net("net_ac_pos", ["V1.positive", "T1.anode", "T4.cathode"], role="ac_input"),
        make_net("net_ac_neg", ["V1.negative", "T2.anode", "T3.cathode"], role="ac_return"),
        make_net("net_dc_pos", ["T1.cathode", "T2.cathode", "L1.pin1"], role="dc_input"),
        make_net("net_lf_out", ["L1.pin2", "C1.positive", "R1.pin1"], role="dc_output"),
        make_net("net_dc_neg", ["T3.anode", "T4.anode", "C1.negative", "R1.pin2", "GND1.pin1"], role="ground"),
    ]

    blocks = [
        make_block("ac_source", "input", role="ac_input", component_ids=["V1", "GND1"]),
        make_block("thyristor_bridge", "rectifier", role="controlled_rectifier", component_ids=["T1", "T2", "T3", "T4"]),
        make_block("dc_output", "output", role="dc_output", component_ids=["L1", "C1", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "vdc_avg", round(vdc, 4)),
        make_trace("design_formula", "firing_angle_deg", round(alpha_deg, 2)),
    ]

    sim_period = 1 / f_line if f_line else 1 / 60
    return CircuitGraph(
        topology="thyristor_rectifier",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "firing_angle_deg": round(alpha_deg, 2),
            "vdc_avg": round(vdc, 4),
            "vpeak": round(vpeak, 4),
            "inductance": round(inductance, 9),
            "r_load": round(r_load, 4),
        },
        simulation={
            "time_step": round(1 / (f_line * 1000), 9),
            "total_time": round(10 / f_line, 6),
        },
        traces=traces,
        metadata={
            "name": "Thyristor Bridge Rectifier",
            "description": (
                f"Thyristor rectifier: Vac={vac_rms}Vrms, "
                f"alpha={alpha_deg}deg, Vdc={vdc:.1f}V"
            ),
        },
    )
