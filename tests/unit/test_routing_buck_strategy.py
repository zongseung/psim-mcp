"""Unit tests for BuckRoutingStrategy."""

from psim_mcp.layout.auto_placer import auto_place
from psim_mcp.routing.engine import generate_routing
from psim_mcp.routing.metrics import count_duplicates, routing_quality_report
from psim_mcp.routing.strategies.buck import BuckRoutingStrategy
from psim_mcp.synthesis.topologies.buck import synthesize_buck


def _make_buck_graph_and_layout():
    """Create a buck CircuitGraph and SchematicLayout for testing."""
    graph = synthesize_buck({"vin": 48, "vout_target": 12, "iout": 2})
    layout = auto_place(graph)
    return graph, layout


def test_buck_strategy_returns_wire_routing():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    assert routing.topology == "buck"
    assert len(routing.segments) > 0


def test_buck_strategy_produces_segments_for_all_routable_nets():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    routed_net_ids = {seg.net_id for seg in routing.segments}
    # All nets should produce at least some segments
    for net in graph.nets:
        assert net.id in routed_net_ids, f"Net {net.id} has no segments"


def test_buck_ground_net_uses_horizontal_trunk():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    gnd_segments = [s for s in routing.segments if s.net_id == "net_gnd"]
    trunk_segs = [s for s in gnd_segments if s.role == "trunk"]
    # Ground net has 5 pins so should have trunk
    assert len(trunk_segs) >= 1
    for trunk in trunk_segs:
        assert trunk.y1 == trunk.y2  # horizontal


def test_buck_no_duplicate_segments():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    assert count_duplicates(routing) == 0


def test_buck_has_junctions():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    # Multi-pin nets should produce junctions
    assert len(routing.junctions) > 0


def test_buck_segments_have_layer_metadata():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    layers = {seg.layer for seg in routing.segments if seg.layer is not None}
    assert "ground" in layers
    assert "power" in layers


def test_buck_metadata_contains_strategy():
    graph, layout = _make_buck_graph_and_layout()
    strategy = BuckRoutingStrategy()
    routing = strategy.route(graph, layout)

    assert routing.metadata["strategy"] == "buck_trunk_branch"


def test_buck_via_generate_routing_dispatch():
    """Test that generate_routing dispatches to BuckRoutingStrategy."""
    graph, layout = _make_buck_graph_and_layout()
    routing = generate_routing(graph, layout)

    assert routing.topology == "buck"
    assert len(routing.segments) > 0


def test_buck_quality_report():
    graph, layout = _make_buck_graph_and_layout()
    routing = generate_routing(graph, layout)
    report = routing_quality_report(routing)

    assert "crossings" in report
    assert "duplicates" in report
    assert "total_length" in report
    assert "junctions" in report
    assert "segment_count" in report
    assert report["duplicates"] == 0
    assert report["total_length"] > 0


def test_buck_to_legacy_segments_format():
    graph, layout = _make_buck_graph_and_layout()
    routing = generate_routing(graph, layout)
    legacy = routing.to_legacy_segments()

    # Legacy count >= original segments because trunks are split at junctions
    assert len(legacy) >= len(routing.segments)
    for seg in legacy:
        assert "id" in seg
        assert "net" in seg
        assert "x1" in seg and "y1" in seg
        assert "x2" in seg and "y2" in seg
