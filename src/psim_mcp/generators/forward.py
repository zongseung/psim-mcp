"""Forward converter topology generator.

Isolated DC-DC converter using a transformer with an output LC filter.
Unlike the flyback, energy transfers during the switch ON period, and
the output inductor provides continuous current to the load.
"""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_diode_h,
    make_diode_v,
    make_gating,
    make_ground,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_transformer,
    make_vdc,
)


class ForwardGenerator(TopologyGenerator):
    """Generate a forward converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "forward"

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

        d_max = 0.45  # practical maximum duty for forward converter

        # Turns ratio Ns/Np
        if requirements.get("n_ratio"):
            n = float(requirements["n_ratio"])
        else:
            n = vout / (vin * d_max) if vin else 1.0
            n = max(0.05, min(n, 10.0))

        # Duty cycle: D = Vout / (Vin * n)
        duty = vout / (vin * n) if (vin and n) else 0.5
        duty = max(0.05, min(duty, 0.95))

        # Output inductor: L = Vout * (1 - D) / (fsw * ripple_ratio * Iout)
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitance: Cout = delta_I / (8 * fsw * Vripple)
        vripple = vripple_ratio * vout
        capacitance = delta_i / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
        capacitance = max(capacitance, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Layout (verified working pattern):
        # VDC(80,80)-(80,130), GND at (80,230)
        # T1: p1(200,80) p2(200,130) s1(250,130) s2(250,80)
        # MOSFET_v: drain(200,130) source(200,180) gate(180,160) — at T1.primary2
        # GATING(160,160)
        # D1(rectifier): anode(270,80) cathode(320,80) — horizontal from T1.secondary2
        # D2(freewheel): anode(270,130) cathode(270,80) — vertical
        # L1(340,80)-(390,80) horizontal inductor
        # C1(390,80)-(390,130) R1(440,80)-(440,130)
        # GND bus at y=230
        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 230),
            make_transformer(
                "T1", 200, 80, 200, 130, 250, 130, 250, 80,
                turns_ratio=round(n, 6),
            ),
            make_mosfet_v("SW1", 200, 130, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 160, 160, fsw, f"0,{int(duty * 360)}"),
            make_diode_h("D1", 270, 80, forward_voltage=0.7),
            make_diode_v("D2", 270, 130, forward_voltage=0.7),
            make_inductor("L1", 340, 80, inductance),
            make_capacitor("C1", 390, 80, capacitance),
            make_resistor("R1", 440, 80, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin_pri1", "pins": ["V1.positive", "T1.primary_in"]},
            {"name": "net_pri2_sw", "pins": ["T1.primary_out", "SW1.drain"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_sw_gnd", "pins": ["SW1.source", "V1.negative", "GND1.pin1"]},
            {"name": "net_sec2_d1", "pins": ["T1.secondary_out", "D1.anode"]},
            {"name": "net_d1_l", "pins": ["D1.cathode", "D2.cathode", "L1.pin1"]},
            {"name": "net_l_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["T1.secondary_in", "D2.anode", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Forward Converter",
                "description": (
                    f"Forward DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "turns_ratio": round(n, 6),
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
