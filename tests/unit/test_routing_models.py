"""Unit tests for Phase 4 routing models."""

from psim_mcp.routing.models import (
    JunctionPoint,
    RoutedSegment,
    RoutingPreference,
    WireRouting,
)


def test_routed_segment_creation():
    seg = RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0)
    assert seg.id == "s1"
    assert seg.net_id == "n1"
    assert seg.x1 == 0 and seg.y1 == 0
    assert seg.x2 == 100 and seg.y2 == 0
    assert seg.role is None
    assert seg.layer is None
    assert seg.metadata == {}


def test_routed_segment_with_role_and_layer():
    seg = RoutedSegment(
        id="s1", net_id="gnd", x1=0, y1=150, x2=350, y2=150,
        role="trunk", layer="ground",
    )
    assert seg.role == "trunk"
    assert seg.layer == "ground"


def test_junction_point_creation():
    jp = JunctionPoint(x=200, y=150, net_id="net_gnd")
    assert jp.x == 200
    assert jp.y == 150
    assert jp.net_id == "net_gnd"


def test_routing_preference_defaults():
    prefs = RoutingPreference()
    assert prefs.style == "schematic"
    assert prefs.use_ground_rail is True
    assert prefs.minimize_crossings is True
    assert prefs.prefer_trunk_branch is True
    assert prefs.ground_rail_y is None


def test_routing_preference_custom():
    prefs = RoutingPreference(ground_rail_y=200, style="compact")
    assert prefs.ground_rail_y == 200
    assert prefs.style == "compact"


def test_wire_routing_creation():
    wr = WireRouting(
        topology="buck",
        segments=[RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0)],
    )
    assert wr.topology == "buck"
    assert len(wr.segments) == 1
    assert wr.junctions == []
    assert wr.metadata == {}


def test_wire_routing_to_dict():
    wr = WireRouting(
        topology="buck",
        segments=[RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0, role="trunk")],
        junctions=[JunctionPoint(x=50, y=0, net_id="n1")],
        metadata={"strategy": "test"},
    )
    d = wr.to_dict()
    assert d["topology"] == "buck"
    assert len(d["segments"]) == 1
    assert d["segments"][0]["id"] == "s1"
    assert d["segments"][0]["role"] == "trunk"
    assert len(d["junctions"]) == 1
    assert d["junctions"][0]["x"] == 50
    assert d["metadata"]["strategy"] == "test"


def test_wire_routing_from_dict_roundtrip():
    original = WireRouting(
        topology="flyback",
        segments=[
            RoutedSegment(id="s1", net_id="n1", x1=10, y1=20, x2=30, y2=20, role="direct"),
            RoutedSegment(id="s2", net_id="n2", x1=40, y1=50, x2=40, y2=100, role="branch", layer="power"),
        ],
        junctions=[JunctionPoint(x=40, y=50, net_id="n2")],
        metadata={"key": "value"},
    )
    d = original.to_dict()
    restored = WireRouting.from_dict(d)

    assert restored.topology == original.topology
    assert len(restored.segments) == len(original.segments)
    assert restored.segments[0].id == "s1"
    assert restored.segments[1].layer == "power"
    assert len(restored.junctions) == 1
    assert restored.junctions[0].x == 40
    assert restored.metadata == {"key": "value"}


def test_wire_routing_to_legacy_segments():
    wr = WireRouting(
        topology="buck",
        segments=[
            RoutedSegment(id="s1", net_id="net_gnd", x1=0, y1=150, x2=350, y2=150, role="trunk"),
            RoutedSegment(id="s2", net_id="net_gnd", x1=200, y1=100, x2=200, y2=150, role="branch"),
        ],
    )
    legacy = wr.to_legacy_segments()
    assert len(legacy) == 2
    assert legacy[0] == {"id": "s1", "net": "net_gnd", "x1": 0, "y1": 150, "x2": 350, "y2": 150}
    assert legacy[1] == {"id": "s2", "net": "net_gnd", "x1": 200, "y1": 100, "x2": 200, "y2": 150}


def test_wire_routing_empty():
    wr = WireRouting(topology="test", segments=[])
    assert wr.to_dict()["segments"] == []
    assert wr.to_legacy_segments() == []


def test_wire_routing_from_dict_empty_optional_fields():
    d = {"topology": "test", "segments": []}
    wr = WireRouting.from_dict(d)
    assert wr.topology == "test"
    assert wr.segments == []
    assert wr.junctions == []
    assert wr.metadata == {}
