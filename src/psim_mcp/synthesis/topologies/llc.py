"""LLC resonant converter synthesizer — creates CircuitGraph from requirements.

Half-bridge LLC with series Lr, Cr, magnetizing Lm, ideal transformer,
and full-bridge diode rectifier. NO position/direction/ports.
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


def synthesize_llc(requirements: dict) -> CircuitGraph:
    """Synthesize an LLC resonant converter CircuitGraph from requirements."""
    vin = float(requirements["vin"])
    vout = float(requirements["vout_target"])
    fsw = float(requirements.get("fsw", 100_000))
    # k_ind = Lm/Lr inductance ratio; PSIM reference designs use K_ind=4.
    # Accept 'k_ind' (preferred) or 'quality_factor' (legacy alias).
    ln_ratio = float(
        requirements.get("k_ind", requirements.get("quality_factor", 4.0))
    )
    ln_ratio = max(3.0, min(ln_ratio, 10.0))

    if requirements.get("power"):
        pout = float(requirements["power"])
        iout = pout / vout if vout else 1.0
    elif requirements.get("iout"):
        iout = float(requirements["iout"])
        pout = vout * iout
    else:
        iout = 1.0
        pout = vout * iout

    r_load = max(vout / iout if iout else 10.0, 0.1)
    n = max(0.1, min(vin / (2 * vout) if vout else 1.0, 20.0))
    fr = fsw
    rac = 8 * n**2 * r_load / (math.pi**2)
    zr = rac if rac > 0 else 10.0
    lr = max(zr / (2 * math.pi * fr) if fr else 1e-6, 1e-9)
    cr = max(1 / ((2 * math.pi * fr) ** 2 * lr) if (fr and lr) else 10e-9, 1e-12)
    lm = max(ln_ratio * lr, 1e-9)

    vripple_ratio = 0.01
    vripple = vripple_ratio * vout
    cout = max(iout / (2 * 2 * fsw * vripple) if (fsw and vripple) else 100e-6, 1e-12)

    components = [
        make_component("V1", "DC_Source", role="input_source",
                        parameters={"voltage": vin}, block_ids=["input_stage"]),
        make_component("GND1", "Ground", role="ground_ref",
                        block_ids=["input_stage"]),
        make_component("GND2", "Ground", role="secondary_ground_ref",
                        block_ids=["output_filter"]),
        make_component("SW1", "MOSFET", role="high_side_switch",
                        parameters={"switching_frequency": fsw, "on_resistance": 0.01},
                        block_ids=["half_bridge"]),
        make_component("SW2", "MOSFET", role="low_side_switch",
                        parameters={"switching_frequency": fsw, "on_resistance": 0.01},
                        block_ids=["half_bridge"]),
        make_component("G1", "PWM_Generator", role="high_side_gate",
                        parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 175."},
                        block_ids=["half_bridge"]),
        make_component("G2", "PWM_Generator", role="low_side_gate",
                        parameters={"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 355."},
                        block_ids=["half_bridge"]),
        make_component("Cr", "Capacitor", role="resonant_capacitor",
                        parameters={"capacitance": round(cr, 9)},
                        block_ids=["resonant_tank"]),
        make_component("Lr", "Inductor", role="resonant_inductor",
                        parameters={"inductance": round(lr, 9)},
                        block_ids=["resonant_tank"]),
        make_component("Lm", "Inductor", role="magnetizing_inductor",
                        parameters={"inductance": round(lm, 9)},
                        block_ids=["magnetizing_branch"]),
        make_component("T1", "IdealTransformer", role="isolation_transformer",
                        parameters={"np_turns": round(n, 6), "ns_turns": 1},
                        block_ids=["transformer_stage"]),
        make_component("BD1", "DiodeBridge", role="output_rectifier",
                        parameters={},
                        block_ids=["secondary_rectifier"]),
        make_component("Cout", "Capacitor", role="output_capacitor",
                        parameters={"capacitance": round(cout, 9)},
                        block_ids=["output_filter"]),
        make_component("Vout", "Resistor", role="load",
                        parameters={"resistance": round(r_load, 4), "VoltageFlag": 1},
                        block_ids=["output_filter"]),
    ]

    nets = [
        make_net("net_vdc_pos", ["V1.positive", "SW1.drain"], role="input_positive"),
        make_net("net_hb_mid", ["Cr.positive", "SW1.source", "SW2.drain"], role="half_bridge_midpoint"),
        make_net("net_cr_lr", ["Cr.negative", "Lr.pin1"], role="resonant_series"),
        make_net("net_resonant_node", ["Lr.pin2", "Lm.pin1", "T1.primary1"], role="resonant_node"),
        make_net("net_tf_sec1_bd_ac_pos", ["T1.secondary1", "BD1.ac_pos"], role="secondary_ac_pos"),
        make_net("net_tf_sec2_bd_ac_neg", ["T1.secondary2", "BD1.ac_neg"], role="secondary_ac_neg"),
        make_net("net_rect_out", ["BD1.dc_pos", "Cout.positive", "Vout.pin1"], role="output_positive"),
        make_net("net_gnd_pri", ["V1.negative", "GND1.pin1", "SW2.source"], role="primary_ground"),
        make_net("net_gnd_sec", [
            "Lm.pin2", "T1.primary2", "GND2.pin1",
            "BD1.dc_neg", "Cout.negative", "Vout.pin2",
        ], role="secondary_ground"),
        make_net("net_gate1", ["G1.output", "SW1.gate"], role="high_side_drive"),
        make_net("net_gate2", ["G2.output", "SW2.gate"], role="low_side_drive"),
    ]

    blocks = [
        make_block("input_stage", "input", role="input", component_ids=["V1", "GND1"]),
        make_block("half_bridge", "switching", role="half_bridge", component_ids=["SW1", "SW2", "G1", "G2"]),
        make_block("resonant_tank", "resonant", role="resonant", component_ids=["Cr", "Lr"]),
        make_block("magnetizing_branch", "magnetic", role="magnetizing", component_ids=["Lm"]),
        make_block("transformer_stage", "transformer", role="isolation", component_ids=["T1"]),
        make_block("secondary_rectifier", "rectifier", role="rectification", component_ids=["BD1"]),
        make_block("output_filter", "filter", role="output", component_ids=["Cout", "Vout", "GND2"]),
    ]

    traces = [
        make_trace("design_formula", "turns_ratio", round(n, 6), rationale="n = Vin/(2*Vout)"),
        make_trace("design_formula", "resonant_inductance", round(lr, 9), rationale="Lr = Zr/(2*pi*fr)"),
        make_trace("design_formula", "resonant_capacitance", round(cr, 9), rationale="Cr = 1/((2*pi*fr)^2*Lr)"),
        make_trace("design_formula", "magnetizing_inductance", round(lm, 9), rationale=f"Lm = {ln_ratio}*Lr (K_ind={ln_ratio}, PSIM ref uses K_ind=4)"),
    ]

    return CircuitGraph(
        topology="llc",
        components=components,
        nets=nets,
        blocks=blocks,
        design={
            "turns_ratio": round(n, 6),
            "resonant_frequency": round(fr, 2),
            "resonant_inductance": round(lr, 9),
            "resonant_capacitance": round(cr, 9),
            "magnetizing_inductance": round(lm, 9),
            "output_capacitance": round(cout, 9),
            "characteristic_impedance": round(zr, 4),
            "ln_ratio": round(ln_ratio, 2),
            "r_load": round(r_load, 4),
        },
        simulation={
            # 200 pts/period for waveform resolution; 500 cycles for LLC steady state
            "time_step": round(1 / (fsw * 200), 9),
            "total_time": round(500 / fsw, 6),
        },
        traces=traces,
        metadata={
            "name": "LLC Resonant Converter",
            "description": (
                f"LLC resonant converter: {vin}V -> {vout}V @ {iout}A, "
                f"fsw={fsw / 1e3:.1f}kHz, n={n:.3f}, fr={fr / 1e3:.1f}kHz"
            ),
        },
    )
