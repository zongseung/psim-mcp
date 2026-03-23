"""EV On-Board Charger (OBC) topology generator (simplified).

Two cascaded stages:
1. PFC boost front-end: VAC → DiodeBridge → boost converter → DC link
2. Buck charger: DC link → buck converter → battery (modeled as R load)

Power stage only — fixed duty cycles, no closed-loop control.

Layout structure:
  VAC → BDIODE1 → L_pfc → SW_pfc → D_pfc → C_dc → SW_buck → D_buck → L_buck → C_out → R_load
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
    make_mosfet_h,
    make_mosfet_v,
    make_resistor,
    make_vac,
)


class EVOBCGenerator(TopologyGenerator):
    """Generate an EV on-board charger circuit (PFC + buck)."""

    @property
    def topology_name(self) -> str:
        return "ev_obc"

    @property
    def required_fields(self) -> list[str]:
        return ["vac_rms", "vbat"]

    @property
    def optional_fields(self) -> list[str]:
        return ["charge_current", "fsw", "power"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vac_rms: float = float(requirements["vac_rms"])
        vbat: float = float(requirements["vbat"])
        i_charge: float = float(requirements.get("charge_current", 10.0))
        fsw: float = float(requirements.get("fsw", 65_000))
        f_line: float = float(requirements.get("frequency", 60.0))

        vin_peak = vac_rms * math.sqrt(2)

        # DC link voltage: above peak input, below isolation stage max
        vdc_link = max(vin_peak * 1.1, 400.0)

        # Power
        if requirements.get("power"):
            pout = float(requirements["power"])
        else:
            pout = vbat * i_charge

        # ---------------------------------------------------------------
        # Stage 1: PFC Boost
        # ---------------------------------------------------------------
        efficiency_pfc = 0.95
        pin_pfc = pout / efficiency_pfc
        iin_peak = pin_pfc * math.sqrt(2) / vac_rms if vac_rms else 1.0

        d_pfc = 1 - vin_peak / vdc_link if vdc_link > vin_peak else 0.1
        d_pfc = max(0.05, min(d_pfc, 0.95))

        ripple_ratio_pfc = 0.3
        delta_i_pfc = ripple_ratio_pfc * iin_peak
        l_pfc = vin_peak * d_pfc / (fsw * delta_i_pfc) if (fsw and delta_i_pfc) else 1e-3
        l_pfc = max(l_pfc, 1e-9)

        # DC link capacitor
        vripple_dc = 0.02 * vdc_link
        c_dc = pout / (2 * f_line * vdc_link * vripple_dc) if (f_line and vdc_link and vripple_dc) else 470e-6
        c_dc = max(c_dc, 1e-12)

        # ---------------------------------------------------------------
        # Stage 2: Buck charger
        # ---------------------------------------------------------------
        d_buck = vbat / vdc_link if vdc_link else 0.5
        d_buck = max(0.05, min(d_buck, 0.95))

        ripple_ratio_buck = 0.2
        delta_i_buck = ripple_ratio_buck * i_charge
        l_buck = vbat * (1 - d_buck) / (fsw * delta_i_buck) if (fsw and delta_i_buck) else 1e-3
        l_buck = max(l_buck, 1e-9)

        # Output capacitor
        vripple_out = 0.01 * vbat
        c_out = delta_i_buck / (8 * fsw * vripple_out) if (fsw and vripple_out) else 100e-6
        c_out = max(c_out, 1e-12)

        # Battery modeled as resistor
        r_bat = vbat / i_charge if i_charge else 10.0
        r_bat = max(r_bat, 0.1)

        # Layout:
        # VAC(80,100)-(80,150), GND(80,150)
        # BDIODE1: ac+(120,100) ac-(120,160) dc+(200,100) dc-(200,160)
        # L_pfc(220,100)-(270,100) horizontal
        # SW_pfc(300,100) vertical: drain(300,100) source(300,150) gate(280,130)
        # G_pfc(280,170)
        # D_pfc(320,100)-(370,100) horizontal diode
        # C_dc(400,100)-(400,150) — shared DC link
        #
        # Stage 2 starts at C_dc output:
        # SW_buck(450,100) horizontal: drain(450,100) source(500,100) gate(480,120)
        # G_buck(480,170)
        # D_buck(520,150) vertical: anode(520,150) cathode(520,100) -- freewheeling
        # L_buck(550,100)-(600,100) horizontal
        # C_out(630,100)-(630,150)
        # R_bat(680,100)-(680,150)
        # GND bus at y=160 (bridge) and y=150 (rest)
        components = [
            make_vac("V1", 80, 100, round(vac_rms, 4), frequency=f_line),
            make_ground("GND1", 80, 150),
            make_diode_bridge("BR1", 120, 100),
            # PFC boost stage
            make_inductor("L_pfc", 220, 100, l_pfc, current_flag=1),
            make_mosfet_v("SW_pfc", 300, 100, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G_pfc", 280, 170, fsw, f"0,{int(d_pfc * 360)}"),
            make_diode_h("D_pfc", 320, 100, forward_voltage=0.7),
            # DC link capacitor
            make_capacitor("C_dc", 400, 100, c_dc),
            # Buck charger stage
            make_mosfet_h("SW_buck", 450, 100, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G_buck", 480, 170, fsw, f"0,{int(d_buck * 360)}"),
            make_diode_h("D_buck", 500, 150, forward_voltage=0.7),
            make_inductor("L_buck", 550, 100, l_buck, current_flag=1),
            make_capacitor("C_out", 630, 100, c_out),
            make_resistor("R_bat", 680, 100, r_bat, voltage_flag=1),
        ]

        nets = [
            # AC source to bridge
            {"name": "net_vac_pos", "pins": ["V1.positive", "BR1.ac_pos"]},
            {"name": "net_vac_neg", "pins": ["V1.negative", "GND1.pin1", "BR1.ac_neg"]},
            # Bridge DC+ to PFC boost
            {"name": "net_br_pos", "pins": ["BR1.dc_pos", "L_pfc.pin1"]},
            {"name": "net_pfc_node", "pins": ["L_pfc.pin2", "SW_pfc.drain", "D_pfc.anode"]},
            {"name": "net_g_pfc", "pins": ["G_pfc.output", "SW_pfc.gate"]},
            # PFC output to DC link
            {"name": "net_dc_link", "pins": [
                "D_pfc.cathode", "C_dc.positive", "SW_buck.drain",
            ]},
            # Buck stage
            {"name": "net_buck_sw_out", "pins": [
                "SW_buck.source", "D_buck.cathode", "L_buck.pin1",
            ]},
            {"name": "net_g_buck", "pins": ["G_buck.output", "SW_buck.gate"]},
            {"name": "net_buck_out", "pins": [
                "L_buck.pin2", "C_out.positive", "R_bat.pin1",
            ]},
            # GND bus: bridge DC-, PFC SW source, D_buck anode, C_dc-, C_out-, R_bat
            {"name": "net_gnd", "pins": [
                "BR1.dc_neg", "SW_pfc.source", "D_buck.anode",
                "C_dc.negative", "C_out.negative", "R_bat.pin2",
            ]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "EV On-Board Charger (PFC + Buck)",
                "description": (
                    f"EV OBC: {vac_rms}V AC -> {vbat}V @ {i_charge}A, "
                    f"Vdc_link={vdc_link:.0f}V, fsw={fsw/1e3:.1f}kHz"
                ),
                "design": {
                    "vdc_link": round(vdc_link, 2),
                    "d_pfc": round(d_pfc, 6),
                    "l_pfc": round(l_pfc, 9),
                    "c_dc": round(c_dc, 9),
                    "d_buck": round(d_buck, 6),
                    "l_buck": round(l_buck, 9),
                    "c_out": round(c_out, 9),
                    "r_bat": round(r_bat, 4),
                    "power": round(pout, 2),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(3 / f_line, 6),  # 3 line cycles
            },
        }
