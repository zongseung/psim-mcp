"""Unit tests for crossing minimization in trunk-branch routing."""

from psim_mcp.routing.models import RoutedSegment
from psim_mcp.routing.trunk_branch import (
    minimize_crossings,
    _count_inter_net_crossings,
    _orthogonal_cross,
)


def _seg(net_id, x1, y1, x2, y2, role="trunk"):
    return RoutedSegment(
        id=f"seg_{net_id}_{x1}_{y1}",
        net_id=net_id,
        x1=x1, y1=y1, x2=x2, y2=y2,
        role=role,
    )


def test_empty_input_returns_empty():
    """Empty list of net segments returns empty."""
    result = minimize_crossings([])
    assert result == []


def test_single_net_no_change():
    """A single net has no inter-net crossings; no minimization needed."""
    segs = [_seg("n1", 0, 50, 200, 50)]
    result = minimize_crossings([segs])
    assert len(result) == 1
    assert len(result[0]) == 1


def test_two_non_crossing_horizontal_trunks_unchanged():
    """Two horizontal trunks that don't cross should remain unchanged."""
    net_a = [_seg("a", 0, 50, 200, 50)]
    net_b = [_seg("b", 0, 100, 200, 100)]
    result = minimize_crossings([net_a, net_b])
    assert _count_inter_net_crossings(result) == 0


def test_two_crossing_trunks_reduced():
    """Two perpendicular trunks that cross should have crossings reduced or zero."""
    # Horizontal trunk from (0,50) to (200,50)
    net_a = [_seg("a", 0, 50, 200, 50)]
    # Vertical trunk from (100,0) to (100,100)
    net_b = [_seg("b", 100, 0, 100, 100)]
    original_crossings = _count_inter_net_crossings([net_a, net_b])
    assert original_crossings == 1

    result = minimize_crossings([net_a, net_b])
    new_crossings = _count_inter_net_crossings(result)
    # Should reduce or maintain crossings
    assert new_crossings <= original_crossings


def test_orthogonal_cross_detection():
    """Perpendicular segments that cross are detected correctly."""
    h = _seg("a", 0, 50, 200, 50)
    v = _seg("b", 100, 0, 100, 100)
    assert _orthogonal_cross(h, v) is True


def test_parallel_segments_no_cross():
    """Parallel horizontal segments never cross."""
    h1 = _seg("a", 0, 50, 200, 50)
    h2 = _seg("b", 0, 100, 200, 100)
    assert _orthogonal_cross(h1, h2) is False


def test_non_intersecting_perpendicular_no_cross():
    """Perpendicular segments that don't actually overlap don't cross."""
    h = _seg("a", 0, 50, 100, 50)
    v = _seg("b", 200, 0, 200, 100)  # v is far to the right
    assert _orthogonal_cross(h, v) is False


def test_crossing_with_trunk_and_branches():
    """Net with trunk + branches crossing another net's trunk."""
    # Net A: horizontal trunk at y=50 with a branch
    net_a = [
        _seg("a", 0, 50, 200, 50, role="trunk"),
        _seg("a", 100, 20, 100, 50, role="branch"),
    ]
    # Net B: vertical trunk at x=100
    net_b = [
        _seg("b", 100, 0, 100, 100, role="trunk"),
    ]
    original = _count_inter_net_crossings([net_a, net_b])
    assert original >= 1

    result = minimize_crossings([net_a, net_b])
    new = _count_inter_net_crossings(result)
    assert new <= original


def test_three_nets_crossing_minimization():
    """Three nets with potential crossings."""
    net_a = [_seg("a", 0, 50, 300, 50)]
    net_b = [_seg("b", 150, 0, 150, 100)]
    net_c = [_seg("c", 0, 80, 300, 80)]

    original = _count_inter_net_crossings([net_a, net_b, net_c])
    result = minimize_crossings([net_a, net_b, net_c])
    new = _count_inter_net_crossings(result)
    assert new <= original


def test_no_trunk_segments_passthrough():
    """Nets with only direct segments (no trunk) pass through unchanged."""
    net_a = [_seg("a", 0, 0, 100, 0, role="direct")]
    net_b = [_seg("b", 50, 50, 150, 50, role="direct")]
    result = minimize_crossings([net_a, net_b])
    assert len(result) == 2
