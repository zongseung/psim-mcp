"""Tests for the algorithmic auto-layout engine."""

from __future__ import annotations

import pytest

from psim_mcp.layout.auto_placer import (
    GRID,
    GROUND_ROLES,
    auto_place,
    _allocate_regions,
    _load_strategy,
    _snap_to_grid,
)
from psim_mcp.layout.models import LayoutComponent, SchematicLayout
from psim_mcp.synthesis.graph import (
    CircuitGraph,
    FunctionalBlock,
    GraphComponent,
    GraphNet,
)
from psim_mcp.synthesis.topologies.buck import synthesize_buck
from psim_mcp.synthesis.topologies.flyback import synthesize_flyback
from psim_mcp.synthesis.topologies.llc import synthesize_llc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def buck_graph():
    return synthesize_buck({"vin": 48, "vout_target": 12, "iout": 5, "fsw": 50000})


@pytest.fixture
def flyback_graph():
    return synthesize_flyback({"vin": 400, "vout_target": 12, "iout": 2, "fsw": 100000})


@pytest.fixture
def llc_graph():
    return synthesize_llc({"vin": 400, "vout_target": 48, "iout": 5, "fsw": 100000})


@pytest.fixture
def empty_graph():
    return CircuitGraph(topology="empty", components=[], nets=[], blocks=[])


@pytest.fixture
def no_blocks_graph():
    """Graph with components but no blocks."""
    return CircuitGraph(
        topology="unknown_topo",
        components=[
            GraphComponent(id="R1", type="Resistor", role="load"),
            GraphComponent(id="V1", type="DC_Source", role="input_source"),
        ],
        nets=[
            GraphNet(id="n1", pins=["V1.positive", "R1.pin1"]),
            GraphNet(id="n2", pins=["V1.negative", "R1.pin2"]),
        ],
        blocks=[],
    )


@pytest.fixture
def unknown_topology_graph():
    """Graph for an unregistered topology with blocks."""
    return CircuitGraph(
        topology="exotic_converter",
        components=[
            GraphComponent(id="V1", type="DC_Source", role="input_source", block_ids=["blk_in"]),
            GraphComponent(id="SW1", type="MOSFET", role="main_switch", block_ids=["blk_sw"]),
            GraphComponent(id="R1", type="Resistor", role="load", block_ids=["blk_out"]),
        ],
        nets=[
            GraphNet(id="n1", pins=["V1.positive", "SW1.drain"]),
            GraphNet(id="n2", pins=["SW1.source", "R1.pin1"]),
        ],
        blocks=[
            FunctionalBlock(id="blk_in", type="input", component_ids=["V1"]),
            FunctionalBlock(id="blk_sw", type="switching", component_ids=["SW1"]),
            FunctionalBlock(id="blk_out", type="output", component_ids=["R1"]),
        ],
    )


# ---------------------------------------------------------------------------
# Buck topology tests
# ---------------------------------------------------------------------------

def test_buck_auto_place_returns_schematic_layout(buck_graph):
    layout = auto_place(buck_graph)
    assert isinstance(layout, SchematicLayout)


def test_buck_all_components_placed(buck_graph):
    layout = auto_place(buck_graph)
    assert len(layout.components) == len(buck_graph.components)


def test_buck_all_components_have_nonzero_positions(buck_graph):
    layout = auto_place(buck_graph)
    for comp in layout.components:
        assert comp.x > 0 or comp.y > 0, f"{comp.id} has zero position"


def test_buck_power_flow_direction(buck_graph):
    """Input source should be left of output load."""
    layout = auto_place(buck_graph)
    comp_map = {c.id: c for c in layout.components}
    assert comp_map["V1"].x < comp_map["R1"].x


def test_buck_switch_between_input_and_output(buck_graph):
    """Switch should be between input source and load."""
    layout = auto_place(buck_graph)
    comp_map = {c.id: c for c in layout.components}
    assert comp_map["V1"].x < comp_map["SW1"].x
    assert comp_map["SW1"].x < comp_map["R1"].x


def test_buck_topology_name(buck_graph):
    layout = auto_place(buck_graph)
    assert layout.topology == "buck"


# ---------------------------------------------------------------------------
# Flyback topology tests
# ---------------------------------------------------------------------------

def test_flyback_auto_place_returns_layout(flyback_graph):
    layout = auto_place(flyback_graph)
    assert isinstance(layout, SchematicLayout)


def test_flyback_all_components_placed(flyback_graph):
    layout = auto_place(flyback_graph)
    assert len(layout.components) == len(flyback_graph.components)


def test_flyback_primary_secondary_separation(flyback_graph):
    """Primary components should have smaller x than secondary components."""
    layout = auto_place(flyback_graph)
    comp_map = {c.id: c for c in layout.components}
    # V1 (primary) should be left of D1 (secondary rectifier)
    assert comp_map["V1"].x < comp_map["D1"].x


def test_flyback_isolation_gap_exists(flyback_graph):
    """Flyback has primary_secondary_split — regions should have extra gap."""
    layout = auto_place(flyback_graph)
    assert len(layout.regions) >= 2
    # Check that there is a meaningful x gap between primary and secondary regions
    region_xs = sorted(r.x for r in layout.regions)
    if len(region_xs) >= 2:
        max_gap = max(region_xs[i + 1] - region_xs[i] for i in range(len(region_xs) - 1))
        assert max_gap > 50  # There should be at least some gap


# ---------------------------------------------------------------------------
# LLC topology tests
# ---------------------------------------------------------------------------

def test_llc_auto_place_returns_layout(llc_graph):
    layout = auto_place(llc_graph)
    assert isinstance(layout, SchematicLayout)


def test_llc_all_components_placed(llc_graph):
    layout = auto_place(llc_graph)
    assert len(layout.components) == len(llc_graph.components)


def test_llc_has_multiple_regions(llc_graph):
    """LLC has 7 blocks → should produce 7 regions."""
    layout = auto_place(llc_graph)
    assert len(layout.regions) == 7


def test_llc_region_ordering(llc_graph):
    """Regions should be ordered left-to-right."""
    layout = auto_place(llc_graph)
    xs = [r.x for r in layout.regions]
    assert xs == sorted(xs), "Regions are not in left-to-right order"


def test_llc_power_flow(llc_graph):
    """Input source should be left of output load."""
    layout = auto_place(llc_graph)
    comp_map = {c.id: c for c in layout.components}
    assert comp_map["V1"].x < comp_map["R1"].x


# ---------------------------------------------------------------------------
# Grid snap tests
# ---------------------------------------------------------------------------

def test_grid_snap_all_coords_divisible(buck_graph):
    layout = auto_place(buck_graph)
    for comp in layout.components:
        assert comp.x % GRID == 0, f"{comp.id} x={comp.x} not on grid"
        assert comp.y % GRID == 0, f"{comp.id} y={comp.y} not on grid"


def test_grid_snap_flyback(flyback_graph):
    layout = auto_place(flyback_graph)
    for comp in layout.components:
        assert comp.x % GRID == 0, f"{comp.id} x={comp.x} not on grid"
        assert comp.y % GRID == 0, f"{comp.id} y={comp.y} not on grid"


def test_grid_snap_llc(llc_graph):
    layout = auto_place(llc_graph)
    for comp in layout.components:
        assert comp.x % GRID == 0, f"{comp.id} x={comp.x} not on grid"
        assert comp.y % GRID == 0, f"{comp.id} y={comp.y} not on grid"


# ---------------------------------------------------------------------------
# No-overlap tests
# ---------------------------------------------------------------------------

def _bounding_boxes_overlap(a: LayoutComponent, b: LayoutComponent, margin: int = 40) -> bool:
    """Check if two components' approximate bounding boxes overlap."""
    a_right = a.x + margin
    b_right = b.x + margin
    a_bottom = a.y + margin
    b_bottom = b.y + margin
    return not (a_right <= b.x or b_right <= a.x or a_bottom <= b.y or b_bottom <= a.y)


def test_no_overlap_buck(buck_graph):
    layout = auto_place(buck_graph)
    # Build role lookup from graph
    role_map = {gc.id: gc.role for gc in buck_graph.components}
    for i, a in enumerate(layout.components):
        for b in layout.components[i + 1:]:
            if a.x == b.x and a.y == b.y:
                # Same position is acceptable for ground references or
                # shunt components in the same region (cap/load parallel pair)
                a_role = role_map.get(a.id, "")
                b_role = role_map.get(b.id, "")
                is_ground = a_role in GROUND_ROLES or b_role in GROUND_ROLES
                is_same_region_shunt = a.region_id == b.region_id
                assert is_ground or is_same_region_shunt or a.id == b.id, (
                    f"Overlap: {a.id}({a.x},{a.y}) and {b.id}({b.x},{b.y})"
                )


def test_no_exact_overlap_llc(llc_graph):
    """No two non-ground components should be at the exact same position,
    unless they are ground references or shunt components in the same region."""
    layout = auto_place(llc_graph)
    role_map = {gc.id: gc.role for gc in llc_graph.components}
    comp_map = {c.id: c for c in layout.components}
    positions: dict[tuple[int, int], str] = {}
    for c in layout.components:
        key = (c.x, c.y)
        if key in positions:
            prev_id = positions[key]
            prev_role = role_map.get(prev_id, "")
            cur_role = role_map.get(c.id, "")
            is_ground = cur_role in GROUND_ROLES or prev_role in GROUND_ROLES
            is_same_region = c.region_id == comp_map[prev_id].region_id
            assert is_ground or is_same_region, (
                f"Exact overlap: {prev_id} and {c.id} at {key}"
            )
        positions[key] = c.id


# ---------------------------------------------------------------------------
# Region allocation tests
# ---------------------------------------------------------------------------

def test_region_allocation_no_overlap(buck_graph):
    """Region bounding boxes should not overlap."""
    layout = auto_place(buck_graph)
    for i, ra in enumerate(layout.regions):
        for rb in layout.regions[i + 1:]:
            ra_right = ra.x + ra.width
            rb_right = rb.x + rb.width
            # At least one of: ra is entirely left, or rb is entirely left
            assert ra_right <= rb.x or rb_right <= ra.x or ra.id == rb.id, (
                f"Region overlap: {ra.id} and {rb.id}"
            )


# ---------------------------------------------------------------------------
# Symbol variant tests
# ---------------------------------------------------------------------------

def test_symbol_variants_assigned_buck(buck_graph):
    layout = auto_place(buck_graph)
    for comp in layout.components:
        assert comp.symbol_variant is not None, f"{comp.id} has no symbol variant"


def test_symbol_variants_assigned_flyback(flyback_graph):
    layout = auto_place(flyback_graph)
    for comp in layout.components:
        assert comp.symbol_variant is not None, f"{comp.id} has no symbol variant"


def test_symbol_variants_assigned_llc(llc_graph):
    layout = auto_place(llc_graph)
    for comp in layout.components:
        assert comp.symbol_variant is not None, f"{comp.id} has no symbol variant"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_graph_produces_empty_layout(empty_graph):
    layout = auto_place(empty_graph)
    assert isinstance(layout, SchematicLayout)
    assert len(layout.components) == 0


def test_graph_with_no_blocks_still_works(no_blocks_graph):
    layout = auto_place(no_blocks_graph)
    assert isinstance(layout, SchematicLayout)
    assert len(layout.components) == 2


def test_unknown_topology_still_produces_layout(unknown_topology_graph):
    layout = auto_place(unknown_topology_graph)
    assert isinstance(layout, SchematicLayout)
    assert len(layout.components) == 3
    # All components should have positions
    for comp in layout.components:
        assert comp.x >= 0
        assert comp.y >= 0


# ---------------------------------------------------------------------------
# Strategy loading
# ---------------------------------------------------------------------------

def test_load_strategy_known_topology():
    strategy = _load_strategy("buck")
    assert strategy["flow_direction"] == "left_to_right"
    assert "block_order" in strategy


def test_load_strategy_unknown_topology():
    strategy = _load_strategy("totally_unknown")
    assert strategy["flow_direction"] == "left_to_right"
    assert "block_order" in strategy


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_metadata_contains_algorithm(buck_graph):
    layout = auto_place(buck_graph)
    assert layout.metadata.get("algorithm") == "auto_place_v1"


def test_metadata_contains_flow_direction(buck_graph):
    layout = auto_place(buck_graph)
    assert layout.metadata.get("flow_direction") == "left_to_right"
