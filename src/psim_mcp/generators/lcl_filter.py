"""LCL filter topology generator for grid-connected inverters."""

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


class LCLFilterGenerator(TopologyGenerator):
    """Generate an LCL filter from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "lcl_filter"

    @property
    def required_fields(self) -> list[str]:
        return []

    @property
    def optional_fields(self) -> list[str]:
        return ["fsw", "f_line", "load_resistance", "vin", "vdc", "delta_i_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.lcl_filter import synthesize_lcl_filter
        return synthesize_lcl_filter(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        fsw: float = float(requirements.get("fsw", 10_000))
        f_line: float = float(requirements.get("f_line", 60.0))
        r_load: float = float(requirements.get("load_resistance", requirements.get("vout_target", 12.0)))
        vin: float = float(requirements.get("vin", 220.0))
        vdc: float = float(requirements.get("vdc", vin * math.sqrt(2)))
        delta_i_ratio: float = float(requirements.get("delta_i_ratio", 0.15))

        # Inverter-side inductor: L1 = Vdc / (delta_I * fsw)
        i_rated = vin / r_load if r_load else 1.0
        delta_i = delta_i_ratio * i_rated * math.sqrt(2)
        delta_i = max(delta_i, 1e-6)
        l1 = vdc / (delta_i * fsw) if fsw else 1e-3
        l1 = max(l1, 1e-9)

        # Grid-side inductor: L2 ~ L1/3
        l2 = l1 / 3
        l2 = max(l2, 1e-9)

        # Resonant frequency between fsw/10 and fsw/5
        f_res = fsw / 7  # middle of range
        # C = 1 / (4*pi^2 * f_res^2 * L1)
        capacitance = 1 / (4 * math.pi**2 * f_res**2 * l1) if (f_res and l1) else 10e-6
        capacitance = max(capacitance, 1e-12)

        # Layout: VAC(80,100) -> L1(150,100) -> C1(220,100) shunt -> L2(290,100) -> R1(360,100)
        # GND bus at y=150
        components = [
            make_vac("V1", 80, 100, vin, f_line),
            make_ground("GND1", 80, 150),
            make_inductor("L1", 150, 100, l1, current_flag=1),
            make_capacitor("C1", 220, 100, capacitance),
            make_inductor("L2", 290, 100, l2),
            make_resistor("R1", 360, 100, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin", "pins": ["V1.positive", "L1.pin1"]},
            {"name": "net_l1_c", "pins": ["L1.pin2", "C1.positive", "L2.pin1"]},
            {"name": "net_l2_out", "pins": ["L2.pin2", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "C1.negative", "R1.pin2"]},
        ]

        sim_period = 1 / f_line if f_line else 1e-3
        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "LCL Filter",
                "description": (
                    f"LCL filter: fsw={fsw/1e3:.1f}kHz, f_line={f_line}Hz, "
                    f"L1={l1*1e6:.1f}uH, C={capacitance*1e9:.1f}nF, L2={l2*1e6:.1f}uH"
                ),
                "design": {
                    "l1": round(l1, 9),
                    "l2": round(l2, 9),
                    "capacitance": round(capacitance, 9),
                    "f_resonant": round(f_res, 2),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(sim_period * 10, 6),
            },
        }
