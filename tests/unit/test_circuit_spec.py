"""Tests for CircuitSpec model."""
import pytest
from psim_mcp.models.circuit_spec import CircuitSpec, ComponentSpec, NetSpec, CircuitMetadata, Position

# Test basic creation
def test_circuit_spec_creation():
    spec = CircuitSpec(
        topology="buck",
        metadata=CircuitMetadata(name="test_buck"),
        components=[
            ComponentSpec(id="V1", kind="dc_source", params={"voltage": 48.0}),
            ComponentSpec(id="R1", kind="resistor", params={"resistance": 10.0}),
        ],
        nets=[
            NetSpec(name="VIN", pins=["V1.positive", "R1.pin1"]),
            NetSpec(name="GND", pins=["V1.negative", "R1.pin2"]),
        ],
    )
    assert spec.topology == "buck"
    assert len(spec.components) == 2
    assert len(spec.nets) == 2

# Test from_legacy conversion
def test_from_legacy_buck():
    legacy = {
        "topology": "buck",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 100, "y": 200}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 300, "y": 200}},
        ],
        "connections": [
            {"from": "V1.positive", "to": "R1.input"},
            {"from": "R1.output", "to": "V1.negative"},
        ],
    }
    spec = CircuitSpec.from_legacy(legacy)
    assert spec.topology == "buck"
    assert len(spec.components) == 2
    assert spec.components[0].kind == "dc_source"
    assert spec.components[0].params["voltage"] == 48.0
    assert len(spec.nets) >= 1

# Test to_legacy roundtrip
def test_to_legacy_roundtrip():
    legacy = {
        "topology": "buck",
        "components": [
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}},
            {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}},
        ],
        "connections": [
            {"from": "V1.positive", "to": "R1.pin1"},
        ],
    }
    spec = CircuitSpec.from_legacy(legacy)
    result = spec.to_legacy()
    assert result["topology"] == "buck"
    assert len(result["components"]) == 2

# Test empty components raises or handles gracefully
def test_circuit_spec_empty_components():
    spec = CircuitSpec(
        topology="test",
        metadata=CircuitMetadata(name="empty"),
        components=[],
        nets=[],
    )
    assert len(spec.components) == 0
