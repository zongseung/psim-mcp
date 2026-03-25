"""PV panel with MPPT boost converter topology generator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph
from .layout import (
    make_ground,
    make_inductor,
    make_capacitor,
    make_resistor,
    make_gating,
    make_mosfet_v,
    make_diode_h,
    _build_component,
)


class PVMPPTBoostGenerator(TopologyGenerator):
    """Generate a PV panel with MPPT boost converter."""

    @property
    def topology_name(self) -> str:
        return "pv_mppt_boost"

    @property
    def required_fields(self) -> list[str]:
        return []

    @property
    def optional_fields(self) -> list[str]:
        return ["voc", "isc", "vout_target", "vmp", "imp", "fsw", "ripple_ratio", "voltage_ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.pv_mppt_boost import synthesize_pv_mppt_boost
        return synthesize_pv_mppt_boost(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin_default = float(requirements.get("vin", 48.0))
        voc: float = float(requirements.get("voc", vin_default * 1.25))
        isc: float = float(requirements.get("isc", 2.0))
        vout: float = float(requirements.get("vout_target", vin_default * 1.5))
        # MPP is typically ~80% of Voc, ~90% of Isc
        vmp: float = float(requirements.get("vmp", voc * 0.8))
        imp: float = float(requirements.get("imp", isc * 0.9))
        fsw: float = float(requirements.get("fsw", 50_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        # Boost converter design based on Vmpp input
        vin = vmp
        duty = 1 - vin / vout if vout > vin else 0.5
        iin = imp
        delta_i = ripple_ratio * iin
        delta_i = max(delta_i, 1e-6)
        inductance = vin * duty / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        iout = iin * (1 - duty)
        capacitance = iout * duty / (fsw * vripple_ratio * vout) if (fsw and vripple_ratio and vout) else 100e-6
        capacitance = max(capacitance, 1e-12)
        r_load = vout / iout if iout else 10.0

        # Layout: PV(80,100) -> L1(150,100) -> junction(220,100)
        # MOSFET vertical: drain(220,100) source(220,150) gate(200,130)
        # G1(200,170)
        # Diode horizontal: anode(240,100) cathode(290,100)
        # C1(320,100)-(320,150) -> R1(380,100)-(380,150)
        # GND bus at y=150

        # Use DC_Source as PV approximation at Vmpp
        pv_comp = _build_component(
            "PV1", "DC_Source",
            {"x": 80, "y": 100}, 0,
            [(80, 100), (80, 150)],
            parameters={"voltage": vmp},
        )

        components = [
            pv_comp,
            make_ground("GND1", 80, 150),
            make_inductor("L1", 150, 100, inductance, current_flag=1),
            make_mosfet_v("SW1", 220, 100, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 200, 170, fsw, f"0,{int(duty * 360)}"),
            make_diode_h("D1", 240, 100, forward_voltage=0.7),
            make_capacitor("C1", 320, 100, capacitance),
            make_resistor("R1", 380, 100, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_pv_l", "pins": ["PV1.positive", "L1.pin1"]},
            {"name": "net_l_sw_d", "pins": ["L1.pin2", "SW1.drain", "D1.anode"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_d_out", "pins": ["D1.cathode", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": [
                "PV1.negative", "GND1.pin1", "SW1.source",
                "C1.negative", "R1.pin2",
            ]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "PV MPPT Boost Converter",
                "description": (
                    f"PV MPPT boost: Voc={voc}V, Isc={isc}A, "
                    f"Vmpp={vmp}V -> {vout}V, fsw={fsw/1e3:.1f}kHz, D={duty:.3f}"
                ),
                "design": {
                    "vmp": round(vmp, 4),
                    "imp": round(imp, 4),
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
