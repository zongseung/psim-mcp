"""Boost PFC (Power Factor Correction) topology generator.

Single-stage boost PFC front-end that shapes the input current to
follow the AC line voltage, achieving near-unity power factor.

Full AC model: VAC -> BDIODE1 (diode bridge) -> Boost stage.
Layout verified against PSIM reference:
  converted_3-ph_PWM_rectifier_with_PFC.py (diode bridge pattern)
  converted_ResonantLLC (BDIODE1 usage)

Layout structure:
  VAC -> BDIODE1 (diode bridge) -> L_boost -> SW -> D_boost -> Cout -> R
                                                     |
                                                    GND
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_diode_bridge,
    make_diode_h,
    make_gating,
    make_ground,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_vac,
)


class BoostPFCGenerator(TopologyGenerator):
    """Generate a boost PFC circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "boost_pfc"

    @property
    def required_fields(self) -> list[str]:
        return ["vin"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vout_target", "power", "fsw", "ripple_ratio"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin_rms: float = float(requirements["vin"])  # AC RMS input
        fsw: float = float(requirements.get("fsw", 65_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.02))
        efficiency: float = 0.95
        f_line: float = float(requirements.get("frequency", 60.0))

        vin_peak = vin_rms * math.sqrt(2)

        # Output DC voltage: default ~400V for 220VAC, or Vpeak*1.1 otherwise
        if requirements.get("vout_target"):
            vout = float(requirements["vout_target"])
        else:
            vout = max(vin_peak * 1.1, 380.0)

        # Output power
        if requirements.get("power"):
            pout = float(requirements["power"])
        elif requirements.get("iout"):
            iout_val = float(requirements["iout"])
            pout = vout * iout_val
        else:
            pout = 200.0  # default 200W

        iout = pout / vout if vout else 1.0
        r_load = vout / iout if iout else 10.0
        r_load = max(r_load, 0.1)

        # Input power accounting for efficiency
        pin = pout / efficiency

        # Peak input current
        iin_peak = pin * math.sqrt(2) / vin_rms if vin_rms else 1.0

        # Maximum duty cycle at peak of line (worst case for inductor)
        d_max = 1 - vin_peak / vout if vout > vin_peak else 0.1
        d_max = max(0.05, min(d_max, 0.95))

        # Boost inductor: L = Vin_peak * D_max / (fsw * ripple_ratio * Iin_peak)
        delta_i = ripple_ratio * iin_peak
        inductance = vin_peak * d_max / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitor: Cout = Pout / (2 * pi * f_line * Vout * vripple)
        # Sized to handle 2*f_line ripple (100Hz or 120Hz)
        vripple = vripple_ratio * vout
        cout = pout / (2 * math.pi * f_line * vout * vripple) if (f_line and vout and vripple) else 470e-6
        cout = max(cout, 1e-12)

        # Full AC model: VAC + diode bridge rectifier + boost stage
        #
        # Layout:
        # VAC(80,100)-(80,150), GND at (80,150)
        # BDIODE1: ac+(120,100), ac-(120,160), dc+(200,100), dc-(200,160)
        # L1(220,100)-(270,100)
        # MOSFET_v: drain(300,100) source(300,150) gate(280,130) DIR=0
        # GATING(280,170)
        # D1: anode(320,100) cathode(370,100) DIR=0 — horizontal
        # Cout(400,100)-(400,150)
        # R1(450,100)-(450,150) with VoltageFlag
        # GND bus at y=160 (bridge) and y=150 (boost stage)
        components = [
            make_vac("V1", 80, 100, round(vin_rms, 4), frequency=f_line),
            make_ground("GND1", 80, 150),
            make_diode_bridge("BR1", 120, 100),
            make_inductor("L1", 220, 100, inductance),
            make_mosfet_v("SW1", 300, 100, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 280, 170, fsw, f"0,{int(d_max * 360)}"),
            make_diode_h("D1", 320, 100, forward_voltage=0.7),
            make_capacitor("Cout", 400, 100, cout),
            make_resistor("R1", 450, 100, r_load, voltage_flag=1),
        ]

        nets = [
            # AC source to bridge AC inputs
            {"name": "net_vac_pos", "pins": ["V1.positive", "BR1.ac_pos"]},
            {"name": "net_vac_neg", "pins": ["V1.negative", "GND1.pin1", "BR1.ac_neg"]},
            # Bridge DC output to boost stage
            {"name": "net_br_pos", "pins": ["BR1.dc_pos", "L1.pin1"]},
            {"name": "net_l_sw_d", "pins": ["L1.pin2", "SW1.drain", "D1.anode"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_d_out", "pins": ["D1.cathode", "Cout.positive", "R1.pin1"]},
            # GND bus: bridge DC-, MOSFET source, Cout-, R1.pin2
            {"name": "net_gnd", "pins": [
                "BR1.dc_neg", "SW1.source", "Cout.negative", "R1.pin2",
            ]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Boost PFC",
                "description": (
                    f"Boost PFC: {vin_rms}V AC -> {vout:.0f}V DC, "
                    f"P={pout:.0f}W, fsw={fsw/1e3:.1f}kHz, D_max={d_max:.3f}"
                ),
                "design": {
                    "d_max": round(d_max, 6),
                    "vin_peak": round(vin_peak, 4),
                    "iin_peak": round(iin_peak, 4),
                    "inductance": round(inductance, 9),
                    "capacitance": round(cout, 9),
                    "r_load": round(r_load, 4),
                    "power": round(pout, 2),
                    "frequency": f_line,
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                # Need enough time to see line-frequency behavior
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(3 / f_line, 6),  # 3 line cycles
            },
        }
