"""Unit tests for SVG preview rendering."""

from __future__ import annotations

from psim_mcp.data.component_library import build_port_pin_map
from psim_mcp.utils.svg_renderer import _build_pin_positions, render_circuit_svg


def test_render_circuit_svg_accepts_nets_for_shared_junction():
    components = [
        {
            "id": "V1",
            "type": "DC_Source",
            "parameters": {"voltage": 48.0},
            "position": {"x": 0, "y": 40},
        },
        {
            "id": "L1",
            "type": "Inductor",
            "parameters": {"inductance": 100e-6},
            "position": {"x": 120, "y": 40},
        },
        {
            "id": "C1",
            "type": "Capacitor",
            "parameters": {"capacitance": 100e-6},
            "position": {"x": 240, "y": 100},
        },
    ]
    nets = [
        {"name": "vin_bus", "pins": ["V1.positive", "L1.pin1", "C1.positive"]},
        {"name": "gnd", "pins": ["V1.negative", "L1.pin2", "C1.negative"]},
    ]

    svg = render_circuit_svg("custom", components, connections=[], nets=nets)

    assert "<svg" in svg
    assert "stroke=\"#2980b9\"" in svg
    assert "fill=\"#2980b9\"" in svg


def test_render_circuit_svg_handles_three_pin_component():
    components = [
        {
            "id": "SW1",
            "type": "MOSFET",
            "parameters": {"switching_frequency": 50000},
            "position": {"x": 100, "y": 50},
        },
        {
            "id": "D1",
            "type": "Diode",
            "parameters": {"forward_voltage": 0.7},
            "position": {"x": 240, "y": 50},
        },
    ]
    connections = [
        {"from": "SW1.drain", "to": "D1.anode"},
        {"from": "SW1.source", "to": "D1.cathode"},
    ]

    svg = render_circuit_svg("custom", components, connections=connections)

    assert "SW1" in svg
    assert "D1" in svg
    assert svg.count("stroke=\"#2980b9\"") >= 1


def test_build_pin_positions_coalesces_alias_pins_on_two_terminal_parts():
    components = [
        {
            "id": "L1",
            "type": "Inductor",
            "parameters": {"inductance": 100e-6},
            "position": {"x": 120, "y": 40},
        },
        {
            "id": "R1",
            "type": "Resistor",
            "parameters": {"resistance": 10.0},
            "position": {"x": 240, "y": 40},
        },
    ]

    pin_positions = _build_pin_positions(components)

    assert pin_positions["L1.pin1"] == pin_positions["L1.input"]
    assert pin_positions["L1.pin2"] == pin_positions["L1.output"]
    assert pin_positions["R1.pin1"] == pin_positions["R1.input"]
    assert pin_positions["R1.pin2"] == pin_positions["R1.output"]


def test_build_pin_positions_uses_transformer_ports():
    components = [
        {
            "id": "T1",
            "type": "Transformer",
            "parameters": {"turns_ratio": 0.25},
            "position": {"x": 200, "y": 80},
            "ports": [200, 80, 200, 130, 250, 130, 250, 80],
        }
    ]

    pin_positions = _build_pin_positions(components)

    assert pin_positions["T1.primary_in"] == (200, 80)
    assert pin_positions["T1.primary_out"] == (200, 130)
    assert pin_positions["T1.secondary_out"] == (250, 130)
    assert pin_positions["T1.secondary_in"] == (250, 80)


def test_build_port_pin_map_centralizes_aliases():
    pin_map = build_port_pin_map(
        {
            "id": "SW1",
            "type": "IGBT",
            "ports": [10, 20, 40, 20, 25, 45],
        }
    )

    assert pin_map["SW1.collector"] == (10, 20)
    assert pin_map["SW1.drain"] == (10, 20)
    assert pin_map["SW1.emitter"] == (40, 20)
    assert pin_map["SW1.source"] == (40, 20)
    assert pin_map["SW1.gate"] == (25, 45)


def test_render_circuit_svg_uses_special_symbols_for_transformer_and_ground():
    components = [
        {
            "id": "GND1",
            "type": "Ground",
            "parameters": {},
            "position": {"x": 80, "y": 230},
            "ports": [80, 230],
        },
        {
            "id": "T1",
            "type": "Transformer",
            "parameters": {"turns_ratio": 0.25},
            "position": {"x": 200, "y": 80},
            "ports": [200, 80, 200, 130, 250, 130, 250, 80],
        },
    ]

    svg = render_circuit_svg("custom", components, connections=[])

    assert "Ground</text>" not in svg
    assert "Transfor" not in svg
    assert "T1" in svg
    assert "GND1" in svg
    assert ">P</text>" in svg
    assert ">S</text>" in svg
    assert svg.count("line x1=\"0\" y1=\"0\" x2=\"0\" y2=\"12\"") == 0


def test_render_circuit_svg_renders_auto_gnd_when_no_ground_component_exists():
    components = [
        {
            "id": "V1",
            "type": "DC_Source",
            "parameters": {"voltage": 48},
            "position": {"x": 20, "y": 20},
            "ports": [20, 35, 100, 35, 100, 75],
        }
    ]

    svg = render_circuit_svg("custom", components, connections=[])

    assert "V1" in svg
    assert 'line x1="0" y1="0" x2="0" y2="12"' in svg
