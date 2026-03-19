"""Unit tests for SVG preview rendering."""

from __future__ import annotations

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
