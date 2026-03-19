"""Forward converter topology generator.

Isolated DC-DC converter using a transformer with an output LC filter.
Unlike the flyback, energy transfers during the switch ON period, and
the output inductor provides continuous current to the load.
"""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import auto_layout


class ForwardGenerator(TopologyGenerator):
    """Generate a forward converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "forward"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "n_ratio", "ripple_ratio", "voltage_ripple_ratio"]

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
        fsw: float = float(requirements.get("fsw", 100_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        d_max = 0.45  # practical maximum duty for forward converter

        # Turns ratio Ns/Np
        if requirements.get("n_ratio"):
            n = float(requirements["n_ratio"])
        else:
            n = vout / (vin * d_max) if vin else 1.0
            n = max(0.05, min(n, 10.0))

        # Duty cycle: D = Vout / (Vin * n)
        duty = vout / (vin * n) if (vin and n) else 0.5
        duty = max(0.05, min(duty, 0.95))

        # Output inductor: L = Vout * (1 - D) / (fsw * ripple_ratio * Iout)
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitance: Cout = delta_I / (8 * fsw * Vripple)
        vripple = vripple_ratio * vout
        capacitance = delta_i / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
        capacitance = max(capacitance, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Forward: V1 -> T1 primary -> SW1 to GND | T1 secondary -> D1 -> L1 -> C1||R1, D2 freewheeling
        components = [
            {
                "id": "V1", "type": "DC_Source",
                "parameters": {"voltage": vin},
                "position": {"x": 120, "y": 100}, "direction": 0,
                "ports": [120, 100, 120, 150],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 120, "y": 150}, "direction": 0,
                "ports": [120, 150],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 100}, "direction": 270,
                "ports": [200, 100, 250, 100, 230, 120],
            },
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": f"0,{int(duty * 360)}",
                },
                "position": {"x": 230, "y": 170}, "direction": 0,
                "ports": [230, 170],
            },
            {
                "id": "T1", "type": "Transformer",
                "parameters": {"turns_ratio": round(n, 6)},
                "position": {"x": 280, "y": 100}, "direction": 0,
                "ports": [280, 100, 280, 150, 330, 100, 330, 150],
            },
            {
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 370, "y": 150}, "direction": 270,
                "ports": [370, 150, 370, 100],
            },
            {
                "id": "D2", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 420, "y": 150}, "direction": 270,
                "ports": [420, 150, 420, 100],
            },
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(inductance, 9)},
                "position": {"x": 450, "y": 100},
                "position2": {"x": 500, "y": 100},
                "direction": 0,
                "ports": [450, 100, 500, 100],
            },
            {
                "id": "C1", "type": "Capacitor",
                "parameters": {"capacitance": round(capacitance, 9)},
                "position": {"x": 500, "y": 100},
                "position2": {"x": 500, "y": 150},
                "direction": 90,
                "ports": [500, 100, 500, 150],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 550, "y": 100},
                "position2": {"x": 550, "y": 150},
                "direction": 90,
                "ports": [550, 100, 550, 150],
            },
        ]

        nets = [
            {"name": "net_vin_pri1", "pins": ["V1.positive", "T1.primary1"]},
            {"name": "net_pri2_sw", "pins": ["T1.primary2", "SW1.drain"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_sw_gnd", "pins": ["SW1.source", "V1.negative", "GND1.pin1"]},
            {"name": "net_sec1_d1", "pins": ["T1.secondary1", "D1.anode"]},
            {"name": "net_d1_l", "pins": ["D1.cathode", "D2.cathode", "L1.pin1"]},
            {"name": "net_l_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["T1.secondary2", "D2.anode", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Forward Converter",
                "description": (
                    f"Forward DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "turns_ratio": round(n, 6),
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
