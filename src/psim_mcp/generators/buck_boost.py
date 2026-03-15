"""Buck-boost (inverting) converter topology generator."""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import auto_layout


class BuckBoostGenerator(TopologyGenerator):
    """Generate a buck-boost converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "buck_boost"

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

        # Buck-boost duty: D = Vout / (Vin + Vout)
        duty = vout / (vin + vout) if (vin + vout) else 0.5
        iin = iout * duty / (1 - duty) if duty < 1 else iout
        delta_i = ripple_ratio * (iin + iout)
        inductance = vin * duty / (fsw * delta_i) if delta_i else 1e-3
        capacitance = iout * duty / (fsw * vripple_ratio * vout) if vout else 100e-6
        r_load = vout / iout if iout else 10.0

        components = [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": vin}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": fsw, "on_resistance": 0.01}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": round(inductance, 9)}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": round(capacitance, 9)}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": round(r_load, 4)}},
        ]

        positions = auto_layout(
            main_path=["V1", "SW1", "L1", "R1"],
            branches={"L1": ["D1"], "R1": ["C1"]},
        )
        for comp in components:
            comp["position"] = positions.get(comp["id"], {"x": 0, "y": 0})

        nets = [
            {"name": "net_vin_sw", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_sw_l", "pins": ["SW1.source", "L1.pin1"]},
            {"name": "net_l_d_out", "pins": ["L1.pin2", "D1.cathode", "C1.positive", "R1.pin1"]},
            {"name": "net_gnd", "pins": ["V1.negative", "D1.anode", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Buck-Boost Converter",
                "description": (
                    f"Buck-Boost DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
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
