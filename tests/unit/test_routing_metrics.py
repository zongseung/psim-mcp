"""Unit tests for routing quality metrics."""

from psim_mcp.routing.metrics import (
    count_crossings,
    count_duplicates,
    count_junctions,
    routing_quality_report,
    total_wire_length,
)
from psim_mcp.routing.models import (
    JunctionPoint,
    RoutedSegment,
    WireRouting,
)


def _make_routing(segments, junctions=None):
    return WireRouting(
        topology="test",
        segments=segments,
        junctions=junctions or [],
    )


def test_count_duplicates_returns_zero_for_clean_routing():
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0),
        RoutedSegment(id="s2", net_id="n1", x1=100, y1=0, x2=100, y2=100),
    ])
    assert count_duplicates(routing) == 0


def test_count_duplicates_detects_duplicate():
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0),
        RoutedSegment(id="s2", net_id="n1", x1=100, y1=0, x2=0, y2=0),  # reversed duplicate
    ])
    assert count_duplicates(routing) == 1


def test_total_wire_length_sums_correctly():
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0),
        RoutedSegment(id="s2", net_id="n1", x1=100, y1=0, x2=100, y2=50),
    ])
    assert total_wire_length(routing) == 150


def test_total_wire_length_empty():
    routing = _make_routing([])
    assert total_wire_length(routing) == 0


def test_count_junctions():
    routing = _make_routing(
        [],
        junctions=[
            JunctionPoint(x=100, y=0, net_id="n1"),
            JunctionPoint(x=200, y=0, net_id="n1"),
        ],
    )
    assert count_junctions(routing) == 2


def test_count_crossings_perpendicular():
    """Two perpendicular segments from different nets that cross."""
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=50, x2=100, y2=50),  # horizontal
        RoutedSegment(id="s2", net_id="n2", x1=50, y1=0, x2=50, y2=100),  # vertical
    ])
    assert count_crossings(routing) == 1


def test_count_crossings_same_net_not_counted():
    """Segments from the same net should not count as crossings."""
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=50, x2=100, y2=50),
        RoutedSegment(id="s2", net_id="n1", x1=50, y1=0, x2=50, y2=100),
    ])
    assert count_crossings(routing) == 0


def test_count_crossings_parallel_no_crossing():
    """Two parallel segments should not cross."""
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0),
        RoutedSegment(id="s2", net_id="n2", x1=0, y1=50, x2=100, y2=50),
    ])
    assert count_crossings(routing) == 0


def test_routing_quality_report_keys():
    routing = _make_routing([
        RoutedSegment(id="s1", net_id="n1", x1=0, y1=0, x2=100, y2=0),
    ])
    report = routing_quality_report(routing)
    assert set(report.keys()) == {
        "crossings", "duplicates", "total_length", "junctions", "segment_count",
        "unconnected_pins", "orphan_nets", "detour_ratio",
    }
    assert report["segment_count"] == 1
    assert report["total_length"] == 100
