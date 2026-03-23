"""Diode bridge rectifier topology generator."""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import (
    make_vac,
    make_ground,
    make_diode_bridge,
    make_capacitor,
    make_resistor,
)


class DiodeBridgeRectifierGenerator(TopologyGenerator):
    """Generate a diode bridge rectifier with capacitor filter."""

    @property
    def topology_name(self) -> str:
        return "diode_bridge_rectifier"

    @property
    def required_fields(self) -> list[str]:
        return ["vac_rms"]

    @property
    def optional_fields(self) -> list[str]:
        return ["f_line", "load_resistance", "capacitance", "ripple_ratio"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vac_rms: float = float(requirements["vac_rms"])
        f_line: float = float(requirements.get("f_line", 60.0))
        r_load: float = float(requirements.get("load_resistance", 100.0))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.05))

        # Output DC voltage: Vpeak - 2*Vd (two diode drops)
        v_peak = vac_rms * math.sqrt(2)
        vdc = v_peak - 1.4  # two diode forward drops
        iout = vdc / r_load if r_load else 0.1

        # Filter capacitor: C = Iout / (2 * f_line * Vripple)
        v_ripple = ripple_ratio * vdc
        if requirements.get("capacitance"):
            capacitance = float(requirements["capacitance"])
        else:
            capacitance = iout / (2 * f_line * v_ripple) if (f_line and v_ripple) else 100e-6
        capacitance = max(capacitance, 1e-12)

        # Layout:
        # VAC(80,100)-(80,150) -> DiodeBridge(150,100) ac+(150,100) ac-(150,160)
        #                                               dc+(230,100) dc-(230,160)
        # C1(280,100)-(280,150) -> R1(340,100)-(340,150)
        # GND bus at y=160
        components = [
            make_vac("V1", 80, 100, vac_rms, f_line),
            make_ground("GND1", 80, 160),
            make_diode_bridge("BR1", 150, 100),
            make_capacitor("C1", 280, 100, capacitance),
            make_resistor("R1", 340, 100, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_ac_pos", "pins": ["V1.positive", "BR1.ac_pos"]},
            {"name": "net_ac_neg", "pins": ["V1.negative", "BR1.ac_neg"]},
            {"name": "net_dc_pos", "pins": ["BR1.dc_pos", "C1.positive", "R1.pin1"]},
            {"name": "net_dc_neg", "pins": ["BR1.dc_neg", "GND1.pin1", "C1.negative", "R1.pin2"]},
        ]

        sim_period = 1 / f_line if f_line else 1 / 60
        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Diode Bridge Rectifier",
                "description": (
                    f"Bridge rectifier: {vac_rms}Vrms @ {f_line}Hz -> "
                    f"{vdc:.1f}Vdc, C={capacitance*1e6:.1f}uF"
                ),
                "design": {
                    "vdc_output": round(vdc, 4),
                    "capacitance": round(capacitance, 9),
                    "r_load": round(r_load, 4),
                    "ripple_voltage": round(v_ripple, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(sim_period / 500, 9),
                "total_time": round(sim_period * 20, 6),
            },
        }
