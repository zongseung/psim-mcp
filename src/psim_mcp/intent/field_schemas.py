"""Declarative JSON Schema fragments for MCP elicitation fields."""

from __future__ import annotations

FIELD_SCHEMA_REGISTRY: dict[str, dict] = {
    "vin": {
        "type": "number",
        "description": "Input voltage in volts.",
        "minimum": 0.001,
        "maximum": 100000,
    },
    "vout_target": {
        "type": "number",
        "description": "Target output voltage in volts.",
        "minimum": 0.001,
        "maximum": 100000,
    },
    "iout": {
        "type": "number",
        "description": "Output current in amps.",
        "minimum": 0.000001,
        "maximum": 100000,
    },
    "fsw": {
        "type": "number",
        "description": "Switching frequency in hertz.",
        "minimum": 1,
        "maximum": 100000000,
        "default": 50000,
    },
    "switching_frequency": {
        "type": "number",
        "description": "Switching frequency in hertz.",
        "minimum": 1,
        "maximum": 100000000,
        "default": 50000,
    },
    "power_rating": {
        "type": "number",
        "description": "Rated output power in watts.",
        "minimum": 0.001,
        "maximum": 100000000,
    },
    "load_resistance": {
        "type": "number",
        "description": "Load resistance in ohms.",
        "minimum": 0.001,
        "maximum": 100000000,
    },
    "output_frequency": {
        "type": "number",
        "description": "Output frequency in hertz.",
        "minimum": 0.001,
        "maximum": 1000000,
        "default": 60,
    },
    "voc": {
        "type": "number",
        "description": "PV open-circuit voltage in volts.",
        "minimum": 0.001,
        "maximum": 100000,
    },
    "isc": {
        "type": "number",
        "description": "PV short-circuit current in amps.",
        "minimum": 0.000001,
        "maximum": 100000,
    },
    "vmp": {
        "type": "number",
        "description": "PV maximum-power voltage in volts.",
        "minimum": 0.001,
        "maximum": 100000,
    },
    "imp": {
        "type": "number",
        "description": "PV maximum-power current in amps.",
        "minimum": 0.000001,
        "maximum": 100000,
    },
    "grid_voltage": {
        "type": "number",
        "description": "Grid voltage in volts.",
        "minimum": 0.001,
        "maximum": 100000,
    },
}


def schema_for_field(field: str) -> dict:
    """Return a JSON Schema property for *field*."""
    return dict(
        FIELD_SCHEMA_REGISTRY.get(
            field,
            {
                "type": "number",
                "description": f"{field} value.",
            },
        )
    )
