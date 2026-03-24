"""Trunk-and-branch routing for multi-pin nets.

For nets with 3+ pins:
1. Determine trunk axis (horizontal or vertical) based on net role
2. Calculate trunk position (median of pin positions along perpendicular axis)
3. Create trunk segment spanning all pins
4. Create branch segments from each pin to the trunk

For 2-pin nets: direct L-shaped orthogonal routing.
"""

from __future__ import annotations

from statistics import median

from .models import JunctionPoint, RoutedSegment

# Maps net roles to preferred trunk axis.
# "horizontal" means the trunk runs left-right (branches go up/down).
# "vertical" means the trunk runs top-bottom (branches go left/right).
# "direct" means shortest-path orthogonal for 2-pin or simple nets.
NET_ROLE_TRUNK_AXIS: dict[str, str] = {
    "ground": "horizontal",
    "primary_ground": "horizontal",
    "secondary_ground": "horizontal",
    "input_positive": "horizontal",
    "output_positive": "horizontal",
    "switch_node": "vertical",
    "half_bridge_midpoint": "vertical",
    "resonant_node": "vertical",
    "drive_signal": "direct",
    "high_side_drive": "direct",
    "low_side_drive": "direct",
}


def _route_two_pin_direct(
    net_id: str,
    p1: tuple[int, int],
    p2: tuple[int, int],
    seg_id_start: int,
) -> tuple[list[RoutedSegment], list[JunctionPoint]]:
    """Route a 2-pin net with an L-shaped orthogonal path."""
    x1, y1 = p1
    x2, y2 = p2
    segments: list[RoutedSegment] = []

    if x1 == x2 and y1 == y2:
        return segments, []

    if x1 == x2 or y1 == y2:
        # Already aligned: single straight segment
        segments.append(RoutedSegment(
            id=f"seg_{seg_id_start}",
            net_id=net_id,
            x1=x1, y1=y1, x2=x2, y2=y2,
            role="direct",
        ))
    else:
        # L-shape: horizontal first, then vertical
        segments.append(RoutedSegment(
            id=f"seg_{seg_id_start}",
            net_id=net_id,
            x1=x1, y1=y1, x2=x2, y2=y1,
            role="direct",
        ))
        segments.append(RoutedSegment(
            id=f"seg_{seg_id_start + 1}",
            net_id=net_id,
            x1=x2, y1=y1, x2=x2, y2=y2,
            role="direct",
        ))
    return segments, []


def _route_horizontal_trunk(
    net_id: str,
    pin_positions: list[tuple[int, int]],
    seg_id_start: int,
) -> tuple[list[RoutedSegment], list[JunctionPoint]]:
    """Route with a horizontal trunk at the median Y of all pins."""
    ys = [p[1] for p in pin_positions]
    trunk_y = int(median(ys))

    xs = sorted(p[0] for p in pin_positions)
    min_x = xs[0]
    max_x = xs[-1]

    segments: list[RoutedSegment] = []
    junctions: list[JunctionPoint] = []
    sid = seg_id_start

    # Trunk segment (horizontal)
    if min_x != max_x:
        segments.append(RoutedSegment(
            id=f"seg_{sid}",
            net_id=net_id,
            x1=min_x, y1=trunk_y, x2=max_x, y2=trunk_y,
            role="trunk",
        ))
        sid += 1

    # Branch segments from each pin to the trunk
    for px, py in pin_positions:
        if py == trunk_y:
            # Pin is on the trunk; check if pin x is not at trunk endpoints
            # (i.e., it's an intermediate point that needs a junction)
            if len(pin_positions) > 2 and min_x < px < max_x:
                junctions.append(JunctionPoint(x=px, y=trunk_y, net_id=net_id))
            continue

        # Vertical branch from pin to trunk
        segments.append(RoutedSegment(
            id=f"seg_{sid}",
            net_id=net_id,
            x1=px, y1=py, x2=px, y2=trunk_y,
            role="branch",
        ))
        sid += 1
        junctions.append(JunctionPoint(x=px, y=trunk_y, net_id=net_id))

    return segments, junctions


def _route_vertical_trunk(
    net_id: str,
    pin_positions: list[tuple[int, int]],
    seg_id_start: int,
) -> tuple[list[RoutedSegment], list[JunctionPoint]]:
    """Route with a vertical trunk at the median X of all pins."""
    xs = [p[0] for p in pin_positions]
    trunk_x = int(median(xs))

    ys = sorted(p[1] for p in pin_positions)
    min_y = ys[0]
    max_y = ys[-1]

    segments: list[RoutedSegment] = []
    junctions: list[JunctionPoint] = []
    sid = seg_id_start

    # Trunk segment (vertical)
    if min_y != max_y:
        segments.append(RoutedSegment(
            id=f"seg_{sid}",
            net_id=net_id,
            x1=trunk_x, y1=min_y, x2=trunk_x, y2=max_y,
            role="trunk",
        ))
        sid += 1

    # Branch segments from each pin to the trunk
    for px, py in pin_positions:
        if px == trunk_x:
            if len(pin_positions) > 2 and min_y < py < max_y:
                junctions.append(JunctionPoint(x=trunk_x, y=py, net_id=net_id))
            continue

        # Horizontal branch from pin to trunk
        segments.append(RoutedSegment(
            id=f"seg_{sid}",
            net_id=net_id,
            x1=px, y1=py, x2=trunk_x, y2=py,
            role="branch",
        ))
        sid += 1
        junctions.append(JunctionPoint(x=trunk_x, y=py, net_id=net_id))

    return segments, junctions


def route_net_trunk_branch(
    net_id: str,
    pin_positions: list[tuple[int, int]],
    net_role: str | None = None,
    segment_id_start: int = 1,
) -> tuple[list[RoutedSegment], list[JunctionPoint]]:
    """Route a single net using trunk-and-branch strategy.

    Parameters
    ----------
    net_id:
        Identifier for the net being routed.
    pin_positions:
        Absolute (x, y) positions of pins in this net.
    net_role:
        Semantic role of the net (e.g. "ground", "switch_node").
        Determines trunk axis preference.
    segment_id_start:
        Starting counter for segment IDs.

    Returns
    -------
    tuple of (segments, junctions)
    """
    if len(pin_positions) < 2:
        return [], []

    # Deduplicate positions (but keep order for 2-pin)
    unique_positions = list(dict.fromkeys(pin_positions))
    if len(unique_positions) < 2:
        return [], []

    # 2-pin net: always direct L-shape
    if len(unique_positions) == 2:
        return _route_two_pin_direct(
            net_id, unique_positions[0], unique_positions[1], segment_id_start,
        )

    # 3+ pin net: determine trunk axis from role
    axis = NET_ROLE_TRUNK_AXIS.get(net_role or "", "horizontal")

    if axis == "direct":
        # Chain pins with L-shapes (for simple signal nets)
        all_segments: list[RoutedSegment] = []
        all_junctions: list[JunctionPoint] = []
        sid = segment_id_start
        for i in range(len(unique_positions) - 1):
            segs, juncs = _route_two_pin_direct(
                net_id, unique_positions[i], unique_positions[i + 1], sid,
            )
            all_segments.extend(segs)
            all_junctions.extend(juncs)
            sid += len(segs)
        return all_segments, all_junctions

    if axis == "vertical":
        return _route_vertical_trunk(net_id, unique_positions, segment_id_start)

    # Default: horizontal trunk
    return _route_horizontal_trunk(net_id, unique_positions, segment_id_start)
