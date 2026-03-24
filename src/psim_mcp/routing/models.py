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


@dataclass
class WireRouting:
    """Complete routing result for a circuit."""

    topology: str
    segments: list[RoutedSegment]
    junctions: list[JunctionPoint] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> WireRouting:
        return cls(
            topology=data["topology"],
            segments=[RoutedSegment(**s) for s in data.get("segments", [])],
            junctions=[JunctionPoint(**j) for j in data.get("junctions", [])],
            metadata=data.get("metadata", {}),
        )

    def to_legacy_segments(self) -> list[dict]:
        """Convert to legacy WireSegment format for SVG/bridge compatibility."""
        return [
            {
                "id": s.id,
                "net": s.net_id,
                "x1": s.x1,
                "y1": s.y1,
                "x2": s.x2,
                "y2": s.y2,
            }
            for s in self.segments
        ]

