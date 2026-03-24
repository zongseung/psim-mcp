"""Algorithmic auto-layout engine.

Generates SchematicLayout from CircuitGraph using:
1. Block-based region allocation (from layout_strategy_registry)
2. Role-based component placement within regions
3. Grid snap (PSIM 50px grid)
4. Constraint enforcement (ground rail, flow direction)
5. Symbol variant selection (from symbol_registry)

This replaces topology-specific hardcoded coordinate tables.
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph, FunctionalBlock
from psim_mcp.layout.models import (
    LayoutComponent,
    LayoutConstraint,
    LayoutRegion,
    SchematicLayout,
)
from psim_mcp.layout.common import PIN_SPACING

# Grid and spacing constants
GRID = PIN_SPACING  # 50px PSIM grid
MIN_REGION_WIDTH = 120
REGION_GAP = 20
REGION_HEIGHT = 200
START_X = 80
START_Y = 80
ISOLATION_GAP = 100  # extra gap for isolated topologies

# ---------------------------------------------------------------------------
# Role classification and direction — loaded from layout_strategy_registry.
# No hardcoded role sets or direction maps in auto_placer itself.
# ---------------------------------------------------------------------------
from psim_mcp.data.layout_strategy_registry import (
    ROLE_PLACEMENT,
    get_layout_defaults,
    get_placement_rows,
    get_role_direction,
    get_role_row,
)

# Derived sets for fast membership checks (built from registry, not hardcoded)
POWER_PATH_ROLES = {r for r, cat in ROLE_PLACEMENT.items() if cat == "power_path"}
SHUNT_ROLES = {r for r, cat in ROLE_PLACEMENT.items() if cat == "shunt"}
CONTROL_ROLES = {r for r, cat in ROLE_PLACEMENT.items() if cat == "control"}
GROUND_ROLES = {r for r, cat in ROLE_PLACEMENT.items() if cat == "ground"}

def _build_type_dir_to_variant() -> dict[tuple[str, int], str]:
    """Build (component_type, direction) → variant_name lookup from symbol_registry.

    This is fully registry-driven — no hardcoded fallback table.
    """
    try:
        from psim_mcp.data.symbol_registry import SYMBOL_VARIANTS
    except ImportError:
        return {}

    mapping: dict[tuple[str, int], str] = {}
    for variant_name, variant_data in SYMBOL_VARIANTS.items():
        comp_type = variant_data.get("component_type", "")
        orientation = variant_data.get("orientation", 0)
        key = (comp_type, orientation)
        # First variant wins per (type, direction) pair
        if key not in mapping:
            mapping[key] = variant_name
    return mapping


# Built once at import time from symbol_registry — no hardcoded values
_TYPE_DIR_TO_VARIANT: dict[tuple[str, int], str] = _build_type_dir_to_variant()


def auto_place(
    graph: CircuitGraph,
    preferences: dict[str, object] | None = None,
) -> SchematicLayout:
    """Generate SchematicLayout from CircuitGraph algorithmically."""
    prefs = preferences or {}
    strategy = _load_strategy(graph.topology)
    layout_defaults = get_layout_defaults()

    # 1. Allocate regions from blocks
    regions = _allocate_regions(graph.blocks, strategy, layout_defaults)

    # 2. Place components in regions
    components = _place_components(graph, regions, strategy, layout_defaults)

    # 2b. Force-directed fine-tuning (reduce wire length, prevent overlap)
    from psim_mcp.layout.force_directed import force_adjust
    force_adjust(
        components,
        graph.nets,
        iterations=30,
        damping=0.3,
        grid=GRID,
        regions=regions,
    )

    # 3. Grid snap
    _snap_to_grid(components)

    # 4. Build constraints
    constraints = _build_constraints(strategy, regions)

    # 5. Enforce constraints (ground rail, bounds)
    component_roles = {gc.id: gc.role for gc in graph.components if gc.role}
    _enforce_constraints(components, regions, constraints, strategy, component_roles)

    # 5b. Re-snap after constraint enforcement (shifts may break grid)
    _snap_to_grid(components)

    # 6. Select symbol variants
    _assign_symbol_variants(components, graph)

    return SchematicLayout(
        topology=graph.topology,
        components=components,
        regions=list(regions.values()),
        constraints=constraints,
        metadata={
            "flow_direction": strategy.get("flow_direction", "left_to_right"),
            "algorithm": "auto_place_v1",
        },
    )


def _load_strategy(topology: str) -> dict:
    """Load strategy from layout_strategy_registry. Fall back to defaults."""
    from psim_mcp.data.layout_strategy_registry import LAYOUT_STRATEGIES

    strategy = LAYOUT_STRATEGIES.get(topology)
    if strategy is not None:
        return dict(strategy)
    # Sensible defaults for unknown topologies
    return {
        "flow_direction": "left_to_right",
        "region_template": ["main_region"],
        "block_order": [],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    }


def _allocate_regions(
    blocks: list[FunctionalBlock],
    strategy: dict,
    layout_defaults: dict[str, int],
) -> dict[str, LayoutRegion]:
    """Allocate rectangular regions for each block, left-to-right."""
    block_order = strategy.get("block_order", [b.id for b in blocks])
    is_isolated = strategy.get("primary_secondary_split", False)
    component_spacing = int(strategy.get("component_spacing", layout_defaults["component_spacing"]))

    # Build a mapping of block_id -> block for quick lookup
    block_map = {b.id: b for b in blocks}

    regions: dict[str, LayoutRegion] = {}
    x_cursor = START_X

    # Determine isolation boundary (between which blocks to add gap)
    isolation_blocks = _find_isolation_boundary(block_order, strategy)

    for i, block_id in enumerate(block_order):
        block = block_map.get(block_id)
        component_count = len(block.component_ids) if block else 1
        region_width = max(component_count * component_spacing, MIN_REGION_WIDTH)

        # Derive region role from block
        if block is not None:
            role = block.role or block.type
        else:
            role = block_id

        regions[block_id] = LayoutRegion(
            id=block_id,
            role=role,
            x=x_cursor,
            y=START_Y,
            width=region_width,
            height=REGION_HEIGHT,
        )
        x_cursor += region_width + REGION_GAP

        # Add isolation gap after primary side
        if is_isolated and block_id in isolation_blocks:
            x_cursor += ISOLATION_GAP

    # If no blocks matched the order, create a single catch-all region
    if not regions:
        total_components = len([b for b in blocks for _ in b.component_ids]) or 1
        regions["main_region"] = LayoutRegion(
            id="main_region",
            role="main",
            x=START_X,
            y=START_Y,
            width=max(total_components * component_spacing, MIN_REGION_WIDTH),
            height=REGION_HEIGHT,
        )

    return regions


def _find_isolation_boundary(
    block_order: list[str],
    strategy: dict,
) -> set[str]:
    """Identify blocks after which an isolation gap should be inserted.

    For isolated topologies, the gap goes before the first "secondary" block.
    We detect this by looking for blocks containing 'secondary', 'output',
    or 'rectifier' keywords after transformer/magnetic blocks.
    """
    if not strategy.get("primary_secondary_split", False):
        return set()

    secondary_keywords = {"secondary", "output", "rectifier"}
    primary_keywords = {"primary", "input", "switch", "half_bridge", "resonant",
                        "magnetizing", "magnetic", "transformer"}

    # Find last primary block
    last_primary_idx = -1
    for i, bid in enumerate(block_order):
        bid_lower = bid.lower()
        if any(kw in bid_lower for kw in primary_keywords):
            last_primary_idx = i

    if last_primary_idx >= 0 and last_primary_idx < len(block_order) - 1:
        return {block_order[last_primary_idx]}

    return set()


def _place_components(
    graph: CircuitGraph,
    regions: dict[str, LayoutRegion],
    strategy: dict,
    layout_defaults: dict[str, int],
) -> list[LayoutComponent]:
    """Place each component within its assigned region based on role."""
    # Map component_id -> block_id
    comp_to_block: dict[str, str] = {}
    for block in graph.blocks:
        for cid in block.component_ids:
            # First block wins for region assignment
            if cid not in comp_to_block:
                comp_to_block[cid] = block.id

    components: list[LayoutComponent] = []

    # Track placement cursors per region for each row type
    placement_rows = get_placement_rows()
    region_cursors: dict[str, dict[str, int]] = {}
    for rid in regions:
        region_cursors[rid] = {row["cursor"]: 0 for row in placement_rows.values()}

    # Misc region for unassigned components
    misc_region_id = _get_misc_region_id(regions)

    for gc in graph.components:
        role = gc.role or ""
        block_id = comp_to_block.get(gc.id)
        region_id = block_id if block_id and block_id in regions else misc_region_id

        region = regions.get(region_id)
        if region is None:
            # Should not happen, but safety fallback
            region = next(iter(regions.values()))
            region_id = region.id

        direction = _get_direction_for_role(role, gc.type)
        x, y = _compute_position_in_region(
            region,
            role,
            gc.type,
            region_cursors[region_id],
            strategy,
            layout_defaults,
        )

        components.append(
            LayoutComponent(
                id=gc.id,
                x=x,
                y=y,
                direction=direction,
                symbol_variant=None,  # assigned in step 6
                region_id=region_id,
            )
        )

    return components


def _get_misc_region_id(regions: dict[str, LayoutRegion]) -> str:
    """Return the ID of a misc/catch-all region, creating one if needed."""
    if "main_region" in regions:
        return "main_region"
    # Use the last region as fallback
    return list(regions.keys())[-1] if regions else "main_region"


def _get_direction_for_role(role: str, component_type: str) -> int:
    """Determine component direction from registry, then component type default."""
    # 1. Role-based direction from layout_strategy_registry
    role_dir = get_role_direction(role)
    if role_dir is not None:
        return role_dir
    # 2. Component type default from symbol_registry
    try:
        from psim_mcp.data.symbol_registry import SYMBOL_VARIANTS
        for _vname, vdata in SYMBOL_VARIANTS.items():
            if vdata.get("component_type") == component_type:
                return vdata.get("orientation", 0)
    except ImportError:
        pass
    return 0


def _compute_position_in_region(
    region: LayoutRegion,
    role: str,
    component_type: str,
    cursors: dict[str, int],
    strategy: dict,
    layout_defaults: dict[str, int],
) -> tuple[int, int]:
    """Compute (x, y) for a component within its region.

    Layout rows within a region:
      - Power path: top row (y = region.y)
      - Shunt: below power path (y = region.y + VERTICAL_SPACING)
      - Control: lower section (y = region.y + 2*VERTICAL_SPACING)
      - Ground: at ground rail (y = region.y + GROUND_RAIL_Y_OFFSET)
    """
    _ = component_type
    component_spacing = int(strategy.get("component_spacing", layout_defaults["component_spacing"]))
    role_row = get_role_row(role)
    cursor_key = str(role_row.get("cursor", "misc_x"))
    base_offset = int(role_row.get("y_offset", 0))
    offset_key = role_row.get("y_offset_key")
    if isinstance(offset_key, str):
        base_offset = int(strategy.get(offset_key, layout_defaults.get(offset_key, base_offset)))
    multiplier = int(role_row.get("y_offset_multiplier", 1))
    y = region.y + base_offset * multiplier
    x = region.x + cursors[cursor_key]
    cursors[cursor_key] += component_spacing
    return x, y


def _snap_to_grid(components: list[LayoutComponent]) -> None:
    """Round all component positions to the nearest grid multiple."""
    for c in components:
        c.x = round(c.x / GRID) * GRID
        c.y = round(c.y / GRID) * GRID


def _build_constraints(
    strategy: dict,
    regions: dict[str, LayoutRegion],
) -> list[LayoutConstraint]:
    """Build layout constraints from strategy metadata."""
    constraints: list[LayoutConstraint] = []

    # Region ordering constraints (left_of)
    region_ids = list(regions.keys())
    for i in range(len(region_ids) - 1):
        constraints.append(
            LayoutConstraint(
                kind="left_of",
                subject_ids=[region_ids[i], region_ids[i + 1]],
            )
        )

    # Rail alignment constraints from rail_policy
    rail_policy = strategy.get("rail_policy", {})
    ground_rail_y = strategy.get("ground_rail_y", START_Y + get_layout_defaults()["ground_rail_y_offset"])

    for rail_name, _rail_type in rail_policy.items():
        constraints.append(
            LayoutConstraint(
                kind="align_to_rail",
                subject_ids=[rail_name],
                value={"y": ground_rail_y},
            )
        )

    return constraints


def _enforce_constraints(
    components: list[LayoutComponent],
    regions: dict[str, LayoutRegion],
    constraints: list[LayoutConstraint],
    strategy: dict,
    component_roles: dict[str, str] | None = None,
) -> None:
    """Enforce placement constraints via the general-purpose dispatcher.

    All constraint enforcement goes through enforce_all() which dispatches
    by constraint.kind. Additional structural constraints (region bounds,
    flow order) are applied afterwards.
    """
    from psim_mcp.layout.constraint_solver import (
        enforce_all,
        enforce_region_bounds,
        enforce_flow_order,
    )

    # 1. General-purpose dispatch for all LayoutConstraint objects
    enforce_all(components, constraints, regions, component_roles)

    # 2. Structural enforcement (always applied regardless of constraints list)
    enforce_region_bounds(components, regions)

    block_order = strategy.get("block_order", [])
    enforce_flow_order(components, block_order, regions)


def _assign_symbol_variants(
    components: list[LayoutComponent],
    graph: CircuitGraph,
) -> None:
    """Assign symbol variant names from symbol_registry.

    Fully registry-driven: looks up SYMBOL_VARIANTS by (type, direction),
    then falls back to any variant matching the component type.
    No hardcoded variant table is used.
    """
    try:
        from psim_mcp.data.symbol_registry import SYMBOL_VARIANTS
    except ImportError:
        return

    # Build component type lookup
    type_map = {gc.id: gc.type for gc in graph.components}

    for comp in components:
        comp_type = type_map.get(comp.id)
        if comp_type is None:
            continue

        # 1. Exact (type, direction) match via registry-built lookup
        variant = _TYPE_DIR_TO_VARIANT.get((comp_type, comp.direction))
        if variant:
            comp.symbol_variant = variant
            continue

        # 2. Search registry for matching orientation
        for vname, vdata in SYMBOL_VARIANTS.items():
            if vdata["component_type"] == comp_type and vdata["orientation"] == comp.direction:
                comp.symbol_variant = vname
                break
        else:
            # 3. Any variant for this component type
            for vname, vdata in SYMBOL_VARIANTS.items():
                if vdata["component_type"] == comp_type:
                    comp.symbol_variant = vname
                    break
