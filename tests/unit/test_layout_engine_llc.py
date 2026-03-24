"""Tests for the LLC resonant converter layout engine."""

import pytest

from psim_mcp.layout import generate_layout
from psim_mcp.layout.models import SchematicLayout
from psim_mcp.synthesis.topologies.llc import synthesize_llc


@pytest.fixture
def llc_requirements():
    return {"vin": 400, "vout_target": 48, "iout": 10, "fsw": 100000}


@pytest.fixture
def llc_graph(llc_requirements):
    return synthesize_llc(llc_requirements)


@pytest.fixture
def llc_layout(llc_graph):
    return generate_layout(llc_graph)


# --- Basic tests ---

def test_returns_schematic_layout(llc_layout):
    assert isinstance(llc_layout, SchematicLayout)


def test_topology_is_llc(llc_layout):
    assert llc_layout.topology == "llc"


def test_all_components_present(llc_graph, llc_layout):
    graph_ids = {c.id for c in llc_graph.components}
    layout_ids = {c.id for c in llc_layout.components}
    assert graph_ids == layout_ids


def test_all_components_have_positions(llc_layout):
    for comp in llc_layout.components:
        assert comp.x != 0 or comp.y != 0, f"{comp.id} at origin"


# --- Region tests ---

def test_input_region_exists(llc_layout):
    assert llc_layout.get_region("input_stage") is not None


def test_half_bridge_region_exists(llc_layout):
    assert llc_layout.get_region("half_bridge") is not None


def test_resonant_region_exists(llc_layout):
    assert llc_layout.get_region("resonant_tank") is not None


def test_magnetizing_region_exists(llc_layout):
    assert llc_layout.get_region("magnetizing_branch") is not None


def test_transformer_region_exists(llc_layout):
    assert llc_layout.get_region("transformer_stage") is not None


def test_secondary_region_exists(llc_layout):
    assert llc_layout.get_region("secondary_rectifier") is not None


def test_output_region_exists(llc_layout):
    assert llc_layout.get_region("output_filter") is not None


def test_seven_regions_total(llc_layout):
    assert len(llc_layout.regions) == 7


# --- Block ordering left-to-right ---

def test_half_bridge_left_of_resonant(llc_layout):
    hb_region = llc_layout.get_region("half_bridge")
    res_region = llc_layout.get_region("resonant_tank")
    assert hb_region is not None and res_region is not None
    assert hb_region.x < res_region.x


def test_resonant_left_of_transformer(llc_layout):
    res_region = llc_layout.get_region("resonant_tank")
    tf_region = llc_layout.get_region("transformer_stage")
    assert res_region is not None and tf_region is not None
    assert res_region.x < tf_region.x


def test_transformer_left_of_secondary(llc_layout):
    tf_region = llc_layout.get_region("transformer_stage")
    sec_region = llc_layout.get_region("secondary_rectifier")
    assert tf_region is not None and sec_region is not None
    assert tf_region.x < sec_region.x


def test_secondary_left_of_output(llc_layout):
    sec_region = llc_layout.get_region("secondary_rectifier")
    out_region = llc_layout.get_region("output_filter")
    assert sec_region is not None and out_region is not None
    assert sec_region.x < out_region.x


# --- Component spatial ordering ---

def test_input_left_of_half_bridge_components(llc_layout):
    v1 = llc_layout.get_component("V1")
    sw1 = llc_layout.get_component("SW1")
    assert v1 is not None and sw1 is not None
    assert v1.x < sw1.x


def test_half_bridge_left_of_resonant_tank(llc_layout):
    sw1 = llc_layout.get_component("SW1")
    cr = llc_layout.get_component("Cr")
    assert sw1 is not None and cr is not None
    assert sw1.x < cr.x


def test_resonant_cap_left_of_inductor(llc_layout):
    cr = llc_layout.get_component("Cr")
    lr = llc_layout.get_component("Lr")
    assert cr is not None and lr is not None
    assert cr.x < lr.x


def test_output_right(llc_layout):
    r1 = llc_layout.get_component("R1")
    sw1 = llc_layout.get_component("SW1")
    assert r1 is not None and sw1 is not None
    assert r1.x > sw1.x


# --- Region assignments ---

def test_switch_in_half_bridge_region(llc_layout):
    sw1 = llc_layout.get_component("SW1")
    assert sw1 is not None
    assert sw1.region_id == "half_bridge"


def test_resonant_cap_in_resonant_region(llc_layout):
    cr = llc_layout.get_component("Cr")
    assert cr is not None
    assert cr.region_id == "resonant_tank"


def test_load_in_output_region(llc_layout):
    r1 = llc_layout.get_component("R1")
    assert r1 is not None
    assert r1.region_id == "output_filter"


# --- Symbol variants ---

def test_components_have_symbol_variants(llc_layout):
    for comp in llc_layout.components:
        assert comp.symbol_variant is not None, f"{comp.id} missing variant"


# --- Constraints ---

def test_has_constraints(llc_layout):
    assert len(llc_layout.constraints) > 0


def test_has_left_of_constraints(llc_layout):
    left_of = [c for c in llc_layout.constraints if c.kind == "left_of"]
    assert len(left_of) >= 5


# --- Metadata ---

def test_flow_direction_metadata(llc_layout):
    assert llc_layout.metadata.get("flow_direction") == "left_to_right"
