"""Buck (step-down) converter topology generator."""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import auto_layout


class BuckGenerator(TopologyGenerator):
    """Generate a buck converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "buck"

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

        duty = vout / vin
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if delta_i else 1e-3
        capacitance = delta_i / (8 * fsw * vripple_ratio * vout) if vout else 100e-6
        r_load = vout / iout if iout else 10.0

        # Layout:
        # VDC(120,100)-(120,150) -> MOSFET drain(150,100) source(200,100) gate(180,120) DIR=270
        # GATING(180,170) -> wire to gate
        # DIODE anode(220,150) cathode(220,100) DIR=270
        # L(250,100)-(300,100) -> C(300,100)-(300,150) -> R(350,100)-(350,150)
        # GND bus at y=150
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
                "position": {"x": 150, "y": 100}, "direction": 270,
                "ports": [150, 100, 200, 100, 180, 120],
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
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 220, "y": 150}, "direction": 270,
                "ports": [220, 150, 220, 100],
            },
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(inductance, 9), "CurrentFlag": 1},
                "position": {"x": 250, "y": 100},
                "position2": {"x": 300, "y": 100},
                "direction": 0,
                "ports": [250, 100, 300, 100],
            },
            {
                "id": "C1", "type": "Capacitor",
                "parameters": {"capacitance": round(capacitance, 9)},
                "position": {"x": 300, "y": 100},
                "position2": {"x": 300, "y": 150},
                "direction": 90,
                "ports": [300, 100, 300, 150],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 350, "y": 100},
                "position2": {"x": 350, "y": 150},
                "direction": 90,
                "ports": [350, 100, 350, 150],
            },
        ]

        # Nets (canonical format: name + pins)
        nets = [
            {"name": "net_vin_sw", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_sw_junc", "pins": ["SW1.source", "D1.cathode", "L1.pin1"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "D1.anode", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Buck Converter",
                "description": (
                    f"Buck DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
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
