"""Cuk converter topology generator.

Non-isolated inverting DC-DC converter using a coupling capacitor for
energy transfer. Provides continuous input and output currents due to
inductors on both sides.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class CukGenerator(TopologyGenerator):
    """Generate a Cuk converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "cuk"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "ripple_ratio", "voltage_ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.cuk import synthesize_cuk
        return synthesize_cuk(requirements)

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

        # Duty cycle: D = Vout / (Vin + Vout)
        denom = vin + vout
        duty = vout / denom if denom else 0.5
        duty = max(0.05, min(duty, 0.95))

        # Input current
        iin = iout * duty / (1 - duty) if duty < 1 else iout

        # Input inductor: L1 = Vin * D / (fsw * ripple_ratio * Iin)
        delta_il1 = ripple_ratio * iin
        l1 = vin * duty / (fsw * delta_il1) if (fsw and delta_il1) else 1e-3
        l1 = max(l1, 1e-9)

        # Output inductor: L2 = Vout * (1 - D) / (fsw * ripple_ratio * Iout)
        delta_il2 = ripple_ratio * iout
        l2 = vout * (1 - duty) / (fsw * delta_il2) if (fsw and delta_il2) else 1e-3
        l2 = max(l2, 1e-9)

        # Coupling capacitor: C1 = Iout * D / (fsw * 0.05 * (Vin + Vout))
        vc1_ripple = 0.05 * denom  # 5% ripple on coupling cap voltage
        c_coupling = iout * duty / (fsw * vc1_ripple) if (fsw and vc1_ripple) else 10e-6
        c_coupling = max(c_coupling, 1e-12)

        # Output capacitor: C2 = delta_IL2 / (8 * fsw * vripple_ratio * Vout)
        vripple = vripple_ratio * vout
        c_out = delta_il2 / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
        c_out = max(c_out, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Cuk: V1 -> L1 -> node_A(SW1.drain, Cc+) -> Cc -> node_B(D1.cathode, L2) -> output
        # SW1 source to GND, D1 anode to GND
        #
        # Layout uses DIR=0 vertical MOSFET (like boost) so source naturally
        # falls to GND rail at y=150:
        #   VDC(80,100)-(80,150) -> L1(120,100)-(170,100)
        #   MOSFET drain(200,100) source(200,150) gate(180,130) DIR=0
        #   GATING(180,170) -> Cc(250,100)-(300,100) horizontal
        #   DIODE anode(320,150) cathode(320,100) DIR=270 (freewheels GND->node_B)
        #   L2(350,100)-(400,100) -> C2(400,100)-(400,150) -> R1(450,100)-(450,150)
        #   GND at y=150
        components = [
            {
                "id": "V1", "type": "DC_Source",
                "parameters": {"voltage": vin},
                "position": {"x": 80, "y": 100}, "direction": 0,
                "ports": [80, 100, 80, 150],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 80, "y": 150}, "direction": 0,
                "ports": [80, 150],
            },
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(l1, 9)},
                "position": {"x": 120, "y": 100},
                "position2": {"x": 170, "y": 100},
                "direction": 0,
                "ports": [120, 100, 170, 100],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 100}, "direction": 0,
                "ports": [200, 100, 200, 150, 180, 130],
            },
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": f" 0 {int(duty * 360)}.",
                },
                "position": {"x": 180, "y": 170}, "direction": 0,
                "ports": [180, 170],
            },
            {
                "id": "Cc", "type": "Capacitor",
                "parameters": {"capacitance": round(c_coupling, 9)},
                "position": {"x": 250, "y": 100},
                "position2": {"x": 300, "y": 100},
                "direction": 0,
                "ports": [250, 100, 300, 100],
            },
            {
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 320, "y": 150}, "direction": 270,
                "ports": [320, 150, 320, 100],
            },
            {
                "id": "L2", "type": "Inductor",
                "parameters": {"inductance": round(l2, 9)},
                "position": {"x": 350, "y": 100},
                "position2": {"x": 400, "y": 100},
                "direction": 0,
                "ports": [350, 100, 400, 100],
            },
            {
                "id": "C2", "type": "Capacitor",
                "parameters": {"capacitance": round(c_out, 9)},
                "position": {"x": 400, "y": 100},
                "position2": {"x": 400, "y": 150},
                "direction": 90,
                "ports": [400, 100, 400, 150],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 450, "y": 100},
                "position2": {"x": 450, "y": 150},
                "direction": 90,
                "ports": [450, 100, 450, 150],
            },
        ]

        nets = [
            {"name": "net_vin_l1", "pins": ["V1.positive", "L1.pin1"]},
            {"name": "net_l1_sw_cc", "pins": ["L1.pin2", "SW1.drain", "Cc.positive"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_cc_d_l2", "pins": ["Cc.negative", "D1.cathode", "L2.pin1"]},
            {"name": "net_l2_out", "pins": ["L2.pin2", "C2.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "SW1.source", "D1.anode", "C2.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Cuk Converter",
                "description": (
                    f"Cuk DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "l1_inductance": round(l1, 9),
                    "l2_inductance": round(l2, 9),
                    "c_coupling": round(c_coupling, 9),
                    "c_output": round(c_out, 9),
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
