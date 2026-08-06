"""Reconstruct electrical nets from parsed schematic geometry.

Algorithm (union-find over exact grid points — PSIM schematics are
grid-snapped, so tolerance-based fuzzy matching is unnecessary and would
only introduce false connections):

1. Collect wire segments (polylines split into consecutive point pairs).
2. Split every segment at any "interesting point" (another segment's
   endpoint, a component pin, a label anchor) that lies on it — this
   realizes T-junction semantics: an endpoint touching a wire mid-span
   connects, while two wires crossing mid-span (no endpoint at the
   crossing) stay separate (crossover).
3. Union the endpoints of every resulting sub-segment.
4. Union same-named labels (label-only nets, no drawn wire).
5. Union all ground pins (electrically-equivalent symbols are one node).
6. Snap component pins to clusters by exact coordinate; coincident pins
   connect directly (pin-to-pin contact is legal in PSIM).

Output is the existing :class:`~psim_mcp.importer.graph.CircuitGraph`
so validators, set_parameter and the simulation path apply unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .graph import CircuitGraph, GraphComponent, GraphNet
from .parser import ParsedSchematic, Point

_GROUND_TYPES = {"GROUND", "GND"}


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[Point, Point] = {}

    def add(self, p: Point) -> None:
        self._parent.setdefault(p, p)

    def find(self, p: Point) -> Point:
        self.add(p)
        root = p
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[p] != root:  # path compression
            self._parent[p], p = root, self._parent[p]
        return root

    def union(self, a: Point, b: Point) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def _on_segment(pt: Point, a: Point, b: Point) -> bool:
    """True if pt lies on segment a-b (collinear and within its bbox)."""
    (px, py), (ax, ay), (bx, by) = pt, a, b
    if (bx - ax) * (py - ay) != (by - ay) * (px - ax):  # cross product
        return False
    return min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by)


@dataclass
class ReconstructionResult:
    """CircuitGraph plus reconstruction diagnostics."""

    graph: CircuitGraph
    dangling_pins: list[str] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)


def reconstruct(parsed: ParsedSchematic, *, topology: str = "imported") -> ReconstructionResult:
    """Build a CircuitGraph with reconstructed nets from parsed geometry."""
    uf = _UnionFind()

    # 1. Wire segments
    segments: list[tuple[Point, Point]] = []
    for wire in parsed.wires:
        segments.extend(wire.segments)

    # 2. Interesting points: segment endpoints, pins, label anchors
    interesting: set[Point] = set()
    for a, b in segments:
        interesting.add(a)
        interesting.add(b)
    for comp in parsed.components:
        interesting.update(comp.pins)
    for label in parsed.labels:
        interesting.add(label.point)

    # 3. Split segments at interesting points, union sub-segment endpoints
    for a, b in segments:
        mids = sorted(
            (p for p in interesting if p != a and p != b and _on_segment(p, a, b)),
            key=lambda p: (abs(p[0] - a[0]), abs(p[1] - a[1])),
        )
        chain = [a, *mids, b]
        for u, v in zip(chain, chain[1:]):
            uf.union(u, v)

    # 4. Same-named labels form one net
    labels_by_name: dict[str, list[Point]] = {}
    for label in parsed.labels:
        labels_by_name.setdefault(label.name, []).append(label.point)
    for points in labels_by_name.values():
        for p in points[1:]:
            uf.union(points[0], p)

    # 5. All ground pins are one node
    ground_pins = [
        pin for comp in parsed.components if comp.type.upper() in _GROUND_TYPES for pin in comp.pins
    ]
    for p in ground_pins[1:]:
        uf.union(ground_pins[0], p)

    # 6. Assign pins to clusters (exact coordinate match)
    clusters: dict[Point, dict] = {}

    def _cluster(root: Point) -> dict:
        return clusters.setdefault(root, {"pins": [], "labels": set(), "ground": False})

    for comp in parsed.components:
        is_ground = comp.type.upper() in _GROUND_TYPES
        for idx, pin in enumerate(comp.pins):
            entry = _cluster(uf.find(pin))
            entry["pins"].append(f"{comp.id}.{idx}")
            if is_ground:
                entry["ground"] = True
    for name, points in labels_by_name.items():
        _cluster(uf.find(points[0]))["labels"].add(name)

    # Build nets: clusters connecting >=2 pins are real nets
    nets: list[GraphNet] = []
    dangling: list[str] = []
    used_net_ids: dict[str, int] = {}
    seq = 0
    for entry in clusters.values():
        pins = sorted(entry["pins"])
        if len(pins) < 2:
            dangling.extend(pins)
            continue
        if entry["ground"]:
            base = "GND"
        elif entry["labels"]:
            base = sorted(entry["labels"])[0]
        else:
            seq += 1
            base = f"N{seq:03d}"
        count = used_net_ids.get(base, 0)
        used_net_ids[base] = count + 1
        net_id = base if count == 0 else f"{base}_{count + 1}"
        nets.append(
            GraphNet(
                id=net_id,
                pins=pins,
                role="ground" if entry["ground"] else None,
                metadata={"labels": sorted(entry["labels"])},
            )
        )

    components = [
        GraphComponent(
            id=comp.id,
            type=comp.type,
            parameters=dict(comp.parameters),
            metadata={**comp.metadata, "name": comp.name},
        )
        for comp in parsed.components
    ]

    graph = CircuitGraph(
        topology=topology,
        components=components,
        nets=sorted(nets, key=lambda n: (-len(n.pins), n.id)),
        simulation=dict(parsed.simulation),
        metadata={"source": "psim_convert_to_python"},
    )

    total_pins = sum(len(c.pins) for c in parsed.components)
    stats = {
        "components": len(components),
        "wires": len(parsed.wires),
        "wire_segments": len(segments),
        "labels": len(parsed.labels),
        "nets": len(nets),
        "connected_pins": total_pins - len(dangling),
        "dangling_pins": len(dangling),
    }
    return ReconstructionResult(graph=graph, dangling_pins=sorted(dangling), stats=stats)
