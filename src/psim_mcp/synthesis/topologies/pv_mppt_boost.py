"""PV MPPT boost synthesizer — creates CircuitGraph from requirements.

PV panel (DC source at Vmpp) → boost converter → DC output. NO position/direction/ports.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def synthesize_pv_mppt_boost(requirements: dict) -> CircuitGraph:
    """Synthesize a PV MPPT boost CircuitGraph from requirements."""
    # PV panel parameters — default to a small panel
    voc = float(requirements.get("voc", requirements.get("vin", 48.0) * 1.25))
    isc = float(requirements.get("isc", 2.0))
    vmp = float(requirements.get("vmp", voc * 0.8))
    imp = float(requirements.get("imp", isc * 0.9))
    vout = float(requirements.get("vout_target", vmp * 2.0))
    fsw = float(requirements.get("fsw", 50_000))
    ripple_ratio = float(requirements.get("ripple_ratio", 0.3))
    vripple_ratio = float(requirements.get("voltage_ripple_ratio", 0.01))

    vin = vmp
    duty = 1 - vin / vout if vout > vin else 0.5
    duty = max(0.05, min(duty, 0.95))
    delta_i = ripple_ratio * imp
    delta_i = max(delta_i, 1e-6)
    inductance = vin * duty / (fsw * delta_i) if (fsw and delta_i) else 1e-3
    inductance = max(inductance, 1e-9)

    iout = imp * (1 - duty)
    capacitance = iout * duty / (fsw * vripple_ratio * vout) if (fsw and vripple_ratio and vout) else 100e-6
    capacitance = max(capacitance, 1e-12)
    r_load = vout / iout if iout else 10.0

    components = [
        make_component(
            "PV1", "DC_Source",
            role="pv_source",
            parameters={"voltage": round(vmp, 4)},
            block_ids=["pv_panel"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["pv_panel"],
        ),
        make_component(
            "L1", "Inductor",
            role="boost_inductor",
            parameters={"inductance": round(inductance, 9), "CurrentFlag": 1},
            block_ids=["boost_stage"],
        ),
        make_component(
            "SW1", "MOSFET",
            role="boost_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["boost_stage"],
        ),
        make_component(
            "G1", "PWM_Generator",
            role="gate_drive",
            parameters={
                "Frequency": fsw,
                "NoOfPoints": 2,
                "Switching_Points": f" 0 {int(duty * 360)}.",
            },
            block_ids=["boost_stage"],
        ),
        make_component(
            "D1", "Diode",
            role="boost_diode",
            parameters={"forward_voltage": 0.7},
            block_ids=["boost_stage"],
        ),
        make_component(
            "C1", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(capacitance, 9)},
            block_ids=["output"],
        ),
        make_component(
            "R1", "Resistor",
            role="load",
            parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
            block_ids=["output"],
        ),
    ]

    nets = [
        make_net("net_pv_l", ["PV1.positive", "L1.pin1"], role="pv_positive"),
        make_net("net_l_sw_d", ["L1.pin2", "SW1.drain", "D1.anode"], role="boost_switch_node"),
        make_net("net_gate", ["G1.output", "SW1.gate"], role="drive_signal"),
        make_net("net_boost_out", ["D1.cathode", "C1.positive", "R1.pin1"], role="boost_output"),
        make_net("net_gnd", ["PV1.negative", "GND1.pin1", "SW1.source", "C1.negative", "R1.pin2"], role="ground"),
    ]

    blocks = [
        make_block("pv_panel", "input", role="pv_source", component_ids=["PV1", "GND1"]),
        make_block("boost_stage", "switching", role="boost_converter", component_ids=["L1", "SW1", "G1", "D1"]),
        make_block("output", "filter", role="output", component_ids=["C1", "R1"]),
    ]

    traces = [
        make_trace("design_formula", "duty", round(duty, 6)),
        make_trace("design_formula", "vmp", round(vmp, 4)),
    ]

    return CircuitGraph(
        topology="pv_mppt_boost",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vmp": round(vmp, 4),
            "imp": round(imp, 4),
            "duty": round(duty, 6),
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
            "name": "PV MPPT Boost Converter",
            "description": (
                f"PV MPPT boost: Vmpp={vmp:.1f}V -> {vout:.1f}V, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
