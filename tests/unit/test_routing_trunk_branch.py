"""Unit tests for trunk-and-branch routing algorithm."""

from psim_mcp.routing.trunk_branch import route_net_trunk_branch


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
