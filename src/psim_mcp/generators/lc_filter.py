"""LC low-pass filter topology generator."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph
from .layout import (
    make_vac,
    make_ground,
    make_inductor,
    make_capacitor,
    make_resistor,
)


class LCFilterGenerator(TopologyGenerator):
    """Generate an LC low-pass filter from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "lc_filter"

    @property
    def required_fields(self) -> list[str]:
        return []

    @property
    def optional_fields(self) -> list[str]:
        return ["load_resistance", "cutoff_freq", "vin_freq", "capacitance", "inductance", "vin", "freq"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.lc_filter import synthesize_lc_filter
        return synthesize_lc_filter(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        r_load: float = float(requirements.get("load_resistance", requirements.get("vout_target", 12.0)))
        vin: float = float(requirements.get("vin", 10.0))
        freq: float = float(requirements.get("freq", 1000.0))

        # Determine L and C from cutoff frequency or explicit values
        if requirements.get("inductance") and requirements.get("capacitance"):
            inductance = float(requirements["inductance"])
            capacitance = float(requirements["capacitance"])
            fc = 1 / (2 * math.pi * math.sqrt(inductance * capacitance))
        elif requirements.get("cutoff_freq"):
            fc = float(requirements["cutoff_freq"])
            z0 = r_load  # match impedance to load
            inductance = z0 / (2 * math.pi * fc)
            capacitance = 1 / (2 * math.pi * fc * z0)
        elif requirements.get("vin_freq"):
            # Filter designed to pass vin_freq, cutoff at 10x vin_freq
            fc = float(requirements["vin_freq"]) * 10
            z0 = r_load
            inductance = z0 / (2 * math.pi * fc)
            capacitance = 1 / (2 * math.pi * fc * z0)
        else:
            # Default: cutoff at 10x input frequency
            fc = freq * 10
            z0 = r_load
            inductance = z0 / (2 * math.pi * fc)
            capacitance = 1 / (2 * math.pi * fc * z0)

        inductance = max(inductance, 1e-9)
        capacitance = max(capacitance, 1e-12)
        z0 = math.sqrt(inductance / capacitance) if capacitance else r_load

        # Layout: VAC(80,100) -> L1(150,100) -> C1(220,100) shunt -> R1(280,100) shunt
        # GND bus at y=150
        components = [
            make_vac("V1", 80, 100, vin, freq),
            make_ground("GND1", 80, 150),
            make_inductor("L1", 150, 100, inductance, current_flag=1),
            make_capacitor("C1", 220, 100, capacitance),
            make_resistor("R1", 280, 100, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin", "pins": ["V1.positive", "L1.pin1"]},
            {"name": "net_lc", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "C1.negative", "R1.pin2"]},
        ]

        sim_period = 1 / freq if freq else 1e-3
        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "LC Low-Pass Filter",
                "description": (
                    f"LC filter: fc={fc:.1f}Hz, L={inductance*1e6:.2f}uH, "
                    f"C={capacitance*1e9:.2f}nF, Z0={z0:.1f}Ohm"
                ),
                "design": {
                    "cutoff_freq": round(fc, 2),
                    "inductance": round(inductance, 9),
                    "capacitance": round(capacitance, 9),
                    "characteristic_impedance": round(z0, 4),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(sim_period / 500, 9),
                "total_time": round(sim_period * 20, 6),
            },
        }
