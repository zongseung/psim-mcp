"""LLC resonant converter topology generator.

Half-bridge LLC resonant converter with series resonant inductor (Lr),
resonant capacitor (Cr), and transformer magnetizing inductance (Lm).
Achieves soft-switching (ZVS) for high efficiency at high frequencies.
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import auto_layout


class LLCGenerator(TopologyGenerator):
    """Generate an LLC resonant converter circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "llc"

    @property
    def required_fields(self) -> list[str]:
        return ["vin", "vout_target"]

    @property
    def optional_fields(self) -> list[str]:
        return ["iout", "fsw", "power", "quality_factor"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin: float = float(requirements["vin"])
        vout: float = float(requirements["vout_target"])
        fsw: float = float(requirements.get("fsw", 100_000))
        ln_ratio: float = float(requirements.get("quality_factor", 6.0))
        ln_ratio = max(3.0, min(ln_ratio, 10.0))

        # Output power
        if requirements.get("power"):
            pout = float(requirements["power"])
            iout = pout / vout if vout else 1.0
        elif requirements.get("iout"):
            iout = float(requirements.get("iout"))
            pout = vout * iout
        else:
            iout = 1.0
            pout = vout * iout

        r_load = vout / iout if iout else 10.0
        r_load = max(r_load, 0.1)

        # Turns ratio for half-bridge: n = Vin / (2 * Vout)
        n = vin / (2 * vout) if vout else 1.0
        n = max(0.1, min(n, 20.0))

        # Resonant frequency = switching frequency (design at resonance)
        fr = fsw

        # Equivalent AC load resistance: Rac = 8 * n^2 * Rload / pi^2
        rac = 8 * n**2 * r_load / (math.pi**2)

        # Characteristic impedance: Zr = Rac (at matched load for unity gain)
        zr = rac if rac > 0 else 10.0

        # Resonant inductor: Lr = Zr / (2 * pi * fr)
        lr = zr / (2 * math.pi * fr) if fr else 1e-6
        lr = max(lr, 1e-9)

        # Resonant capacitor: Cr = 1 / ((2*pi*fr)^2 * Lr)
        cr = 1 / ((2 * math.pi * fr) ** 2 * lr) if (fr and lr) else 10e-9
        cr = max(cr, 1e-12)

        # Magnetizing inductance: Lm = Ln_ratio * Lr
        lm = ln_ratio * lr
        lm = max(lm, 1e-9)

        # Output capacitor: sized for ripple at 2*fsw (full-bridge rectifier)
        vripple_ratio = 0.01
        vripple = vripple_ratio * vout
        cout = iout / (2 * 2 * fsw * vripple) if (fsw and vripple) else 100e-6
        cout = max(cout, 1e-12)

        # LLC: Half-bridge (SW1+SW2) -> Lr -> Cr -> T1 -> D1+D2 rectifier -> Cout||R1
        # 50% duty with complementary gating and dead time
        components = [
            {
                "id": "V1", "type": "DC_Source",
                "parameters": {"voltage": vin},
                "position": {"x": 120, "y": 100}, "direction": 0,
                "ports": [120, 100, 120, 150],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 120, "y": 200}, "direction": 0,
                "ports": [120, 200],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 100}, "direction": 270,
                "ports": [200, 100, 250, 100, 230, 120],
            },
            {
                "id": "SW2", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 200, "y": 150}, "direction": 270,
                "ports": [200, 150, 250, 150, 230, 170],
            },
            # Complementary gating: ~50% duty, small dead time
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": "0,175",
                },
                "position": {"x": 230, "y": 250}, "direction": 0,
                "ports": [230, 250],
            },
            {
                "id": "G2", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": "180,355",
                },
                "position": {"x": 300, "y": 250}, "direction": 0,
                "ports": [300, 250],
            },
            {
                "id": "Lr", "type": "Inductor",
                "parameters": {"inductance": round(lr, 9)},
                "position": {"x": 300, "y": 100},
                "position2": {"x": 350, "y": 100},
                "direction": 0,
                "ports": [300, 100, 350, 100],
            },
            {
                "id": "Cr", "type": "Capacitor",
                "parameters": {"capacitance": round(cr, 9)},
                "position": {"x": 350, "y": 100},
                "position2": {"x": 400, "y": 100},
                "direction": 0,
                "ports": [350, 100, 400, 100],
            },
            {
                "id": "T1", "type": "Transformer",
                "parameters": {"turns_ratio": round(n, 6), "magnetizing_inductance": round(lm, 9)},
                "position": {"x": 430, "y": 100}, "direction": 0,
                "ports": [430, 100, 430, 150, 480, 100, 480, 150],
            },
            {
                "id": "D1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 520, "y": 150}, "direction": 270,
                "ports": [520, 150, 520, 100],
            },
            {
                "id": "D2", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 570, "y": 150}, "direction": 270,
                "ports": [570, 150, 570, 100],
            },
            {
                "id": "Cout", "type": "Capacitor",
                "parameters": {"capacitance": round(cout, 9)},
                "position": {"x": 620, "y": 100},
                "position2": {"x": 620, "y": 150},
                "direction": 90,
                "ports": [620, 100, 620, 150],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 670, "y": 100},
                "position2": {"x": 670, "y": 150},
                "direction": 90,
                "ports": [670, 100, 670, 150],
            },
        ]

        # Half-bridge LLC:
        # SW1.drain = V+, SW1.source = SW2.drain = half-bridge midpoint
        # SW2.source = V- (gnd)
        # midpoint -> Lr -> Cr -> T1.primary1, T1.primary2 -> gnd
        # T1.secondary1 -> D1 (center-tap rectifier)
        # T1.secondary2 -> D2
        # D1.cathode + D2.cathode -> Cout -> R1
        nets = [
            {"name": "net_vdc_pos", "pins": ["V1.positive", "SW1.drain"]},
            {"name": "net_hb_mid", "pins": ["SW1.source", "SW2.drain", "Lr.pin1"]},
            {"name": "net_lr_cr", "pins": ["Lr.pin2", "Cr.positive"]},
            {"name": "net_cr_pri", "pins": ["Cr.negative", "T1.primary1"]},
            {"name": "net_pri_gnd", "pins": ["T1.primary2", "V1.negative", "GND1.pin1", "SW2.source"]},
            {"name": "net_sec1_d1", "pins": ["T1.secondary1", "D1.anode"]},
            {"name": "net_sec2_d2", "pins": ["T1.secondary2", "D2.anode"]},
            {"name": "net_rect_out", "pins": ["D1.cathode", "D2.cathode", "Cout.positive", "R1.pin1"]},
            {"name": "net_sec_gnd", "pins": ["Cout.negative", "R1.pin2"]},
            {"name": "net_gate1", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_gate2", "pins": ["G2.output", "SW2.gate"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "LLC Resonant Converter",
                "description": (
                    f"LLC resonant converter: {vin}V -> {vout}V @ {iout}A, "
                    f"fsw={fsw/1e3:.1f}kHz, n={n:.3f}, fr={fr/1e3:.1f}kHz"
                ),
                "design": {
                    "turns_ratio": round(n, 6),
                    "resonant_frequency": round(fr, 2),
                    "resonant_inductance": round(lr, 9),
                    "resonant_capacitance": round(cr, 9),
                    "magnetizing_inductance": round(lm, 9),
                    "output_capacitance": round(cout, 9),
                    "characteristic_impedance": round(zr, 4),
                    "ln_ratio": round(ln_ratio, 2),
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
