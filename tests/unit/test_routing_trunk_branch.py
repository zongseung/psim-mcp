"""Unit tests for trunk-and-branch routing algorithm."""

from psim_mcp.routing.trunk_branch import (
    _segment_has_collision,
    route_net_trunk_branch,
)


def test_two_pin_horizontal_produces_single_segment():
    """Two pins at same Y should produce one straight segment."""
    segs, juncs = route_net_trunk_branch("n1", [(100, 100), (200, 100)])
    assert len(segs) == 1
    assert segs[0].x1 == 100 and segs[0].y1 == 100
    assert segs[0].x2 == 200 and segs[0].y2 == 100
    assert segs[0].role == "direct"
    assert juncs == []


def test_two_pin_vertical_produces_single_segment():
    """Two pins at same X should produce one straight segment."""
    segs, juncs = route_net_trunk_branch("n1", [(100, 100), (100, 200)])
    assert len(segs) == 1
    assert segs[0].x1 == 100 and segs[0].y1 == 100
    assert segs[0].x2 == 100 and segs[0].y2 == 200
    assert juncs == []


def test_two_pin_l_shape():
    """Two pins at different X and Y should produce L-shaped route (2 segments)."""
    segs, juncs = route_net_trunk_branch("n1", [(100, 100), (200, 200)])
    assert len(segs) == 2
    # First segment: horizontal
    assert segs[0].x1 == 100 and segs[0].y1 == 100
    assert segs[0].x2 == 200 and segs[0].y2 == 100
    # Second segment: vertical
    assert segs[1].x1 == 200 and segs[1].y1 == 100
    assert segs[1].x2 == 200 and segs[1].y2 == 200


def test_three_pin_horizontal_trunk_ground_role():
    """Ground net with 3 pins uses horizontal trunk."""
    pins = [(100, 150), (200, 100), (300, 150)]
    segs, juncs = route_net_trunk_branch("net_gnd", pins, net_role="ground")

    # Should have a trunk + branches
    trunk_segs = [s for s in segs if s.role == "trunk"]
    assert len(trunk_segs) >= 1
    # Trunk should be horizontal
    trunk = trunk_segs[0]
    assert trunk.y1 == trunk.y2  # horizontal


def test_three_pin_vertical_trunk_switch_node():
    """Switch node with 3 pins uses vertical trunk."""
    pins = [(200, 100), (220, 150), (250, 100)]
    segs, juncs = route_net_trunk_branch("net_sw", pins, net_role="switch_node")

    trunk_segs = [s for s in segs if s.role == "trunk"]
    assert len(trunk_segs) >= 1
    trunk = trunk_segs[0]
    assert trunk.x1 == trunk.x2  # vertical


def test_five_pin_ground_rail():
    """Ground net with 5 pins produces trunk + branches."""
    pins = [(120, 150), (120, 150), (220, 150), (300, 150), (350, 150)]
    segs, juncs = route_net_trunk_branch("net_gnd", pins, net_role="ground")

    # All pins are at y=150, so trunk is along y=150
    # Deduplication removes (120,150) duplicate -> 4 unique
    assert len(segs) >= 1
    trunk_segs = [s for s in segs if s.role == "trunk"]
    assert len(trunk_segs) >= 1


def test_branch_segments_connect_to_trunk():
    """Branch endpoints should touch the trunk line."""
    pins = [(100, 100), (200, 200), (300, 100)]
    segs, juncs = route_net_trunk_branch("n1", pins, net_role="ground")

    trunk_segs = [s for s in segs if s.role == "trunk"]
    branch_segs = [s for s in segs if s.role == "branch"]

    if trunk_segs:
        trunk_y = trunk_segs[0].y1
        for branch in branch_segs:
            # One end of branch should be at trunk_y
            assert branch.y1 == trunk_y or branch.y2 == trunk_y


def test_junction_points_at_trunk_branch_intersections():
    """Junctions should be created where branches meet the trunk."""
    pins = [(100, 100), (200, 200), (300, 100)]
    segs, juncs = route_net_trunk_branch("n1", pins, net_role="ground")

    # The pin at (200,200) needs a branch to the trunk -> junction at trunk
    assert len(juncs) >= 1
    for j in juncs:
        assert j.net_id == "n1"


def test_no_zero_length_segments():
    """No segments should have zero length (same start and end)."""
    pins = [(100, 100), (200, 200), (300, 100), (400, 150)]
    segs, juncs = route_net_trunk_branch("n1", pins, net_role="ground")

    for seg in segs:
        length = abs(seg.x2 - seg.x1) + abs(seg.y2 - seg.y1)
        assert length > 0, f"Zero-length segment: {seg}"


def test_single_pin_returns_empty():
    """A net with only 1 pin cannot be routed."""
    segs, juncs = route_net_trunk_branch("n1", [(100, 100)])
    assert segs == []
    assert juncs == []


def test_duplicate_pins_returns_empty():
    """A net where all pins are at the same position returns empty."""
    segs, juncs = route_net_trunk_branch("n1", [(100, 100), (100, 100)])
    assert segs == []
    assert juncs == []


def test_direct_role_chains_l_shapes():
    """Drive signal (direct role) with 3+ pins chains L-shapes."""
    pins = [(180, 170), (180, 120), (200, 100)]
    segs, juncs = route_net_trunk_branch("net_gate", pins, net_role="drive_signal")

    # Should chain: pin0->pin1, pin1->pin2
    assert len(segs) >= 2
    for seg in segs:
        assert seg.role == "direct"


def test_segment_ids_start_from_given_value():
    """Segment IDs should start from the given segment_id_start value."""
    segs, _ = route_net_trunk_branch("n1", [(0, 0), (100, 100)], segment_id_start=42)
    assert segs[0].id == "seg_42"


def test_all_segments_have_correct_net_id():
    """All generated segments should reference the correct net_id."""
    segs, _ = route_net_trunk_branch(
        "my_net", [(0, 0), (100, 0), (200, 50)], net_role="ground",
    )
    for seg in segs:
        assert seg.net_id == "my_net"


def test_vertical_trunk_branches_are_horizontal():
    """Branches from a vertical trunk should be horizontal."""
    pins = [(100, 50), (250, 100), (100, 200)]
    segs, juncs = route_net_trunk_branch("n1", pins, net_role="switch_node")

    branch_segs = [s for s in segs if s.role == "branch"]
    for branch in branch_segs:
        assert branch.y1 == branch.y2  # horizontal branch


# ---------------------------------------------------------------------------
# Pin collision avoidance tests
# ---------------------------------------------------------------------------


def test_segment_has_collision_horizontal():
    """Horizontal segment detects pin on its path."""
    avoid = {(150, 100)}
    assert _segment_has_collision(100, 100, 200, 100, avoid) is True


def test_segment_has_collision_at_endpoint_is_false():
    """Pin at segment endpoint should NOT count as collision."""
    avoid = {(100, 100)}
    assert _segment_has_collision(100, 100, 200, 100, avoid) is False


def test_segment_has_collision_vertical():
    """Vertical segment detects pin on its path."""
    avoid = {(100, 150)}
    assert _segment_has_collision(100, 100, 100, 200, avoid) is True


def test_segment_no_collision_when_off_path():
    """Pin not on segment path should not collide."""
    avoid = {(150, 150)}  # not on the horizontal line y=100
    assert _segment_has_collision(100, 100, 200, 100, avoid) is False


def test_two_pin_straight_avoids_foreign_pin():
    """A straight 2-pin segment should detour around a foreign pin."""
    # Pin at (150, 100) belongs to another net
    avoid = {(150, 100)}
    segs, _ = route_net_trunk_branch(
        "n1", [(100, 100), (200, 100)], avoid_positions=avoid,
    )
    # Should have more than 1 segment (detour)
    assert len(segs) > 1
    # No segment should pass through the avoided position
    for seg in segs:
        assert not _segment_has_collision(
            seg.x1, seg.y1, seg.x2, seg.y2, avoid,
        ), f"Segment {seg.id} passes through avoided pin"


def test_two_pin_straight_no_detour_without_collision():
    """Without a foreign pin on the path, straight segment is preserved."""
    avoid = {(150, 200)}  # not on path y=100
    segs, _ = route_net_trunk_branch(
        "n1", [(100, 100), (200, 100)], avoid_positions=avoid,
    )
    assert len(segs) == 1


def test_l_shape_avoids_foreign_pin():
    """L-shape should try alt orientation when default collides."""
    # Default L-shape: horiz (100,100)->(200,100), vert (200,100)->(200,200)
    # Put foreign pin at (150, 100) on the horizontal leg
    avoid = {(150, 100)}
    segs, _ = route_net_trunk_branch(
        "n1", [(100, 100), (200, 200)], avoid_positions=avoid,
    )
    # No segment should pass through avoided pin
    for seg in segs:
        assert not _segment_has_collision(
            seg.x1, seg.y1, seg.x2, seg.y2, avoid,
        ), f"Segment {seg.id} passes through avoided pin"


def test_horizontal_trunk_shifts_to_avoid_foreign_pin():
    """Horizontal trunk should shift Y when a foreign pin is on the trunk line."""
    # 3-pin ground net, median Y = 150
    pins = [(100, 150), (200, 100), (300, 150)]
    # Foreign pin at (200, 150) -- right on the median trunk line
    avoid = {(200, 150)}
    segs, _ = route_net_trunk_branch(
        "net_gnd", pins, net_role="ground", avoid_positions=avoid,
    )
    trunk_segs = [s for s in segs if s.role == "trunk"]
    assert len(trunk_segs) >= 1
    # Trunk Y should NOT be 150 (shifted away from the foreign pin)
    trunk = trunk_segs[0]
    assert trunk.y1 != 150 or not _segment_has_collision(
        trunk.x1, trunk.y1, trunk.x2, trunk.y2, avoid,
    )


def test_vertical_trunk_shifts_to_avoid_foreign_pin():
    """Vertical trunk should shift X when a foreign pin is on the trunk line."""
    pins = [(200, 100), (250, 200), (200, 300)]
    # Foreign pin at (200, 200) -- on the median trunk X=200
    avoid = {(200, 200)}
    segs, _ = route_net_trunk_branch(
        "net_sw", pins, net_role="switch_node", avoid_positions=avoid,
    )
    trunk_segs = [s for s in segs if s.role == "trunk"]
    assert len(trunk_segs) >= 1
    for seg in segs:
        assert not _segment_has_collision(
            seg.x1, seg.y1, seg.x2, seg.y2, avoid,
        ), f"Segment {seg.id} passes through avoided pin"


def test_no_avoid_positions_preserves_original_behavior():
    """When avoid_positions is None or empty, behavior is unchanged."""
    pins = [(100, 150), (200, 100), (300, 150)]
    segs_none, _ = route_net_trunk_branch("n1", pins, net_role="ground")
    segs_empty, _ = route_net_trunk_branch(
        "n1", pins, net_role="ground", avoid_positions=set(),
    )
    assert len(segs_none) == len(segs_empty)
    for a, b in zip(segs_none, segs_empty):
        assert (a.x1, a.y1, a.x2, a.y2) == (b.x1, b.y1, b.x2, b.y2)


def test_half_bridge_scenario_no_false_connections():
    """Simulates the half_bridge problem: wire from (400,200) to (550,200)
    must not pass through foreign pins at (450,200) and (500,200)."""
    avoid = {(450, 200), (500, 200)}
    segs, _ = route_net_trunk_branch(
        "net_gnd", [(400, 200), (550, 200)], avoid_positions=avoid,
    )
    for seg in segs:
        assert not _segment_has_collision(
            seg.x1, seg.y1, seg.x2, seg.y2, avoid,
        ), f"Segment {seg.id} falsely connects through foreign pin"
