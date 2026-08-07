"""Unit tests for CircuitGraph and related models."""

from psim_mcp.importer.graph import CircuitGraph, GraphComponent, GraphNet


def test_graph_component_creation():
    c = GraphComponent(id="V1", type="DC_Source")
    assert c.id == "V1"
    assert c.type == "DC_Source"
    assert c.role is None


def test_graph_net_creation():
    n = GraphNet(id="net1", pins=["V1.positive", "SW1.drain"])
    assert n.id == "net1"
    assert len(n.pins) == 2


def test_circuit_graph_creation():
    comps = [GraphComponent(id="V1", type="DC_Source")]
    nets = [GraphNet(id="net1", pins=["V1.positive"])]
    g = CircuitGraph(topology="buck", components=comps, nets=nets)
    assert g.topology == "buck"
    assert len(g.components) == 1
    assert len(g.nets) == 1


def test_circuit_graph_to_dict():
    g = CircuitGraph(
        topology="buck",
        components=[GraphComponent(id="V1", type="DC_Source", role="input")],
        nets=[GraphNet(id="net1", pins=["V1.positive"], role="positive")],
    )
    d = g.to_dict()
    assert d["topology"] == "buck"
    assert d["components"][0]["id"] == "V1"
    assert d["nets"][0]["role"] == "positive"


def test_get_net():
    g = CircuitGraph(
        topology="buck",
        components=[],
        nets=[GraphNet(id="GND", pins=["V1.negative"])],
    )
    assert g.get_net("GND").pins == ["V1.negative"]
    assert g.get_net("missing") is None
