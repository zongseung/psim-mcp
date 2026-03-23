"""BLDC motor drive (6-step commutation) topology generator.

Three-phase inverter bridge driving a BLDC motor with basic
120-degree conduction 6-step commutation pattern.

Power stage only — fixed commutation sequence, no hall-sensor feedback.

Layout structure:
  VDC → 6 MOSFETs (3-phase bridge) → BLDC motor
"""

from __future__ import annotations


from .base import TopologyGenerator
from .layout import (
    make_bldc_motor,
    make_gating,
    make_ground,
    make_mosfet_v,
    make_vdc,
)


class BLDCDriveGenerator(TopologyGenerator):
    """Generate a BLDC 6-step drive circuit."""

    @property
    def topology_name(self) -> str:
        return "bldc_drive"

    @property
    def required_fields(self) -> list[str]:
        return ["vdc"]

    @property
    def optional_fields(self) -> list[str]:
        return ["motor_power", "speed", "fsw"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vdc: float = float(requirements["vdc"])
        motor_power: float = float(requirements.get("motor_power", 500.0))
        speed_rpm: float = float(requirements.get("speed", 3000.0))
        fsw: float = float(requirements.get("fsw", 20_000))

        # Electrical frequency for a typical 8-pole BLDC
        poles = 8
        f_elec = poles * speed_rpm / (2 * 60)  # Hz
        f_elec = max(f_elec, 1.0)

        # 6-step commutation: each switch conducts 120 degrees (1/3 of cycle)
        # Phase A high: 0-120, Phase B high: 120-240, Phase C high: 240-360
        # Phase A low: 180-300, Phase B low: 300-60(=300,420), Phase C low: 60-180
        #
        # For PSIM GATING blocks using electrical frequency:
        # High-side switches
        # SW_AH: ON from 0 to 120 deg
        # SW_BH: ON from 120 to 240 deg
        # SW_CH: ON from 240 to 360 deg
        # Low-side switches
        # SW_AL: ON from 180 to 300 deg
        # SW_BL: ON from 300 to 420(=60 next) deg
        # SW_CL: ON from 60 to 180 deg

        # Layout:
        # VDC(80,80)-(80,130), GND(80,290)
        #
        # 3-phase bridge:
        #   Phase A leg x=200: SW_AH(200,80-130), SW_AL(200,160-210)
        #   Phase B leg x=350: SW_BH(350,80-130), SW_BL(350,160-210)
        #   Phase C leg x=500: SW_CH(500,80-130), SW_CL(500,160-210)
        #
        # GATINGs (to the left of each MOSFET gate):
        #   G_AH(160,110), G_AL(160,190)
        #   G_BH(310,110), G_BL(310,190)
        #   G_CH(460,110), G_CL(460,190)
        #
        # BLDC Motor at x=620: phase_a(620,130), phase_b(620,180), phase_c(620,230)
        components = [
            make_vdc("V1", 80, 80, vdc),
            make_ground("GND1", 80, 290),
            # Phase A leg
            make_mosfet_v("SW_AH", 200, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW_AL", 200, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G_AH", 160, 110, f_elec, "0,120"),
            make_gating("G_AL", 160, 190, f_elec, "180,300"),
            # Phase B leg
            make_mosfet_v("SW_BH", 350, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW_BL", 350, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G_BH", 310, 110, f_elec, "120,240"),
            make_gating("G_BL", 310, 190, f_elec, "300,420"),
            # Phase C leg
            make_mosfet_v("SW_CH", 500, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW_CL", 500, 160, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G_CH", 460, 110, f_elec, "240,360"),
            make_gating("G_CL", 460, 190, f_elec, "60,180"),
            # Motor
            make_bldc_motor("M1", 620, 130,
                            poles=poles, Rs=0.1, Ls=1e-3, Ke=0.01, J=0.005),
        ]

        nets = [
            # DC bus
            {"name": "net_vdc_pos", "pins": [
                "V1.positive", "SW_AH.drain", "SW_BH.drain", "SW_CH.drain",
            ]},
            {"name": "net_gnd", "pins": [
                "V1.negative", "GND1.pin1",
                "SW_AL.source", "SW_BL.source", "SW_CL.source",
            ]},
            # Phase midpoints → motor
            {"name": "net_phase_a", "pins": [
                "SW_AH.source", "SW_AL.drain", "M1.phase_a",
            ]},
            {"name": "net_phase_b", "pins": [
                "SW_BH.source", "SW_BL.drain", "M1.phase_b",
            ]},
            {"name": "net_phase_c", "pins": [
                "SW_CH.source", "SW_CL.drain", "M1.phase_c",
            ]},
            # Gate signals
            {"name": "net_g_ah", "pins": ["G_AH.output", "SW_AH.gate"]},
            {"name": "net_g_al", "pins": ["G_AL.output", "SW_AL.gate"]},
            {"name": "net_g_bh", "pins": ["G_BH.output", "SW_BH.gate"]},
            {"name": "net_g_bl", "pins": ["G_BL.output", "SW_BL.gate"]},
            {"name": "net_g_ch", "pins": ["G_CH.output", "SW_CH.gate"]},
            {"name": "net_g_cl", "pins": ["G_CL.output", "SW_CL.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "BLDC Motor Drive (6-Step)",
                "description": (
                    f"BLDC 6-step drive: Vdc={vdc}V, P={motor_power}W, "
                    f"speed={speed_rpm}rpm, f_elec={f_elec:.1f}Hz"
                ),
                "design": {
                    "vdc": round(vdc, 2),
                    "motor_power": round(motor_power, 2),
                    "speed_rpm": round(speed_rpm, 1),
                    "poles": poles,
                    "f_electrical": round(f_elec, 2),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(10 / f_elec, 6),  # 10 electrical cycles
            },
        }
