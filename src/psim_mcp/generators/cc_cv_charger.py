"""CC/CV battery charger topology generator (buck-based)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph
from .layout import (
    make_vdc,
    make_ground,
    make_inductor,
    make_capacitor,
    make_resistor,
    make_gating,
    make_mosfet_h,
    make_diode_v,
)


class CCCVChargerGenerator(TopologyGenerator):
    """Generate a CC/CV battery charger circuit (buck topology)."""

    @property
    def topology_name(self) -> str:
        return "cc_cv_charger"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vbat", "iout", "charge_current", "fsw", "ripple_ratio", "voltage_ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.cc_cv_charger import synthesize_cc_cv_charger
        return synthesize_cc_cv_charger(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vbat: float = float(requirements.get("vbat", requirements.get("vout_target", vin * 0.5)))
        i_charge: float = float(requirements.get("charge_current", requirements.get("iout", 1.0)))
        fsw: float = float(requirements.get("fsw", 50_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        # Buck converter design: D = Vbat / Vin
        duty = vbat / vin if vin else 0.5
        delta_i = ripple_ratio * i_charge
        delta_i = max(delta_i, 1e-6)
        inductance = vbat * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)
        capacitance = delta_i / (8 * fsw * vripple_ratio * vbat) if (fsw and vripple_ratio and vbat) else 100e-6
        capacitance = max(capacitance, 1e-12)

        # Battery modeled as resistor at charge current
        r_bat = vbat / i_charge if i_charge else 10.0

        # Layout (same as buck):
        # VDC(120,100)-(120,150) -> MOSFET drain(150,100) source(200,100) gate(180,120)
        # GATING(180,170)
        # DIODE anode(220,150) cathode(220,100)
        # L(250,100)-(300,100) -> C(300,100)-(300,150) -> R_bat(350,100)-(350,150)
        # GND bus at y=150
        components = [
            make_vdc("V1", 120, 100, vin),
            make_ground("GND1", 120, 150),
            make_mosfet_h("SW1", 150, 100, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 180, 170, fsw, f" 0 {int(duty * 360)}."),
            make_diode_v("D1", 220, 150, forward_voltage=0.7),
            make_inductor("L1", 250, 100, inductance, current_flag=1),
            make_capacitor("C1", 300, 100, capacitance),
            make_resistor("R1", 350, 100, r_bat, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin_sw", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_sw_junc", "pins": ["SW1.source", "D1.cathode", "L1.pin1"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": [
                "V1.negative", "GND1.pin1", "D1.anode",
                "C1.negative", "R1.pin2",
            ]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "CC/CV Battery Charger",
                "description": (
                    f"CC/CV charger: {vin}V -> {vbat}V @ {i_charge}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "inductance": round(inductance, 9),
                    "capacitance": round(capacitance, 9),
                    "r_battery": round(r_bat, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(50 / fsw, 6),
            },
        }
