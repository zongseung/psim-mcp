"""Induction motor V/f drive topology generator.

Three-phase two-level inverter (6 IGBTs) driving an induction motor
with V/f (volts-per-hertz) open-loop control. The DC bus feeds three
half-bridge legs, each providing one phase to the motor windings.
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import (
    make_gating,
    make_ground,
    make_igbt_v,
    make_induction_motor,
    make_vdc,
)


class InductionMotorVfGenerator(TopologyGenerator):
    """Generate a V/f induction motor drive circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "induction_motor_vf"

    @property
    def required_fields(self) -> list[str]:
        return ["vdc"]

    @property
    def optional_fields(self) -> list[str]:
        return [
            "motor_power", "load_torque", "fsw", "f_motor", "poles",
            "Rs", "Rr", "Ls", "Lr", "Lm", "J",
        ]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vdc: float = float(requirements["vdc"])
        fsw: float = float(requirements.get("fsw", 5_000))
        f_motor: float = float(requirements.get("f_motor", 60.0))
        poles: int = int(requirements.get("poles", 4))

        # Motor parameters (defaults for a typical ~5kW induction motor)
        rs: float = float(requirements.get("Rs", 0.5))
        rr: float = float(requirements.get("Rr", 0.4))
        ls: float = float(requirements.get("Ls", 0.08))
        lr: float = float(requirements.get("Lr", 0.08))
        lm: float = float(requirements.get("Lm", 0.075))
        j_inertia: float = float(requirements.get("J", 0.1))

        # V/f control: Vout proportional to frequency
        # Vout_line_rms = Vdc * m / sqrt(2), where m = modulation index
        # At rated frequency, m ~ 0.9
        m = 0.9
        vout_line_rms = vdc * m / math.sqrt(2)
        vout_phase_rms = vout_line_rms / math.sqrt(3)

        # Synchronous speed
        ns = 120 * f_motor / poles  # RPM

        # Motor power estimate if not given
        motor_power = float(requirements.get("motor_power", vout_phase_rms * 10))

        # Layout:
        # VDC(80,80)-(80,130), GND at (80,280)
        #
        # 3-phase bridge using 6 IGBTs:
        #   Phase A at x=200: SW1(high) + SW2(low)
        #   Phase B at x=350: SW3(high) + SW4(low)
        #   Phase C at x=500: SW5(high) + SW6(low)
        #
        # Each IGBT vertical (DIR=0):
        #   High-side: collector(x,80) emitter(x,130) gate(x-20,110)
        #   Low-side:  collector(x,160) emitter(x,210) gate(x-20,190)
        #
        # 6 gating blocks (one per IGBT):
        #   Phase A: G1(x-40,110), G2(x-40,190)  120deg apart from B,C
        #   Phase B: G3 shifted 120deg, Phase C: G5 shifted 240deg
        #
        # Induction motor M1 at x=650:
        #   phase_a(650,100), phase_b(650,150), phase_c(650,200)

        # 3-phase PWM gating with 120-degree phase offsets
        # Each leg has complementary switching (high ON = "0,180", low = "180,360")
        # Phase shifts: A=0deg, B=120deg, C=240deg
        # Simplified: using phase-shifted square wave for basic V/f
        g1_points = "0,180"
        g2_points = "180,360"
        g3_points = "120,300"
        g4_points = "300,120"  # complement wraps: 300->360 + 0->120
        g5_points = "240,60"   # 240->360 + 0->60
        g6_points = "60,240"

        components = [
            make_vdc("V1", 80, 80, vdc),
            make_ground("GND1", 80, 280),
            # Phase A leg
            make_igbt_v("SW1", 200, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("SW2", 200, 160, switching_frequency=fsw, on_resistance=0.02),
            # Phase B leg
            make_igbt_v("SW3", 350, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("SW4", 350, 160, switching_frequency=fsw, on_resistance=0.02),
            # Phase C leg
            make_igbt_v("SW5", 500, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("SW6", 500, 160, switching_frequency=fsw, on_resistance=0.02),
            # Gating signals
            make_gating("G1", 160, 110, fsw, g1_points),
            make_gating("G2", 160, 190, fsw, g2_points),
            make_gating("G3", 310, 110, fsw, g3_points),
            make_gating("G4", 310, 190, fsw, g4_points),
            make_gating("G5", 460, 110, fsw, g5_points),
            make_gating("G6", 460, 190, fsw, g6_points),
            # Induction motor
            make_induction_motor(
                "M1", 650, 100,
                poles=poles, Rs=rs, Rr=rr, Ls=ls, Lr=lr, Lm=lm, J=j_inertia,
            ),
        ]

        nets = [
            # DC bus
            {"name": "net_vdc_pos", "pins": [
                "V1.positive", "SW1.collector", "SW3.collector", "SW5.collector",
            ]},
            {"name": "net_gnd", "pins": [
                "V1.negative", "GND1.pin1",
                "SW2.emitter", "SW4.emitter", "SW6.emitter",
            ]},
            # Phase midpoints to motor
            {"name": "net_phase_a", "pins": ["SW1.emitter", "SW2.collector", "M1.phase_a"]},
            {"name": "net_phase_b", "pins": ["SW3.emitter", "SW4.collector", "M1.phase_b"]},
            {"name": "net_phase_c", "pins": ["SW5.emitter", "SW6.collector", "M1.phase_c"]},
            # Gate nets
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_gate3", "pins": ["G3.output", "SW3.gate"]},
            {"name": "net_gate4", "pins": ["G4.output", "SW4.gate"]},
            {"name": "net_gate5", "pins": ["G5.output", "SW5.gate"]},
            {"name": "net_gate6", "pins": ["G6.output", "SW6.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Induction Motor V/f Drive",
                "description": (
                    f"V/f induction motor drive: Vdc={vdc}V, "
                    f"fsw={fsw/1e3:.1f}kHz, f_motor={f_motor}Hz, "
                    f"poles={poles}, ns={ns:.0f}RPM"
                ),
                "design": {
                    "vdc": round(vdc, 4),
                    "vout_line_rms": round(vout_line_rms, 4),
                    "vout_phase_rms": round(vout_phase_rms, 4),
                    "modulation_index": round(m, 4),
                    "motor_frequency": round(f_motor, 4),
                    "synchronous_speed_rpm": round(ns, 2),
                    "motor_power_est": round(motor_power, 2),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(5 / f_motor, 6),
            },
        }
