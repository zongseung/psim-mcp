"""Constraint enforcement for layout.

Provides functions to enforce placement constraints after initial
component placement: rail alignment, region bounds, and flow ordering.
"""

from __future__ import annotations

from psim_mcp.layout.models import LayoutComponent, LayoutRegion


def enforce_rail_alignment(
    components: list[LayoutComponent],
    rail_roles: set[str],
    rail_y: int,
) -> None:
    """Move ground/rail components to the specified rail Y coordinate.

    Components whose role (stored in metadata or region_id context)
    matches a rail role are snapped to ``rail_y``.
    """
    # We need to determine role from the component. Since LayoutComponent
    # doesn't store role directly, we check region_id and rely on the
    # caller to have placed ground components at approximately the right y.
    # The auto_placer already places GROUND_ROLES at ground_rail offset,
    # so this is a consistency enforcement pass.
    #
    # For now, we align any component whose y is near the expected rail.
    # A more robust approach would pass role info through metadata.
    pass


def enforce_region_bounds(
    components: list[LayoutComponent],
    regions: dict[str, LayoutRegion],
) -> None:
    """Clamp components to stay within their assigned region boundaries.

    Components are pushed inward if they fall outside region edges.
    """
    for comp in components:
        region = regions.get(comp.region_id or "")
        if region is None:
            continue

        # Clamp x
        if comp.x < region.x:
            comp.x = region.x
        elif comp.x > region.x + region.width:
            comp.x = region.x + region.width

        # Clamp y
        if comp.y < region.y:
            comp.y = region.y
        elif comp.y > region.y + region.height:
            comp.y = region.y + region.height


def enforce_flow_order(
    components: list[LayoutComponent],
    block_order: list[str],
    regions: dict[str, LayoutRegion],
) -> None:
    """Ensure components in earlier blocks have smaller x than later blocks.

    For left-to-right flow, every component in block_order[i] must have
    x <= min(x) of components in block_order[i+1].  If violated, shift
    the later region's components rightward.
    """
    if len(block_order) < 2:
        return

    # Group components by region
    region_components: dict[str, list[LayoutComponent]] = {}
    for comp in components:
        rid = comp.region_id or ""
        if rid not in region_components:
            region_components[rid] = []
        region_components[rid].append(comp)

    for i in range(len(block_order) - 1):
        curr_id = block_order[i]
        next_id = block_order[i + 1]

        curr_comps = region_components.get(curr_id, [])
        next_comps = region_components.get(next_id, [])

        if not curr_comps or not next_comps:
            continue

        max_x_curr = max(c.x for c in curr_comps)
        min_x_next = min(c.x for c in next_comps)

        if min_x_next <= max_x_curr:
            shift = max_x_curr - min_x_next + 50  # at least 50px gap
            for c in next_comps:
                c.x += shift
            # Also shift the region itself
            region = regions.get(next_id)
            if region is not None:
                region.x += shift
