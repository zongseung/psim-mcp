"""LLC resonant converter topology generator.

Half-bridge LLC resonant converter with series resonant inductor (Lr),
resonant capacitor (Cr), and transformer magnetizing inductance (Lm).
Achieves soft-switching (ZVS) for high efficiency at high frequencies.

Layout verified against PSIM reference:
  converted_ResonantLLC_CurrentAndVoltageLoop.py
  - TF_IDEAL with PORTS=[860,170, 860,220, 910,170, 910,220], DIR=0
  - Lm as separate vertical inductor in parallel with TF primary
  - BDIODE1 full-bridge rectifier on secondary side
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_capacitor_h,
    make_diode_bridge,
    make_gating,
    make_ground,
    make_ideal_transformer,
    make_inductor,
    make_inductor_v,
    make_mosfet_v,
    make_resistor,
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

        # Layout based on PSIM reference (converted_ResonantLLC_CurrentAndVoltageLoop.py):
        #
        # Key insight: PSIM LLC uses TF_IDEAL (not TF_1F_1) + separate Lm inductor
        # in PARALLEL with transformer primary. Lm is NOT a transformer parameter.
        #
        # Reference components and their PORTS from the converted file:
        #   VDC "VDC1": PORTS=[350,200, 350,250], Amplitude="Vin"
        #   TF_IDEAL "TI2": PORTS=[860,170, 860,220, 910,170, 910,220], DIR=0
        #   MULTI_INDUCTOR "Ls": PORTS=[720,170, 770,170], DIR=0  (series resonant)
        #   MULTI_INDUCTOR "Lm": PORTS=[810,180, 810,230], DIR=90 (magnetizing, vertical shunt)
        #   MULTI_CAPACITOR "Cs": PORTS=[660,170, 710,170], DIR=0  (series resonant)
        #   BDIODE1 "BD11": PORTS=[940,170, 940,230, 1020,170, 1020,230], DIR=0
        #   MULTI_CAPACITOR "Co": PORTS=[1200,180, 1200,230], DIR=90
        #   MULTI_RESISTOR "R6": PORTS=[1620,170, 1620,220], DIR=270
        #
        # Our simplified layout (same topology, no control loop):
        #   Half-bridge: stacked MOSFETs (verified pattern from half_bridge.py)
        #   Resonant tank: Cr → Lr → node → Lm(shunt) + TF_IDEAL
        #   Rectifier: BDIODE1 full-bridge on secondary side
        #
        # VDC(80,80)-(80,130), GND bus at y=230
        # SW1(200,80-130), SW2(200,160-210), G1(160,110), G2(160,190)
        # Cr(260,130)-(310,130) horizontal → Lr(330,130)-(380,130) horizontal
        # → node at (400,130): Lm(400,130)-(400,180) vertical shunt
        #   TF_IDEAL p1(420,130) p2(420,180) s1(470,130) s2(470,180)
        # BDIODE1: ac+(490,130) ac-(490,190) dc+(570,130) dc-(570,190)
        # Cout(600,130)-(600,180), R1(650,130)-(650,180)
        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 230),
            make_ground("GND2", 490, 230),  # secondary-side GND hub
            make_mosfet_v("SW1", 200, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW2", 200, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 160, 110, fsw, "0,175"),
            make_gating("G2", 160, 190, fsw, "180,355"),
            make_capacitor_h("Cr", 260, 130, cr),  # resonant capacitor, horizontal
            make_inductor("Lr", 330, 130, lr),
            make_inductor_v("Lm", 400, 130, lm),
            make_ideal_transformer(
                "T1",
                420, 130, 420, 180,  # primary1, primary2
                470, 130, 470, 180,  # secondary1, secondary2
                np_turns=round(n, 6), ns_turns=1,
            ),
            make_diode_bridge("BD1", 490, 130),
            make_capacitor("Cout", 600, 130, cout),
            make_resistor("R1", 650, 130, r_load, voltage_flag=1),
        ]

        # LLC net connections:
        # Half-bridge: V+ → SW1.drain, SW1.source/SW2.drain = midpoint
        # Resonant chain: midpoint → Cr → Lr → node(400,130)
        # At node: Lm shunts down, TF_IDEAL primary1 connects
        # TF primary2 and Lm bottom both go to GND bus
        # Secondary: TF_IDEAL sec → BDIODE1 ac inputs → dc outputs → Cout/R1
        nets = [
            {"name": "net_vdc_pos", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_hb_mid", "pins": ["Cr.positive", "SW1.source", "SW2.drain"]},
            {"name": "net_cr_lr", "pins": ["Cr.negative", "Lr.pin1"]},
            {"name": "net_resonant_node", "pins": ["Lr.pin2", "Lm.pin1", "T1.primary1"]},
            {"name": "net_tf_sec1_bd_ac_pos", "pins": ["T1.secondary1", "BD1.ac_pos"]},
            {"name": "net_tf_sec2_bd_ac_neg", "pins": ["T1.secondary2", "BD1.ac_neg"]},
            {"name": "net_rect_out", "pins": ["BD1.dc_pos", "Cout.positive", "R1.pin1"]},
            # GND: two Ground symbols to avoid long wires crossing gate area
            {"name": "net_gnd_pri", "pins": ["V1.negative", "GND1.pin1", "SW2.source"]},
            {"name": "net_gnd_sec", "pins": [
                "Lm.pin2", "T1.primary2", "GND2.pin1",
                "BD1.dc_neg", "Cout.negative", "R1.pin2",
            ]},
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
