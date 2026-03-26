"""PV Grid-Tied inverter topology generator (simplified).

DC source (representing PV array at DC-link voltage) driving a
3-phase IGBT bridge connected through an L filter to the AC grid.

Power stage only — no PLL, no MPPT, no current control loop.
Basic 3-phase sinusoidal PWM provides grid-frequency output.

Layout structure:
  VDC (PV) → C_dc → 6 IGBTs (3-phase bridge) → L_filter (per phase) → VAC (grid)
"""

from __future__ import annotations


from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_gating,
    make_ground,
    make_igbt_v,
    make_inductor,
    make_vac,
    make_vdc,
)


class PVGridTiedGenerator(TopologyGenerator):
    """Generate a simplified PV grid-tied inverter circuit."""

    @property
    def topology_name(self) -> str:
        return "pv_grid_tied"

    @property
    def required_fields(self) -> list[str]:
        return ["vdc"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vgrid_rms", "power", "fsw", "f_grid"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vdc: float = float(requirements["vdc"])
        vgrid_rms: float = float(requirements.get("vgrid_rms", 220.0))
        pout: float = float(requirements.get("power", 3000.0))
        fsw: float = float(requirements.get("fsw", 10_000))
        f_grid: float = float(requirements.get("f_grid", 60.0))

        # DC-link capacitor: C_dc = P / (2 * f_grid * Vdc * delta_V)
        vripple_ratio = 0.02
        delta_v = vripple_ratio * vdc
        c_dc = pout / (2 * f_grid * vdc * delta_v) if (f_grid and vdc and delta_v) else 1000e-6
        c_dc = max(c_dc, 1e-12)

        # Filter inductor per phase: L = Vdc / (delta_I * fsw)
        # delta_I = 20% of rated phase current
        i_phase = pout / (3 * vgrid_rms) if vgrid_rms else 1.0
        delta_i = 0.2 * i_phase
        l_filter = vdc / (delta_i * fsw) if (delta_i and fsw) else 5e-3
        l_filter = max(l_filter, 1e-9)

        # Layout:
        # VDC(80,80)-(80,130), C_dc(80,80)-(80,130) paralleled
        # GND(80,290)
        #
        # 3-phase IGBT bridge:
        #   Phase A leg x=200: Q_AH(200,80-130), Q_AL(200,160-210)
        #   Phase B leg x=350: Q_BH(350,80-130), Q_BL(350,160-210)
        #   Phase C leg x=500: Q_CH(500,80-130), Q_CL(500,160-210)
        #
        # L filters: La(250,130)-(300,130), Lb(400,130)-(450,130), Lc(550,130)-(600,130)
        # Grid VAC sources: VA(650,130), VB(650,180), VC(650,230)
        # Grid neutral GND2(700,290)
        components = [
            make_vdc("V_PV", 80, 80, vdc),
            make_ground("GND1", 80, 290),
            make_capacitor("C_dc", 130, 80, c_dc),
            # Phase A leg
            make_igbt_v("Q_AH", 200, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("Q_AL", 200, 160, switching_frequency=fsw, on_resistance=0.02),
            make_gating("G_AH", 160, 110, f_grid, " 0 180."),
            make_gating("G_AL", 160, 190, f_grid, " 180 360."),
            # Phase B leg
            make_igbt_v("Q_BH", 350, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("Q_BL", 350, 160, switching_frequency=fsw, on_resistance=0.02),
            make_gating("G_BH", 310, 110, f_grid, " 120 300."),
            make_gating("G_BL", 310, 190, f_grid, " 300 480."),
            # Phase C leg
            make_igbt_v("Q_CH", 500, 80, switching_frequency=fsw, on_resistance=0.02),
            make_igbt_v("Q_CL", 500, 160, switching_frequency=fsw, on_resistance=0.02),
            make_gating("G_CH", 460, 110, f_grid, " 240 420."),
            make_gating("G_CL", 460, 190, f_grid, " 60 240."),
            # L filters (one per phase)
            make_inductor("La", 250, 130, l_filter),
            make_inductor("Lb", 400, 130, l_filter),
            make_inductor("Lc", 550, 130, l_filter),
            # Grid AC sources (3-phase, 120 deg apart)
            make_vac("V_GA", 650, 130, round(vgrid_rms, 4), frequency=f_grid),
            make_vac("V_GB", 700, 130, round(vgrid_rms, 4), frequency=f_grid),
            make_vac("V_GC", 750, 130, round(vgrid_rms, 4), frequency=f_grid),
            make_ground("GND2", 700, 290),
        ]

        nets = [
            # DC bus
            {"name": "net_dc_pos", "pins": [
                "V_PV.positive", "C_dc.positive",
                "Q_AH.collector", "Q_BH.collector", "Q_CH.collector",
            ]},
            {"name": "net_dc_neg", "pins": [
                "V_PV.negative", "GND1.pin1", "C_dc.negative",
                "Q_AL.emitter", "Q_BL.emitter", "Q_CL.emitter",
            ]},
            # Phase A: bridge midpoint → L_filter → grid
            {"name": "net_phase_a_mid", "pins": [
                "Q_AH.emitter", "Q_AL.collector", "La.pin1",
            ]},
            {"name": "net_phase_a_grid", "pins": ["La.pin2", "V_GA.positive"]},
            # Phase B
            {"name": "net_phase_b_mid", "pins": [
                "Q_BH.emitter", "Q_BL.collector", "Lb.pin1",
            ]},
            {"name": "net_phase_b_grid", "pins": ["Lb.pin2", "V_GB.positive"]},
            # Phase C
            {"name": "net_phase_c_mid", "pins": [
                "Q_CH.emitter", "Q_CL.collector", "Lc.pin1",
            ]},
            {"name": "net_phase_c_grid", "pins": ["Lc.pin2", "V_GC.positive"]},
            # Grid neutral
            {"name": "net_grid_neutral", "pins": [
                "V_GA.negative", "V_GB.negative", "V_GC.negative", "GND2.pin1",
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
                "name": "PV Grid-Tied Inverter (Simplified)",
                "description": (
                    f"PV grid-tied: Vdc={vdc}V -> {vgrid_rms}V AC grid, "
                    f"P={pout:.0f}W, fsw={fsw/1e3:.1f}kHz"
                ),
                "design": {
                    "vdc": round(vdc, 2),
                    "vgrid_rms": round(vgrid_rms, 2),
                    "power": round(pout, 2),
                    "c_dc": round(c_dc, 9),
                    "l_filter": round(l_filter, 9),
                    "i_phase": round(i_phase, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(5 / f_grid, 6),  # 5 grid cycles
            },
        }
