"""Comprehensive circuit templates for PSIM-MCP.

Every template defines components, connections, and layout positions
so that both ASCII and SVG renderers can produce meaningful diagrams.
"""

from __future__ import annotations

TEMPLATES: dict[str, dict] = {}


def _t(name: str, description: str, category: str, components: list, connections: list):
    """Register a template."""
    TEMPLATES[name] = {
        "description": description,
        "category": category,
        "components": components,
        "connections": connections,
    }


# =========================================================================
# 1. DC-DC Converters — Non-Isolated
# =========================================================================

_t("buck", "DC-DC Buck (step-down) converter / 벅 강압 컨버터",
   "dc_dc",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000, "on_resistance": 0.01}, "position": {"x": 180, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}, "position": {"x": 340, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 500, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 500, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "L1.input"},
       {"from": "SW1.source", "to": "D1.cathode"},
       {"from": "D1.anode", "to": "V1.negative"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "R1.output", "to": "V1.negative"},
       {"from": "C1.negative", "to": "V1.negative"},
   ])

_t("boost", "DC-DC Boost (step-up) converter / 부스트 승압 컨버터",
   "dc_dc",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 12.0}, "position": {"x": 40, "y": 120}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 180, "y": 50}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000, "on_resistance": 0.01}, "position": {"x": 340, "y": 190}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 340, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 47e-6}, "position": {"x": 500, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 50.0}, "position": {"x": 500, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "SW1.drain"},
       {"from": "L1.output", "to": "D1.anode"},
       {"from": "SW1.source", "to": "V1.negative"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D1.cathode", "to": "C1.positive"},
       {"from": "R1.output", "to": "V1.negative"},
       {"from": "C1.negative", "to": "V1.negative"},
   ])

_t("buck_boost", "DC-DC Buck-Boost converter / 벅-부스트 컨버터",
   "dc_dc",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 24.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000, "on_resistance": 0.01}, "position": {"x": 180, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 340, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 68e-6}, "position": {"x": 180, "y": 190}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 220e-6}, "position": {"x": 500, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 500, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "L1.input"},
       {"from": "L1.output", "to": "D1.anode"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D1.cathode", "to": "C1.positive"},
       {"from": "R1.output", "to": "V1.negative"},
       {"from": "C1.negative", "to": "V1.negative"},
       {"from": "V1.negative", "to": "L1.output"},
   ])

_t("cuk", "Cuk converter / 쿡 컨버터",
   "dc_dc",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 24.0}, "position": {"x": 40, "y": 120}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 180, "y": 50}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 180, "y": 190}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 10e-6}, "position": {"x": 340, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 340, "y": 190}},
       {"id": "L2", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 500, "y": 50}},
       {"id": "C2", "type": "Capacitor", "parameters": {"capacitance": 220e-6}, "position": {"x": 660, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 660, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "SW1.drain"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "SW1.source", "to": "V1.negative"},
       {"from": "C1.negative", "to": "D1.cathode"},
       {"from": "C1.negative", "to": "L2.input"},
       {"from": "D1.anode", "to": "V1.negative"},
       {"from": "L2.output", "to": "R1.input"},
       {"from": "L2.output", "to": "C2.positive"},
       {"from": "R1.output", "to": "V1.negative"},
       {"from": "C2.negative", "to": "V1.negative"},
   ])

_t("sepic", "SEPIC converter / SEPIC 컨버터",
   "dc_dc",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 12.0}, "position": {"x": 40, "y": 120}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 180, "y": 50}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 180, "y": 190}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 10e-6}, "position": {"x": 340, "y": 50}},
       {"id": "L2", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 500, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 500, "y": 190}},
       {"id": "C2", "type": "Capacitor", "parameters": {"capacitance": 220e-6}, "position": {"x": 660, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 24.0}, "position": {"x": 660, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "SW1.drain"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "SW1.source", "to": "V1.negative"},
       {"from": "C1.negative", "to": "L2.input"},
       {"from": "L2.output", "to": "D1.cathode"},
       {"from": "D1.anode", "to": "V1.negative"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D1.cathode", "to": "C2.positive"},
       {"from": "R1.output", "to": "V1.negative"},
       {"from": "C2.negative", "to": "V1.negative"},
   ])

_t("bidirectional_buck_boost", "Bidirectional Buck-Boost / 양방향 벅-부스트",
   "dc_dc",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 50000}, "position": {"x": 220, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 400, "y": 120}},
       {"id": "BAT1", "type": "Battery", "parameters": {"voltage": 24.0, "capacity_Ah": 100}, "position": {"x": 560, "y": 120}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "L1.input"},
       {"from": "L1.output", "to": "BAT1.positive"},
       {"from": "BAT1.negative", "to": "V1.negative"},
   ])

# =========================================================================
# 2. DC-DC Converters — Isolated
# =========================================================================

_t("flyback", "Flyback converter / 플라이백 컨버터",
   "dc_dc_isolated",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 310.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 180, "y": 190}},
       {"id": "T1", "type": "Transformer", "parameters": {"turns_ratio": 0.1, "Lm": 500e-6}, "position": {"x": 340, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 500, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 1000e-6}, "position": {"x": 660, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 5.0}, "position": {"x": 660, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "T1.primary_in"},
       {"from": "T1.primary_out", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "V1.negative"},
       {"from": "T1.secondary_out", "to": "D1.anode"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D1.cathode", "to": "C1.positive"},
       {"from": "R1.output", "to": "T1.secondary_in"},
       {"from": "C1.negative", "to": "T1.secondary_in"},
   ])

_t("forward", "Forward converter / 포워드 컨버터",
   "dc_dc_isolated",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 120}},
       {"id": "D_clamp", "type": "Diode", "parameters": {"forward_voltage": 0.01}, "position": {"x": 140, "y": 50}},
        {"id": "R_clamp", "type": "Resistor", "parameters": {"resistance": 10000.0}, "position": {"x": 100, "y": 30}},
        {"id": "C_clamp", "type": "Capacitor", "parameters": {"capacitance": 100e-9}, "position": {"x": 60, "y": 30}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 200000}, "position": {"x": 180, "y": 190}},
       {"id": "T1", "type": "Transformer", "parameters": {"turns_ratio": 0.25}, "position": {"x": 340, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 500, "y": 50}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 500, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 22e-6}, "position": {"x": 660, "y": 50}},
       {"id": "Cout", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 820, "y": 190}},
       {"id": "Vout", "type": "Resistor", "parameters": {"resistance": 5.0}, "position": {"x": 820, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "T1.primary_in"},
       {"from": "V1.positive", "to": "R_clamp.output"},
       {"from": "V1.positive", "to": "C_clamp.negative"},
       {"from": "T1.primary_out", "to": "SW1.drain"},
       {"from": "T1.primary_out", "to": "D_clamp.anode"},
       {"from": "D_clamp.cathode", "to": "R_clamp.input"},
       {"from": "D_clamp.cathode", "to": "C_clamp.positive"},
       {"from": "SW1.source", "to": "V1.negative"},
       {"from": "T1.secondary_out", "to": "D1.anode"},
       {"from": "D1.cathode", "to": "L1.input"},
       {"from": "D2.cathode", "to": "L1.input"},
       {"from": "D2.anode", "to": "T1.secondary_in"},
       {"from": "L1.output", "to": "Vout.input"},
       {"from": "L1.output", "to": "Cout.positive"},
       {"from": "Vout.output", "to": "T1.secondary_in"},
       {"from": "Cout.negative", "to": "T1.secondary_in"},
   ])

_t("push_pull", "Push-Pull converter / 푸시풀 컨버터",
   "dc_dc_isolated",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 150}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 180, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 180, "y": 250}},
       {"id": "T1", "type": "Center_Tap_Transformer", "parameters": {"turns_ratio": 0.5}, "position": {"x": 380, "y": 150}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 540, "y": 50}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 540, "y": 250}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 22e-6}, "position": {"x": 700, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 860, "y": 250}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 5.0}, "position": {"x": 860, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "T1.primary_center"},
       {"from": "T1.primary_top", "to": "SW1.drain"},
       {"from": "T1.primary_bottom", "to": "SW2.drain"},
       {"from": "SW1.source", "to": "V1.negative"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "T1.secondary_top", "to": "D1.anode"},
       {"from": "T1.secondary_bottom", "to": "D2.anode"},
       {"from": "D1.cathode", "to": "L1.input"},
       {"from": "D2.cathode", "to": "L1.input"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "R1.output", "to": "T1.secondary_center"},
       {"from": "C1.negative", "to": "T1.secondary_center"},
   ])

_t("llc", "LLC Resonant converter / LLC 공진 컨버터",
   "dc_dc_isolated",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 200, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 200, "y": 190}},
       {"id": "Lr", "type": "Inductor", "parameters": {"inductance": 15e-6}, "position": {"x": 360, "y": 50}},
       {"id": "Cr", "type": "Capacitor", "parameters": {"capacitance": 47e-9}, "position": {"x": 360, "y": 190}},
       {"id": "T1", "type": "Center_Tap_Transformer", "parameters": {"turns_ratio": 0.1, "Lm": 200e-6}, "position": {"x": 520, "y": 120}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 680, "y": 50}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 680, "y": 190}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 1000e-6}, "position": {"x": 840, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 5.0}, "position": {"x": 840, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "Lr.input"},
       {"from": "Lr.output", "to": "Cr.positive"},
       {"from": "Lr.output", "to": "T1.primary_top"},
       {"from": "Cr.negative", "to": "V1.negative"},
       {"from": "T1.primary_bottom", "to": "V1.negative"},
       {"from": "T1.secondary_top", "to": "D1.anode"},
       {"from": "T1.secondary_bottom", "to": "D2.anode"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D2.cathode", "to": "R1.input"},
       {"from": "R1.output", "to": "C1.positive"},
       {"from": "C1.negative", "to": "T1.secondary_center"},
   ])

_t("dab", "Dual Active Bridge / 듀얼 액티브 브리지",
   "dc_dc_isolated",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 150}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 200, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 200, "y": 250}},
       {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 340, "y": 50}},
       {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 340, "y": 250}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 50e-6}, "position": {"x": 480, "y": 150}},
       {"id": "T1", "type": "Transformer", "parameters": {"turns_ratio": 1.0}, "position": {"x": 620, "y": 150}},
       {"id": "SW5", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 760, "y": 50}},
       {"id": "SW6", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 760, "y": 250}},
       {"id": "SW7", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 900, "y": 50}},
       {"id": "SW8", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 900, "y": 250}},
       {"id": "V2", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 1040, "y": 150}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "V1.positive", "to": "SW3.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW3.source", "to": "SW4.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW4.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "L1.input"},
       {"from": "L1.output", "to": "T1.primary_in"},
       {"from": "SW3.source", "to": "T1.primary_out"},
       {"from": "T1.secondary_out", "to": "SW5.drain"},
       {"from": "SW5.source", "to": "SW6.drain"},
       {"from": "SW7.source", "to": "SW8.drain"},
       {"from": "T1.secondary_in", "to": "SW7.drain"},
       {"from": "SW6.source", "to": "V2.negative"},
       {"from": "SW8.source", "to": "V2.negative"},
       {"from": "SW5.drain", "to": "V2.positive"},
   ])

_t("phase_shifted_full_bridge", "Phase-Shifted Full-Bridge (PSFB) / 위상 천이 풀 브리지",
   "dc_dc_isolated",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 150}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 200, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 200, "y": 250}},
       {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 340, "y": 50}},
       {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 340, "y": 250}},
       {"id": "T1", "type": "Center_Tap_Transformer", "parameters": {"turns_ratio": 0.1}, "position": {"x": 520, "y": 150}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 680, "y": 50}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 680, "y": 250}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 10e-6}, "position": {"x": 840, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 470e-6}, "position": {"x": 1000, "y": 250}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 5.0}, "position": {"x": 1000, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "V1.positive", "to": "SW3.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW3.source", "to": "SW4.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW4.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "T1.primary_top"},
       {"from": "SW3.source", "to": "T1.primary_bottom"},
       {"from": "T1.secondary_top", "to": "D1.anode"},
       {"from": "T1.secondary_bottom", "to": "D2.anode"},
       {"from": "D1.cathode", "to": "L1.input"},
       {"from": "D2.cathode", "to": "L1.input"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "R1.output", "to": "T1.secondary_center"},
       {"from": "C1.negative", "to": "T1.secondary_center"},
   ])

# =========================================================================
# 3. DC-AC Inverters
# =========================================================================

_t("half_bridge", "Single-phase Half-Bridge inverter / 단상 하프 브리지 인버터",
   "dc_ac",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 220, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 400, "y": 120}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 560, "y": 120}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "L1.input"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "R1.output", "to": "V1.negative"},
   ])

_t("full_bridge", "Single-phase Full-Bridge (H-Bridge) inverter / 단상 풀 브리지 인버터",
   "dc_ac",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 150}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 200, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 200, "y": 250}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 380, "y": 150}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 540, "y": 150}},
       {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 700, "y": 50}},
       {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 700, "y": 250}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "V1.positive", "to": "SW3.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW3.source", "to": "SW4.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW4.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "L1.pin1"},
       {"from": "L1.pin2", "to": "R1.pin1"},
       {"from": "R1.pin2", "to": "SW3.source"},
   ])

_t("three_phase_inverter", "Three-phase 2-level inverter / 3상 2-레벨 인버터",
   "dc_ac",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 600.0}, "position": {"x": 40, "y": 200}},
       {"id": "SW1", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 220, "y": 300}},
       {"id": "SW3", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 380, "y": 50}},
       {"id": "SW4", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 380, "y": 300}},
       {"id": "SW5", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 540, "y": 50}},
       {"id": "SW6", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 540, "y": 300}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 700, "y": 100}},
       {"id": "R2", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 700, "y": 200}},
       {"id": "R3", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 700, "y": 300}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.collector"},
       {"from": "V1.positive", "to": "SW3.collector"},
       {"from": "V1.positive", "to": "SW5.collector"},
       {"from": "SW1.emitter", "to": "SW2.collector"},
       {"from": "SW3.emitter", "to": "SW4.collector"},
       {"from": "SW5.emitter", "to": "SW6.collector"},
       {"from": "SW2.emitter", "to": "V1.negative"},
       {"from": "SW4.emitter", "to": "V1.negative"},
       {"from": "SW6.emitter", "to": "V1.negative"},
       {"from": "SW1.emitter", "to": "R1.input"},
       {"from": "SW3.emitter", "to": "R2.input"},
       {"from": "SW5.emitter", "to": "R3.input"},
   ])

_t("three_level_npc", "Three-level NPC inverter / 3-레벨 NPC 인버터",
   "dc_ac",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 100}},
       {"id": "V2", "type": "DC_Source", "parameters": {"voltage": 400.0}, "position": {"x": 40, "y": 250}},
       {"id": "SW1", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 250, "y": 50}},
       {"id": "SW2", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 250, "y": 130}},
       {"id": "SW3", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 250, "y": 210}},
       {"id": "SW4", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 250, "y": 290}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 1.5}, "position": {"x": 400, "y": 130}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 1.5}, "position": {"x": 400, "y": 210}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 2e-3}, "position": {"x": 550, "y": 170}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 700, "y": 170}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.collector"},
       {"from": "SW1.emitter", "to": "SW2.collector"},
       {"from": "SW2.emitter", "to": "SW3.collector"},
       {"from": "SW3.emitter", "to": "SW4.collector"},
       {"from": "SW4.emitter", "to": "V2.negative"},
       {"from": "V1.negative", "to": "V2.positive"},
       {"from": "D1.cathode", "to": "SW2.collector"},
       {"from": "D2.anode", "to": "SW3.collector"},
       {"from": "D1.anode", "to": "V1.negative"},
       {"from": "D2.cathode", "to": "V1.negative"},
       {"from": "SW2.emitter", "to": "L1.input"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "R1.output", "to": "V1.negative"},
   ])

# =========================================================================
# 4. AC-DC Rectifiers
# =========================================================================

_t("diode_bridge_rectifier", "Single-phase diode bridge rectifier / 단상 다이오드 브리지 정류기",
   "ac_dc",
   [
       {"id": "V1", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 40, "y": 120}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 220, "y": 50}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 220, "y": 190}},
       {"id": "D3", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 380, "y": 50}},
       {"id": "D4", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 380, "y": 190}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 470e-6}, "position": {"x": 540, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 100.0}, "position": {"x": 540, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "D1.anode"},
       {"from": "V1.positive", "to": "D4.cathode"},
       {"from": "V1.negative", "to": "D2.anode"},
       {"from": "V1.negative", "to": "D3.cathode"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D2.cathode", "to": "R1.input"},
       {"from": "D3.anode", "to": "C1.negative"},
       {"from": "D4.anode", "to": "C1.negative"},
       {"from": "R1.output", "to": "C1.positive"},
       {"from": "C1.negative", "to": "R1.output"},
   ])

_t("thyristor_rectifier", "Single-phase thyristor rectifier / 단상 사이리스터 정류기",
   "ac_dc",
   [
       {"id": "V1", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 40, "y": 120}},
       {"id": "T1", "type": "Thyristor", "parameters": {"firing_angle": 30}, "position": {"x": 220, "y": 50}},
       {"id": "T2", "type": "Thyristor", "parameters": {"firing_angle": 30}, "position": {"x": 220, "y": 190}},
       {"id": "T3", "type": "Thyristor", "parameters": {"firing_angle": 30}, "position": {"x": 380, "y": 50}},
       {"id": "T4", "type": "Thyristor", "parameters": {"firing_angle": 30}, "position": {"x": 380, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 10e-3}, "position": {"x": 540, "y": 50}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 700, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "T1.anode"},
       {"from": "V1.positive", "to": "T4.cathode"},
       {"from": "V1.negative", "to": "T2.anode"},
       {"from": "V1.negative", "to": "T3.cathode"},
       {"from": "T1.cathode", "to": "L1.input"},
       {"from": "T2.cathode", "to": "L1.input"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "R1.output", "to": "T3.anode"},
       {"from": "R1.output", "to": "T4.anode"},
   ])

# =========================================================================
# 5. PFC (Power Factor Correction)
# =========================================================================

_t("boost_pfc", "Boost PFC / 부스트 역률보정",
   "pfc",
   [
       {"id": "V1", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 40, "y": 120}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 50}},
       {"id": "D2", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 190}},
       {"id": "D3", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 300, "y": 50}},
       {"id": "D4", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 300, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 500e-6}, "position": {"x": 440, "y": 50}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 65000}, "position": {"x": 580, "y": 190}},
       {"id": "D5", "type": "Diode", "parameters": {"forward_voltage": 1.2}, "position": {"x": 580, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 330e-6}, "position": {"x": 720, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 500.0}, "position": {"x": 720, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "D1.anode"},
       {"from": "V1.positive", "to": "D4.cathode"},
       {"from": "V1.negative", "to": "D2.anode"},
       {"from": "V1.negative", "to": "D3.cathode"},
       {"from": "D1.cathode", "to": "L1.input"},
       {"from": "D2.cathode", "to": "L1.input"},
       {"from": "L1.output", "to": "SW1.drain"},
       {"from": "L1.output", "to": "D5.anode"},
       {"from": "SW1.source", "to": "D3.anode"},
       {"from": "D5.cathode", "to": "R1.input"},
       {"from": "D5.cathode", "to": "C1.positive"},
       {"from": "R1.output", "to": "D3.anode"},
       {"from": "C1.negative", "to": "D3.anode"},
   ])

_t("totem_pole_pfc", "Totem-Pole Bridgeless PFC / 토템폴 브릿지리스 PFC",
   "pfc",
   [
       {"id": "V1", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 65000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 65000}, "position": {"x": 220, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 200e-6}, "position": {"x": 380, "y": 120}},
       {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 120}, "position": {"x": 540, "y": 50}},
       {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 120}, "position": {"x": 540, "y": 190}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 330e-6}, "position": {"x": 700, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 500.0}, "position": {"x": 700, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "SW1.source"},
       {"from": "L1.output", "to": "SW2.drain"},
       {"from": "SW1.drain", "to": "R1.input"},
       {"from": "SW1.drain", "to": "C1.positive"},
       {"from": "SW2.source", "to": "R1.output"},
       {"from": "SW2.source", "to": "C1.negative"},
       {"from": "V1.negative", "to": "SW3.source"},
       {"from": "V1.negative", "to": "SW4.drain"},
       {"from": "SW3.drain", "to": "C1.positive"},
       {"from": "SW4.source", "to": "C1.negative"},
   ])

# =========================================================================
# 6. Renewable Energy
# =========================================================================

_t("pv_mppt_boost", "PV + MPPT Boost converter / 태양광 MPPT 부스트",
   "renewable",
   [
       {"id": "PV1", "type": "PV_Panel", "parameters": {"Voc": 40.0, "Isc": 10.0, "Vmp": 32.0, "Imp": 9.0}, "position": {"x": 40, "y": 120}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 200e-6}, "position": {"x": 200, "y": 50}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000}, "position": {"x": 360, "y": 190}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 360, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 220e-6}, "position": {"x": 520, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 20.0}, "position": {"x": 520, "y": 50}},
   ],
   [
       {"from": "PV1.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "SW1.drain"},
       {"from": "L1.output", "to": "D1.anode"},
       {"from": "SW1.source", "to": "PV1.negative"},
       {"from": "D1.cathode", "to": "R1.input"},
       {"from": "D1.cathode", "to": "C1.positive"},
       {"from": "R1.output", "to": "PV1.negative"},
       {"from": "C1.negative", "to": "PV1.negative"},
   ])

_t("pv_grid_tied", "PV grid-tied inverter / 태양광 계통연계 인버터",
   "renewable",
   [
       {"id": "PV1", "type": "PV_Panel", "parameters": {"Voc": 400.0, "Isc": 10.0}, "position": {"x": 40, "y": 150}},
       {"id": "C_dc", "type": "Capacitor", "parameters": {"capacitance": 1000e-6}, "position": {"x": 200, "y": 250}},
       {"id": "SW1", "type": "IGBT", "parameters": {"switching_frequency": 20000}, "position": {"x": 360, "y": 50}},
       {"id": "SW2", "type": "IGBT", "parameters": {"switching_frequency": 20000}, "position": {"x": 360, "y": 250}},
       {"id": "SW3", "type": "IGBT", "parameters": {"switching_frequency": 20000}, "position": {"x": 500, "y": 50}},
       {"id": "SW4", "type": "IGBT", "parameters": {"switching_frequency": 20000}, "position": {"x": 500, "y": 250}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 3e-3}, "position": {"x": 660, "y": 100}},
       {"id": "V_grid", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 820, "y": 150}},
   ],
   [
       {"from": "PV1.positive", "to": "SW1.collector"},
       {"from": "PV1.positive", "to": "SW3.collector"},
       {"from": "PV1.positive", "to": "C_dc.positive"},
       {"from": "PV1.negative", "to": "SW2.emitter"},
       {"from": "PV1.negative", "to": "SW4.emitter"},
       {"from": "PV1.negative", "to": "C_dc.negative"},
       {"from": "SW1.emitter", "to": "SW2.collector"},
       {"from": "SW3.emitter", "to": "SW4.collector"},
       {"from": "SW1.emitter", "to": "L1.input"},
       {"from": "L1.output", "to": "V_grid.positive"},
       {"from": "SW3.emitter", "to": "V_grid.negative"},
   ])

# =========================================================================
# 7. Motor Drives
# =========================================================================

_t("bldc_drive", "BLDC motor drive (6-step) / BLDC 6스텝 드라이브",
   "motor_drive",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 200}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 220, "y": 300}},
       {"id": "SW3", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 380, "y": 50}},
       {"id": "SW4", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 380, "y": 300}},
       {"id": "SW5", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 540, "y": 50}},
       {"id": "SW6", "type": "MOSFET", "parameters": {"switching_frequency": 20000}, "position": {"x": 540, "y": 300}},
       {"id": "M1", "type": "BLDC_Motor", "parameters": {"poles": 8, "Rs": 0.1, "Ls": 1e-3, "Ke": 0.01}, "position": {"x": 740, "y": 200}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "V1.positive", "to": "SW3.drain"},
       {"from": "V1.positive", "to": "SW5.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW3.source", "to": "SW4.drain"},
       {"from": "SW5.source", "to": "SW6.drain"},
       {"from": "SW2.source", "to": "V1.negative"},
       {"from": "SW4.source", "to": "V1.negative"},
       {"from": "SW6.source", "to": "V1.negative"},
       {"from": "SW1.source", "to": "M1.phase_a"},
       {"from": "SW3.source", "to": "M1.phase_b"},
       {"from": "SW5.source", "to": "M1.phase_c"},
   ])

_t("pmsm_foc_drive", "PMSM FOC drive / PMSM 벡터 제어 드라이브",
   "motor_drive",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 300.0}, "position": {"x": 40, "y": 200}},
       {"id": "SW1", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 220, "y": 300}},
       {"id": "SW3", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 380, "y": 50}},
       {"id": "SW4", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 380, "y": 300}},
       {"id": "SW5", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 540, "y": 50}},
       {"id": "SW6", "type": "IGBT", "parameters": {"switching_frequency": 10000}, "position": {"x": 540, "y": 300}},
       {"id": "M1", "type": "PMSM", "parameters": {"poles": 8, "Rs": 0.1, "Ld": 1e-3, "Lq": 1e-3, "flux": 0.05, "J": 0.01}, "position": {"x": 740, "y": 200}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.collector"},
       {"from": "V1.positive", "to": "SW3.collector"},
       {"from": "V1.positive", "to": "SW5.collector"},
       {"from": "SW1.emitter", "to": "SW2.collector"},
       {"from": "SW3.emitter", "to": "SW4.collector"},
       {"from": "SW5.emitter", "to": "SW6.collector"},
       {"from": "SW2.emitter", "to": "V1.negative"},
       {"from": "SW4.emitter", "to": "V1.negative"},
       {"from": "SW6.emitter", "to": "V1.negative"},
       {"from": "SW1.emitter", "to": "M1.phase_a"},
       {"from": "SW3.emitter", "to": "M1.phase_b"},
       {"from": "SW5.emitter", "to": "M1.phase_c"},
   ])

_t("induction_motor_vf", "Induction motor V/f drive / 유도 전동기 V/f 드라이브",
   "motor_drive",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 540.0}, "position": {"x": 40, "y": 200}},
       {"id": "SW1", "type": "IGBT", "parameters": {"switching_frequency": 5000}, "position": {"x": 220, "y": 50}},
       {"id": "SW2", "type": "IGBT", "parameters": {"switching_frequency": 5000}, "position": {"x": 220, "y": 300}},
       {"id": "SW3", "type": "IGBT", "parameters": {"switching_frequency": 5000}, "position": {"x": 380, "y": 50}},
       {"id": "SW4", "type": "IGBT", "parameters": {"switching_frequency": 5000}, "position": {"x": 380, "y": 300}},
       {"id": "SW5", "type": "IGBT", "parameters": {"switching_frequency": 5000}, "position": {"x": 540, "y": 50}},
       {"id": "SW6", "type": "IGBT", "parameters": {"switching_frequency": 5000}, "position": {"x": 540, "y": 300}},
       {"id": "M1", "type": "Induction_Motor", "parameters": {"poles": 4, "Rs": 0.5, "Rr": 0.4, "J": 0.1}, "position": {"x": 740, "y": 200}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.collector"},
       {"from": "V1.positive", "to": "SW3.collector"},
       {"from": "V1.positive", "to": "SW5.collector"},
       {"from": "SW1.emitter", "to": "SW2.collector"},
       {"from": "SW3.emitter", "to": "SW4.collector"},
       {"from": "SW5.emitter", "to": "SW6.collector"},
       {"from": "SW2.emitter", "to": "V1.negative"},
       {"from": "SW4.emitter", "to": "V1.negative"},
       {"from": "SW6.emitter", "to": "V1.negative"},
       {"from": "SW1.emitter", "to": "M1.phase_a"},
       {"from": "SW3.emitter", "to": "M1.phase_b"},
       {"from": "SW5.emitter", "to": "M1.phase_c"},
   ])

# =========================================================================
# 8. Battery / Charging
# =========================================================================

_t("cc_cv_charger", "CC-CV Battery Charger / CC-CV 배터리 충전기",
   "battery",
   [
       {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 120}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 180, "y": 50}},
       {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 180, "y": 190}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}, "position": {"x": 340, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 500, "y": 190}},
       {"id": "BAT1", "type": "Battery", "parameters": {"voltage": 12.0, "capacity_Ah": 50}, "position": {"x": 500, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "L1.input"},
       {"from": "SW1.source", "to": "D1.cathode"},
       {"from": "D1.anode", "to": "V1.negative"},
       {"from": "L1.output", "to": "BAT1.positive"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "BAT1.negative", "to": "V1.negative"},
       {"from": "C1.negative", "to": "V1.negative"},
   ])

_t("ev_obc", "EV On-Board Charger / EV 온보드 충전기",
   "battery",
   [
       {"id": "V1", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 40, "y": 150}},
       {"id": "D_B1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 50}},
       {"id": "D_B2", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 250}},
       {"id": "L_pfc", "type": "Inductor", "parameters": {"inductance": 500e-6}, "position": {"x": 340, "y": 50}},
       {"id": "SW_pfc", "type": "MOSFET", "parameters": {"switching_frequency": 65000}, "position": {"x": 340, "y": 250}},
       {"id": "D_pfc", "type": "Diode", "parameters": {"forward_voltage": 1.2}, "position": {"x": 500, "y": 50}},
       {"id": "C_dc", "type": "Capacitor", "parameters": {"capacitance": 470e-6}, "position": {"x": 500, "y": 250}},
       {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 660, "y": 50}},
       {"id": "SW2", "type": "MOSFET", "parameters": {"switching_frequency": 100000}, "position": {"x": 660, "y": 250}},
       {"id": "T1", "type": "Center_Tap_Transformer", "parameters": {"turns_ratio": 0.1}, "position": {"x": 820, "y": 150}},
       {"id": "D_out1", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 980, "y": 50}},
       {"id": "D_out2", "type": "Diode", "parameters": {"forward_voltage": 0.5}, "position": {"x": 980, "y": 250}},
       {"id": "BAT1", "type": "Battery", "parameters": {"voltage": 400.0, "capacity_Ah": 60}, "position": {"x": 1140, "y": 150}},
   ],
   [
       {"from": "V1.positive", "to": "D_B1.anode"},
       {"from": "D_B1.cathode", "to": "L_pfc.input"},
       {"from": "L_pfc.output", "to": "SW_pfc.drain"},
       {"from": "L_pfc.output", "to": "D_pfc.anode"},
       {"from": "D_pfc.cathode", "to": "C_dc.positive"},
       {"from": "SW_pfc.source", "to": "D_B2.anode"},
       {"from": "V1.negative", "to": "D_B2.cathode"},
       {"from": "C_dc.positive", "to": "SW1.drain"},
       {"from": "SW1.source", "to": "SW2.drain"},
       {"from": "SW2.source", "to": "C_dc.negative"},
       {"from": "SW1.source", "to": "T1.primary_top"},
       {"from": "C_dc.negative", "to": "T1.primary_bottom"},
       {"from": "T1.secondary_top", "to": "D_out1.anode"},
       {"from": "T1.secondary_bottom", "to": "D_out2.anode"},
       {"from": "D_out1.cathode", "to": "BAT1.positive"},
       {"from": "D_out2.cathode", "to": "BAT1.positive"},
       {"from": "BAT1.negative", "to": "T1.secondary_center"},
   ])

# =========================================================================
# 9. Filters
# =========================================================================

_t("lc_filter", "LC output filter / LC 출력 필터",
   "filter",
   [
       {"id": "V1", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 40, "y": 120}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 220, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 10e-6}, "position": {"x": 380, "y": 190}},
       {"id": "R1", "type": "Resistor", "parameters": {"resistance": 50.0}, "position": {"x": 380, "y": 50}},
   ],
   [
       {"from": "V1.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "L1.output", "to": "R1.input"},
       {"from": "C1.negative", "to": "V1.negative"},
       {"from": "R1.output", "to": "V1.negative"},
   ])

_t("lcl_filter", "LCL grid filter / LCL 계통 필터",
   "filter",
   [
       {"id": "V_inv", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 20000}, "position": {"x": 40, "y": 120}},
       {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}, "position": {"x": 220, "y": 50}},
       {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 10e-6}, "position": {"x": 380, "y": 190}},
       {"id": "L2", "type": "Inductor", "parameters": {"inductance": 0.5e-3}, "position": {"x": 540, "y": 50}},
       {"id": "V_grid", "type": "AC_Source", "parameters": {"voltage": 220.0, "frequency": 60}, "position": {"x": 700, "y": 120}},
   ],
   [
       {"from": "V_inv.positive", "to": "L1.input"},
       {"from": "L1.output", "to": "C1.positive"},
       {"from": "L1.output", "to": "L2.input"},
       {"from": "C1.negative", "to": "V_inv.negative"},
       {"from": "L2.output", "to": "V_grid.positive"},
       {"from": "V_grid.negative", "to": "V_inv.negative"},
   ])


# =========================================================================
# Category labels for listing
# =========================================================================

CATEGORIES: dict[str, str] = {
    "dc_dc": "DC-DC 컨버터 (비절연)",
    "dc_dc_isolated": "DC-DC 컨버터 (절연)",
    "dc_ac": "DC-AC 인버터",
    "ac_dc": "AC-DC 정류기",
    "pfc": "역률 보정 (PFC)",
    "renewable": "신재생 에너지",
    "motor_drive": "모터 드라이브",
    "battery": "배터리/충전",
    "filter": "필터",
}
