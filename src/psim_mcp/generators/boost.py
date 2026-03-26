"""Boost (step-up) converter topology generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class BoostGenerator(TopologyGenerator):
    """Generate a boost converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "boost"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "ripple_ratio", "voltage_ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.boost import synthesize_boost
        return synthesize_boost(requirements)

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

        duty = 1 - vin / vout if vout else 0.5
        iin = iout / (1 - duty) if duty < 1 else iout
        delta_i = ripple_ratio * iin
        inductance = vin * duty / (fsw * delta_i) if delta_i else 1e-3
        capacitance = iout * duty / (fsw * vripple_ratio * vout) if vout else 100e-6
        r_load = vout / iout if iout else 10.0

        # Layout:
        # VDC(80,100)-(80,150) -> L(120,100)-(170,100) -> junction(200,100)
        # MOSFET: vertical DIR=0, drain(200,100) source(200,150) gate(180,130)
        # GATING(180,170)
        # DIODE: horizontal DIR=0, anode(220,100) cathode(270,100)
        # C(300,100)-(300,150) -> R(350,100)-(350,150)
        # GND bus at y=150
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
                "parameters": {"inductance": round(inductance, 9)},
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
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 220, "y": 100}, "direction": 0,
                "ports": [220, 100, 270, 100],
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

        nets = [
            {"name": "net_vin_l", "pins": ["V1.positive", "L1.pin1"]},
            {"name": "net_l_sw_d", "pins": ["L1.pin2", "SW1.drain", "D1.anode"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_d_out", "pins": ["D1.cathode", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "SW1.source", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Boost Converter",
                "description": (
                    f"Boost DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
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
