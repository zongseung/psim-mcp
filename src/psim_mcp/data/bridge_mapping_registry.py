"""Parameter-name mappings shared with the PSIM bridge."""

from __future__ import annotations

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

def get_parameter_mapping(component_type: str) -> dict[str, str]:
    """Return parameter name translation dict for *component_type*.

    Returns an empty dict if no mapping is registered.
    """
    return dict(PARAMETER_NAME_MAP.get(component_type, {}))
