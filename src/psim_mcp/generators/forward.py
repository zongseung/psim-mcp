"""Forward converter topology generator.

Isolated DC-DC converter using a transformer with an output LC filter.
Unlike the flyback, energy transfers during the switch ON period, and
the output inductor provides continuous current to the load.

Includes an RCD clamp on the primary side for transformer demagnetization
(core reset). Without this, the magnetizing current accumulates every
switching cycle and the transformer saturates, producing incorrect results.
"""

from __future__ import annotations

import re

from .base import TopologyGenerator
from .layout import (
    make_capacitor,
    make_diode_h,
    make_diode_v,
    make_gating,
    make_ground,
    make_inductor,
    make_mosfet_v,
    make_resistor,
    make_transformer,
    make_vdc,
)


class ForwardGenerator(TopologyGenerator):
    """Generate a forward converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "forward"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return [
            "iout",
            "fsw",
            "switching_frequency",
            "n_ratio",
            "duty_cycle",
            "switching_points",
            "ripple_ratio",
            "voltage_ripple_ratio",
            "rectifier_diode_drop",
            "freewheel_diode_drop",
        ]

    @staticmethod
    def _normalize_ratio(value: float) -> float:
        """Accept fractional duty (0-1) or percentage (0-100)."""
        if value > 1.0 and value <= 100.0:
            return value / 100.0
        return value

    @classmethod
    def _parse_switching_points(cls, raw_value: object) -> tuple[float | None, str | None]:
        """Parse a two-point PWM switching string/list into duty ratio."""
        if raw_value is None:
            return None, None

        if isinstance(raw_value, (list, tuple)):
            if len(raw_value) >= 2:
                degrees = float(raw_value[1])
                return degrees / 360.0, f" 0 {int(round(degrees))}."
            return None, None

        text = str(raw_value).strip()
        if not text:
            return None, None

        numbers = re.findall(r"-?\d+(?:\.\d+)?", text)
        if len(numbers) < 2:
            return None, None

        degrees = float(numbers[1])
        return degrees / 360.0, f" 0 {int(round(degrees))}."

    @classmethod
    def _resolve_duty_override(cls, requirements: dict) -> tuple[float | None, str | None]:
        """Resolve explicit PWM override from switching points or duty ratio."""
        for key in ("switching_points", "Switching_Points"):
            duty, points = cls._parse_switching_points(requirements.get(key))
            if duty is not None:
                return duty, points

        for key in ("duty_cycle", "duty"):
            if requirements.get(key) is None:
                continue
            duty = cls._normalize_ratio(float(requirements[key]))
            return duty, None

        return None, None

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        iout: float = float(requirements.get("iout", requirements.get("iout_target", 1.0)))
        fsw: float = float(requirements.get("fsw", requirements.get("switching_frequency", 100_000)))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.01))
        rectifier_diode_drop: float = float(
            requirements.get("rectifier_diode_drop", requirements.get("diode_drop", 0.7))
        )
        freewheel_diode_drop: float = float(
            requirements.get("freewheel_diode_drop", requirements.get("diode_drop", 0.7))
        )
        duty_override, switching_points_override = self._resolve_duty_override(requirements)

        d_target = self._normalize_ratio(float(requirements.get("target_duty", 0.45)))
        d_target = max(0.05, min(d_target, 0.49))

        # Turns ratio Ns/Np
        if requirements.get("n_ratio"):
            n = float(requirements["n_ratio"])
        elif duty_override is not None:
            n = (
                vout + freewheel_diode_drop + duty_override * (rectifier_diode_drop - freewheel_diode_drop)
            ) / (vin * duty_override) if (vin and duty_override) else 1.0
        else:
            n = (
                vout + freewheel_diode_drop + d_target * (rectifier_diode_drop - freewheel_diode_drop)
            ) / (vin * d_target) if (vin and d_target) else 1.0
        n = max(0.05, min(n, 10.0))

        # Steady-state inductor balance:
        # D*(n*Vin - Vd_rect - Vout) + (1-D)*(-Vout - Vd_free) = 0
        # => D = (Vout + Vd_free) / (n*Vin - Vd_rect + Vd_free)
        if duty_override is not None:
            duty = max(0.01, min(duty_override, 0.99))
        else:
            duty_denom = vin * n - rectifier_diode_drop + freewheel_diode_drop
            duty = (vout + freewheel_diode_drop) / duty_denom if duty_denom else 0.5
            duty = max(0.05, min(duty, 0.95))
        # PSIM GATING format: space-separated angles with trailing period
        switching_points = switching_points_override or f" 0 {int(round(duty * 360))}."

        # Output inductor: L = Vout * (1 - D) / (fsw * ripple_ratio * Iout)
        delta_i = ripple_ratio * iout
        inductance = vout * (1 - duty) / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitance: Cout = delta_I / (8 * fsw * Vripple)
        vripple = vripple_ratio * vout
        capacitance = delta_i / (8 * fsw * vripple) if (fsw and vripple) else 100e-6
        capacitance = max(capacitance, 1e-12)

        r_load = vout / iout if iout else 10.0

        # Magnetizing inductance: sized so mag current ≈ 10% of reflected load
        # Lm = Vin * D / (fsw * 0.1 * Iout_reflected)
        i_reflected = max(iout * n, 0.01)
        lm = vin * duty / (fsw * 0.1 * i_reflected) if (fsw and i_reflected) else 1e-3
        lm = max(lm, 1e-6)

        # RCD Clamp design (transformer demagnetization / core reset)
        # Without a reset path, magnetizing current accumulates each cycle
        # and the transformer saturates, producing wrong simulation results.
        #
        # Clamp voltage ≈ Vin ensures demagnetization within (1-D) period.
        # Imag_peak = Vin * D / (Lm * fsw)
        # P_clamp = 0.5 * Lm * Imag_peak^2 * fsw
        # R_clamp = V_clamp^2 / P_clamp
        # C_clamp: RC >> 1/fsw for low ripple on clamp voltage
        v_clamp = vin
        i_mag_peak = vin * duty / (lm * fsw) if (lm and fsw) else 0.1
        p_clamp = max(0.5 * lm * i_mag_peak**2 * fsw, 0.1)
        r_clamp = v_clamp**2 / p_clamp
        r_clamp = round(max(1000, min(r_clamp, 200_000)), 1)
        c_clamp = 20 / (fsw * r_clamp) if (fsw and r_clamp) else 100e-9
        c_clamp = max(c_clamp, 1e-9)

        # Layout:
        #   RCD clamp above main power path (y=30 clamp node, y=80 Vin+ rail)
        #   C_clamp(65,30)-(65,80)  R_clamp(100,30)-(100,80)
        #   D_clamp(130,80) anode → (130,30) cathode [vertical, cathode up]
        #
        #   Main path: VDC(80,80) → T1(200,80-130) → D1(270,80) → L1(360,80) → ...
        #   SW1 below T1.primary2 at (200,130)
        #   GND bus at y=230
        components = [
            make_vdc("V1", 80, 80, vin),
            make_ground("GND1", 80, 230),
            make_transformer(
                "T1", 200, 80, 200, 130, 250, 130, 250, 80,
                np_turns=1, ns_turns=round(n, 6),
                magnetizing_inductance=round(lm, 9),
            ),
            make_mosfet_v("SW1", 200, 130, switching_frequency=fsw, on_resistance=0.01),
            make_gating("G1", 160, 160, fsw, switching_points),
            # RCD clamp: D_clamp → R_clamp + C_clamp (parallel) → Vin+
            make_diode_v("D_clamp", 130, 80, forward_voltage=0.01),
            make_resistor("R_clamp", 100, 30, r_clamp),
            make_capacitor("C_clamp", 65, 30, c_clamp),
            # Secondary side
            make_diode_h("D1", 270, 80, forward_voltage=rectifier_diode_drop),
            make_diode_v("D2", 340, 130, forward_voltage=freewheel_diode_drop),
            make_inductor("L1", 360, 80, inductance),
            make_capacitor("Cout", 440, 80, capacitance),
            make_resistor("Vout", 490, 80, r_load, voltage_flag=1),
        ]

        nets = [
            {"name": "net_vin_p1", "pins": [
                "V1.positive", "T1.primary1",
                "R_clamp.pin2", "C_clamp.negative",
            ]},
            {"name": "net_p2_sw", "pins": ["T1.primary2", "SW1.drain", "D_clamp.anode"]},
            {"name": "net_clamp", "pins": ["D_clamp.cathode", "R_clamp.pin1", "C_clamp.positive"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_sec2_d1", "pins": ["T1.secondary2", "D1.anode"]},
            {"name": "net_d1_d2_l", "pins": ["D1.cathode", "D2.cathode", "L1.pin1"]},
            {"name": "net_out", "pins": ["L1.pin2", "Cout.positive", "Vout.pin1"]},
            {"name": "net_sec_gnd", "pins": ["T1.secondary1", "D2.anode", "Cout.negative", "Vout.pin2"]},
            {"name": "net_pri_gnd", "pins": ["SW1.source", "V1.negative", "GND1.pin1"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Forward Converter",
                "description": (
                    f"Forward DC-DC converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, D={duty:.3f}, n={n:.3f}"
                ),
                "design": {
                    "duty": round(duty, 6),
                    "switching_points": switching_points,
                    "turns_ratio": round(n, 6), "np_turns": 1, "ns_turns": round(n, 6),
                    "inductance": round(inductance, 9),
                    "capacitance": round(capacitance, 9),
                    "magnetizing_inductance": round(lm, 9),
                    "r_load": round(r_load, 4),
                    "r_clamp": round(r_clamp, 1),
                    "c_clamp": round(c_clamp, 12),
                    "rectifier_diode_drop": rectifier_diode_drop,
                    "freewheel_diode_drop": freewheel_diode_drop,
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(500 / fsw, 6),
            },
        }
