"""SEPIC (Single-Ended Primary-Inductor Converter) topology generator.

Non-isolated, non-inverting DC-DC converter that can step up or step
down voltage. Uses a coupling capacitor for energy transfer with
continuous input current.
"""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import auto_layout


class SepicGenerator(TopologyGenerator):
    """Generate a SEPIC converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "sepic"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "ripple_ratio", "voltage_ripple_ratio"]

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
        iin = iout * vout / vin if vin else iout

        # Input inductor: L1 = Vin * D / (fsw * ripple_ratio * Iin)
        delta_il1 = ripple_ratio * iin
        l1 = vin * duty / (fsw * delta_il1) if (fsw and delta_il1) else 1e-3
        l1 = max(l1, 1e-9)

        # Second inductor: L2 = Vin * D / (fsw * ripple_ratio * Iout)
        delta_il2 = ripple_ratio * iout
        l2 = vin * duty / (fsw * delta_il2) if (fsw and delta_il2) else 1e-3
        l2 = max(l2, 1e-9)

        # Coupling capacitor: Cc = D * Iout / (fsw * 0.05 * Vin)
        vc_ripple = 0.05 * vin  # 5% ripple on coupling cap
        c_coupling = duty * iout / (fsw * vc_ripple) if (fsw and vc_ripple) else 10e-6
        c_coupling = max(c_coupling, 1e-12)

        # Output capacitor: Cout = Iout * D / (fsw * vripple_ratio * Vout)
        vripple = vripple_ratio * vout
        c_out = iout * duty / (fsw * vripple) if (fsw and vripple) else 100e-6
        c_out = max(c_out, 1e-12)

        r_load = vout / iout if iout else 10.0

        # SEPIC: V1 -> L1 -> node_A(SW1.drain, Cc+) -> Cc -> node_B(D1.anode, L2.pin1)
        # D1.cathode -> output, SW1.source -> GND, L2.pin2 -> GND
        #
        # Layout uses DIR=0 vertical MOSFET (like boost) so source falls to GND:
        #   VDC(80,100)-(80,150) -> L1(120,100)-(170,100)
        #   MOSFET drain(200,100) source(200,150) gate(180,130) DIR=0
        #   GATING(180,170) -> Cc(250,100)-(300,100) horizontal
        #   L2(300,100)-(300,150) vertical (pin1=node_B at top, pin2=GND at bottom)
        #   DIODE anode(320,100) cathode(370,100) DIR=0 horizontal
        #   Cout(400,100)-(400,150) -> R1(450,100)-(450,150)
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
                    "Switching_Points": f"0,{int(duty * 360)}",
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
                "id": "L2", "type": "Inductor",
                "parameters": {"inductance": round(l2, 9)},
                "position": {"x": 300, "y": 100},
                "position2": {"x": 300, "y": 150},
                "direction": 90,
                "ports": [300, 100, 300, 150],
            },
            {
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 320, "y": 100}, "direction": 0,
                "ports": [320, 100, 370, 100],
            },
            {
                "id": "Cout", "type": "Capacitor",
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
            {"name": "net_cc_l2_d", "pins": ["Cc.negative", "L2.pin1", "D1.anode"]},
            {"name": "net_d_out", "pins": ["D1.cathode", "Cout.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "SW1.source", "L2.pin2", "Cout.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "SEPIC Converter",
                "description": (
                    f"SEPIC DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
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
