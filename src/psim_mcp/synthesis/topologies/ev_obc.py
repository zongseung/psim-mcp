"""EV On-Board Charger (OBC) synthesizer — creates CircuitGraph from requirements.

PFC boost front-end + isolation transformer + output rectifier + charger output.
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


def synthesize_ev_obc(requirements: dict) -> CircuitGraph:
    """Synthesize an EV OBC CircuitGraph from requirements."""
    vac_rms = float(requirements.get("vac_rms", requirements.get("vin", 220.0)))
    vbat = float(requirements.get("vbat", requirements.get("vout_target", 400.0)))
    i_charge = float(requirements.get("charge_current", requirements.get("iout", 10.0)))
    fsw = float(requirements.get("fsw", 65_000))
    f_line = float(requirements.get("frequency", 60.0))

    vin_peak = vac_rms * math.sqrt(2)
    vdc_link = max(vin_peak * 1.1, 400.0)
    pout = float(requirements.get("power", vbat * i_charge))

    # Stage 1: PFC boost
    efficiency_pfc = 0.95
    pin_pfc = pout / efficiency_pfc
    iin_peak = pin_pfc * math.sqrt(2) / vac_rms if vac_rms else 1.0
    d_pfc = 1 - vin_peak / vdc_link if vdc_link > vin_peak else 0.1
    d_pfc = max(0.05, min(d_pfc, 0.95))
    delta_i_pfc = 0.3 * iin_peak
    l_pfc = vin_peak * d_pfc / (fsw * delta_i_pfc) if (fsw and delta_i_pfc) else 1e-3
    l_pfc = max(l_pfc, 1e-9)
    vripple_dc = 0.02 * vdc_link
    c_dc = pout / (2 * f_line * vdc_link * vripple_dc) if (f_line and vdc_link and vripple_dc) else 470e-6
    c_dc = max(c_dc, 1e-12)

    # Isolation transformer turns ratio: Vdc_link / Vbat
    n = vdc_link / vbat if vbat else 1.0
    n = max(0.1, min(n, 20.0))

    # Stage 2: output rectifier and capacitor
    delta_i_out = 0.2 * i_charge
    vripple_out = 0.01 * vbat
    c_out = delta_i_out / (8 * fsw * vripple_out) if (fsw and vripple_out) else 100e-6
    c_out = max(c_out, 1e-12)
    r_bat = vbat / i_charge if i_charge else 10.0
    r_bat = max(r_bat, 0.1)

    components = [
        make_component(
            "V1", "AC_Source",
            role="ac_source",
            parameters={"amplitude": round(vin_peak, 4), "frequency": f_line},
            block_ids=["ac_input"],
        ),
        make_component(
            "GND1", "Ground",
            role="ground_ref",
            block_ids=["ac_input"],
        ),
        make_component(
            "BR1", "Diode_Bridge",
            role="input_rectifier",
            parameters={"forward_voltage": 0.7},
            block_ids=["ac_input"],
        ),
        # PFC boost stage
        make_component(
            "L_pfc", "Inductor",
            role="pfc_inductor",
            parameters={"inductance": round(l_pfc, 9), "CurrentFlag": 1},
            block_ids=["pfc_stage"],
        ),
        make_component(
            "SW_pfc", "MOSFET",
            role="pfc_switch",
            parameters={"switching_frequency": fsw, "on_resistance": 0.01},
            block_ids=["pfc_stage"],
        ),
        make_component(
            "G_pfc", "PWM_Generator",
            role="gate_drive",
            parameters={"Frequency": fsw, "NoOfPoints": 2,
                        "Switching_Points": f" 0 {int(d_pfc * 360)}."},
            block_ids=["pfc_stage"],
        ),
        make_component(
            "D_pfc", "Diode",
            role="pfc_boost_diode",
            parameters={"forward_voltage": 0.7},
            block_ids=["pfc_stage"],
        ),
        make_component(
            "C_dc", "Capacitor",
            role="dc_link_capacitor",
            parameters={"capacitance": round(c_dc, 9)},
            block_ids=["pfc_stage"],
        ),
        # Isolation transformer
        make_component(
            "T1", "IdealTransformer",
            role="isolation_transformer",
            parameters={"np_turns": 1, "ns_turns": round(1.0 / n, 6)},
            block_ids=["isolated_dcdc"],
        ),
        # Output rectifier
        make_component(
            "D_out", "Diode",
            role="output_rectifier",
            parameters={"forward_voltage": 0.7},
            block_ids=["battery_output"],
        ),
        make_component(
            "C_out", "Capacitor",
            role="output_capacitor",
            parameters={"capacitance": round(c_out, 9)},
            block_ids=["battery_output"],
        ),
        make_component(
            "R_bat", "Resistor",
            role="battery",
            parameters={"resistance": round(r_bat, 4), "VoltageFlag": 1},
            block_ids=["battery_output"],
        ),
        make_component(
            "GND2", "Ground",
            role="secondary_gnd_ref",
            block_ids=["battery_output"],
        ),
    ]

    nets = [
        make_net("net_vac_pos", ["V1.positive", "BR1.ac_pos"], role="ac_input"),
        make_net("net_vac_neg", ["V1.negative", "GND1.pin1", "BR1.ac_neg"], role="ac_return"),
        make_net("net_br_pos", ["BR1.dc_pos", "L_pfc.pin1"], role="rectified_dc"),
        make_net("net_pfc_node", ["L_pfc.pin2", "SW_pfc.drain", "D_pfc.anode"], role="pfc_switch_node"),
        make_net("net_g_pfc", ["G_pfc.output", "SW_pfc.gate"], role="pfc_gate"),
        make_net("net_dc_link",
                 ["D_pfc.cathode", "C_dc.positive", "T1.primary1"],
                 role="pfc_output"),
        make_net("net_pri_gnd", ["BR1.dc_neg", "SW_pfc.source", "C_dc.negative", "T1.primary2"],
                 role="primary_ground"),
        make_net("net_sec_pos", ["T1.secondary1", "D_out.anode"], role="secondary_positive"),
        make_net("net_sec_rect", ["D_out.cathode", "C_out.positive", "R_bat.pin1"],
                 role="secondary_dc"),
        make_net("net_sec_gnd", ["T1.secondary2", "C_out.negative", "R_bat.pin2", "GND2.pin1"],
                 role="secondary_ground"),
    ]

    blocks = [
        make_block("ac_input", "input", role="ac_source", component_ids=["V1", "GND1", "BR1"]),
        make_block("pfc_stage", "switching", role="pfc_boost",
                   component_ids=["L_pfc", "SW_pfc", "G_pfc", "D_pfc", "C_dc"]),
        make_block("isolated_dcdc", "transformer", role="isolation", component_ids=["T1"]),
        make_block("battery_output", "output", role="charger_output",
                   component_ids=["D_out", "C_out", "R_bat", "GND2"]),
    ]

    traces = [
        make_trace("design_formula", "vdc_link", round(vdc_link, 2)),
        make_trace("design_formula", "d_pfc", round(d_pfc, 6)),
    ]

    return CircuitGraph(
        topology="ev_obc",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "vdc_link": round(vdc_link, 2),
            "d_pfc": round(d_pfc, 6),
            "l_pfc": round(l_pfc, 9),
            "c_dc": round(c_dc, 9),
            "c_out": round(c_out, 9),
            "r_bat": round(r_bat, 4),
            "power": round(pout, 2),
        },
        simulation={
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(3 / f_line, 6),
        },
        traces=traces,
        metadata={
            "name": "EV On-Board Charger",
            "description": (
                f"EV OBC: {vac_rms}V AC -> {vbat}V @ {i_charge}A, fsw={fsw / 1e3:.1f}kHz"
            ),
        },
    )
