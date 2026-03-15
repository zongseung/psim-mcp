"""Spec-to-component parameter mapping rules.

Maps high-level specification keys (like V_in, R_load) to specific
component types and their parameter names. Used as a fallback when
the generator path is not available.
"""

from __future__ import annotations

SPEC_MAP: dict[str, list[tuple[str, str]]] = {
    "V_in": [("DC_Source", "voltage")],
    "v_in": [("DC_Source", "voltage")],
    "vin": [("DC_Source", "voltage")],
    "voltage": [("DC_Source", "voltage")],
    "R_load": [("Resistor", "resistance")],
    "r_load": [("Resistor", "resistance")],
    "resistance": [("Resistor", "resistance")],
    "load": [("Resistor", "resistance")],
    "load_resistance": [("Resistor", "resistance")],
    "switching_frequency": [("MOSFET", "switching_frequency")],
    "frequency": [("MOSFET", "switching_frequency")],
    "freq": [("MOSFET", "switching_frequency")],
    "fsw": [("MOSFET", "switching_frequency")],
    "inductance": [("Inductor", "inductance")],
    "L": [("Inductor", "inductance")],
    "capacitance": [("Capacitor", "capacitance")],
    "C": [("Capacitor", "capacitance")],
    "forward_voltage": [("Diode", "forward_voltage")],
    "on_resistance": [("MOSFET", "on_resistance")],
}


def apply_specs(components: list[dict], specs: dict) -> None:
    """Apply high-level specs to template components in-place.

    Handles both mapped keys (V_in -> DC_Source.voltage) and derived
    values (V_out + I_load -> R_load).
    """
    v_out = specs.get("V_out") or specs.get("v_out") or specs.get("vout_target")
    i_load = specs.get("I_load") or specs.get("i_load") or specs.get("iout")
    if v_out and i_load and "R_load" not in specs and "r_load" not in specs:
        specs["R_load"] = v_out / i_load

    for key, value in specs.items():
        targets = SPEC_MAP.get(key)
        if not targets:
            continue
        for comp_type, param_name in targets:
            for comp in components:
                if comp.get("type") == comp_type:
                    comp.setdefault("parameters", {})[param_name] = value
                    break
