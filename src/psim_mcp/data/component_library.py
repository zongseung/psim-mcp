"""PSIM component library — all component types available for circuit building."""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Pin & Parameter definition helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PinDef:
    """Definition of a single component pin."""

    name: str
    description: str = ""


@dataclass(frozen=True)
class ParamDef:
    """Definition of a single component parameter."""

    name: str
    default: float | int | str = 0
    unit: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
# Component definitions
# ---------------------------------------------------------------------------
# Each entry: type_name → {category, korean, default_parameters, symbol,
#                           pins, psim_element_type}
# symbol is used for ASCII rendering

# NOTE: ``psim_element_type`` can override the bridge-side PSIM element name.
# When it is left blank in the source data, we normalize it to the canonical
# component type below so downstream code never sees an empty string.
# Windows smoke tests can later replace individual entries with real PSIM names.
COMPONENTS: dict[str, dict] = {
    # === Switches ===
    # PSIM element types confirmed from PSIM 2026 Python API samples
    "MOSFET": {"category": "switch", "korean": "MOSFET", "symbol": "MOS",
               "default_parameters": {"switching_frequency": 50000, "on_resistance": 0.01},
               "pins": ["drain", "source", "gate"],
               "psim_element_type": "MULTI_MOSFET"},
    "IGBT": {"category": "switch", "korean": "IGBT", "symbol": "IGBT",
             "default_parameters": {"switching_frequency": 20000, "on_resistance": 0.02},
             "pins": ["collector", "emitter", "gate"],
             "psim_element_type": "MULTI_IGBT"},
    "Thyristor": {"category": "switch", "korean": "사이리스터(SCR)", "symbol": "SCR",
                  "default_parameters": {"firing_angle": 30},
                  "pins": ["anode", "cathode", "gate"],
                  "psim_element_type": "THYRISTOR"},
    "TRIAC": {"category": "switch", "korean": "트라이액", "symbol": "TRIAC",
              "default_parameters": {"firing_angle": 90},
              "pins": ["terminal1", "terminal2", "gate"],
              "psim_element_type": "TRIAC"},
    "GTO": {"category": "switch", "korean": "GTO", "symbol": "GTO",
            "default_parameters": {"switching_frequency": 1000},
            "pins": ["anode", "cathode", "gate"],
            "psim_element_type": "GTO"},
    "Ideal_Switch": {"category": "switch", "korean": "이상 스위치", "symbol": "SW",
                     "default_parameters": {},
                     "pins": ["pin1", "pin2", "control"],
                     "psim_element_type": "SWITCH"},

    # === Diodes ===
    "Diode": {"category": "diode", "korean": "다이오드", "symbol": "D",
              "default_parameters": {"forward_voltage": 0.7},
              "pins": ["anode", "cathode"],
              "psim_element_type": "MULTI_DIODE"},
    "Zener_Diode": {"category": "diode", "korean": "제너 다이오드", "symbol": "ZD",
                    "default_parameters": {"zener_voltage": 5.1},
                    "pins": ["anode", "cathode"],
                    "psim_element_type": "ZENER"},
    "Schottky_Diode": {"category": "diode", "korean": "쇼트키 다이오드", "symbol": "SD",
                       "default_parameters": {"forward_voltage": 0.3},
                       "pins": ["anode", "cathode"],
                       "psim_element_type": "DIODE"},

    # === Passives ===
    "Resistor": {"category": "passive", "korean": "저항", "symbol": "R",
                 "default_parameters": {"Resistance": 10.0},
                 "pins": ["pin1", "pin2", "input", "output"],
                 "psim_element_type": "MULTI_RESISTOR"},
    "Inductor": {"category": "passive", "korean": "인덕터", "symbol": "L",
                 "default_parameters": {"Inductance": 100e-6},
                 "pins": ["pin1", "pin2", "input", "output"],
                 "psim_element_type": "MULTI_INDUCTOR"},
    "Capacitor": {"category": "passive", "korean": "커패시터", "symbol": "C",
                  "default_parameters": {"Capacitance": 100e-6},
                  "pins": ["positive", "negative"],
                  "psim_element_type": "MULTI_CAPACITOR"},
    "Coupled_Inductor": {"category": "passive", "korean": "결합 인덕터", "symbol": "CL",
                         "default_parameters": {"L1": 100e-6, "L2": 100e-6, "coupling": 0.99},
                         "pins": ["L1_pin1", "L1_pin2", "L2_pin1", "L2_pin2"],
                         "psim_element_type": "COUPLED_INDUCTOR"},

    # === Sources ===
    "DC_Source": {"category": "source", "korean": "DC 전원", "symbol": "VDC",
                  "default_parameters": {"Amplitude": 48.0},
                  "pins": ["positive", "negative"],
                  "psim_element_type": "VDC"},
    "AC_Source": {"category": "source", "korean": "AC 전원", "symbol": "VAC",
                  "default_parameters": {"Amplitude": 220.0, "Frequency": 60},
                  "pins": ["positive", "negative"],
                  "psim_element_type": "VAC"},
    "DC_Current_Source": {"category": "source", "korean": "DC 전류원", "symbol": "IDC",
                          "default_parameters": {"Amplitude": 1.0},
                          "pins": ["positive", "negative"],
                          "psim_element_type": "IDC"},
    "AC_Current_Source": {"category": "source", "korean": "AC 전류원", "symbol": "IAC",
                          "default_parameters": {"Amplitude": 1.0, "Frequency": 60},
                          "pins": ["positive", "negative"],
                          "psim_element_type": "IAC"},
    "PV_Panel": {"category": "source", "korean": "태양광 패널", "symbol": "PV",
                 "default_parameters": {"Voc": 40.0, "Isc": 10.0, "Vmp": 32.0, "Imp": 9.0},
                 "pins": ["positive", "negative"],
                 "psim_element_type": "SOLAR_CELL"},

    # === Transformers ===
    "Transformer": {"category": "transformer", "korean": "변압기", "symbol": "XFMR",
                    "default_parameters": {"turns_ratio": 1.0, "Lm": 1e-3},
                    "pins": ["primary_in", "primary_out", "secondary_in", "secondary_out"],
                    "psim_element_type": "TF_1F_1"},
    "Three_Phase_Transformer": {"category": "transformer", "korean": "3상 변압기", "symbol": "3XFMR",
                                 "default_parameters": {"turns_ratio": 1.0, "connection": "Yy"},
                                 "pins": ["primary_a", "primary_b", "primary_c",
                                          "secondary_a", "secondary_b", "secondary_c"],
                                 "psim_element_type": "TRANSFORMER_3P"},
    "Center_Tap_Transformer": {"category": "transformer", "korean": "센터탭 변압기", "symbol": "CTXF",
                                "default_parameters": {"turns_ratio": 1.0},
                                "pins": ["primary_in", "primary_out",
                                         "secondary_top", "secondary_center", "secondary_bottom"],
                                "psim_element_type": "TRANSFORMER_CT"},

    # === Motors ===
    "DC_Motor": {"category": "motor", "korean": "DC 모터", "symbol": "DCM",
                 "default_parameters": {"Ra": 0.5, "La": 5e-3, "Ke": 0.1, "J": 0.01},
                 "pins": ["positive", "negative"],
                 "psim_element_type": "DC_MACHINE"},
    "Induction_Motor": {"category": "motor", "korean": "유도 전동기", "symbol": "IM",
                        "default_parameters": {"poles": 4, "Rs": 0.5, "Rr": 0.4, "Ls": 0.08, "Lr": 0.08, "Lm": 0.075, "J": 0.1},
                        "pins": ["phase_a", "phase_b", "phase_c"],
                        "psim_element_type": "INDUCTION_MACHINE"},
    "PMSM": {"category": "motor", "korean": "영구자석 동기 전동기", "symbol": "PMSM",
             "default_parameters": {"poles": 8, "Rs": 0.1, "Ld": 1e-3, "Lq": 1e-3, "flux": 0.05, "J": 0.01},
             "pins": ["phase_a", "phase_b", "phase_c"],
             "psim_element_type": "PMSM"},
    "BLDC_Motor": {"category": "motor", "korean": "BLDC 모터", "symbol": "BLDC",
                   "default_parameters": {"poles": 8, "Rs": 0.1, "Ls": 1e-3, "Ke": 0.01, "J": 0.005},
                   "pins": ["phase_a", "phase_b", "phase_c"],
                   "psim_element_type": "BLDC"},
    "SRM": {"category": "motor", "korean": "스위치드 릴럭턴스 모터", "symbol": "SRM",
            "default_parameters": {"poles_stator": 8, "poles_rotor": 6, "J": 0.01},
            "pins": ["phase_a", "phase_b", "phase_c"],
            "psim_element_type": "SRM"},

    # === Sensors ===
    "Voltage_Probe": {"category": "sensor", "korean": "전압 프로브", "symbol": "VP",
                      "default_parameters": {},
                      "pins": ["positive", "negative"],
                      "psim_element_type": "VP"},
    "Current_Probe": {"category": "sensor", "korean": "전류 프로브", "symbol": "IP",
                      "default_parameters": {},
                      "pins": ["pin1", "pin2"],
                      "psim_element_type": "IP"},

    # === Filters (composite — built from primitives) ===
    "L_Filter": {"category": "filter", "korean": "L 필터", "symbol": "LF",
                 "default_parameters": {"Inductance": 1e-3},
                 "pins": ["input", "output"],
                 "psim_element_type": "L"},
    "LC_Filter": {"category": "filter", "korean": "LC 필터", "symbol": "LCF",
                  "default_parameters": {"Inductance": 1e-3, "Capacitance": 10e-6},
                  "pins": ["input", "output", "ground"],
                  "psim_element_type": "LC_FILTER"},
    "LCL_Filter": {"category": "filter", "korean": "LCL 필터", "symbol": "LCLF",
                   "default_parameters": {"L1": 1e-3, "C": 10e-6, "L2": 0.5e-3},
                   "pins": ["input", "output", "ground"],
                   "psim_element_type": "LCL_FILTER"},
    "EMI_Filter": {"category": "filter", "korean": "EMI 필터", "symbol": "EMI",
                   "default_parameters": {"Lcm": 1e-3, "Cx": 100e-9, "Cy": 2.2e-9},
                   "pins": ["line_in", "neutral_in", "line_out", "neutral_out", "ground"],
                   "psim_element_type": "EMI_FILTER"},

    # === Control ===
    "PI_Controller": {"category": "control", "korean": "PI 제어기", "symbol": "PI",
                      "default_parameters": {"Kp": 1.0, "Ki": 100.0},
                      "pins": ["input", "output"],
                      "psim_element_type": "PI"},
    "PID_Controller": {"category": "control", "korean": "PID 제어기", "symbol": "PID",
                       "default_parameters": {"Kp": 1.0, "Ki": 100.0, "Kd": 0.001},
                       "pins": ["input", "output"],
                       "psim_element_type": "PID"},
    "PWM_Generator": {"category": "control", "korean": "PWM 생성기", "symbol": "PWM",
                      "default_parameters": {"Frequency": 50000},
                      "pins": ["input", "output"],
                      "psim_element_type": "GATING"},
    "PLL": {"category": "control", "korean": "PLL (위상 동기 루프)", "symbol": "PLL",
            "default_parameters": {"Frequency": 60},
            "pins": ["input", "output"],
            "psim_element_type": "PLL"},

    # === Battery ===
    "Battery": {"category": "storage", "korean": "배터리", "symbol": "BAT",
                "default_parameters": {"voltage": 48.0, "capacity_Ah": 100, "SOC": 0.8},
                "pins": ["positive", "negative"],
                "psim_element_type": "BATTERY"},
    "Supercapacitor": {"category": "storage", "korean": "슈퍼커패시터", "symbol": "SCAP",
                       "default_parameters": {"Capacitance": 100.0, "voltage": 2.7},
                       "pins": ["positive", "negative"],
                       "psim_element_type": "SUPERCAP"},

    # === Thermal ===
    "Heatsink": {"category": "thermal", "korean": "방열판", "symbol": "HS",
                 "default_parameters": {"Rth_sa": 0.5},
                 "pins": ["thermal_in"],
                 "psim_element_type": "HEATSINK"},

    # === Special (PSIM infrastructure) ===
    "Ground": {"category": "special", "korean": "접지", "symbol": "GND",
               "default_parameters": {},
               "pins": ["pin1"],
               "psim_element_type": "Ground"},
    "SimControl": {"category": "special", "korean": "시뮬레이션 설정", "symbol": "SIM",
                   "default_parameters": {"TIMESTEP": "1E-005", "TOTALTIME": "0.1"},
                   "pins": [],
                   "psim_element_type": "SIMCONTROL"},
}

# Backfill empty element mappings with the canonical component type so callers
# always have an explicit bridge-facing element name.
for _type_name, _component in COMPONENTS.items():
    _component["psim_element_type"] = _component.get("psim_element_type") or _type_name

# ---------------------------------------------------------------------------
# Category labels
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, str] = {
    "switch": "스위치 소자",
    "diode": "다이오드",
    "passive": "수동 소자",
    "source": "전원",
    "transformer": "변압기",
    "motor": "모터",
    "sensor": "센서",
    "filter": "필터",
    "control": "제어",
    "storage": "에너지 저장",
    "thermal": "열 관리",
}

# ---------------------------------------------------------------------------
# Lookup index: lowercase kind → canonical type name
# ---------------------------------------------------------------------------

_KIND_INDEX: dict[str, str] = {k.lower(): k for k in COMPONENTS}


# ---------------------------------------------------------------------------
# Public helper functions
# ---------------------------------------------------------------------------


def get_component(kind: str) -> dict | None:
    """Return the component definition dict for a given *kind* (case-insensitive).

    Returns ``None`` if *kind* is not found.
    """
    canonical = _KIND_INDEX.get(kind.lower())
    if canonical is None:
        return None
    return COMPONENTS[canonical]


def validate_kind(kind: str) -> bool:
    """Return ``True`` if *kind* matches a known component type."""
    return kind.lower() in _KIND_INDEX


def validate_pin(kind: str, pin_name: str) -> bool:
    """Return ``True`` if *pin_name* is a valid pin for the given component *kind*."""
    comp = get_component(kind)
    if comp is None:
        return False
    return pin_name in comp.get("pins", [])


def get_default_params(kind: str) -> dict:
    """Return a copy of the default parameter dict for *kind*.

    Returns an empty dict if *kind* is unknown.
    """
    comp = get_component(kind)
    if comp is None:
        return {}
    return dict(comp.get("default_parameters", {}))


def resolve_psim_element_type(kind: str) -> str:
    """Return the explicit PSIM element type for *kind*.

    Unknown component kinds fall back to the provided *kind* so custom
    components continue to flow through the bridge unchanged.
    """
    comp = get_component(kind)
    if comp is None:
        return kind
    return str(comp.get("psim_element_type") or kind)


# ---------------------------------------------------------------------------
# Pin direction registry (centralized)
# ---------------------------------------------------------------------------
# Used by wiring.py, svg_renderer to determine pin placement.

LEFT_PINS: frozenset[str] = frozenset({
    "positive", "drain", "input", "anode", "pin1", "collector",
    "primary_in", "phase_a", "terminal1", "line_in", "L1_pin1",
})

RIGHT_PINS: frozenset[str] = frozenset({
    "negative", "source", "output", "cathode", "pin2", "emitter",
    "primary_out", "secondary_in", "secondary_out", "phase_b", "phase_c",
    "terminal2", "line_out", "neutral_in", "neutral_out", "L1_pin2",
    "L2_pin1", "L2_pin2", "ground", "gate", "control", "thermal_in",
    "secondary_top", "secondary_center", "secondary_bottom",
})


def get_pin_side(pin_name: str) -> str:
    """Return 'left', 'right', or 'center' for a pin name."""
    if pin_name in LEFT_PINS:
        return "left"
    if pin_name in RIGHT_PINS:
        return "right"
    return "center"
