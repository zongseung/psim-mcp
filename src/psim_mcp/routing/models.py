"""Routing model primitives."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TypedDict


class WireSegment(TypedDict, total=False):
    """Single schematic wire segment (legacy format)."""

    id: str
    net: str | None
    x1: int
    y1: int
    x2: int
    y2: int


# ---------------------------------------------------------------------------
# Phase 4: Advanced routing models
# ---------------------------------------------------------------------------


@dataclass
class RoutedSegment:
    """A wire segment with net and role metadata."""

    id: str
    net_id: str
    x1: int
    y1: int
    x2: int
    y2: int
    role: str | None = None  # "trunk" | "branch" | "rail" | "direct"
    layer: str | None = None  # "power" | "control" | "ground"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class JunctionPoint:
    """A wire junction where 3+ segments meet."""

    x: int
    y: int
    net_id: str


@dataclass
class RoutingPreference:
    """User/system preferences for routing behavior."""

    style: str = "schematic"
    use_ground_rail: bool = True
    minimize_crossings: bool = True
    prefer_trunk_branch: bool = True
    ground_rail_y: int | None = None


def _split_segment_at_junctions(
    seg: RoutedSegment,
    junction_set: set[tuple[int, int]],
) -> list[dict]:
    """Split a segment at junction points that lie strictly between its endpoints.

    Returns a list of coordinate dicts (without ``id`` or ``net`` keys;
    those are added by the caller).
    """
    points_on_seg: list[tuple[int, int]] = []
    for jx, jy in junction_set:
        if seg.x1 == seg.x2 == jx:  # vertical segment
            lo, hi = min(seg.y1, seg.y2), max(seg.y1, seg.y2)
            if lo < jy < hi:
                points_on_seg.append((jx, jy))
        elif seg.y1 == seg.y2 == jy:  # horizontal segment
            lo, hi = min(seg.x1, seg.x2), max(seg.x1, seg.x2)
            if lo < jx < hi:
                points_on_seg.append((jx, jy))

    if not points_on_seg:
        return [{"x1": seg.x1, "y1": seg.y1, "x2": seg.x2, "y2": seg.y2}]

    # Sort points along segment direction
    if seg.x1 == seg.x2:  # vertical
        points_on_seg.sort(key=lambda p: p[1])
    else:  # horizontal
        points_on_seg.sort(key=lambda p: p[0])

    # Build sub-segments preserving original direction (start → end)
    all_points = [(seg.x1, seg.y1)] + points_on_seg + [(seg.x2, seg.y2)]
    sub_segs: list[dict] = []
    for i in range(len(all_points) - 1):
        p1, p2 = all_points[i], all_points[i + 1]
        if p1 != p2:
            sub_segs.append({"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1]})
    return sub_segs


@dataclass
class WireRouting:
    """Complete routing result for a circuit."""

    topology: str
    segments: list[RoutedSegment]
    junctions: list[JunctionPoint] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    routing_version: str = "1.0"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> WireRouting:
        return cls(
            topology=data["topology"],
            segments=[RoutedSegment(**s) for s in data.get("segments", [])],
            junctions=[JunctionPoint(**j) for j in data.get("junctions", [])],
            metadata=data.get("metadata", {}),
            routing_version=data.get("routing_version", "1.0"),
        )

    def to_legacy_segments(self) -> list[dict]:
        """Convert to legacy WireSegment format for SVG/bridge compatibility.

        Trunk segments are automatically split at junction points so that
        branch endpoints share coordinates with trunk sub-segment endpoints.
        PSIM only connects wires at shared endpoints, so this splitting is
        required for correct connectivity.
        """
        junction_set = {(j.x, j.y) for j in self.junctions}
        result: list[dict] = []
        sub_id = 0
        for s in self.segments:
            sub_segs = _split_segment_at_junctions(s, junction_set)
            for sub in sub_segs:
                sub["id"] = f"{s.id}" if len(sub_segs) == 1 else f"{s.id}_sub{sub_id}"
                sub["net"] = s.net_id
                sub_id += 1
                result.append(sub)
        return result

