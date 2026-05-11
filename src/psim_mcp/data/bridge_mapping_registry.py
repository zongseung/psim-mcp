"""Bridge mapping registry -- PSIM element type and parameter mappings.

Centralises the PSIM element type names and parameter name mappings that
the bridge script needs to translate from the MCP component model to PSIM
native element types.  The authoritative source for ``psim_element_type``
values is ``component_library.py``; this module mirrors those mappings in a
flat lookup table and adds parameter-name translation tables.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# PSIM element type map
# Maps MCP canonical component type -> PSIM element type string.
# Values are sourced from component_library.py psim_element_type fields.
# ---------------------------------------------------------------------------

PSIM_TYPE_MAP: dict[str, str] = {
    # Switches
    "MOSFET": "MULTI_MOSFET",
    "IGBT": "MULTI_IGBT",
    "Thyristor": "THYRISTOR",
    "TRIAC": "TRIAC",
    "GTO": "GTO",
    "Ideal_Switch": "SWITCH",
    # Diodes
    "Diode": "MULTI_DIODE",
    "Zener_Diode": "ZENER",
    "Schottky_Diode": "DIODE",
    # Passives
    "Resistor": "MULTI_RESISTOR",
    "Inductor": "MULTI_INDUCTOR",
    "Capacitor": "MULTI_CAPACITOR",
    "Coupled_Inductor": "COUPLED_INDUCTOR",
    # Sources
    "DC_Source": "VDC",
    "AC_Source": "VAC",
    "DC_Current_Source": "IDC",
    "AC_Current_Source": "IAC",
    "PV_Panel": "SOLAR_CELL",
    # Transformers
    "Transformer": "TF_1F_1",
    "Three_Phase_Transformer": "TRANSFORMER_3P",
    "Center_Tap_Transformer": "TRANSFORMER_CT",
    "IdealTransformer": "TF_IDEAL",
    "DiodeBridge": "BDIODE1",
    # Motors
    "DC_Motor": "DC_MACHINE",
    "Induction_Motor": "INDUCTION_MACHINE",
    "PMSM": "PMSM",
    "BLDC_Motor": "BLDC",
    "SRM": "SRM",
    # Sensors
    "Voltage_Probe": "VP",
    "Current_Probe": "IP",
    # Filters
    "L_Filter": "L",
    "LC_Filter": "LC_FILTER",
    "LCL_Filter": "LCL_FILTER",
    "EMI_Filter": "EMI_FILTER",
    # Control
    "PI_Controller": "PI",
    "PID_Controller": "PID",
    "PWM_Generator": "GATING",
    "PLL": "PLL",
    "C_Block": "SIMPLECBLOCK",
    "Label": "LABEL",
    "OnCtrl": "ONCTRL",
    # Storage
    "Battery": "BATTERY",
    "Supercapacitor": "SUPERCAP",
    # Thermal
    "Heatsink": "HEATSINK",
    # Special
    "Ground": "Ground",
    "SimControl": "SIMCONTROL",
}


# ---------------------------------------------------------------------------
# Parameter name map
# Maps MCP parameter names -> PSIM parameter names per component type.
# PSIM often uses short or legacy names (e.g. "V1" for voltage, "R1" for
# resistance).  This table provides the translation.
# ---------------------------------------------------------------------------

PARAMETER_NAME_MAP: dict[str, dict[str, str]] = {
    # PSIM 2026 VDC/VAC use "Amplitude" (not "V1") — confirmed via
    # output/converted_*.py reference scripts (e.g. converted_fullbridge.py
    # line 96: ``Amplitude = "390"``). Sending "V1" silently no-ops and
    # PSIM keeps its default Amplitude=100.
    "DC_Source": {
        "voltage": "Amplitude",
        "amplitude": "Amplitude",
        "Amplitude": "Amplitude",
    },
    "AC_Source": {
        "voltage": "Amplitude",
        "amplitude": "Amplitude",
        "Amplitude": "Amplitude",
        "frequency": "Freq",
        "Frequency": "Freq",
    },
    "Inductor": {
        "inductance": "Inductance",
        "Inductance": "Inductance",
        "CurrentFlag": "Current_Flag",
    },
    "Capacitor": {
        "capacitance": "Capacitance",
        "Capacitance": "Capacitance",
    },
    "Resistor": {
        "resistance": "Resistance",
        "Resistance": "Resistance",
        "VoltageFlag": "Voltage_Flag",
    },
    "MOSFET": {
        "on_resistance": "On_Resistance",
        "switching_frequency": None,  # not a PSIM MULTI_MOSFET parameter
    },
    "IGBT": {
        "on_resistance": "R_transistor",
        "switching_frequency": None,
    },
    "Diode": {
        "forward_voltage": "Diode_Voltage_Drop",
    },
    # Validated from PsimConvertToPython outputs:
    # - output/converted_Flyback_converter_with_peak_current_mode_control.py
    # - output/converted_ResonantLLC_CurrentAndVoltageLoop.py
    "Transformer": {
        "turns_ratio": None,
        "np_turns": "Np__primary_",
        "ns_turns": "Ns__secondary_",
        "magnetizing_inductance": "Lm__magnetizing_",
        "Lm": "Lm__magnetizing_",
    },
    "IdealTransformer": {
        "turns_ratio": None,
        "np_turns": "Np__primary_",
        "ns_turns": "Ns__secondary_",
    },
    "PWM_Generator": {
        "Frequency": "Frequency",
        "NoOfPoints": "No__of_Points",
        "Switching_Points": "Switching_Points",
    },
    # SIMPLECBLOCK creation kwargs map (the C source is NOT a creation
    # parameter — it's set via PsimSetElmValue2 after the element is
    # created — so ``c_code`` is intentionally not surfaced here.
    # The bridge picks it out of the component dict separately.)
    "C_Block": {
        "input_count": "_InputCount",
        "output_count": "_OutputCount",
        "c_code": None,
    },
    "Battery": {
        "voltage": "V1",
        "capacity_Ah": "Capacity",
        "SOC": "SOC",
    },
    "SimControl": {
        "TIMESTEP": "TimeStep",
        "TOTALTIME": "TotalTime",
    },
}


PORT_PIN_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "MOSFET": (("drain", "collector"), ("source", "emitter"), ("gate",)),
    "IGBT": (("collector", "drain"), ("emitter", "source"), ("gate",)),
    "Diode": (("anode",), ("cathode",)),
    "DIODE": (("anode",), ("cathode",)),
    "Schottky_Diode": (("anode",), ("cathode",)),
    "Zener_Diode": (("anode",), ("cathode",)),
    "DC_Source": (("positive", "pin1"), ("negative", "pin2")),
    "AC_Source": (("positive", "pin1"), ("negative", "pin2")),
    "Battery": (("positive", "pin1"), ("negative", "pin2")),
    "DC_Current_Source": (("positive", "pin1"), ("negative", "pin2")),
    "AC_Current_Source": (("positive", "pin1"), ("negative", "pin2")),
    "Inductor": (("pin1", "input"), ("pin2", "output")),
    "Resistor": (("pin1", "input"), ("pin2", "output")),
    "Capacitor": (("positive", "pin1"), ("negative", "pin2")),
    "Ground": (("pin1",),),
    "PWM_Generator": (("output",),),
    "Voltage_Probe": (("positive",),),
    "Current_Probe": (("input",), ("output",)),
    "DiodeBridge": (("ac_pos",), ("ac_neg",), ("dc_pos",), ("dc_neg",)),
    "Transformer": (
        ("primary1", "primary_in"),
        ("primary2", "primary_out"),
        ("secondary1", "secondary_out"),
        ("secondary2", "secondary_in"),
    ),
    "IdealTransformer": (
        ("primary1", "primary_in"),
        ("primary2", "primary_out"),
        ("secondary1", "secondary_out"),
        ("secondary2", "secondary_in"),
    ),
    "Center_Tap_Transformer": (
        ("primary_top",),
        ("primary_center",),
        ("primary_bottom",),
        ("secondary_top",),
        ("secondary_center",),
        ("secondary_bottom",),
    ),
    # 3-pin semiconductors
    "Thyristor": (("anode",), ("cathode",), ("gate",)),
    # Motors (3-phase terminals)
    "Induction_Motor": (("phase_a",), ("phase_b",), ("phase_c",)),
    "PMSM": (("phase_a",), ("phase_b",), ("phase_c",)),
    "BLDC_Motor": (("phase_a",), ("phase_b",), ("phase_c",)),
    # Closed-loop control elements (PSIM native types). Port ordering
    # was confirmed from output/converted_*.py reference schematics.
    # VSEN: PORTS=[V+, V-, Vout]; SUM2: PORTS=[in1, in2, out];
    # COMP: PORTS=[in+, in-, out]; VTRI: PORTS=[pos, neg].
    "Voltage_Sensor": (("positive",), ("negative",), ("output",)),
    "VSEN": (("positive",), ("negative",), ("output",)),
    "Constant": (("output",),),
    "CONSTANT": (("output",),),
    "Summer": (("in1", "input1", "pin1"), ("in2", "input2", "pin2"), ("output",)),
    "Subtractor": (("in1", "input1", "pin1"), ("in2", "input2", "pin2"), ("output",)),
    "SUM2": (("in1", "input1", "pin1"), ("in2", "input2", "pin2"), ("output",)),
    "PI_Controller": (("input",), ("output",)),
    "PI": (("input",), ("output",)),
    "Comparator": (("positive", "in_pos"), ("negative", "in_neg"), ("output",)),
    "COMP": (("positive", "in_pos"), ("negative", "in_neg"), ("output",)),
    "Triangular_Source": (("positive",), ("negative",)),
    "VTRI": (("positive",), ("negative",)),
    "C_Block": (("in1",), ("in2",), ("out1",)),
    "Label": (("pin1",),),
    "OnCtrl": (("input",), ("output",)),
}


def get_bridge_mapping(component_type: str) -> dict | None:
    """Return full bridge mapping dict for *component_type*, or None."""
    psim_type = PSIM_TYPE_MAP.get(component_type)
    param_map = PARAMETER_NAME_MAP.get(component_type, {})
    if psim_type is None:
        return None
    return {
        "psim_element_type": psim_type,
        "parameter_map": dict(param_map),
    }


def get_psim_type(component_type: str) -> str:
    """Return the PSIM element type for a given MCP component type.

    Falls back to the component type itself if no mapping exists.
    """
    return PSIM_TYPE_MAP.get(component_type, component_type)


def get_psim_element_type(component_type: str) -> str:
    """Alias for get_psim_type for API compatibility."""
    return get_psim_type(component_type)


def get_parameter_mapping(component_type: str) -> dict[str, str]:
    """Return parameter name translation dict for *component_type*.

    Returns an empty dict if no mapping is registered.
    """
    return dict(PARAMETER_NAME_MAP.get(component_type, {}))


def get_port_pin_groups(component_type: str) -> tuple[tuple[str, ...], ...]:
    """Return grouped pin aliases used to reconstruct port coordinates."""
    return PORT_PIN_GROUPS.get(component_type, ())
