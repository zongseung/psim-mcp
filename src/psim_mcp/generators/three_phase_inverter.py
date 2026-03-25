"""Three-phase inverter topology generator."""

from __future__ import annotations

from .base import TopologyGenerator
from .layout import (
    make_vdc,
    make_ground,
    make_resistor,
    make_mosfet_v,
    make_gating,
)


class ThreePhaseInverterGenerator(TopologyGenerator):
    """Generate a three-phase six-switch inverter circuit."""

    @property
    def topology_name(self) -> str:
        return "three_phase_inverter"

    @property
    def required_fields(self) -> list[str]:
        return ["vdc"]

    @property
    def optional_fields(self) -> list[str]:
        return ["load_resistance", "fsw"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vdc: float = float(requirements["vdc"])
        r_load: float = float(requirements.get("load_resistance", 10.0))
        fsw: float = float(requirements.get("fsw", 10_000))

        # Three legs, each with high-side and low-side MOSFET
        # 120-degree phase shift: A=0, B=120, C=240
        # Switching_Points: on_angle, off_angle
        sw_points_high = [" 0 180.", " 120 300.", " 240 60."]
        sw_points_low = [" 180 360.", " 300 120.", " 60 240."]

        # Layout:
        # VDC(80,80)-(80,230), GND at (80,230)
        # Leg A: SW1(200,80) SW2(200,160)  G1(160,110) G2(160,190)  R1(260,130)-(260,180)
        # Leg B: SW3(340,80) SW4(340,160)  G3(300,110) G4(300,190)  R2(400,130)-(400,180)
        # Leg C: SW5(480,80) SW6(480,160)  G5(440,110) G6(440,190)  R3(540,130)-(540,180)
        # V+ rail at y=80, GND bus at y=230

        leg_x_start = 200
        leg_spacing = 140
        components = [
            make_vdc("V1", 80, 80, vdc),
            make_ground("GND1", 80, 230),
        ]

        nets = [
            {"name": "net_vdc_pos", "pins": ["V1.positive"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1"]},
        ]

        phase_labels = ["A", "B", "C"]
        for i in range(3):
            lx = leg_x_start + i * leg_spacing
            sw_hi_id = f"SW{2*i+1}"
            sw_lo_id = f"SW{2*i+2}"
            g_hi_id = f"G{2*i+1}"
            g_lo_id = f"G{2*i+2}"
            r_id = f"R{i+1}"

            # High-side MOSFET: drain at V+ rail (y=80), source at y=130
            components.append(
                make_mosfet_v(sw_hi_id, lx, 80, switching_frequency=fsw, on_resistance=0.01)
            )
            # Low-side MOSFET: drain at y=160, source at y=210
            components.append(
                make_mosfet_v(sw_lo_id, lx, 160, switching_frequency=fsw, on_resistance=0.01)
            )

            # Gating signals
            components.append(
                make_gating(g_hi_id, lx - 40, 110, fsw, sw_points_high[i])
            )
            components.append(
                make_gating(g_lo_id, lx - 40, 190, fsw, sw_points_low[i])
            )

            # Load resistor (from bridge midpoint to common star point)
            components.append(
                make_resistor(r_id, lx + 60, 130, r_load, voltage_flag=1)
            )

            # Nets for this leg
            nets[0]["pins"].append(f"{sw_hi_id}.drain")  # V+ rail
            nets[1]["pins"].append(f"{sw_lo_id}.source")  # GND bus

            nets.extend([
                {"name": f"net_bridge_{phase_labels[i].lower()}", "pins": [
                    f"{sw_hi_id}.source", f"{sw_lo_id}.drain", f"{r_id}.pin1",
                ]},
                {"name": f"net_gate_{phase_labels[i].lower()}_hi", "pins": [
                    f"{g_hi_id}.output", f"{sw_hi_id}.gate",
                ]},
                {"name": f"net_gate_{phase_labels[i].lower()}_lo", "pins": [
                    f"{g_lo_id}.output", f"{sw_lo_id}.gate",
                ]},
            ])

        # Star point: connect all load resistor return pins
        nets.append({
            "name": "net_star",
            "pins": ["R1.pin2", "R2.pin2", "R3.pin2"],
        })

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Three-Phase Inverter",
                "description": (
                    f"3-phase inverter: Vdc={vdc}V, "
                    f"fsw={fsw/1e3:.1f}kHz, R_load={r_load}Ohm"
                ),
                "design": {
                    "vdc": round(vdc, 4),
                    "r_load": round(r_load, 4),
                    "fsw": round(fsw, 2),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(100 / fsw, 6),
            },
        }
