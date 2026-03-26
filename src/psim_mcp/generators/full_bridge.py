"""Full-bridge inverter topology generator.

Four-switch H-bridge configuration for DC-AC conversion or DC-DC
conversion with bipolar output. Supports both inverter mode and
DC-DC mode with output LC filter.
"""

from __future__ import annotations

import math

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class FullBridgeInverterGenerator(TopologyGenerator):
    """Generate a full-bridge inverter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "full_bridge"

    @property
    def required_fields(self) -> list[str]:
        return ["vin"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vout_target", "iout", "fsw", "load_resistance", "modulation_index"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.full_bridge import synthesize_full_bridge
        return synthesize_full_bridge(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        fsw: float = float(requirements.get("fsw", 20_000))
        m: float = float(requirements.get("modulation_index", 0.8))
        m = max(0.1, min(m, 1.0))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))

        # Output voltage: Vout_rms = m * Vin / 2 (for unipolar PWM)
        vout_rms = m * vin / 2
        vout_target = float(requirements.get("vout_target", vout_rms))

        # Load
        if requirements.get("load_resistance"):
            r_load = float(requirements["load_resistance"])
            iout = vout_target / r_load if r_load else 1.0
        elif requirements.get("iout"):
            iout = float(requirements["iout"])
            r_load = vout_target / iout if iout else 10.0
        else:
            iout = 1.0
            r_load = vout_target / iout if iout else 10.0

        r_load = max(r_load, 0.1)

        # Filter inductor: Lf = Vin / (8 * fsw * ripple_ratio * Iout)
        delta_i = ripple_ratio * iout
        lf = vin / (8 * fsw * delta_i) if (fsw and delta_i) else 1e-3
        lf = max(lf, 1e-9)

        # Filter capacitor: Cf = 1 / ((2*pi*f_cutoff)^2 * Lf), f_cutoff = fsw/10
        f_cutoff = fsw / 10
        cf = 1 / ((2 * math.pi * f_cutoff) ** 2 * lf) if (f_cutoff and lf) else 10e-6
        cf = max(cf, 1e-12)

        # Full bridge: 4 MOSFETs in H-bridge configuration
        # Left leg: SW1(high) + SW3(low), Right leg: SW2(high) + SW4(low)
        # Individual GATING per MOSFET, diagonal pairs share switching points
        #
        # Verified stacked-MOSFET layout (DIR=0, 50px pin spacing):
        #   V+ bus at y=80 connects both legs, GND bus at y=230
        #   VDC(80,80)-(80,130), GND at (80,230)
        #   Left leg at x=200:
        #     SW1 drain(200,80) source(200,130) gate(180,110)
        #     30px gap
        #     SW3 drain(200,160) source(200,210) gate(180,190)
        #     G1(160,110)->SW1.gate, G3(160,190)->SW3.gate (left side)
        #   Right leg at x=400:
        #     SW2 drain(400,80) source(400,130) gate(420,110)
        #     30px gap
        #     SW4 drain(400,160) source(400,210) gate(420,190)
        #     G2(420,110)->SW2.gate, G4(420,190)->SW4.gate (right side)
        #   Diagonal gating: SW1+SW4="0,180", SW2+SW3="180,360"
        #   Lf(260,130)-(310,130) from left mid, R1(350,130)-(350,180)
        components = [
            {
                "id": "V1", "type": "DC_Source",
                "parameters": {"voltage": vin},
                "position": {"x": 80, "y": 80}, "direction": 0,
                "ports": [80, 80, 80, 130],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 80, "y": 230}, "direction": 0,
                "ports": [80, 230],
            },
            # Left leg: SW1 (high-side) + SW3 (low-side)
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 80}, "direction": 0,
                "ports": [200, 80, 200, 130, 180, 110],
            },
            {
                "id": "SW3", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 160}, "direction": 0,
                "ports": [200, 160, 200, 210, 180, 190],
            },
            # Right leg: SW2 (high-side) + SW4 (low-side)
            {
                "id": "SW2", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 400, "y": 80}, "direction": 0,
                "ports": [400, 80, 400, 130, 380, 110],
            },
            {
                "id": "SW4", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 400, "y": 160}, "direction": 0,
                "ports": [400, 160, 400, 210, 380, 190],
            },
            # Individual GATING per MOSFET (avoids long diagonal wires)
            # Diagonal pair: SW1+SW4 get "0,180", SW2+SW3 get "180,360"
            # Left-side GATINGs to the LEFT of MOSFETs
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
                "position": {"x": 160, "y": 110}, "direction": 0,
                "ports": [160, 110],
            },
            {
                "id": "G3", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
                "position": {"x": 160, "y": 190}, "direction": 0,
                "ports": [160, 190],
            },
            # Right-side GATINGs to the LEFT of right-leg MOSFETs (gate is at x-20)
            {
                "id": "G2", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
                "position": {"x": 360, "y": 110}, "direction": 0,
                "ports": [360, 110],
            },
            {
                "id": "G4", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
                "position": {"x": 360, "y": 190}, "direction": 0,
                "ports": [360, 190],
            },
            # Output filter: Lf from left midpoint, R1 to GND
            {
                "id": "Lf", "type": "Inductor",
                "parameters": {"inductance": round(lf, 9)},
                "position": {"x": 260, "y": 130},
                "position2": {"x": 310, "y": 130},
                "direction": 0,
                "ports": [260, 130, 310, 130],
            },
            {
                "id": "Cf", "type": "Capacitor",
                "parameters": {"capacitance": round(cf, 9)},
                "position": {"x": 340, "y": 130},
                "position2": {"x": 340, "y": 180},
                "direction": 90,
                "ports": [340, 130, 340, 180],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 390, "y": 130},
                "position2": {"x": 390, "y": 180},
                "direction": 90,
                "ports": [390, 130, 390, 180],
            },
        ]

        # H-bridge nets with pin ordering for clean wires:
        # Left leg: SW1(high-side) + SW3(low-side)
        # Right leg: SW2(high-side) + SW4(low-side)
        # Diagonal gating: G1 -> SW1, G4 -> SW4 (pair "0,180")
        #                   G2 -> SW2, G3 -> SW3 (pair "180,360")
        # Net ordering: horizontal first, then vertical drop
        nets = [
            {"name": "net_vdc_high", "pins": ["V1.positive", "SW1.drain", "SW2.drain"]},
            {"name": "net_left_mid", "pins": ["Lf.pin1", "SW1.source", "SW3.drain"]},
            {"name": "net_lf_out", "pins": ["Lf.pin2", "Cf.positive", "R1.pin1"]},
            {"name": "net_right_mid", "pins": ["Cf.negative", "R1.pin2", "SW2.source", "SW4.drain"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "SW3.source", "SW4.source"]},
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_gate3", "pins": ["G3.output", "SW3.gate"]},
            {"name": "net_gate4", "pins": ["G4.output", "SW4.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Full-Bridge Inverter",
                "description": (
                    f"Full-bridge inverter: {vin}V DC -> {vout_target:.1f}V RMS, "
                    f"fsw={fsw/1e3:.1f}kHz, m={m:.2f}"
                ),
                "design": {
                    "modulation_index": round(m, 4),
                    "vout_rms": round(vout_rms, 4),
                    "filter_inductance": round(lf, 9),
                    "filter_capacitance": round(cf, 9),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(100 / fsw, 6),
            },
        }
