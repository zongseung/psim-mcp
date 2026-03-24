"""Trunk-and-branch routing for multi-pin nets.

For nets with 3+ pins:
1. Determine trunk axis (horizontal or vertical) based on net role
2. Calculate trunk position (median of pin positions along perpendicular axis)
3. Create trunk segment spanning all pins
4. Create branch segments from each pin to the trunk

For 2-pin nets: direct L-shaped orthogonal routing.
"""

from __future__ import annotations

import copy
from statistics import median

from .models import JunctionPoint, RoutedSegment

# Spacing constant used when shifting trunks to minimize crossings.
PIN_SPACING = 10

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


# ---------------------------------------------------------------------------
# Crossing minimization helpers
# ---------------------------------------------------------------------------

def _count_inter_net_crossings(all_net_segments: list[list[RoutedSegment]]) -> int:
    """Count crossings between segments from different nets."""
    flat: list[RoutedSegment] = []
    for net_segs in all_net_segments:
        flat.extend(net_segs)

    crossings = 0
    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            si, sj = flat[i], flat[j]
            if si.net_id == sj.net_id:
                continue
            if _orthogonal_cross(si, sj):
                crossings += 1
    return crossings


def _orthogonal_cross(a: RoutedSegment, b: RoutedSegment) -> bool:
    """Check if two orthogonal segments cross (not share endpoints)."""
    ax1, ay1, ax2, ay2 = a.x1, a.y1, a.x2, a.y2
    bx1, by1, bx2, by2 = b.x1, b.y1, b.x2, b.y2

    if ax1 > ax2:
        ax1, ax2 = ax2, ax1
    if ay1 > ay2:
        ay1, ay2 = ay2, ay1
    if bx1 > bx2:
        bx1, bx2 = bx2, bx1
    if by1 > by2:
        by1, by2 = by2, by1

    a_horiz = ay1 == ay2 and ax1 != ax2
    a_vert = ax1 == ax2 and ay1 != ay2
    b_horiz = by1 == by2 and bx1 != bx2
    b_vert = bx1 == bx2 and by1 != by2

    if a_horiz and b_vert:
        if ax1 < bx1 < ax2 and by1 < ay1 < by2:
            return True
    elif a_vert and b_horiz:
        if bx1 < ax1 < bx2 and ay1 < by1 < ay2:
            return True
    return False


def _shift_trunk(
    segments: list[RoutedSegment],
    delta: int,
) -> list[RoutedSegment]:
    """Shift trunk position by *delta* in the perpendicular direction.

    For horizontal trunks (y1 == y2) shift Y.
    For vertical trunks (x1 == x2) shift X.
    Branch endpoints touching the trunk are also adjusted.
    """
    shifted: list[RoutedSegment] = []
    # Identify trunk Y/X
    trunk_segs = [s for s in segments if s.role == "trunk"]
    if not trunk_segs:
        return list(segments)

    ts = trunk_segs[0]
    is_horiz = ts.y1 == ts.y2

    for seg in segments:
        s = copy.copy(seg)
        s.metadata = dict(seg.metadata) if seg.metadata else {}
        if s.role == "trunk":
            if is_horiz:
                s.y1 += delta
                s.y2 += delta
            else:
                s.x1 += delta
                s.x2 += delta
        elif s.role == "branch":
            if is_horiz:
                # Branch connects pin to trunk_y -- adjust the end that was on trunk
                if s.y2 == ts.y1:
                    s.y2 += delta
                elif s.y1 == ts.y1:
                    s.y1 += delta
            else:
                if s.x2 == ts.x1:
                    s.x2 += delta
                elif s.x1 == ts.x1:
                    s.x1 += delta
        shifted.append(s)
    return shifted


def minimize_crossings(
    all_net_segments: list[list[RoutedSegment]],
) -> list[list[RoutedSegment]]:
    """Reorder trunk positions to minimize inter-net crossings.

    Simple heuristic: for each net with a trunk, try shifting trunk Y (or X)
    by +/- PIN_SPACING. Keep the variant with fewer total crossings.
    """
    if len(all_net_segments) <= 1:
        return all_net_segments

    best = [list(segs) for segs in all_net_segments]
    best_crossings = _count_inter_net_crossings(best)

    if best_crossings == 0:
        return best

    # Try shifting each net's trunk and see if it reduces crossings
    improved = True
    max_iterations = 3
    iteration = 0
    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        for idx in range(len(best)):
            trunk_segs = [s for s in best[idx] if s.role == "trunk"]
            if not trunk_segs:
                continue

            for delta in (PIN_SPACING, -PIN_SPACING):
                candidate = list(best)
                candidate[idx] = _shift_trunk(best[idx], delta)
                c = _count_inter_net_crossings(candidate)
                if c < best_crossings:
                    best = candidate
                    best_crossings = c
                    improved = True
                    if best_crossings == 0:
                        return best

    return best
