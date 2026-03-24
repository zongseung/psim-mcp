"""Force-directed fine-tuning for component placement.

After initial role-based placement, this applies spring forces
(nets = attraction) and repulsion (overlap prevention) to
improve layout quality.
"""

from __future__ import annotations

import math
from itertools import combinations

from psim_mcp.layout.models import LayoutComponent, LayoutRegion
from psim_mcp.synthesis.graph import GraphNet


# Force constants
ATTRACTION_K = 0.05  # spring constant for connected components
REPULSION_K = 5000.0  # repulsion strength
MIN_DISTANCE = 30.0  # minimum distance to avoid division by zero
OVERLAP_MARGIN = 60  # approximate component bounding box size


def force_adjust(
    components: list[LayoutComponent],
    nets: list[GraphNet],
    iterations: int = 30,
    damping: float = 0.3,
    grid: int = 50,
    regions: dict[str, LayoutRegion] | None = None,
) -> None:
    """Adjust component positions in-place using force-directed algorithm.

    Parameters
    ----------
    components:
        Layout components with initial positions.
    nets:
        Graph nets defining connectivity (attraction springs).
    iterations:
        Number of simulation steps.
    damping:
        Velocity damping factor (0..1). Lower = more damping.
    grid:
        Grid snap size after final iteration.
    regions:
        Optional region bounds for clamping.
    """
    if len(components) < 2:
        return

    # Build component lookup by id
    comp_map: dict[str, LayoutComponent] = {c.id: c for c in components}

    # Extract net connectivity as pairs of component ids
    net_pairs: list[tuple[str, str]] = []
    for net in nets:
        comp_ids = _extract_component_ids(net.pins)
        unique_ids = list(set(comp_ids))
        for a, b in combinations(unique_ids, 2):
            if a in comp_map and b in comp_map:
                net_pairs.append((a, b))

    for iteration in range(iterations):
        forces: dict[str, tuple[float, float]] = {c.id: (0.0, 0.0) for c in components}

        # Attractive forces: connected components pulled together
        for a_id, b_id in net_pairs:
            a = comp_map[a_id]
            b = comp_map[b_id]
            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < MIN_DISTANCE:
                continue
            # Hooke's law: F = k * displacement
            fx = ATTRACTION_K * dx
            fy = ATTRACTION_K * dy
            forces[a_id] = (forces[a_id][0] + fx, forces[a_id][1] + fy)
            forces[b_id] = (forces[b_id][0] - fx, forces[b_id][1] - fy)

        # Repulsive forces: all component pairs push apart
        for a, b in combinations(components, 2):
            dx = b.x - a.x
            dy = b.y - a.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < MIN_DISTANCE * MIN_DISTANCE:
                dist = MIN_DISTANCE
                dist_sq = MIN_DISTANCE * MIN_DISTANCE
            else:
                dist = math.sqrt(dist_sq)

            # Only repel if close enough to matter
            if dist > OVERLAP_MARGIN * 4:
                continue

            # Coulomb-like repulsion: F = K / d^2
            force_mag = REPULSION_K / dist_sq
            nx = dx / dist
            ny = dy / dist
            fx = -force_mag * nx
            fy = -force_mag * ny
            forces[a.id] = (forces[a.id][0] + fx, forces[a.id][1] + fy)
            forces[b.id] = (forces[b.id][0] - fx, forces[b.id][1] - fy)

        # Apply forces with damping
        for c in components:
            fx, fy = forces[c.id]
            c.x = round(c.x + fx * damping)
            c.y = round(c.y + fy * damping)

        # Clamp to region bounds after each iteration
        if regions:
            _clamp_to_regions(components, regions)

    # Final grid snap
    for c in components:
        c.x = round(c.x / grid) * grid
        c.y = round(c.y / grid) * grid


def _extract_component_ids(pins: list[str]) -> list[str]:
    """Extract component IDs from pin references like 'V1.positive'."""
    ids = []
    for pin in pins:
        parts = pin.split(".", 1)
        if parts:
            ids.append(parts[0])
    return ids


def _clamp_to_regions(
    components: list[LayoutComponent],
    regions: dict[str, LayoutRegion],
) -> None:
    """Clamp components to stay within their assigned region bounds."""
    for c in components:
        region = regions.get(c.region_id or "")
        if region is None:
            continue
        c.x = max(region.x, min(c.x, region.x + region.width - OVERLAP_MARGIN))
        c.y = max(region.y, min(c.y, region.y + region.height - OVERLAP_MARGIN))
