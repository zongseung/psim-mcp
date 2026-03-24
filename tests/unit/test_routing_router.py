"""Unit tests for canonical wire routing helpers."""

from psim_mcp.routing import (
    prepare_components_for_layout,
    resolve_wire_segments,
    route_nets_to_segments,
    segments_to_junctions,
)


def _sample_components() -> list[dict]:
    return [
        {
            "id": "SW1",
            "type": "MOSFET",
            "parameters": {"switching_frequency": 50000},
            "position": {"x": 200, "y": 100},
            "ports": [200, 100, 200, 150, 180, 130],
        },
        {
            "id": "Lf",
            "type": "Inductor",
            "parameters": {"inductance": 100e-6},
            "position": {"x": 260, "y": 130},
            "position2": {"x": 310, "y": 130},
            "ports": [260, 130, 310, 130],
        },
        {
            "id": "SW2",
            "type": "MOSFET",
            "parameters": {"switching_frequency": 50000},
            "position": {"x": 200, "y": 160},
            "ports": [200, 160, 200, 210, 180, 190],
        },
    ]


def test_route_nets_to_segments_builds_bridge_compatible_orthogonal_segments():
    nets = [{"name": "bridge_mid", "pins": ["Lf.pin1", "SW1.source", "SW2.drain"]}]

    segments = route_nets_to_segments(_sample_components(), nets)

    assert segments == [
        {"id": "wire_1", "net": "bridge_mid", "x1": 260, "y1": 130, "x2": 200, "y2": 130},
        {"id": "wire_2", "net": "bridge_mid", "x1": 200, "y1": 130, "x2": 200, "y2": 150},
        {"id": "wire_3", "net": "bridge_mid", "x1": 200, "y1": 150, "x2": 200, "y2": 160},
    ]


def test_resolve_wire_segments_prefers_explicit_geometry():
    explicit = [{"x1": 1, "y1": 2, "x2": 3, "y2": 4}]
    nets = [{"name": "n1", "pins": ["A.pin1", "B.pin1"]}]

    segments = resolve_wire_segments(
        components=[],
        nets=nets,
        wire_segments=explicit,
    )

    assert segments == [{"id": "wire_1", "net": None, "x1": 1, "y1": 2, "x2": 3, "y2": 4}]


def test_segments_to_junctions_returns_shared_endpoints_only():
    wire_segments = [
        {"x1": 10, "y1": 10, "x2": 20, "y2": 10},
        {"x1": 20, "y1": 10, "x2": 20, "y2": 20},
        {"x1": 20, "y1": 20, "x2": 30, "y2": 20},
    ]

    assert segments_to_junctions(wire_segments) == [(20, 10), (20, 20)]


def test_resolve_wire_segments_dedupes_duplicate_segments():
    segments = resolve_wire_segments(
        components=[],
        wire_segments=[
            {"x1": 10, "y1": 10, "x2": 20, "y2": 10, "net": "n1"},
            {"x1": 20, "y1": 10, "x2": 10, "y2": 10, "net": "n1"},
        ],
    )

    assert segments == [{"id": "wire_1", "net": "n1", "x1": 10, "y1": 10, "x2": 20, "y2": 10}]


def test_prepare_components_for_layout_rotates_shunt_parts_from_connections():
    components = [
        {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 40, "y": 120}},
        {"id": "D1", "type": "Diode", "parameters": {"forward_voltage": 0.7}, "position": {"x": 180, "y": 190}},
        {"id": "L1", "type": "Inductor", "parameters": {"inductance": 47e-6}, "position": {"x": 340, "y": 50}},
        {"id": "C1", "type": "Capacitor", "parameters": {"capacitance": 100e-6}, "position": {"x": 500, "y": 190}},
        {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 500, "y": 50}},
    ]
    connections = [
        {"from": "V1.positive", "to": "L1.pin1"},
        {"from": "L1.pin2", "to": "R1.pin1"},
        {"from": "L1.pin2", "to": "C1.positive"},
        {"from": "D1.anode", "to": "V1.negative"},
        {"from": "R1.pin2", "to": "V1.negative"},
        {"from": "C1.negative", "to": "V1.negative"},
    ]

    prepared = prepare_components_for_layout(components, connections=connections)
    directions = {component["id"]: component.get("direction", 0) for component in prepared}

    assert directions["V1"] in {90, 270}
    assert directions["D1"] in {90, 270}
    assert directions["C1"] in {90, 270}
    assert directions["R1"] in {90, 270}
    assert directions["L1"] == 0
