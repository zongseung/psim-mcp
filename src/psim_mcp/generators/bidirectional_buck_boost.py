"""Bidirectional buck-boost converter topology generator.

Non-isolated bidirectional DC-DC converter using two active switches
(no diodes in the power path). Operates in buck mode when Vin > Vout
and boost mode when Vin < Vout. Supports bidirectional power flow
for battery charging/discharging and energy storage applications.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class BidirectionalBuckBoostGenerator(TopologyGenerator):
    """Generate a bidirectional buck-boost converter from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "bidirectional_buck_boost"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "ripple_ratio", "voltage_ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.bidirectional_buck_boost import synthesize_bidirectional_buck_boost
        return synthesize_bidirectional_buck_boost(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        iout: float = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
        fsw: float = float(requirements.get("fsw", 50_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        # Calculate duty for both modes, use the operating mode
        # Buck mode (Vin > Vout): D_buck = Vout / Vin
        # Boost mode (Vin < Vout): D_boost = 1 - Vin / Vout
        if vin >= vout:
            duty_buck = vout / vin if vin else 0.5
            duty_boost = 0.0
            operating_mode = "buck"
            duty = duty_buck
        else:
            duty_buck = 1.0
            duty_boost = 1 - vin / vout if vout else 0.5
            operating_mode = "boost"
            duty = duty_boost

        duty = max(0.05, min(duty, 0.95))

        # Buck mode inductor: L_buck = Vout * (1 - D_buck) / (fsw * ripple * Iout)
        d_buck_calc = vout / vin if vin else 0.5
        d_buck_calc = max(0.05, min(d_buck_calc, 0.95))
        delta_i_buck = ripple_ratio * iout
        l_buck = vout * (1 - d_buck_calc) / (fsw * delta_i_buck) if (fsw and delta_i_buck) else 1e-3

        # Boost mode inductor: L_boost = Vin * D_boost / (fsw * ripple * Iin)
        d_boost_calc = 1 - vin / vout if (vout and vout > vin) else 0.1
        d_boost_calc = max(0.05, min(d_boost_calc, 0.95))
        iin_boost = iout * vout / vin if vin else iout
        delta_i_boost = ripple_ratio * iin_boost
        l_boost = vin * d_boost_calc / (fsw * delta_i_boost) if (fsw and delta_i_boost) else 1e-3

        # Use the more conservative (larger) value
        inductance = max(l_buck, l_boost, 1e-9)

        # Buck mode output cap: C_buck = delta_I / (8 * fsw * Vripple)
        vripple_buck = vripple_ratio * vout
        c_buck = delta_i_buck / (8 * fsw * vripple_buck) if (fsw and vripple_buck) else 100e-6

        # Boost mode output cap: C_boost = Iout * D / (fsw * Vripple)
        c_boost = iout * d_boost_calc / (fsw * vripple_buck) if (fsw and vripple_buck) else 100e-6

        # Use the more conservative (larger) value
        capacitance = max(c_buck, c_boost, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Bidirectional: Half-bridge leg (SW1 high-side + SW2 low-side) -> L1 -> C1||R1
        # Complementary gating: SW1 gets G1, SW2 gets G2
        #
        # Verified stacked-MOSFET layout (DIR=0, 50px pin spacing):
        #   V+ rail at y=80, GND bus at y=230 (below everything)
        #   VDC(80,80)-(80,130), GND at (80,230), wire neg down to GND bus
        #   SW1 drain(200,80) source(200,130) gate(180,110) — 50px spacing
        #   30px gap
        #   SW2 drain(200,160) source(200,210) gate(180,190) — 50px spacing
        #   G1(160,110)->SW1.gate, G2(160,190)->SW2.gate
        #   L1(260,130)-(310,130) -> C1(340,130)-(340,180) -> R1(390,130)-(390,180)
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
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": f" 0 {int(duty * 360)}."},
                "position": {"x": 160, "y": 110}, "direction": 0,
                "ports": [160, 110],
            },
            {
                "id": "G2", "type": "PWM_Generator",
                "parameters": {"Frequency": fsw, "NoOfPoints": 2, "Switching_Points": f" {int(duty * 360)} 360."},
                "position": {"x": 160, "y": 190}, "direction": 0,
                "ports": [160, 190],
            },
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(inductance, 9)},
                "position": {"x": 260, "y": 130},
                "position2": {"x": 310, "y": 130},
                "direction": 0,
                "ports": [260, 130, 310, 130],
            },
            {
                "id": "C1", "type": "Capacitor",
                "parameters": {"capacitance": round(capacitance, 9)},
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

        # Half-bridge leg: SW1(high-side) + SW2(low-side)
        # V+ -> SW1.drain, SW1.source -> SW2.drain (30px gap) -> L1 -> Vout
        # SW2.source -> GND bus at y=230
        # Net pin ordering ensures clean horizontal/vertical wires:
        #   L1.pin1 -> SW1.source = horizontal, SW1.source -> SW2.drain = vertical
        nets = [
            {"name": "net_vin_sw1", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_sw_node", "pins": ["L1.pin1", "SW1.source", "SW2.drain"]},
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_l_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "SW2.source", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Bidirectional Buck-Boost Converter",
                "description": (
                    f"Bidirectional buck-boost: {vin}V <-> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, mode={operating_mode}, D={duty:.3f}"
                ),
                "design": {
                    "operating_mode": operating_mode,
                    "duty": round(duty, 6),
                    "duty_buck": round(d_buck_calc, 6),
                    "duty_boost": round(d_boost_calc, 6),
                    "inductance": round(inductance, 9),
                    "capacitance": round(capacitance, 9),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(50 / fsw, 6),
            },
        }
