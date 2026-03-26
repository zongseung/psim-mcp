"""Single-phase thyristor bridge rectifier topology generator.

Four thyristors (SCRs) in a full-bridge configuration for controlled
AC-to-DC conversion. The firing angle alpha controls the average DC
output voltage. An output inductor smooths the load current.
"""

from __future__ import annotations

import math

from typing import TYPE_CHECKING

from .base import TopologyGenerator
from .layout import (
    make_ground,
    make_inductor,
    make_resistor,
    make_vac,
    make_thyristor_v,
)

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class ThyristorRectifierGenerator(TopologyGenerator):
    """Generate a single-phase thyristor bridge rectifier from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "thyristor_rectifier"

    @property
    def required_fields(self) -> list[str]:
        return ["vin"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vac_rms", "firing_angle", "f_line", "load_resistance", "ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.thyristor_rectifier import synthesize_thyristor_rectifier
        return synthesize_thyristor_rectifier(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vac_rms: float = float(requirements.get("vac_rms", requirements.get("vin", 220.0)))
        alpha_deg: float = float(requirements.get("firing_angle", 30.0))
        f_line: float = float(requirements.get("f_line", 60.0))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.1))

        alpha_rad = math.radians(alpha_deg)
        vpeak = vac_rms * math.sqrt(2)

        # Average DC output voltage: Vdc = (2 * Vpeak / pi) * cos(alpha)
        # For a fully-controlled bridge: Vdc = 0.9 * Vrms * cos(alpha)
        vdc = 0.9 * vac_rms * math.cos(alpha_rad)
        vdc = max(vdc, 0.1)  # ensure positive for resistive load sizing

        # Load resistance
        r_load = float(requirements.get("load_resistance", 10.0))
        r_load = max(r_load, 0.1)
        idc = vdc / r_load

        # Output inductor to smooth current ripple
        # L = (Vdc - Vload) / (2 * f_line * delta_I)
        # Simplified: L = Vpeak / (2 * f_line * delta_I * pi)
        delta_i = ripple_ratio * idc if idc > 0 else 1.0
        inductance = vpeak / (2 * math.pi * f_line * delta_i) if (f_line and delta_i) else 10e-3
        inductance = max(inductance, 1e-9)

        # Layout:
        # VAC(80,100)-(80,150), GND at (80,230)
        #
        # Thyristor bridge (same topology as diode bridge but with thyristors):
        #   T1: anode connects to VAC+, cathode connects to DC+ rail
        #   T2: anode connects to VAC-, cathode connects to DC+ rail
        #   T3: cathode connects to VAC-, anode connects to DC- rail
        #   T4: cathode connects to VAC+, anode connects to DC- rail
        #
        # Using vertical thyristors (DIR=0): anode(x,y) cathode(x,y+50) gate(x-20,y+30)
        #
        # Left column at x=200: T1(top) and T4(bottom)
        #   T1: anode(200,80) cathode(200,130) gate(180,110) — VAC+ to DC+
        #   T4: anode(200,150) cathode(200,200) gate(180,180) — DC- to VAC+
        #   Note: T4 needs reversed polarity — cathode to VAC+
        #   Actually for bridge: T1 anode=AC+, cathode=DC+; T4 cathode=AC+, anode=DC-
        #
        # Right column at x=350: T2(top) and T3(bottom)
        #   T2: anode(350,80) cathode(350,130) gate(330,110) — VAC- to DC+
        #   T3: anode(350,150) cathode(350,200) gate(330,180) — DC- to VAC-
        #
        # DC+ rail at y=80, DC- rail at y=200
        # L1(420,80)-(470,80), R1(500,80)-(500,130)
        # R1 bottom to DC- rail

        components = [
            make_vac("V1", 80, 100, vac_rms, frequency=f_line),
            make_ground("GND1", 80, 230),
            # Thyristor bridge
            # Top pair (anodes from AC, cathodes to DC+)
            make_thyristor_v("T1", 200, 80, firing_angle=alpha_deg),
            make_thyristor_v("T2", 350, 80, firing_angle=alpha_deg),
            # Bottom pair (anodes from DC-, cathodes to AC)
            make_thyristor_v("T3", 350, 150, firing_angle=alpha_deg),
            make_thyristor_v("T4", 200, 150, firing_angle=alpha_deg),
            # Output filter
            make_inductor("L1", 420, 80, inductance, current_flag=1),
            make_resistor("R1", 500, 80, r_load, voltage_flag=1),
        ]

        nets = [
            # AC connections
            {"name": "net_ac_pos", "pins": ["V1.positive", "T1.anode", "T4.cathode"]},
            {"name": "net_ac_neg", "pins": ["V1.negative", "T2.anode", "T3.cathode"]},
            # DC+ rail (thyristor cathodes to inductor)
            {"name": "net_dc_pos", "pins": ["T1.cathode", "T2.cathode", "L1.pin1"]},
            # DC- rail (thyristor anodes from load return)
            {"name": "net_dc_neg", "pins": [
                "T3.anode", "T4.anode", "R1.pin2", "GND1.pin1",
            ]},
            # Output
            {"name": "net_lf_out", "pins": ["L1.pin2", "R1.pin1"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Thyristor Bridge Rectifier",
                "description": (
                    f"Single-phase thyristor rectifier: Vac={vac_rms}Vrms, "
                    f"alpha={alpha_deg}deg, Vdc={vdc:.1f}V, "
                    f"f_line={f_line}Hz"
                ),
                "design": {
                    "firing_angle_deg": round(alpha_deg, 2),
                    "vdc_avg": round(vdc, 4),
                    "vpeak": round(vpeak, 4),
                    "idc": round(idc, 4),
                    "inductance": round(inductance, 9),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (f_line * 1000), 9),
                "total_time": round(10 / f_line, 6),
            },
        }
