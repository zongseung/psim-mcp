"""Flyback converter topology generator.

Isolated DC-DC converter using a coupled inductor (transformer) for
energy storage and voltage transformation. Suitable for low-to-medium
power applications requiring galvanic isolation.
"""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_diode_h,
    make_gating,
    make_ground,
    make_mosfet_v,
    make_resistor,
    make_transformer,
    make_vdc,
)


class FlybackGenerator(TopologyGenerator):
    """Generate a flyback converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "flyback"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "n_ratio", "ripple_ratio", "voltage_ripple_ratio"]

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
        fsw: float = float(requirements.get("fsw", 100_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        # Turns ratio Ns/Np
        if requirements.get("n_ratio"):
            n = float(requirements["n_ratio"])
        else:
            # Choose n so that duty ~0.45 at nominal Vin:
            # D = (Vout * n) / (Vin + Vout * n) => n = D * Vin / (Vout * (1 - D))
            d_target = 0.45
            n = d_target * vin / (vout * (1 - d_target)) if vout else 1.0
            n = max(0.1, min(n, 10.0))

        # Duty cycle: D = (Vout * n) / (Vin + Vout * n)
        denom = vin + vout * n
        duty = (vout * n) / denom if denom else 0.5
        duty = max(0.05, min(duty, 0.95))

        # Input current
        pout = vout * iout
        iin = pout / (vin * duty) if (vin and duty) else iout

        # Magnetizing inductance: Lm = Vin * D / (fsw * delta_I)
        delta_i = ripple_ratio * iin
        lm = vin * duty / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        lm = max(lm, 1e-9)

        # Output capacitance: Cout = Iout * D / (fsw * Vripple)
        vripple = vripple_ratio * vout
        cout = iout * duty / (fsw * vripple) if (fsw and vripple) else 100e-6
        cout = max(cout, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Layout (verified working — V=6.95V):
        # VDC(80,80)-(80,130), GND at (80,230)
        # T1: p1(200,80) p2(200,130) s1(250,130) s2(250,80)
        # MOSFET_v: drain(200,130) source(200,180) gate(180,160) — at T1.primary2
        # GATING(160,160)
        # Diode_h: anode(270,80) cathode(320,80) — from T1.secondary2
        # C1(320,80)-(320,130) R1(370,80)-(370,130)
        # GND bus at y=230
        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 230),
            make_transformer(
                "T1", 200, 80, 200, 130, 250, 130, 250, 80,
                turns_ratio=round(n, 6), magnetizing_inductance=round(lm, 9),
            ),
            make_mosfet_v("SW1", 200, 130, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 160, 160, fsw, f"0,{int(duty * 360)}"),
            make_diode_h("D1", 270, 80, forward_voltage=0.7),
            make_capacitor("C1", 320, 80, cout),
            make_resistor("R1", 370, 80, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin_pri1", "pins": ["V1.positive", "T1.primary_in"]},
            {"name": "net_pri2_sw", "pins": ["T1.primary_out", "SW1.drain"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_sw_gnd", "pins": ["SW1.source", "V1.negative", "GND1.pin1"]},
            {"name": "net_sec2_d", "pins": ["T1.secondary_out", "D1.anode"]},
            {"name": "net_d_out", "pins": ["D1.cathode", "C1.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["T1.secondary_in", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Flyback Converter",
                "description": (
                    f"Flyback DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "turns_ratio": round(n, 6),
                    "magnetizing_inductance": round(lm, 9),
                    "capacitance": round(cout, 9),
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
