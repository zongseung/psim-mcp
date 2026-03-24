"""Unit tests for Phase 4 routing models (RoutedSegment, WireRouting, etc.)."""

from psim_mcp.routing.models import (
    JunctionPoint,
    RoutedSegment,
    RoutingPreference,
    WireRouting,
)


def test_routed_segment_creation():
    s = RoutedSegment(id="seg_1", net_id="net_gnd", x1=100, y1=150, x2=350, y2=150)
    assert s.id == "seg_1"
    assert s.net_id == "net_gnd"
    assert s.role is None


def test_routed_segment_with_role():
    s = RoutedSegment(id="seg_1", net_id="net_gnd", x1=0, y1=0, x2=100, y2=0, role="trunk", layer="ground")
    assert s.role == "trunk"
    assert s.layer == "ground"


def test_junction_point():
    j = JunctionPoint(x=200, y=150, net_id="net_gnd")
    assert j.x == 200
    assert j.y == 150
    assert j.net_id == "net_gnd"


def test_routing_preference_defaults():
    p = RoutingPreference()
    assert p.style == "schematic"
    assert p.use_ground_rail is True
    assert p.minimize_crossings is True
    assert p.prefer_trunk_branch is True
    assert p.ground_rail_y is None


def test_wire_routing_creation():
    segs = [RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0)]
    wr = WireRouting(topology="buck", segments=segs)
    assert wr.topology == "buck"
    assert len(wr.segments) == 1
    assert wr.junctions == []


def test_wire_routing_to_dict():
    wr = WireRouting(
        topology="buck",
        segments=[RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0, role="trunk")],
        junctions=[JunctionPoint(x=50, y=0, net_id="n1")],
        metadata={"strategy": "test"},
    )
    d = wr.to_dict()
    assert d["topology"] == "buck"
    assert d["segments"][0]["role"] == "trunk"
    assert d["junctions"][0]["x"] == 50
    assert d["metadata"]["strategy"] == "test"


def test_wire_routing_from_dict():
    d = {
        "topology": "buck",
        "segments": [{"id": "s1", "net_id": "n1", "x1": 0, "y1": 0, "x2": 100, "y2": 0}],
        "junctions": [{"x": 50, "y": 0, "net_id": "n1"}],
        "metadata": {},
    }
    wr = WireRouting.from_dict(d)
    assert wr.topology == "buck"
    assert len(wr.segments) == 1
    assert wr.segments[0].net_id == "n1"


def test_wire_routing_roundtrip():
    wr = WireRouting(
        topology="flyback",
        segments=[
            RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0, role="trunk"),
            RoutedSegment(id="s2", net_id="n1", x1=50, y1=0, x2=50, y2=50, role="branch"),
        ],
        junctions=[JunctionPoint(x=50, y=0, net_id="n1")],
    )
    d = wr.to_dict()
    wr2 = WireRouting.from_dict(d)
    assert wr2.topology == "flyback"
    assert len(wr2.segments) == 2
    assert wr2.segments[1].role == "branch"


def test_to_legacy_segments():
    wr = WireRouting(
        topology="buck",
        segments=[
            RoutedSegment(id="s1", net_id="net_gnd", x1=120, y1=150, x2=350, y2=150, role="trunk"),
            RoutedSegment(id="s2", net_id="net_gnd", x1=220, y1=150, x2=220, y2=100, role="branch"),
        ],
    )
    legacy = wr.to_legacy_segments()
    assert len(legacy) == 2
    assert legacy[0]["id"] == "s1"
    assert legacy[0]["net"] == "net_gnd"
    assert legacy[0]["x1"] == 120
    assert "role" not in legacy[0]


def test_to_legacy_segments_empty():
    wr = WireRouting(topology="buck", segments=[])
    assert wr.to_legacy_segments() == []
