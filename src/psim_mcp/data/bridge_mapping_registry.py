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
    "DC_Source": {
        "voltage": "V1",
        "Amplitude": "V1",
    },
    "AC_Source": {
        "voltage": "V1",
        "Amplitude": "V1",
        "Frequency": "Freq",
    },
    "Inductor": {
        "inductance": "L1",
        "Inductance": "L1",
        "CurrentFlag": "CurrentFlag",
    },
    "Capacitor": {
        "capacitance": "C1",
        "Capacitance": "C1",
    },
    "Resistor": {
        "resistance": "R1",
        "Resistance": "R1",
        "VoltageFlag": "VoltageFlag",
    },
    "MOSFET": {
        "on_resistance": "Ron",
        "switching_frequency": "Freq",
    },
    "IGBT": {
        "on_resistance": "Ron",
        "switching_frequency": "Freq",
    },
    "Diode": {
        "forward_voltage": "Vd",
    },
    "Transformer": {
        "turns_ratio": "Ratio",
        "np_turns": "N1",
        "ns_turns": "N2",
        "magnetizing_inductance": "Lm",
        "Lm": "Lm",
    },
    "IdealTransformer": {
        "turns_ratio": "Ratio",
        "np_turns": "N1",
        "ns_turns": "N2",
    },
    "PWM_Generator": {
        "Frequency": "Freq",
        "NoOfPoints": "NoOfPoints",
        "Switching_Points": "Points",
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
