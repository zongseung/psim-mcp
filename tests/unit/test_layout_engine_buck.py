"""Tests for the buck converter layout engine."""

import pytest

from psim_mcp.layout import generate_layout
from psim_mcp.layout.models import SchematicLayout
from psim_mcp.synthesis.topologies.buck import synthesize_buck


@pytest.fixture
def buck_requirements():
    return {"vin": 48, "vout_target": 12, "iout": 5, "fsw": 50000}


@pytest.fixture
def buck_graph(buck_requirements):
    return synthesize_buck(buck_requirements)


@pytest.fixture
def buck_layout(buck_graph):
    return generate_layout(buck_graph)


# --- Basic layout tests ---

def test_generate_layout_returns_schematic_layout(buck_layout):
    assert isinstance(buck_layout, SchematicLayout)


def test_layout_topology_is_buck(buck_layout):
    assert buck_layout.topology == "buck"


def test_all_components_have_positions(buck_layout):
    for comp in buck_layout.components:
        assert comp.x != 0 or comp.y != 0, f"{comp.id} has zero position"


def test_all_components_present(buck_graph, buck_layout):
    graph_ids = {c.id for c in buck_graph.components}
    layout_ids = {c.id for c in buck_layout.components}
    assert graph_ids == layout_ids


# --- Direction tests ---

def test_mosfet_direction_270(buck_layout):
    sw1 = buck_layout.get_component("SW1")
    assert sw1 is not None
    assert sw1.direction == 270, "MOSFET should be horizontal (DIR=270)"


def test_inductor_direction_0(buck_layout):
    l1 = buck_layout.get_component("L1")
    assert l1 is not None
    assert l1.direction == 0, "Inductor should be horizontal (DIR=0)"


def test_capacitor_direction_90(buck_layout):
    c1 = buck_layout.get_component("C1")
    assert c1 is not None
    assert c1.direction == 90, "Capacitor should be vertical (DIR=90)"


def test_resistor_direction_90(buck_layout):
    r1 = buck_layout.get_component("R1")
    assert r1 is not None
    assert r1.direction == 90, "Resistor should be vertical (DIR=90)"


def test_diode_direction_270(buck_layout):
    d1 = buck_layout.get_component("D1")
    assert d1 is not None
    assert d1.direction == 270, "Diode should have cathode-up (DIR=270)"


def test_source_direction_0(buck_layout):
    v1 = buck_layout.get_component("V1")
    assert v1 is not None
    assert v1.direction == 0


# --- Region tests ---

def test_input_region_exists(buck_layout):
    r = buck_layout.get_region("input_stage")
    assert r is not None
    assert r.role == "input"


def test_switch_region_exists(buck_layout):
    r = buck_layout.get_region("switch_stage")
    assert r is not None
    assert r.role == "switching"


def test_output_region_exists(buck_layout):
    r = buck_layout.get_region("output_filter")
    assert r is not None
    assert r.role == "output"


# --- Region assignment tests ---

def test_source_in_input_region(buck_layout):
    v1 = buck_layout.get_component("V1")
    assert v1 is not None
    assert v1.region_id == "input_stage"


def test_ground_in_input_region(buck_layout):
    gnd = buck_layout.get_component("GND1")
    assert gnd is not None
    assert gnd.region_id == "input_stage"


def test_switch_in_switch_region(buck_layout):
    sw1 = buck_layout.get_component("SW1")
    assert sw1 is not None
    assert sw1.region_id == "switch_stage"


def test_inductor_in_output_region(buck_layout):
    l1 = buck_layout.get_component("L1")
    assert l1 is not None
    assert l1.region_id == "output_filter"


# --- Symbol variant tests ---

def test_components_have_symbol_variants(buck_layout):
    for comp in buck_layout.components:
        assert comp.symbol_variant is not None, f"{comp.id} missing symbol_variant"


# --- Spatial ordering tests ---

def test_input_left_of_switch(buck_layout):
    v1 = buck_layout.get_component("V1")
    sw1 = buck_layout.get_component("SW1")
    assert v1 is not None and sw1 is not None
    assert v1.x < sw1.x, "Input source should be left of switch"


def test_switch_left_of_output(buck_layout):
    sw1 = buck_layout.get_component("SW1")
    l1 = buck_layout.get_component("L1")
    assert sw1 is not None and l1 is not None
    assert sw1.x < l1.x, "Switch should be left of inductor"


def test_inductor_left_of_or_same_as_capacitor(buck_layout):
    l1 = buck_layout.get_component("L1")
    c1 = buck_layout.get_component("C1")
    assert l1 is not None and c1 is not None
    assert l1.x <= c1.x, "Inductor should be left of or at same x as capacitor"


def test_capacitor_left_of_or_same_as_load(buck_layout):
    c1 = buck_layout.get_component("C1")
    r1 = buck_layout.get_component("R1")
    assert c1 is not None and r1 is not None
    assert c1.x <= r1.x, "Capacitor should be left of or at same x as load"


# --- Ground rail tests ---

def test_ground_at_rail_y(buck_layout):
    gnd = buck_layout.get_component("GND1")
    assert gnd is not None
    assert gnd.y == 150, "Ground should be at y=150"


def test_diode_at_rail_y(buck_layout):
    d1 = buck_layout.get_component("D1")
    assert d1 is not None
    assert d1.y == 150, "Diode anode should be at ground rail y=150"


# --- Constraints tests ---

def test_has_constraints(buck_layout):
    assert len(buck_layout.constraints) > 0


def test_has_left_of_constraints(buck_layout):
    left_of = [c for c in buck_layout.constraints if c.kind == "left_of"]
    assert len(left_of) >= 2


# --- Metadata tests ---

def test_flow_direction_metadata(buck_layout):
    assert buck_layout.metadata.get("flow_direction") == "left_to_right"


def test_algorithm_metadata(buck_layout):
    assert buck_layout.metadata.get("algorithm") == "auto_place_v1"


# --- Error handling ---

def test_unknown_topology_uses_auto_place_fallback():
    """Unknown topologies now fall back to auto_place instead of raising."""
    from psim_mcp.synthesis.graph import CircuitGraph
    from psim_mcp.layout.models import SchematicLayout
    graph = CircuitGraph(topology="unknown_topology", components=[], nets=[])
    layout = generate_layout(graph)
    assert isinstance(layout, SchematicLayout)
    assert layout.topology == "unknown_topology"
