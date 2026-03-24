"""Constraint enforcement for layout.

Provides a general-purpose constraint dispatcher as well as individual
enforcement functions for rail alignment, region bounds, and flow ordering.

Supported LayoutConstraint kinds:
- ``align_to_rail`` — snap components matching rail roles to a fixed Y
- ``inside_region`` — clamp component positions within region bounds
- ``left_of`` — ensure region ordering along X axis
- ``same_row`` — align a set of components to the same Y
- ``same_column`` — align a set of components to the same X
"""

from __future__ import annotations

from psim_mcp.layout.models import LayoutComponent, LayoutConstraint, LayoutRegion


def enforce_all(
    components: list[LayoutComponent],
    constraints: list[LayoutConstraint],
    regions: dict[str, LayoutRegion],
    component_roles: dict[str, str] | None = None,
) -> None:
    """General-purpose constraint dispatcher.

    Iterates *constraints* and applies the matching enforcement function
    for each ``kind``.  Unknown kinds are silently skipped.
    """
    comp_map = {c.id: c for c in components}

    for constraint in constraints:
        kind = constraint.kind

        if kind == "align_to_rail":
            rail_y = (constraint.value or {}).get("y")  # type: ignore[union-attr]
            if rail_y is not None:
                rail_roles = set(constraint.subject_ids)
                enforce_rail_alignment(
                    components, rail_roles, int(rail_y), component_roles,
                )

        elif kind == "inside_region":
            for cid in constraint.subject_ids:
                comp = comp_map.get(cid)
                if comp:
                    enforce_region_bounds([comp], regions)

        elif kind == "left_of":
            if len(constraint.subject_ids) >= 2:
                enforce_flow_order(
                    components, constraint.subject_ids, regions,
                )

        elif kind == "same_row":
            _enforce_same_row(constraint.subject_ids, comp_map)

        elif kind == "same_column":
            _enforce_same_column(constraint.subject_ids, comp_map)


def _enforce_same_row(
    subject_ids: list[str],
    comp_map: dict[str, LayoutComponent],
) -> None:
    """Align components to the median Y of the group."""
    comps = [comp_map[cid] for cid in subject_ids if cid in comp_map]
    if len(comps) < 2:
        return
    median_y = sorted(c.y for c in comps)[len(comps) // 2]
    for c in comps:
        c.y = median_y


def _enforce_same_column(
    subject_ids: list[str],
    comp_map: dict[str, LayoutComponent],
) -> None:
    """Align components to the median X of the group."""
    comps = [comp_map[cid] for cid in subject_ids if cid in comp_map]
    if len(comps) < 2:
        return
    median_x = sorted(c.x for c in comps)[len(comps) // 2]
    for c in comps:
        c.x = median_x


def enforce_rail_alignment(
    components: list[LayoutComponent],
    rail_roles: set[str],
    rail_y: int,
    component_roles: dict[str, str] | None = None,
) -> None:
    """Move ground/rail components to the specified rail Y coordinate.

    Parameters
    ----------
    components:
        Layout components to adjust.
    rail_roles:
        Set of role names that should be aligned to the rail
        (e.g. {"ground_ref", "primary_ground_ref", "secondary_ground_ref"}).
    rail_y:
        Target Y coordinate for the rail.
    component_roles:
        Mapping of component ID to role name. When provided, role matching
        is exact. Otherwise, falls back to heuristic (y near rail ± tolerance).
    """
    TOLERANCE = 60  # how close to rail_y to be considered "near rail"

    for comp in components:
        # Exact role match if roles are provided
        if component_roles:
            role = component_roles.get(comp.id, "")
            if role in rail_roles:
                comp.y = rail_y
                continue
        else:
            # Heuristic: if component y is near the expected rail, snap it
            if abs(comp.y - rail_y) <= TOLERANCE:
                # Only snap if it looks like a ground-area component
                comp.y = rail_y


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
