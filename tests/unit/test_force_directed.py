"""Tests for the force-directed fine-tuning module."""

from __future__ import annotations

import pytest

from psim_mcp.layout.force_directed import force_adjust
from psim_mcp.layout.models import LayoutComponent, LayoutRegion
from psim_mcp.synthesis.graph import GraphNet


@pytest.fixture
def two_connected_components():
    """Two components far apart, connected by one net."""
    comps = [
        LayoutComponent(id="A", x=100, y=100, direction=0, region_id="r1"),
        LayoutComponent(id="B", x=500, y=100, direction=0, region_id="r1"),
    ]
    nets = [
        GraphNet(id="n1", pins=["A.pin1", "B.pin1"]),
    ]
    return comps, nets


@pytest.fixture
def two_overlapping_components():
    """Two components at nearly the same position, not connected."""
    comps = [
        LayoutComponent(id="A", x=200, y=200, direction=0, region_id="r1"),
        LayoutComponent(id="B", x=210, y=200, direction=0, region_id="r1"),
    ]
    nets: list[GraphNet] = []
    return comps, nets


@pytest.fixture
def region_bounds():
    return {
        "r1": LayoutRegion(id="r1", role="main", x=50, y=50, width=600, height=400),
    }


def test_connected_components_move_closer(two_connected_components):
    comps, nets = two_connected_components
    initial_dist = abs(comps[1].x - comps[0].x)
    force_adjust(comps, nets, iterations=30, damping=0.3, grid=50)
    final_dist = abs(comps[1].x - comps[0].x)
    assert final_dist < initial_dist, (
        f"Connected components should move closer: {initial_dist} -> {final_dist}"
    )


def test_overlapping_components_push_apart(two_overlapping_components):
    comps, nets = two_overlapping_components
    initial_dist = abs(comps[1].x - comps[0].x)
    force_adjust(comps, nets, iterations=30, damping=0.3, grid=50)
    final_dist = abs(comps[1].x - comps[0].x)
    assert final_dist > initial_dist, (
        f"Overlapping components should push apart: {initial_dist} -> {final_dist}"
    )


def test_grid_snap_after_adjustment(two_connected_components):
    comps, nets = two_connected_components
    force_adjust(comps, nets, iterations=10, damping=0.3, grid=50)
    for c in comps:
        assert c.x % 50 == 0, f"{c.id} x={c.x} not on grid"
        assert c.y % 50 == 0, f"{c.id} y={c.y} not on grid"


def test_components_stay_within_region_bounds(two_connected_components, region_bounds):
    comps, nets = two_connected_components
    force_adjust(comps, nets, iterations=30, damping=0.3, grid=50, regions=region_bounds)
    region = region_bounds["r1"]
    for c in comps:
        assert c.x >= region.x, f"{c.id} x={c.x} below region x={region.x}"
        assert c.y >= region.y, f"{c.id} y={c.y} below region y={region.y}"


def test_single_component_no_crash():
    """Single component should not crash."""
    comps = [LayoutComponent(id="A", x=100, y=100, direction=0)]
    force_adjust(comps, [], iterations=10, damping=0.3)
    assert comps[0].x == 100
    assert comps[0].y == 100


def test_empty_components_no_crash():
    """Empty list should not crash."""
    force_adjust([], [], iterations=10, damping=0.3)
