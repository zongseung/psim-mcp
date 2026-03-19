"""Boost PFC (Power Factor Correction) topology generator.

Single-stage boost PFC front-end that shapes the input current to
follow the AC line voltage, achieving near-unity power factor. Uses
a full-bridge diode rectifier followed by a boost stage with active
switching.
"""

from __future__ import annotations

import math

from .base import TopologyGenerator
from .layout import auto_layout


class BoostPFCGenerator(TopologyGenerator):
    """Generate a boost PFC circuit from high-level requirements."""

    @property
    def topology_name(self) -> str:
        return "boost_pfc"

    @property
    def required_fields(self) -> list[str]:
        return ["vin"]

    @property
    def optional_fields(self) -> list[str]:
        return ["vout_target", "power", "fsw", "ripple_ratio"]

    # ------------------------------------------------------------------
    # Design
    # ------------------------------------------------------------------

    def generate(self, requirements: dict) -> dict:
        missing = self.missing_fields(requirements)
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        vin_rms: float = float(requirements["vin"])  # AC RMS input
        fsw: float = float(requirements.get("fsw", 65_000))
        ripple_ratio: float = float(requirements.get("ripple_ratio", 0.3))
        vripple_ratio: float = float(requirements.get("voltage_ripple_ratio", 0.02))
        efficiency: float = 0.95
        f_line: float = 50.0  # line frequency, Hz

        vin_peak = vin_rms * math.sqrt(2)

        # Output DC voltage: default ~400V for 220VAC, or Vpeak*1.1 otherwise
        if requirements.get("vout_target"):
            vout = float(requirements["vout_target"])
        else:
            vout = max(vin_peak * 1.1, 380.0)

        # Output power
        if requirements.get("power"):
            pout = float(requirements["power"])
        elif requirements.get("iout"):
            iout_val = float(requirements["iout"])
            pout = vout * iout_val
        else:
            pout = 200.0  # default 200W

        iout = pout / vout if vout else 1.0
        r_load = vout / iout if iout else 10.0
        r_load = max(r_load, 0.1)

        # Input power accounting for efficiency
        pin = pout / efficiency

        # Peak input current
        iin_peak = pin * math.sqrt(2) / vin_rms if vin_rms else 1.0

        # Maximum duty cycle at peak of line (worst case for inductor)
        d_max = 1 - vin_peak / vout if vout > vin_peak else 0.1
        d_max = max(0.05, min(d_max, 0.95))

        # Boost inductor: L = Vin_peak * D_max / (fsw * ripple_ratio * Iin_peak)
        delta_i = ripple_ratio * iin_peak
        inductance = vin_peak * d_max / (fsw * delta_i) if (fsw and delta_i) else 1e-3
        inductance = max(inductance, 1e-9)

        # Output capacitor: Cout = Pout / (2 * pi * f_line * Vout * vripple)
        # Sized to handle 2*f_line ripple (100Hz or 120Hz)
        vripple = vripple_ratio * vout
        cout = pout / (2 * math.pi * f_line * vout * vripple) if (f_line and vout and vripple) else 470e-6
        cout = max(cout, 1e-12)

        # Boost PFC: VAC -> D_br1-4 rectifier -> L1 -> SW1 & D_boost -> Cout||R1
        components = [
            {
                "id": "V1", "type": "AC_Source",
                "parameters": {"voltage": vin_rms, "frequency": f_line},
                "position": {"x": 120, "y": 100}, "direction": 0,
                "ports": [120, 100, 120, 150],
            },
            {
                "id": "GND1", "type": "Ground",
                "parameters": {},
                "position": {"x": 120, "y": 200}, "direction": 0,
                "ports": [120, 200],
            },
            # Full-bridge rectifier
            {
                "id": "D_br1", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 200, "y": 100}, "direction": 270,
                "ports": [200, 100, 200, 50],
            },
            {
                "id": "D_br2", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 200, "y": 150}, "direction": 270,
                "ports": [200, 150, 200, 100],
            },
            {
                "id": "D_br3", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 250, "y": 100}, "direction": 270,
                "ports": [250, 100, 250, 50],
            },
            {
                "id": "D_br4", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 250, "y": 150}, "direction": 270,
                "ports": [250, 150, 250, 100],
            },
            # Boost stage
            {
                "id": "L1", "type": "Inductor",
                "parameters": {"inductance": round(inductance, 9)},
                "position": {"x": 300, "y": 100},
                "position2": {"x": 350, "y": 100},
                "direction": 0,
                "ports": [300, 100, 350, 100],
            },
            {
                "id": "SW1", "type": "MOSFET",
                "parameters": {"switching_frequency": fsw, "on_resistance": 0.01},
                "position": {"x": 370, "y": 100}, "direction": 270,
                "ports": [370, 100, 420, 100, 400, 120],
            },
            {
                "id": "G1", "type": "PWM_Generator",
                "parameters": {
                    "Frequency": fsw,
                    "NoOfPoints": 2,
                    "Switching_Points": f"0,{int(d_max * 360)}",
                },
                "position": {"x": 400, "y": 250}, "direction": 0,
                "ports": [400, 250],
            },
            {
                "id": "D_boost", "type": "Diode",
                "parameters": {"forward_voltage": 0.7},
                "position": {"x": 450, "y": 150}, "direction": 270,
                "ports": [450, 150, 450, 100],
            },
            {
                "id": "Cout", "type": "Capacitor",
                "parameters": {"capacitance": round(cout, 9)},
                "position": {"x": 500, "y": 100},
                "position2": {"x": 500, "y": 150},
                "direction": 90,
                "ports": [500, 100, 500, 150],
            },
            {
                "id": "R1", "type": "Resistor",
                "parameters": {"resistance": round(r_load, 4), "VoltageFlag": 1},
                "position": {"x": 550, "y": 100},
                "position2": {"x": 550, "y": 150},
                "direction": 90,
                "ports": [550, 100, 550, 150],
            },
        ]

        # Full-bridge rectifier nets:
        # AC+ -> D_br1 anode & D_br2 cathode
        # AC- -> D_br3 anode & D_br4 cathode
        # D_br1 cathode & D_br3 cathode -> DC+ (to L1)
        # D_br2 anode & D_br4 anode -> DC- (ground)
        nets = [
            {"name": "net_ac_pos", "pins": ["V1.positive", "D_br1.anode", "D_br2.cathode"]},
            {"name": "net_ac_neg", "pins": ["V1.negative", "D_br3.anode", "D_br4.cathode"]},
            {"name": "net_rect_pos", "pins": ["D_br1.cathode", "D_br3.cathode", "L1.pin1"]},
            {"name": "net_l_sw_dboost", "pins": ["L1.pin2", "SW1.drain", "D_boost.anode"]},
            {"name": "net_gate", "pins": ["G1.output", "SW1.gate"]},
            {"name": "net_dboost_out", "pins": ["D_boost.cathode", "Cout.positive", "R1.pin1"]},
            {"name": "net_dc_gnd", "pins": ["D_br2.anode", "D_br4.anode", "GND1.pin1", "SW1.source", "Cout.negative", "R1.pin2"]},
        ]

        return {
            "topology": self.topology_name,
            "metadata": {
                "name": "Boost PFC",
                "description": (
                    f"Boost PFC: {vin_rms}V AC -> {vout:.0f}V DC, "
                    f"P={pout:.0f}W, fsw={fsw/1e3:.1f}kHz, D_max={d_max:.3f}"
                ),
                "design": {
                    "d_max": round(d_max, 6),
                    "vin_peak": round(vin_peak, 4),
                    "iin_peak": round(iin_peak, 4),
                    "inductance": round(inductance, 9),
                    "capacitance": round(cout, 9),
                    "r_load": round(r_load, 4),
                    "power": round(pout, 2),
                },
            },
            "components": components,
            "nets": nets,
            "simulation": {
                # Need enough time to see line-frequency behavior
                "time_step": round(1 / (fsw * 200), 9),
                "total_time": round(3 / f_line, 6),  # 3 line cycles
            },
        }
