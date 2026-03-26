"""Routing quality metrics."""

from __future__ import annotations

import math

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


def count_unconnected_pins(routing: WireRouting, tolerance: int = 5) -> int:
    """Count pins that appear in net definitions but have no routed segment nearby.

    A pin is considered connected if at least one segment endpoint for its net
    is within *tolerance* units (Manhattan distance) of the pin's expected
    position.  Because ``WireRouting`` does not carry pin position data
    directly, this implementation counts pins referenced in
    ``routing.metadata["net_pins"]`` (a dict mapping net_id -> list of
    ``(x, y)`` tuples) that lack a nearby segment endpoint.  If the metadata
    is absent the metric returns 0 (no data to evaluate).
    """
    net_pins: dict[str, list[tuple[int, int]]] = routing.metadata.get("net_pins", {})
    if not net_pins:
        return 0

    # Build per-net endpoint sets
    net_endpoints: dict[str, set[tuple[int, int]]] = {}
    for seg in routing.segments:
        net_endpoints.setdefault(seg.net_id, set()).add((seg.x1, seg.y1))
        net_endpoints.setdefault(seg.net_id, set()).add((seg.x2, seg.y2))

    unconnected = 0
    for net_id, pins in net_pins.items():
        endpoints = net_endpoints.get(net_id, set())
        for px, py in pins:
            if not any(
                abs(ex - px) + abs(ey - py) <= tolerance
                for ex, ey in endpoints
            ):
                unconnected += 1
    return unconnected


def count_orphan_nets(routing: WireRouting) -> int:
    """Count nets with only one pin (useless nets).

    Uses ``routing.metadata["net_pins"]`` if available.  Falls back to
    counting nets that have only a single segment endpoint pair (i.e. one
    segment with no branches).
    """
    net_pins: dict[str, list] = routing.metadata.get("net_pins", {})
    if net_pins:
        return sum(1 for pins in net_pins.values() if len(pins) <= 1)

    # Fallback: count nets with only one unique endpoint
    net_endpoints: dict[str, set[tuple[int, int]]] = {}
    for seg in routing.segments:
        net_endpoints.setdefault(seg.net_id, set()).add((seg.x1, seg.y1))
        net_endpoints.setdefault(seg.net_id, set()).add((seg.x2, seg.y2))
    return sum(1 for eps in net_endpoints.values() if len(eps) <= 1)


def routing_detour_ratio(routing: WireRouting) -> float:
    """Ratio of actual wire length to ideal Manhattan distance between endpoints.

    Computed per-net: for each net the ideal length is the Manhattan distance
    of the bounding box of all segment endpoints, and the actual length is
    the sum of all segment lengths.  The overall ratio is the sum of actual
    lengths divided by the sum of ideal lengths.

    Returns 1.0 for a perfect routing (no detours).  Returns ``math.inf``
    when ideal length is 0 (all endpoints coincide).
    """
    net_segments: dict[str, list] = {}
    for seg in routing.segments:
        net_segments.setdefault(seg.net_id, []).append(seg)

    total_actual = 0
    total_ideal = 0
    for net_id, segs in net_segments.items():
        xs: list[int] = []
        ys: list[int] = []
        actual = 0
        for s in segs:
            xs.extend([s.x1, s.x2])
            ys.extend([s.y1, s.y2])
            actual += abs(s.x2 - s.x1) + abs(s.y2 - s.y1)
        ideal = (max(xs) - min(xs)) + (max(ys) - min(ys)) if xs else 0
        total_actual += actual
        total_ideal += ideal

    if total_ideal == 0:
        return math.inf if total_actual > 0 else 1.0
    return total_actual / total_ideal


def routing_quality_report(routing: WireRouting) -> dict:
    """Generate a comprehensive routing quality report."""
    return {
        "crossings": count_crossings(routing),
        "duplicates": count_duplicates(routing),
        "total_length": total_wire_length(routing),
        "junctions": count_junctions(routing),
        "segment_count": len(routing.segments),
        "unconnected_pins": count_unconnected_pins(routing),
        "orphan_nets": count_orphan_nets(routing),
        "detour_ratio": routing_detour_ratio(routing),
    }
