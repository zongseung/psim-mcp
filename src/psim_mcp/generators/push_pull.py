"""Push-pull converter topology generator.

Isolated DC-DC converter using two primary-side switches that alternately
drive a center-tapped transformer. The secondary is full-wave rectified
with an LC output filter. Suitable for medium-power applications requiring
galvanic isolation.
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


class PushPullGenerator(TopologyGenerator):
    """Generate a push-pull converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "push_pull"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target", "iout"]

    @property
    def optional_fields(self) -> list[str]:
        return ["fsw", "n_ratio", "ripple_ratio", "voltage_ripple_ratio"]

    def synthesize(self, requirements: dict) -> "CircuitGraph":
        from psim_mcp.synthesis.topologies.push_pull import synthesize_push_pull
        return synthesize_push_pull(requirements)

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

        # Turns ratio Ns/Np — choose so duty is approximately 0.4
        if requirements.get("n_ratio"):
            n = float(requirements["n_ratio"])
        else:
            # D = (Ns/Np) * Vout / Vin => n = D * Vin / Vout
            d_target = 0.4
            n = d_target * vin / vout if vout else 1.0
            n = max(0.1, min(n, 10.0))

        # Effective duty per switch: D = n * Vout / Vin
        # In push-pull, the effective output frequency is 2*fsw (both halves)
        duty = n * vout / vin if vin else 0.5
        duty = max(0.05, min(duty, 0.48))  # max ~0.48 to avoid overlap

        # Output inductor: L = Vout * (1 - 2*D) / (2 * fsw * delta_I)
        # For push-pull, effective ripple frequency is 2*fsw
        delta_i = ripple_ratio * iout
        # Use standard forward-derived formula adapted for push-pull
        inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitor: C = Iout * D / (fsw * Vripple)
        vripple = vripple_ratio * vout
        capacitance = iout * duty / (fsw * vripple) if (fsw and vripple) else 100e-6
        capacitance = max(capacitance, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Layout:
        # VDC(80,100)-(80,150), GND at (80,230)
        #
        # Center-tap transformer:
        #   primary_top(200,80) connects to SW1.drain
        #   primary_center(200,130) connects to V1.positive (center-tap = Vin+)
        #   primary_bottom(200,180) connects to SW2.drain
        #   Secondary: sec_top(250,80), sec_center(250,130), sec_bottom(250,180)
        #
        # SW1 drain(150,80) source(150,130) gate(130,110) — top switch
        # SW2 drain(150,150) source(150,200) gate(130,180) — bottom switch
        # G1(110,110) -> SW1, G2(110,180) -> SW2 (alternating 180 deg apart)
        #
        # D1 anode(270,80) cathode(320,80) — top rectifier
        # D2 anode(270,180) cathode(320,180) — bottom rectifier
        # Both cathodes connect to L1(340,80)
        # L1(340,80)-(390,80), C1(420,80)-(420,130), R1(470,80)-(470,130)
        # Secondary center-tap to GND bus at y=230

        # Center-tap transformer component (6 pins)
        ct_transformer = _build_component(
            "T1", "Center_Tap_Transformer",
            {"x": 200, "y": 80}, 0,
            [(200, 80), (200, 130), (200, 180), (250, 80), (250, 130), (250, 180)],
            parameters={
                "turns_ratio": round(1.0 / n, 6) if n else 1.0,
            },
        )

        components = [
            make_vdc("V1", 80, 100, vin),
            make_ground("GND1", 80, 230),
            ct_transformer,
            make_mosfet_v("SW1", 150, 80, switching_frequency=fsw, on_resistance=0.01),
            make_mosfet_v("SW2", 150, 150, switching_frequency=fsw, on_resistance=0.01),
            # Alternating gating: SW1 ON for first half, SW2 ON for second half
            make_gating("G1", 110, 110, fsw, f" 0 {int(duty * 360)}."),
            make_gating("G2", 110, 180, fsw, f" 180 {180 + int(duty * 360)}."),
            make_diode_h("D1", 270, 80, forward_voltage=0.5),
            make_diode_h("D2", 270, 180, forward_voltage=0.5),
            make_inductor("L1", 340, 80, inductance, current_flag=1),
            make_capacitor("C1", 420, 80, capacitance),
            make_resistor("R1", 470, 80, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin_ct", "pins": ["V1.positive", "T1.primary_center"]},
            {"name": "net_ptop_sw1", "pins": ["T1.primary_top", "SW1.drain"]},
            {"name": "net_pbot_sw2", "pins": ["T1.primary_bottom", "SW2.drain"]},
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
            {"name": "net_pri_gnd", "pins": ["SW1.source", "SW2.source", "V1.negative", "GND1.pin1"]},
            {"name": "net_stop_d1", "pins": ["T1.secondary_top", "D1.anode"]},
            {"name": "net_sbot_d2", "pins": ["T1.secondary_bottom", "D2.anode"]},
            {"name": "net_rect_l", "pins": ["D1.cathode", "D2.cathode", "L1.pin1"]},
            {"name": "net_out", "pins": ["L1.pin2", "C1.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["T1.secondary_center", "C1.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Push-Pull Converter",
                "description": (
                    f"Push-pull DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}, n(Ns/Np)={n:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "turns_ratio": round(n, 6),
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
