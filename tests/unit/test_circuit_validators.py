"""Tests for circuit validation (psim_mcp.validators)."""
from psim_mcp.validators import validate_circuit


def test_valid_buck_circuit():
    spec = {
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000}},
            {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}},
            {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}},
        ],
        "nets": [],
    }
    result = validate_circuit(spec)
    assert result.is_valid


def test_empty_components():
    result = validate_circuit({"components": [], "nets": []})
    assert not result.is_valid
    assert any(e.code == "STRUCT_EMPTY" for e in result.errors)


def test_duplicate_ids():
    spec = {
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48}},
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 24}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10}},
        ],
        "nets": [],
    }
    result = validate_circuit(spec)
    assert not result.is_valid
    assert any(e.code == "STRUCT_DUP_ID" for e in result.errors)


def test_no_source():
    spec = {
        "components": [
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 1e-3}},
        ],
        "nets": [],
    }
    result = validate_circuit(spec)
    assert not result.is_valid
    assert any(e.code == "ELEC_NO_SOURCE" for e in result.errors)


def test_no_load():
    spec = {
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48}},
            {"id": "SW1", "type": "MOSFET", "parameters": {"switching_frequency": 50000}},
        ],
        "nets": [],
    }
    result = validate_circuit(spec)
    # NO_LOAD is a warning, not an error in the electrical validator
    assert any(w.code == "ELEC_NO_LOAD" for w in result.warnings)


def test_negative_resistance():
    spec = {
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": -10}},
        ],
        "nets": [],
    }
    result = validate_circuit(spec)
    assert not result.is_valid
    assert any(e.code == "PARAM_NEGATIVE" for e in result.errors)
