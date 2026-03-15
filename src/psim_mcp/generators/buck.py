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
        return ["vin", "vout_target", "iout"]

    @property
    def optional_fields(self) -> list[str]:
        return ["fsw", "ripple_ratio", "voltage_ripple_ratio"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        iout: float = float(requirements["iout"])
        fsw: float = float(requirements.get("fsw", 50_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        duty = vout / vin
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if delta_i else 1e-3
        capacitance = delta_i / (8 * fsw * vripple_ratio * vout) if vout else 100e-6
        r_load = vout / iout if iout else 10.0

        # Component list
        components = [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": vin}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": fsw, "on_resistance": 0.01}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": round(inductance, 9)}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": round(capacitance, 9)}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": round(r_load, 4)}},
        ]

        # Layout
        positions = auto_layout(
            main_path=["V1", "SW1", "L1", "R1"],
            branches={"SW1": ["D1"], "R1": ["C1"]},
        )
        for comp in components:
            comp["position"] = positions.get(comp["id"], {"x": 0, "y": 0})

        # Nets
        nets = [
            {"id": "net_vin_sw", "connections": ["V1.positive", "SW1.drain"]},
            {"id": "net_sw_l", "connections": ["SW1.source", "D1.cathode", "L1.input"]},
            {"id": "net_l_out", "connections": ["L1.output", "C1.positive", "R1.positive"]},
            {"id": "net_gnd", "connections": ["V1.negative", "D1.anode", "C1.negative", "R1.negative"]},
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
