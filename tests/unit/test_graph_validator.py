"""Unit tests for graph validation."""

from psim_mcp.synthesis.graph import CircuitGraph, GraphComponent, GraphNet
from psim_mcp.validators.graph import GraphValidationIssue, is_valid, validate_graph


def _buck_graph():
    """Create a minimal valid buck graph for testing."""
    return CircuitGraph(
        topology="buck",
        components=[
            GraphComponent(id="V1", type="DC_Source"),
            GraphComponent(id="SW1", type="MOSFET"),
        ],
        nets=[
            GraphNet(id="net1", pins=["V1.positive", "SW1.drain"]),
        ],
    )


def test_valid_graph_no_issues():
    g = _buck_graph()
    issues = validate_graph(g)
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0


def test_is_valid_returns_true():
    g = _buck_graph()
    assert is_valid(g) is True


def test_empty_components_error():
    g = CircuitGraph(topology="buck", components=[], nets=[GraphNet(id="n1", pins=[])])
    issues = validate_graph(g)
    codes = [i.code for i in issues]
    assert "EMPTY_COMPONENTS" in codes


def test_empty_nets_error():
    g = CircuitGraph(topology="buck", components=[GraphComponent(id="V1", type="DC_Source")], nets=[])
    issues = validate_graph(g)
    codes = [i.code for i in issues]
    assert "EMPTY_NETS" in codes


def test_duplicate_component_id():
    g = CircuitGraph(
        topology="buck",
        components=[
            GraphComponent(id="V1", type="DC_Source"),
            GraphComponent(id="V1", type="DC_Source"),
        ],
        nets=[GraphNet(id="n1", pins=["V1.positive"])],
    )
    issues = validate_graph(g)
    dup_issues = [i for i in issues if i.code == "DUPLICATE_COMPONENT_ID"]
    assert len(dup_issues) == 1


def test_dangling_pin_reference():
    g = CircuitGraph(
        topology="buck",
        components=[GraphComponent(id="V1", type="DC_Source")],
        nets=[GraphNet(id="n1", pins=["V1.positive", "X1.pin1"])],
    )
    issues = validate_graph(g)
    dangling = [i for i in issues if i.code == "DANGLING_PIN_REF"]
    assert len(dangling) == 1
    assert "X1" in dangling[0].message


def test_invalid_pin_format_warning():
    g = CircuitGraph(
        topology="buck",
        components=[GraphComponent(id="V1", type="DC_Source")],
        nets=[GraphNet(id="n1", pins=["invalid_no_dot"])],
    )
    issues = validate_graph(g)
    fmt = [i for i in issues if i.code == "INVALID_PIN_FORMAT"]
    assert len(fmt) == 1


def test_is_valid_false_on_error():
    g = CircuitGraph(topology="buck", components=[], nets=[])
    assert is_valid(g) is False


def test_multiple_valid_nets():
    g = CircuitGraph(
        topology="buck",
        components=[
            GraphComponent(id="V1", type="DC_Source"),
            GraphComponent(id="SW1", type="MOSFET"),
            GraphComponent(id="L1", type="Inductor"),
        ],
        nets=[
            GraphNet(id="n1", pins=["V1.positive", "SW1.drain"]),
            GraphNet(id="n2", pins=["SW1.source", "L1.pin1"]),
        ],
    )
    issues = validate_graph(g)
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0


def test_validation_issue_dataclass():
    issue = GraphValidationIssue(severity="error", code="TEST", message="test msg", component_id="V1")
    assert issue.severity == "error"
    assert issue.component_id == "V1"
