"""Three-level Neutral-Point-Clamped (NPC) inverter topology generator.

Single-phase three-level NPC inverter using four IGBTs and two clamping
diodes connected to the DC-bus midpoint. Produces three output voltage
levels: +Vdc/2, 0, and -Vdc/2. Used in medium-voltage high-power
applications for reduced harmonic distortion.
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import (
    make_diode_v,
    make_gating,
    make_ground,
    make_inductor,
    make_resistor,
    make_vdc,
    make_igbt_v,
    _build_component,
)


class ThreeLevelNPCGenerator(TopologyGenerator):
    """Generate a three-level NPC inverter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "three_level_npc"

    @property
    def required_fields(self) -> list[str]:
        return ["vdc_total"]

    @property
    def optional_fields(self) -> list[str]:
        return ["fsw", "load_resistance", "filter_inductance", "modulation_index"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vdc_total: float = float(requirements["vdc_total"])
        vdc_half = vdc_total / 2.0
        fsw: float = float(requirements.get("fsw", 10_000))
        m: float = float(requirements.get("modulation_index", 0.8))
        m = max(0.1, min(m, 1.0))

        # Output voltage: Vout_rms = m * Vdc/2 / sqrt(2) for sinusoidal modulation
        vout_rms = m * vdc_half / math.sqrt(2)

        # Load
        r_load = float(requirements.get("load_resistance", 10.0))
        r_load = max(r_load, 0.1)
        iout = vout_rms / r_load

        # Filter inductor: suppress switching harmonics
        if requirements.get("filter_inductance"):
            lf = float(requirements["filter_inductance"])
        else:
            # L = Vdc / (8 * fsw * delta_I), target 30% ripple
            delta_i = 0.3 * iout if iout > 0 else 1.0
            lf = vdc_half / (8 * fsw * delta_i) if (fsw and delta_i) else 2e-3
            lf = max(lf, 1e-9)

        # NPC switching states (simplified level-shifted PWM):
        # SW1+SW2 ON => output = +Vdc/2
        # SW2+SW3 ON => output = 0 (clamped to midpoint)
        # SW3+SW4 ON => output = -Vdc/2
        # Complementary pairs: SW1/SW3 and SW2/SW4
        # SW1: "0,90" (positive half), SW2: "0,180" (upper)
        # SW3: "180,360" (lower complement of SW2), SW4: "90,270" (complement of SW1)

        # Layout:
        # Two series VDC sources for split DC bus:
        #   V1(80,80)-(80,130) = +Vdc/2 (top)
        #   V2(80,150)-(80,200) = +Vdc/2 (bottom)
        #   Midpoint at y=150 (V1.negative = V2.positive)
        #   GND at (80,250) connected to V2.negative
        #
        # 4 IGBTs stacked vertically at x=250:
        #   SW1: collector(250,60) emitter(250,110) gate(230,90)
        #   SW2: collector(250,110) emitter(250,160) gate(230,140)
        #   SW3: collector(250,180) emitter(250,230) gate(230,210)
        #   SW4: collector(250,230) emitter(250,280) gate(230,260)
        #
        # Clamp diodes at x=350:
        #   D1: anode(350,150) cathode(350,100) — connects midpoint to SW1/SW2 junction
        #   D2: anode(350,230) cathode(350,180) — connects SW3/SW4 junction to midpoint
        #   (using make_diode_v: anode at y, cathode at y-50)
        #
        # Output from SW2/SW3 junction (y=170):
        #   L1(400,170)-(450,170), R1(480,170)-(480,220)
        #   R1 bottom returns to midpoint

        components = [
            make_vdc("V1", 80, 80, vdc_half),
            make_vdc("V2", 80, 150, vdc_half),
            make_ground("GND1", 80, 250),
            # 4-IGBT stack
            make_igbt_v("SW1", 250, 60, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("SW2", 250, 110, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("SW3", 250, 180, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("SW4", 250, 230, switching_frequency=fsw, on_resistance=0.02),
            # Gating signals (level-shifted PWM, complementary pairs)
            make_gating("G1", 210, 90, fsw, "0,90"),
            make_gating("G2", 210, 140, fsw, "0,180"),
            make_gating("G3", 210, 210, fsw, "180,360"),
            make_gating("G4", 210, 260, fsw, "90,270"),
            # Clamp diodes (cathode UP toward midpoint)
            make_diode_v("D1", 350, 160, forward_voltage=1.5),
            make_diode_v("D2", 350, 230, forward_voltage=1.5),
            # Output filter
            make_inductor("L1", 400, 170, lf, current_flag=1),
            make_resistor("R1", 480, 170, r_load, voltage_flag=1),
        ]

        nets = [
            # DC bus top
            {"name": "net_vdc_top", "pins": ["V1.positive", "SW1.collector"]},
            # DC bus midpoint
            {"name": "net_midpoint", "pins": [
                "V1.negative", "V2.positive", "D1.anode", "D2.cathode",
            ]},
            # DC bus bottom
            {"name": "net_vdc_bot", "pins": ["V2.negative", "GND1.pin1", "SW4.emitter"]},
            # IGBT stack connections
            {"name": "net_sw1_sw2", "pins": ["SW1.emitter", "SW2.collector", "D1.cathode"]},
            {"name": "net_sw2_sw3", "pins": ["SW2.emitter", "SW3.collector", "L1.pin1"]},
            {"name": "net_sw3_sw4", "pins": ["SW3.emitter", "SW4.collector", "D2.anode"]},
            # Gate nets
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_gate3", "pins": ["G3.output", "SW3.gate"]},
            {"name": "net_gate4", "pins": ["G4.output", "SW4.gate"]},
            # Output
            {"name": "net_lf_out", "pins": ["L1.pin2", "R1.pin1"]},
            {"name": "net_load_return", "pins": [
                "R1.pin2", "V1.negative",
            ]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Three-Level NPC Inverter",
                "description": (
                    f"3-level NPC inverter: Vdc={vdc_total}V (2x{vdc_half}V), "
                    f"fsw={fsw/1e3:.1f}kHz, m={m:.2f}, Vout_rms={vout_rms:.1f}V"
                ),
                "design": {
                    "vdc_half": round(vdc_half, 4),
                    "modulation_index": round(m, 4),
                    "vout_rms": round(vout_rms, 4),
                    "filter_inductance": round(lf, 9),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(100 / fsw, 6),
            },
        }
