"""LLC resonant converter topology generator.

Half-bridge LLC resonant converter with series resonant inductor (Lr),
resonant capacitor (Cr), and transformer magnetizing inductance (Lm).
Achieves soft-switching (ZVS) for high efficiency at high frequencies.
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_diode_h,
    make_gating,
    make_ground,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_transformer,
    make_vdc,
)


class LLCGenerator(TopologyGenerator):
    """Generate an LLC resonant converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "llc"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "power", "quality_factor"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        fsw: float = float(requirements.get("fsw", 100_000))
        ln_ratio: float = float(requirements.get("quality_factor", 6.0))
        ln_ratio = max(3.0, min(ln_ratio, 10.0))

        # Output power
        if requirements.get("power"):
            pout = float(requirements["power"])
            iout = pout / vout if vout else 1.0
        elif requirements.get("iout"):
            iout = float(requirements.get("iout"))
            pout = vout * iout
        else:
            iout = 1.0
            pout = vout * iout

        r_load = vout / iout if iout else 10.0
        r_load = max(r_load, 0.1)

        # Turns ratio for half-bridge: n = Vin / (2 * Vout)
        n = vin / (2 * vout) if vout else 1.0
        n = max(0.1, min(n, 20.0))

        # Resonant frequency = switching frequency (design at resonance)
        fr = fsw

        # Equivalent AC load resistance: Rac = 8 * n^2 * Rload / pi^2
        rac = 8 * n**2 * r_load / (math.pi**2)

        # Characteristic impedance: Zr = Rac (at matched load for unity gain)
        zr = rac if rac > 0 else 10.0

        # Resonant inductor: Lr = Zr / (2 * pi * fr)
        lr = zr / (2 * math.pi * fr) if fr else 1e-6
        lr = max(lr, 1e-9)

        # Resonant capacitor: Cr = 1 / ((2*pi*fr)^2 * Lr)
        cr = 1 / ((2 * math.pi * fr) ** 2 * lr) if (fr and lr) else 10e-9
        cr = max(cr, 1e-12)

        # Magnetizing inductance: Lm = Ln_ratio * Lr
        lm = ln_ratio * lr
        lm = max(lm, 1e-9)

        # Output capacitor: sized for ripple at 2*fsw (full-bridge rectifier)
        vripple_ratio = 0.01
        vripple = vripple_ratio * vout
        cout = iout / (2 * 2 * fsw * vripple) if (fsw and vripple) else 100e-6
        cout = max(cout, 1e-12)

        # Layout (verified stacked MOSFET pattern):
        # VDC(80,80)-(80,130), GND at (80,230)
        # Stacked MOSFETs: SW1 drain(200,80) source(200,130),
        #   30px gap, SW2 drain(200,160) source(200,210)
        # G1(160,110) G2(160,190) — near gates, NOT overlapping GND bus
        # Cr: horizontal capacitor at (260,130)-(310,130)
        # Lr: inductor at (330,130)-(380,130)
        # T1: p1(380,80) p2(380,130) s1(430,130) s2(430,80)
        # D1: anode(450,80) cathode(500,80), D2: anode(450,130) cathode(500,130)
        # Cout(500,80)-(500,130), R1(550,80)-(550,130)
        # GND bus at y=230

        # Cr is placed horizontally — inline dict since make_capacitor is vertical.
        cr_cap = {
            "id": "Cr", "type": "Capacitor",
            "parameters": {"capacitance": round(cr, 9)},
            "position": {"x": 260, "y": 130},
            "position2": {"x": 310, "y": 130},
            "direction": 0,
            "ports": [260, 130, 310, 130],
        }

        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 230),
            make_mosfet_v("SW1", 200, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW2", 200, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 160, 110, fsw, "0,175"),
            make_gating("G2", 160, 190, fsw, "180,355"),
            cr_cap,
            make_inductor("Lr", 330, 130, lr),
            make_transformer(
                "T1", 380, 80, 380, 130, 430, 130, 430, 80,
                turns_ratio=round(n, 6), magnetizing_inductance=round(lm, 9),
            ),
            make_diode_h("D1", 450, 80, forward_voltage=0.7),
            make_diode_h("D2", 450, 130, forward_voltage=0.7),
            make_capacitor("Cout", 500, 80, cout),
            make_resistor("R1", 550, 80, r_load, voltage_flag=1),
        ]

        # Half-bridge LLC with stacked vertical MOSFETs:
        # SW1.drain = V+, SW1.source = SW2.drain = half-bridge midpoint
        # SW2.source = V- (gnd path via y=230)
        # midpoint -> Cr -> Lr -> T1.primary_in, T1.primary_out -> gnd
        # T1.secondary_out -> D1, T1.secondary_in -> D2
        # D1.cathode + D2.cathode -> Cout -> R1
        nets = [
            {"name": "net_vdc_pos", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_hb_mid", "pins": ["SW1.source", "SW2.drain", "Cr.positive"]},
            {"name": "net_cr_lr", "pins": ["Cr.negative", "Lr.pin1"]},
            {"name": "net_lr_pri", "pins": ["Lr.pin2", "T1.primary_in"]},
            {"name": "net_pri_gnd", "pins": ["T1.primary_out", "V1.negative", "GND1.pin1", "SW2.source"]},
            {"name": "net_sec2_d1", "pins": ["T1.secondary_out", "D1.anode"]},
            {"name": "net_sec1_d2", "pins": ["T1.secondary_in", "D2.anode"]},
            {"name": "net_rect_out", "pins": ["D1.cathode", "D2.cathode", "Cout.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["Cout.negative", "R1.pin2"]},
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "LLC Resonant Converter",
                "description": (
                    f"LLC resonant converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, n={n:.3f}, fr={fr/1e3:.1f}kHz"
                ),
                "design": {
                    "turns_ratio": round(n, 6),
                    "resonant_frequency": round(fr, 2),
                    "resonant_inductance": round(lr, 9),
                    "resonant_capacitance": round(cr, 9),
                    "magnetizing_inductance": round(lm, 9),
                    "output_capacitance": round(cout, 9),
                    "characteristic_impedance": round(zr, 4),
                    "ln_ratio": round(ln_ratio, 2),
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
