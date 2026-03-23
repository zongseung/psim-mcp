"""PMSM drive topology generator (simplified — power stage + sinusoidal PWM).

Three-phase IGBT inverter bridge driving a PMSM motor with basic
sinusoidal 3-phase PWM (120-degree phase-shifted gating).

Power stage only — no FOC control loop, no current sensors, no PI controllers.
This provides basic motor rotation without vector control.

Layout structure:
  VDC → 6 IGBTs (3-phase bridge) → PMSM motor
"""

from __future__ import annotations


from .base import TopologyGenerator
from .layout import (
    make_gating,
    make_ground,
    make_igbt_v,
    make_pmsm,
    make_vdc,
)


class PMSMFOCDriveGenerator(TopologyGenerator):
    """Generate a PMSM drive circuit with basic 3-phase PWM."""

    @property
    def topology_name(self) -> str:
        return "pmsm_foc_drive"

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
        motor_power: float = float(requirements.get("motor_power", 1000.0))
        speed_rpm: float = float(requirements.get("speed", 3000.0))
        fsw: float = float(requirements.get("fsw", 10_000))

        # Electrical frequency for a typical 8-pole PMSM
        poles = 8
        f_elec = poles * speed_rpm / (2 * 60)  # Hz
        f_elec = max(f_elec, 1.0)

        # Sinusoidal PWM: 3 phases shifted 120 degrees apart
        # For simple open-loop control, each high/low IGBT pair switches
        # complementarily.  We use 50% duty gating at fsw with phase offsets
        # encoded as switching points in electrical degrees.
        #
        # Phase A: 0-180, Phase B: 120-300, Phase C: 240-360+0-100 => 240,420(=60)
        # This gives simple 6-step like behavior at the electrical frequency.

        # Layout:
        # VDC(80,80)-(80,130), GND(80,290)
        #
        # 3-phase IGBT bridge:
        #   Phase A leg x=200: Q_AH(200,80-130), Q_AL(200,160-210)
        #   Phase B leg x=350: Q_BH(350,80-130), Q_BL(350,160-210)
        #   Phase C leg x=500: Q_CH(500,80-130), Q_CL(500,160-210)
        #
        # GATINGs: same pattern as BLDC but at electrical frequency
        #
        # PMSM at x=620: phase_a(620,130), phase_b(620,180), phase_c(620,230)
        components = [
            make_vdc("V1", 80, 80, vdc),
            make_ground("GND1", 80, 290),
            # Phase A leg
            make_igbt_v("Q_AH", 200, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("Q_AL", 200, 160, switching_frequency=fsw, on_resistance=0.02),
            make_gating("G_AH", 160, 110, f_elec, "0,180"),
            make_gating("G_AL", 160, 190, f_elec, "180,360"),
            # Phase B leg
            make_igbt_v("Q_BH", 350, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("Q_BL", 350, 160, switching_frequency=fsw, on_resistance=0.02),
            make_gating("G_BH", 310, 110, f_elec, "120,300"),
            make_gating("G_BL", 310, 190, f_elec, "300,480"),
            # Phase C leg
            make_igbt_v("Q_CH", 500, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("Q_CL", 500, 160, switching_frequency=fsw, on_resistance=0.02),
            make_gating("G_CH", 460, 110, f_elec, "240,420"),
            make_gating("G_CL", 460, 190, f_elec, "60,240"),
            # Motor
            make_pmsm("M1", 620, 130,
                       poles=poles, Rs=0.1, Ld=1e-3, Lq=1e-3, flux=0.05, J=0.01),
        ]

        nets = [
            # DC bus
            {"name": "net_vdc_pos", "pins": [
                "V1.positive", "Q_AH.collector", "Q_BH.collector", "Q_CH.collector",
            ]},
            {"name": "net_gnd", "pins": [
                "V1.negative", "GND1.pin1",
                "Q_AL.emitter", "Q_BL.emitter", "Q_CL.emitter",
            ]},
            # Phase midpoints → motor
            {"name": "net_phase_a", "pins": [
                "Q_AH.emitter", "Q_AL.collector", "M1.phase_a",
            ]},
            {"name": "net_phase_b", "pins": [
                "Q_BH.emitter", "Q_BL.collector", "M1.phase_b",
            ]},
            {"name": "net_phase_c", "pins": [
                "Q_CH.emitter", "Q_CL.collector", "M1.phase_c",
            ]},
            # Gate signals
            {"name": "net_g_ah", "pins": ["G_AH.output", "Q_AH.gate"]},
            {"name": "net_g_al", "pins": ["G_AL.output", "Q_AL.gate"]},
            {"name": "net_g_bh", "pins": ["G_BH.output", "Q_BH.gate"]},
            {"name": "net_g_bl", "pins": ["G_BL.output", "Q_BL.gate"]},
            {"name": "net_g_ch", "pins": ["G_CH.output", "Q_CH.gate"]},
            {"name": "net_g_cl", "pins": ["G_CL.output", "Q_CL.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "PMSM Drive (Simplified)",
                "description": (
                    f"PMSM drive: Vdc={vdc}V, P={motor_power}W, "
                    f"speed={speed_rpm}rpm, fsw={fsw/1e3:.1f}kHz"
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
