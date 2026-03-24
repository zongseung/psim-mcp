"""Unit tests for buck topology synthesizer (CircuitGraph output)."""

from psim_mcp.synthesis.topologies.buck import synthesize_buck
from psim_mcp.validators.graph import is_valid, validate_graph


def _default_reqs():
    return {"vin": 48, "vout_target": 12, "iout": 5}


def test_synthesize_buck_returns_circuit_graph():
    g = synthesize_buck(_default_reqs())
    assert g.topology == "buck"


def test_synthesize_buck_has_8_components():
    g = synthesize_buck(_default_reqs())
    assert len(g.components) == 8


def test_synthesize_buck_has_5_nets():
    g = synthesize_buck(_default_reqs())
    assert len(g.nets) == 5


def test_synthesize_buck_passes_validation():
    g = synthesize_buck(_default_reqs())
    assert is_valid(g)
    issues = validate_graph(g)
    errors = [i for i in issues if i.severity == "error"]
    assert len(errors) == 0


def test_synthesize_buck_components_have_roles():
    g = synthesize_buck(_default_reqs())
    for comp in g.components:
        assert comp.role is not None, f"Component {comp.id} has no role"


def test_synthesize_buck_has_blocks():
    g = synthesize_buck(_default_reqs())
    assert len(g.blocks) >= 3
    block_ids = {b.id for b in g.blocks}
    assert "input_stage" in block_ids
    assert "switch_stage" in block_ids
    assert "output_filter" in block_ids


def test_synthesize_buck_nets_have_roles():
    g = synthesize_buck(_default_reqs())
    for net in g.nets:
        assert net.role is not None, f"Net {net.id} has no role"


def test_synthesize_buck_has_design_values():
    g = synthesize_buck(_default_reqs())
    assert "duty" in g.design
    assert "inductance" in g.design
    assert "capacitance" in g.design
    assert g.design["duty"] == 0.25  # 12/48


def test_synthesize_buck_has_traces():
    g = synthesize_buck(_default_reqs())
    assert len(g.traces) >= 3
    trace_keys = {t.key for t in g.traces}
    assert "duty" in trace_keys
    assert "inductance" in trace_keys


def test_synthesize_buck_components_in_blocks():
    g = synthesize_buck(_default_reqs())
    for comp in g.components:
        assert len(comp.block_ids) > 0, f"Component {comp.id} not in any block"
