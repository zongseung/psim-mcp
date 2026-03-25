"""Phase-Shifted Full-Bridge (PSFB) converter topology generator.

Isolated DC-DC converter using four MOSFETs in a full-bridge configuration
with phase-shifted complementary PWM control. The secondary uses a
center-tapped transformer with full-wave rectification and LC output filter.
ZVS (zero-voltage switching) is achieved through the phase shift between
the two bridge legs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import TopologyGenerator

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph
from .layout import (
    make_capacitor,
    make_diode_h,
    make_gating,
    make_ground,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_vdc,
    _build_component,
)


class PhaseShiftedFullBridgeGenerator(TopologyGenerator):
    """Generate a phase-shifted full-bridge converter from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "phase_shifted_full_bridge"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target", "iout"]

    @property
    def optional_fields(self) -> list[str]:
        return ["fsw", "n_ratio", "ripple_ratio", "voltage_ripple_ratio", "phase_shift"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.phase_shifted_full_bridge import synthesize_phase_shifted_full_bridge
        return synthesize_phase_shifted_full_bridge(requirements)

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        iout: float = float(requirements["iout"])
        fsw: float = float(requirements.get("fsw", 100_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))

        d_max = 0.45  # maximum effective duty cycle

        # Turns ratio: n = Vout / (Vin * D_max) for center-tapped secondary
        if requirements.get("n_ratio"):
            n = float(requirements["n_ratio"])
        else:
            n = vout / (vin * d_max) if vin else 1.0
            n = max(0.01, min(n, 10.0))

        # Effective duty: D = Vout / (Vin * n)
        duty = vout / (vin * n) if (vin and n) else 0.5
        duty = max(0.05, min(duty, 0.95))

        # Phase shift angle in degrees (proportional to duty)
        phase_shift_deg = int(requirements.get("phase_shift", duty * 180))

        # Output inductor: L = Vout * (1 - D) / (fsw * delta_I)
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitor: C = delta_I / (8 * fsw * Vripple)
        vripple = vripple_ratio * vout
        capacitance = delta_i / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
        capacitance = max(capacitance, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Layout:
        # Full bridge on primary side, center-tap transformer, rectifier + LC on secondary
        #
        # VDC(80,80)-(80,130), GND at (80,230)
        #
        # Left leg at x=200: SW1(high) + SW2(low)
        #   SW1: drain(200,80) source(200,130) gate(180,110)
        #   SW2: drain(200,160) source(200,210) gate(180,190)
        #
        # Right leg at x=350: SW3(high) + SW4(low)
        #   SW3: drain(350,80) source(350,130) gate(330,110)
        #   SW4: drain(350,160) source(350,210) gate(330,190)
        #
        # Phase-shifted PWM:
        #   Leading leg (SW1/SW2): G1="0,180", G2="180,360"
        #   Lagging leg (SW3/SW4): G3 shifted by phase_shift_deg
        #   G3="phase_shift,phase_shift+180", G4 complement
        #
        # Center-tap transformer T1 at x=450:
        #   pri_top(450,80), pri_center(450,130), pri_bottom(450,180)
        #   sec_top(500,80), sec_center(500,130), sec_bottom(500,180)
        #
        # D1 anode(520,80) cathode(570,80)
        # D2 anode(520,180) cathode(570,180)
        # L1(590,80)-(640,80), C1(670,80)-(670,130), R1(720,80)-(720,130)

        # Leading leg gating: 50% duty, complementary
        g1_points = "0,180"
        g2_points = "180,360"
        # Lagging leg: shifted by phase_shift_deg
        g3_start = phase_shift_deg
        g3_points = f"{g3_start},{g3_start + 180}"
        g4_start = (g3_start + 180) % 360
        g4_points = f"{g4_start},{g4_start + 180}"

        ct_transformer = _build_component(
            "T1", "Center_Tap_Transformer",
            {"x": 450, "y": 80}, 0,
            [(450, 80), (450, 130), (450, 180), (500, 80), (500, 130), (500, 180)],
            parameters={"turns_ratio": round(n, 6)},
        )

        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 230),
            # Left leg (leading)
            make_mosfet_v("SW1", 200, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW2", 200, 160, switching_frequency=fsw, on_resistance=0.01),
            # Right leg (lagging)
            make_mosfet_v("SW3", 350, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW4", 350, 160, switching_frequency=fsw, on_resistance=0.01),
            # Gating signals
            make_gating("G1", 160, 110, fsw, g1_points),
            make_gating("G2", 160, 190, fsw, g2_points),
            make_gating("G3", 310, 110, fsw, g3_points),
            make_gating("G4", 310, 190, fsw, g4_points),
            # Transformer
            ct_transformer,
            # Secondary rectifier
            make_diode_h("D1", 520, 80, forward_voltage=0.5),
            make_diode_h("D2", 520, 180, forward_voltage=0.5),
            # Output LC filter
            make_inductor("L1", 590, 80, inductance, current_flag=1),
            make_capacitor("C1", 670, 80, capacitance),
            make_resistor("R1", 720, 80, r_load, voltage_flag=1),
        ]

        nets = [
            # DC bus
            {"name": "net_vdc_high", "pins": ["V1.positive", "SW1.drain", "SW3.drain"]},
            {"name": "net_gnd", "pins": ["V1.negative", "GND1.pin1", "SW2.source", "SW4.source"]},
            # Left leg midpoint to transformer primary top
            {"name": "net_left_mid", "pins": ["SW1.source", "SW2.drain", "T1.primary_top"]},
            # Right leg midpoint to transformer primary bottom
            {"name": "net_right_mid", "pins": ["SW3.source", "SW4.drain", "T1.primary_bottom"]},
            # Gate nets
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_gate3", "pins": ["G3.output", "SW3.gate"]},
            {"name": "net_gate4", "pins": ["G4.output", "SW4.gate"]},
            # Secondary
            {"name": "net_sec_top_d1", "pins": ["T1.secondary_top", "D1.anode"]},
            {"name": "net_sec_bot_d2", "pins": ["T1.secondary_bottom", "D2.anode"]},
            {"name": "net_rect_l", "pins": ["D1.cathode", "D2.cathode", "L1.pin1"]},
            {"name": "net_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["T1.secondary_center", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Phase-Shifted Full-Bridge Converter",
                "description": (
                    f"PSFB DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}, "
                    f"phase_shift={phase_shift_deg}deg"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "turns_ratio": round(n, 6),
                    "phase_shift_deg": phase_shift_deg,
                    "inductance": round(inductance, 9),
                    "capacitance": round(capacitance, 9),
                    "r_load": round(r_load, 4),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(50 / fsw, 6),
            },
        }
