"""Half-bridge inverter topology generator.

Two-switch configuration with split DC-bus capacitors for DC-AC or
DC-DC conversion. Output voltage is limited to Vin/2 peak, making
it suitable for lower-power applications with reduced switch count.
"""

from __future__ import annotations

import math

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class HalfBridgeInverterGenerator(TopologyGenerator):
    """Generate a half-bridge inverter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "half_bridge"

    @property
    def required_fields(self) -> list[str]:
        return ["vin"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vout_target", "iout", "fsw", "load_resistance"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.half_bridge import synthesize_half_bridge
        return synthesize_half_bridge(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        fsw: float = float(requirements.get("fsw", 20_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))

        # Output peak voltage is Vin/2
        vout_peak = vin / 2
        vout_target = float(requirements.get("vout_target", vout_peak))

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

        # Split DC-bus capacitors: C = Iout / (2 * fsw * 0.01 * Vin)  [1% ripple]
        vin_ripple = 0.01 * vin  # 1% ripple on DC bus
        c_split = iout / (2 * fsw * vin_ripple) if (fsw and vin_ripple) else 100e-6
        c_split = max(c_split, 1e-12)

        # Filter inductor: Lf = (Vin/2) / (8 * fsw * ripple_ratio * Iout)
        delta_i = ripple_ratio * iout
        lf = vout_peak / (8 * fsw * delta_i) if (fsw and delta_i) else 1e-3
        lf = max(lf, 1e-9)

        # Filter capacitor (optional, using same cutoff approach)
        f_cutoff = fsw / 10
        cf = 1 / ((2 * math.pi * f_cutoff) ** 2 * lf) if (f_cutoff and lf) else 10e-6
        cf = max(cf, 1e-12)

        # Half bridge: SW1 (high-side) + SW2 (low-side) with complementary gating
        # Split DC-bus caps: C1 top half, C2 bottom half
        # Output from bridge midpoint through Lf to R, return to GND bus
        #
        # Verified stacked-MOSFET layout (DIR=0, 50px pin spacing):
        #   V+ rail at y=80, GND bus at y=230 (below everything)
        #   VDC(80,80)-(80,130), GND at (80,230)
        #   C1(130,80)-(130,130) top cap, C2(130,150)-(130,200) bottom cap
        #   SW1 drain(200,80) source(200,130) gate(180,110) — 50px spacing
        #   30px gap
        #   SW2 drain(200,160) source(200,210) gate(180,190) — 50px spacing
        #   G1(160,110)->SW1.gate, G2(160,190)->SW2.gate
        #   Lf(260,130)-(310,130) -> R1(340,130)-(340,180)
        #   All GND pins wire down individually to y=230
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
            {
                "id": "C1", "type": "Capacitor",
                "parameters": {"capacitance": round(c_split, 9)},
                "position": {"x": 130, "y": 80},
                "position2": {"x": 130, "y": 130},
                "direction": 90,
                "ports": [130, 80, 130, 130],
            },
            {
                "id": "C2", "type": "Capacitor",
                "parameters": {"capacitance": round(c_split, 9)},
                "position": {"x": 130, "y": 150},
                "position2": {"x": 130, "y": 200},
                "direction": 90,
                "ports": [130, 150, 130, 200],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 80}, "direction": 0,
                "ports": [200, 80, 200, 130, 180, 110],
            },
            {
                "id": "SW2", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 160}, "direction": 0,
                "ports": [200, 160, 200, 210, 180, 190],
            },
            # Individual GATING per MOSFET, placed next to gate pins
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 0 180."},
                "position": {"x": 160, "y": 110}, "direction": 0,
                "ports": [160, 110],
            },
            {
                "id": "G2", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": " 180 360."},
                "position": {"x": 160, "y": 190}, "direction": 0,
                "ports": [160, 190],
            },
            {
                "id": "Lf", "type": "Inductor",
                "parameters": {"inductance": round(lf, 9)},
                "position": {"x": 260, "y": 130},
                "position2": {"x": 310, "y": 130},
                "direction": 0,
                "ports": [260, 130, 310, 130],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 340, "y": 130},
                "position2": {"x": 340, "y": 180},
                "direction": 90,
                "ports": [340, 130, 340, 180],
            },
        ]

        # Net pin ordering ensures clean horizontal/vertical wires:
        #   Lf.pin1 -> SW1.source = horizontal, SW1.source -> SW2.drain = vertical
        nets = [
            {"name": "net_vdc_pos", "pins": ["V1.positive", "C1.positive", "SW1.drain"]},
            {"name": "net_cap_mid", "pins": ["C1.negative", "C2.positive", "R1.pin2"]},
            {"name": "net_bridge_mid", "pins": ["Lf.pin1", "SW1.source", "SW2.drain"]},
            {"name": "net_lf_out", "pins": ["Lf.pin2", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "C2.negative", "SW2.source"]},
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Half-Bridge Inverter",
                "description": (
                    f"Half-bridge inverter: {vin}V DC -> {vout_target:.1f}V peak, "
                    f"fsw={fsw/1e3:.1f}kHz"
                ),
                "design": {
                    "vout_peak": round(vout_peak, 4),
                    "c_split": round(c_split, 9),
                    "filter_inductance": round(lf, 9),
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
