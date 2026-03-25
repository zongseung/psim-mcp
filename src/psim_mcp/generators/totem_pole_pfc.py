"""Totem-Pole Bridgeless PFC topology generator.

Totem-pole PFC uses two MOSFET pairs instead of a diode bridge:
- High-frequency (HF) pair: fast-switching MOSFETs at fsw (~65 kHz)
- Low-frequency (LF) pair: line-frequency MOSFETs (~60 Hz) for polarity steering

Power stage only — fixed duty cycle, no closed-loop control.

Layout structure:
  VAC → L1 → HF MOSFET pair (totem-pole) + LF MOSFET pair → C1 → R1
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph
from .layout import (
    make_capacitor,
    make_gating,
    make_ground,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_vac,
)


class TotemPolePFCGenerator(TopologyGenerator):
    """Generate a totem-pole bridgeless PFC circuit."""

    @property
    def topology_name(self) -> str:
        return "totem_pole_pfc"

    @property
    def required_fields(self) -> list[str]:
        return ["vin"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vac_rms", "vout_target", "power", "fsw", "ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.totem_pole_pfc import synthesize_totem_pole_pfc
        return synthesize_totem_pole_pfc(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vac_rms: float = float(requirements.get("vac_rms", requirements.get("vin", 220.0)))
        fsw: float = float(requirements.get("fsw", 65_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.02))
        f_line: float = float(requirements.get("frequency", 60.0))

        vin_peak = vac_rms * math.sqrt(2)

        # Output voltage
        if requirements.get("vout_target"):
            vout = float(requirements["vout_target"])
        else:
            vout = max(vin_peak * 1.1, 400.0)

        # Power
        if requirements.get("power"):
            pout = float(requirements["power"])
        else:
            pout = 500.0  # default 500W

        iout = pout / vout if vout else 1.0
        r_load = vout / iout if iout else 10.0
        r_load = max(r_load, 0.1)

        # Peak input current
        iin_peak = pout * math.sqrt(2) / (vac_rms * 0.95) if vac_rms else 1.0

        # Max duty at peak of line
        d_max = 1 - vin_peak / vout if vout > vin_peak else 0.1
        d_max = max(0.05, min(d_max, 0.95))

        # Boost inductor: L = Vin_peak * D_max / (fsw * delta_I)
        delta_i = ripple_ratio * iin_peak
        inductance = vin_peak * d_max / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitor: C = P / (2 * f_line * Vout * delta_V)
        vripple = vripple_ratio * vout
        cout = pout / (2 * f_line * vout * vripple) if (f_line and vout and vripple) else 470e-6
        cout = max(cout, 1e-12)

        # Layout:
        # VAC(80,130)-(80,180), GND at y=250
        # L1(120,130)-(170,130) — boost inductor from VAC+
        #
        # HF leg at x=250: SW_HF1(250,80-130) high, SW_HF2(250,160-210) low
        #   G_HF1(210,110), G_HF2(210,190)  — switching at fsw
        #
        # LF leg at x=400: SW_LF1(400,80-130) high, SW_LF2(400,160-210) low
        #   G_LF1(380,110), G_LF2(380,190) — switching at line freq
        #
        # Cout(500,80)-(500,130), R1(550,80)-(550,130)
        # GND bus at y=250
        components = [
            make_vac("V1", 80, 130, round(vac_rms, 4), frequency=f_line),
            make_ground("GND1", 80, 250),
            make_inductor("L1", 120, 130, inductance, current_flag=1),
            # HF switching leg (65 kHz)
            make_mosfet_v("SW_HF1", 250, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW_HF2", 250, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G_HF1", 210, 110, fsw, f"0,{int(d_max * 360)}"),
            make_gating("G_HF2", 210, 190, fsw, f"{int(d_max * 360)},360"),
            # LF polarity-steering leg (line frequency)
            make_mosfet_v("SW_LF1", 400, 80, switching_frequency=f_line, on_resistance=0.01),
            make_mosfet_v("SW_LF2", 400, 160, switching_frequency=f_line, on_resistance=0.01),
            make_gating("G_LF1", 380, 110, f_line, "0,180"),
            make_gating("G_LF2", 380, 190, f_line, "180,360"),
            # Output
            make_capacitor("Cout", 500, 80, cout),
            make_resistor("R1", 550, 80, r_load, voltage_flag=1),
        ]

        nets = [
            # VAC positive → inductor → HF leg midpoint
            {"name": "net_vac_pos_l", "pins": ["V1.positive", "L1.pin1"]},
            {"name": "net_l_hf_mid", "pins": ["L1.pin2", "SW_HF1.source", "SW_HF2.drain"]},
            # VAC negative → LF leg midpoint
            {"name": "net_vac_neg_lf", "pins": ["V1.negative", "GND1.pin1", "SW_LF1.source", "SW_LF2.drain"]},
            # DC+ bus: HF high-side drain + LF high-side drain + Cout+ + R1 top
            {"name": "net_dc_pos", "pins": [
                "SW_HF1.drain", "SW_LF1.drain", "Cout.positive", "R1.pin1",
            ]},
            # DC- bus: HF low-side source + LF low-side source + Cout- + R1 bottom
            {"name": "net_dc_neg", "pins": [
                "SW_HF2.source", "SW_LF2.source", "Cout.negative", "R1.pin2",
            ]},
            # Gate signals
            {"name": "net_g_hf1", "pins": ["G_HF1.output", "SW_HF1.gate"]},
            {"name": "net_g_hf2", "pins": ["G_HF2.output", "SW_HF2.gate"]},
            {"name": "net_g_lf1", "pins": ["G_LF1.output", "SW_LF1.gate"]},
            {"name": "net_g_lf2", "pins": ["G_LF2.output", "SW_LF2.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Totem-Pole Bridgeless PFC",
                "description": (
                    f"Totem-pole PFC: {vac_rms}V AC -> {vout:.0f}V DC, "
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
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(3 / f_line, 6),  # 3 line cycles
            },
        }
