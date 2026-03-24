"""Routing quality metrics."""

from __future__ import annotations

from .models import WireRouting


def _segments_intersect(
    ax1: int, ay1: int, ax2: int, ay2: int,
    bx1: int, by1: int, bx2: int, by2: int,
) -> bool:
    """Check if two orthogonal segments cross (not just share an endpoint).

    Only detects perpendicular crossings (one horizontal, one vertical).
    """
    # Normalize segment directions
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
        # A is horizontal, B is vertical
        # They cross if B's x is strictly between A's x range
        # and A's y is strictly between B's y range
        if ax1 < bx1 < ax2 and by1 < ay1 < by2:
            return True
    elif a_vert and b_horiz:
        # A is vertical, B is horizontal
        if bx1 < ax1 < bx2 and ay1 < by1 < ay2:
            return True

    return False


def count_crossings(routing: WireRouting) -> int:
    """Count wire crossings between segments of different nets."""
    crossings = 0
    segs = routing.segments
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            si, sj = segs[i], segs[j]
            if si.net_id == sj.net_id:
                continue
            if _segments_intersect(
                si.x1, si.y1, si.x2, si.y2,
                sj.x1, sj.y1, sj.x2, sj.y2,
            ):
                crossings += 1
    return crossings


def count_duplicates(routing: WireRouting) -> int:
    """Count duplicate segments (same net, same endpoints)."""
    seen: set[tuple[str, tuple[int, int], tuple[int, int]]] = set()
    duplicates = 0
    for s in routing.segments:
        start = (min(s.x1, s.x2), min(s.y1, s.y2))
        end = (max(s.x1, s.x2), max(s.y1, s.y2))
        key = (s.net_id, start, end)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return duplicates


def total_wire_length(routing: WireRouting) -> int:
    """Sum of all segment lengths (Manhattan distance)."""
    total = 0
    for s in routing.segments:
        total += abs(s.x2 - s.x1) + abs(s.y2 - s.y1)
    return total


def count_junctions(routing: WireRouting) -> int:
    """Count junction points."""
    return len(routing.junctions)


def routing_quality_report(routing: WireRouting) -> dict:
    """Generate a comprehensive routing quality report."""
    return {
        "crossings": count_crossings(routing),
        "duplicates": count_duplicates(routing),
        "total_length": total_wire_length(routing),
        "junctions": count_junctions(routing),
        "segment_count": len(routing.segments),
    }
