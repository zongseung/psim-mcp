"""Tests for the flyback converter layout engine."""

import pytest

from psim_mcp.layout import generate_layout
from psim_mcp.layout.models import SchematicLayout
from psim_mcp.synthesis.topologies.flyback import synthesize_flyback


@pytest.fixture
def flyback_requirements():
    return {"vin": 400, "vout_target": 12, "iout": 3, "fsw": 100000}


@pytest.fixture
def flyback_graph(flyback_requirements):
    return synthesize_flyback(flyback_requirements)


@pytest.fixture
def flyback_layout(flyback_graph):
    return generate_layout(flyback_graph)


# --- Basic tests ---

def test_returns_schematic_layout(flyback_layout):
    assert isinstance(flyback_layout, SchematicLayout)


def test_topology_is_flyback(flyback_layout):
    assert flyback_layout.topology == "flyback"


def test_all_components_present(flyback_graph, flyback_layout):
    graph_ids = {c.id for c in flyback_graph.components}
    layout_ids = {c.id for c in flyback_layout.components}
    assert graph_ids == layout_ids


def test_all_components_have_positions(flyback_layout):
    for comp in flyback_layout.components:
        assert comp.x != 0 or comp.y != 0, f"{comp.id} at origin"


# --- Region tests ---

def test_primary_region_exists(flyback_layout):
    r = flyback_layout.get_region("primary_input")
    assert r is not None
    assert r.role == "input"


def test_secondary_region_exists(flyback_layout):
    r = flyback_layout.get_region("output_filter")
    assert r is not None
    assert r.role == "output"


# --- Primary-left, secondary-right ordering ---

def test_primary_components_left_of_transformer(flyback_layout):
    v1 = flyback_layout.get_component("V1")
    t1 = flyback_layout.get_component("T1")
    assert v1 is not None and t1 is not None
    assert v1.x < t1.x, "Input source should be left of transformer"


def test_secondary_components_right_of_transformer(flyback_layout):
    t1 = flyback_layout.get_component("T1")
    d1 = flyback_layout.get_component("D1")
    assert t1 is not None and d1 is not None
    assert d1.x > t1.x, "Secondary diode should be right of transformer"


def test_output_cap_right_of_diode(flyback_layout):
    d1 = flyback_layout.get_component("D1")
    c1 = flyback_layout.get_component("C1")
    assert d1 is not None and c1 is not None
    assert c1.x > d1.x


def test_load_right_of_or_same_as_cap(flyback_layout):
    c1 = flyback_layout.get_component("C1")
    r1 = flyback_layout.get_component("R1")
    assert c1 is not None and r1 is not None
    assert r1.x >= c1.x


# --- Region assignment ---

def test_source_in_primary_region(flyback_layout):
    v1 = flyback_layout.get_component("V1")
    assert v1 is not None
    assert v1.region_id == "primary_input"


def test_diode_in_secondary_region(flyback_layout):
    d1 = flyback_layout.get_component("D1")
    assert d1 is not None
    assert d1.region_id == "secondary_rectifier_block"


# --- Symbol variants ---

def test_components_have_symbol_variants(flyback_layout):
    for comp in flyback_layout.components:
        assert comp.symbol_variant is not None, f"{comp.id} missing variant"


# --- Constraints ---

def test_has_left_of_constraint(flyback_layout):
    left_of = [c for c in flyback_layout.constraints if c.kind == "left_of"]
    assert len(left_of) >= 1


# --- Metadata ---

def test_algorithm_metadata(flyback_layout):
    assert flyback_layout.metadata.get("algorithm") == "auto_place_v1"
