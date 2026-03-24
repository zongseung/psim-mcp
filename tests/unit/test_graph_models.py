"""Unit tests for CircuitGraph and related models."""

from psim_mcp.synthesis.graph import (
    CircuitGraph,
    DesignDecisionTrace,
    FunctionalBlock,
    GraphComponent,
    GraphNet,
)
from psim_mcp.synthesis.graph_builders import (
    make_block,
    make_component,
    make_net,
    make_trace,
)


def test_graph_component_creation():
    c = GraphComponent(id="V1", type="DC_Source")
    assert c.id == "V1"
    assert c.type == "DC_Source"
    assert c.role is None
    assert c.tags == []


def test_graph_component_with_role():
    c = GraphComponent(id="V1", type="DC_Source", role="input_source")
    assert c.role == "input_source"


def test_graph_net_creation():
    n = GraphNet(id="net1", pins=["V1.positive", "SW1.drain"])
    assert n.id == "net1"
    assert len(n.pins) == 2


def test_functional_block():
    b = FunctionalBlock(id="input_stage", type="input", component_ids=["V1", "GND1"])
    assert b.id == "input_stage"
    assert len(b.component_ids) == 2


def test_design_decision_trace():
    t = DesignDecisionTrace(source="formula", key="duty", value=0.25)
    assert t.source == "formula"
    assert t.confidence is None


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


def test_circuit_graph_from_dict_roundtrip():
    g = CircuitGraph(
        topology="buck",
        components=[GraphComponent(id="V1", type="DC_Source", role="input")],
        nets=[GraphNet(id="net1", pins=["V1.positive"])],
        blocks=[FunctionalBlock(id="blk1", type="input", component_ids=["V1"])],
        traces=[DesignDecisionTrace(source="formula", key="duty", value=0.25)],
        design={"duty": 0.25},
    )
    d = g.to_dict()
    g2 = CircuitGraph.from_dict(d)
    assert g2.topology == "buck"
    assert g2.components[0].role == "input"
    assert g2.blocks[0].component_ids == ["V1"]
    assert g2.traces[0].value == 0.25
    assert g2.design["duty"] == 0.25


def test_get_component():
    g = CircuitGraph(
        topology="buck",
        components=[
            GraphComponent(id="V1", type="DC_Source"),
            GraphComponent(id="L1", type="Inductor"),
        ],
        nets=[],
    )
    assert g.get_component("V1").type == "DC_Source"
    assert g.get_component("L1").type == "Inductor"
    assert g.get_component("X1") is None


def test_components_in_block():
    g = CircuitGraph(
        topology="buck",
        components=[
            GraphComponent(id="V1", type="DC_Source", block_ids=["input"]),
            GraphComponent(id="GND1", type="Ground", block_ids=["input"]),
            GraphComponent(id="L1", type="Inductor", block_ids=["filter"]),
        ],
        nets=[],
    )
    input_comps = g.components_in_block("input")
    assert len(input_comps) == 2
    assert {c.id for c in input_comps} == {"V1", "GND1"}


def test_make_component_helper():
    c = make_component("V1", "DC_Source", role="input_source", parameters={"voltage": 48})
    assert c.id == "V1"
    assert c.role == "input_source"
    assert c.parameters["voltage"] == 48


def test_make_net_helper():
    n = make_net("net1", ["V1.positive", "SW1.drain"], role="input_positive")
    assert n.id == "net1"
    assert n.role == "input_positive"


def test_make_block_helper():
    b = make_block("blk1", "input", role="input", component_ids=["V1"])
    assert b.id == "blk1"
    assert b.component_ids == ["V1"]


def test_make_trace_helper():
    t = make_trace("formula", "duty", 0.25, confidence=0.99, rationale="D=Vout/Vin")
    assert t.source == "formula"
    assert t.confidence == 0.99
    assert t.rationale == "D=Vout/Vin"
