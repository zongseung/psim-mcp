"""Dual Active Bridge (DAB) topology generator.

Two full-bridge converters connected through a series inductor and
high-frequency transformer.  Power flow is controlled by the phase
shift angle between the two bridges.

Power stage only — open-loop fixed phase shift, no closed-loop control.

Layout structure:
  VDC1 → 4 MOSFETs (bridge 1) → Ls (series inductor) → Transformer
       → 4 MOSFETs (bridge 2) → VDC2 (load represented by R)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph
from .layout import (
    make_gating,
    make_ground,
    make_ideal_transformer,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_vdc,
)


class DABGenerator(TopologyGenerator):
    """Generate a Dual Active Bridge converter from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "dab"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["power", "fsw", "phase_shift_deg"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.dab import synthesize_dab
        return synthesize_dab(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        iout_default = float(requirements.get("iout", 1.0))
        pout: float = float(requirements.get("power", vout * iout_default))
        fsw: float = float(requirements.get("fsw", 100_000))

        # Turns ratio
        n = vout / vin if vin else 1.0
        n = max(0.1, min(n, 20.0))

        # Phase shift angle (radians).  Default: size for rated power.
        # P = Vin * Vout * phi * (pi - phi) / (2 * pi^2 * fsw * Ls)
        # Solve for phi given a default Ls guess, or pick phi first.
        phi_deg = float(requirements.get("phase_shift_deg", 30.0))
        phi_deg = max(5.0, min(phi_deg, 85.0))
        phi = math.radians(phi_deg)

        # Series inductance from power equation
        ls = vin * vout * phi * (math.pi - phi) / (2 * math.pi**2 * fsw * pout) if (fsw and pout) else 10e-6
        ls = max(ls, 1e-9)

        # Load resistance (represents secondary-side load or battery)
        r_load = vout**2 / pout if pout else 10.0
        r_load = max(r_load, 0.1)

        # Gating: Bridge1 legs: Leg_A = SW1(high)/SW3(low), Leg_B = SW2(high)/SW4(low)
        # Bridge1: SW1,SW4 on 0-180 deg; SW2,SW3 on 180-360 deg
        # Bridge2: phase-shifted by phi_deg
        # Bridge2: SW5,SW8 on phi_deg to phi_deg+180; SW6,SW7 on phi_deg+180 to phi_deg+360
        b2_on = round(phi_deg, 1)
        b2_off = round(phi_deg + 180, 1)
        b2_comp_on = round(phi_deg + 180, 1)
        b2_comp_off = round(phi_deg + 360, 1)

        # Layout:
        # VDC1(80,80)-(80,130), GND1(80,290)
        #
        # Bridge 1 (primary side):
        #   Left leg x=200: SW1(200,80-130) high, SW3(200,160-210) low
        #   Right leg x=350: SW2(350,80-130) high, SW4(350,160-210) low
        #   GATINGs: G1(160,110), G3(160,190), G2(330,110), G4(330,190)
        #   V+ bus y=80, mid-bus y=130, low-bus y=210, GND bus y=290
        #
        # Ls(420,130)-(470,130) series inductor from right-leg midpoint
        # Transformer T1: p1(500,130) p2(500,180) s1(550,130) s2(550,180)
        #
        # Bridge 2 (secondary side):
        #   Left leg x=620: SW5(620,80-130) high, SW7(620,160-210) low
        #   Right leg x=770: SW6(770,80-130) high, SW8(770,160-210) low
        #   GATINGs: G5(600,110), G7(600,190), G6(750,110), G8(750,190)
        #
        # R1(850,80)-(850,130) load, GND2(850,290)
        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 290),
            # Bridge 1 — left leg
            make_mosfet_v("SW1", 200, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW3", 200, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 160, 110, fsw, "0,180"),
            make_gating("G3", 160, 190, fsw, "180,360"),
            # Bridge 1 — right leg
            make_mosfet_v("SW2", 350, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW4", 350, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G2", 330, 110, fsw, "180,360"),
            make_gating("G4", 330, 190, fsw, "0,180"),
            # Series inductor + transformer
            make_inductor("Ls", 420, 130, ls, current_flag=1),
            make_ideal_transformer(
                "T1",
                500, 130, 500, 180,   # primary1, primary2
                550, 130, 550, 180,   # secondary1, secondary2
                np_turns=1, ns_turns=round(n, 6),
            ),
            # Bridge 2 — left leg
            make_mosfet_v("SW5", 620, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW7", 620, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G5", 600, 110, fsw, f"{b2_on},{b2_off}"),
            make_gating("G7", 600, 190, fsw, f"{b2_comp_on},{b2_comp_off}"),
            # Bridge 2 — right leg
            make_mosfet_v("SW6", 770, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW8", 770, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G6", 750, 110, fsw, f"{b2_comp_on},{b2_comp_off}"),
            make_gating("G8", 750, 190, fsw, f"{b2_on},{b2_off}"),
            # Load
            make_resistor("R1", 850, 80, r_load, voltage_flag=1),
            make_ground("GND2", 850, 290),
        ]

        nets = [
            # Primary side DC bus
            {"name": "net_vdc_pos", "pins": ["V1.positive", "SW1.drain", "SW2.drain"]},
            {"name": "net_gnd_pri", "pins": [
                "V1.negative", "GND1.pin1", "SW3.source", "SW4.source",
            ]},
            # Bridge 1 midpoints
            {"name": "net_b1_left_mid", "pins": ["SW1.source", "SW3.drain", "Ls.pin1"]},
            {"name": "net_b1_right_mid", "pins": ["SW2.source", "SW4.drain", "T1.primary2"]},
            # Series inductor to transformer primary
            {"name": "net_ls_tf", "pins": ["Ls.pin2", "T1.primary1"]},
            # Secondary side DC bus
            {"name": "net_sec_pos", "pins": ["T1.secondary1", "SW5.drain", "SW6.drain"]},
            {"name": "net_gnd_sec", "pins": [
                "T1.secondary2", "GND2.pin1", "SW7.source", "SW8.source", "R1.pin2",
            ]},
            # Bridge 2 midpoints
            {"name": "net_b2_left_mid", "pins": ["SW5.source", "SW7.drain", "R1.pin1"]},
            {"name": "net_b2_right_mid", "pins": ["SW6.source", "SW8.drain"]},
            # Gate signals — Bridge 1
            {"name": "net_g1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_g2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_g3", "pins": ["G3.output", "SW3.gate"]},
            {"name": "net_g4", "pins": ["G4.output", "SW4.gate"]},
            # Gate signals — Bridge 2
            {"name": "net_g5", "pins": ["G5.output", "SW5.gate"]},
            {"name": "net_g6", "pins": ["G6.output", "SW6.gate"]},
            {"name": "net_g7", "pins": ["G7.output", "SW7.gate"]},
            {"name": "net_g8", "pins": ["G8.output", "SW8.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Dual Active Bridge",
                "description": (
                    f"DAB converter: {vin}V -> {vout}V, P={pout}W, "
                    f"fsw={fsw/1e3:.1f}kHz, phi={phi_deg:.1f} deg"
                ),
                "design": {
                    "turns_ratio": round(n, 6),
                    "phase_shift_deg": round(phi_deg, 2),
                    "series_inductance": round(ls, 9),
                    "r_load": round(r_load, 4),
                    "power": round(pout, 2),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(50 / fsw, 6),
            },
        }
