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
COMPONENT_SPACING = 80  # min horizontal spacing between components
VERTICAL_SPACING = 80  # min vertical spacing for branch components
MIN_REGION_WIDTH = 120
REGION_GAP = 20
REGION_HEIGHT = 200
START_X = 80
START_Y = 80
GROUND_RAIL_Y_OFFSET = 150  # ground rail relative offset
ISOLATION_GAP = 100  # extra gap for isolated topologies

# Role classification for placement
POWER_PATH_ROLES = {
    "main_switch",
    "output_inductor",
    "resonant_capacitor",
    "resonant_inductor",
    "input_source",
    "isolation_transformer",
    "primary_switch",
    "high_side_switch",
    "low_side_switch",
    "secondary_rectifier",
    "bridge_rectifier",
    "output_rectifier",
    "magnetizing_inductor",
    "boost_diode",
    "boost_inductor",
}

SHUNT_ROLES = {
    "freewheel_diode",
    "output_capacitor",
    "load",
    "magnetizing_inductance",
    "coupling_capacitor",
    "filter_capacitor",
    "filter_inductor",
}

CONTROL_ROLES = {
    "gate_drive",
    "high_side_gate",
    "low_side_gate",
    "pwm_controller",
    "feedback_sensor",
}

GROUND_ROLES = {
    "ground_ref",
    "primary_ground_ref",
    "secondary_ground_ref",
}

# Direction assignment by role / component type
_ROLE_DIRECTION_MAP: dict[str, int] = {
    # Horizontal passives
    "output_inductor": 0,
    "resonant_inductor": 0,
    "boost_inductor": 0,
    "filter_inductor": 0,
    # Vertical passives
    "output_capacitor": 90,
    "filter_capacitor": 90,
    "load": 90,
    "resonant_capacitor": 0,  # horizontal in resonant path
    "coupling_capacitor": 0,
    # Sources
    "input_source": 0,
    # MOSFETs
    "main_switch": 270,  # horizontal MOSFET
    "primary_switch": 0,  # vertical MOSFET
    "high_side_switch": 0,  # vertical
    "low_side_switch": 0,  # vertical
    # Diodes
    "freewheel_diode": 270,  # vertical cathode up
    "secondary_rectifier": 0,  # horizontal
    "boost_diode": 0,
    "output_rectifier": 0,
    "bridge_rectifier": 0,
    # Transformers
    "isolation_transformer": 0,
    "magnetizing_inductor": 90,  # vertical
    # Control
    "gate_drive": 0,
    "high_side_gate": 0,
    "low_side_gate": 0,
    # Ground
    "ground_ref": 0,
    "primary_ground_ref": 0,
    "secondary_ground_ref": 0,
}

# Symbol variant selection by (component_type, direction)
_TYPE_DIR_TO_VARIANT: dict[tuple[str, int], str] = {
    ("DC_Source", 0): "dc_source_vertical",
    ("AC_Source", 0): "ac_source_vertical",
    ("MOSFET", 270): "mosfet_horizontal",
    ("MOSFET", 0): "mosfet_vertical",
    ("Diode", 0): "diode_horizontal",
    ("Diode", 270): "diode_vertical_cathode_up",
    ("Inductor", 0): "inductor_horizontal",
    ("Inductor", 90): "inductor_vertical",
    ("Capacitor", 90): "capacitor_vertical",
    ("Capacitor", 0): "capacitor_horizontal",
    ("Resistor", 90): "resistor_vertical",
    ("Transformer", 0): "transformer_vertical",
    ("IdealTransformer", 0): "ideal_transformer",
    ("DiodeBridge", 0): "diode_bridge",
    ("PWM_Generator", 0): "pwm_block",
    ("Ground", 0): "ground",
}


def auto_place(
    graph: CircuitGraph,
    preferences: dict[str, object] | None = None,
) -> SchematicLayout:
    """Generate SchematicLayout from CircuitGraph algorithmically."""
    prefs = preferences or {}
    strategy = _load_strategy(graph.topology)

    # 1. Allocate regions from blocks
    regions = _allocate_regions(graph.blocks, strategy)

    # 2. Place components in regions
    components = _place_components(graph, regions, strategy)

    # 3. Grid snap
    _snap_to_grid(components)

    # 4. Build constraints
    constraints = _build_constraints(strategy, regions)

    # 5. Enforce constraints (ground rail, bounds)
    _enforce_constraints(components, regions, constraints, strategy)

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
) -> dict[str, LayoutRegion]:
    """Allocate rectangular regions for each block, left-to-right."""
    block_order = strategy.get("block_order", [b.id for b in blocks])
    is_isolated = strategy.get("primary_secondary_split", False)

    # Build a mapping of block_id -> block for quick lookup
    block_map = {b.id: b for b in blocks}

    regions: dict[str, LayoutRegion] = {}
    x_cursor = START_X

    # Determine isolation boundary (between which blocks to add gap)
    isolation_blocks = _find_isolation_boundary(block_order, strategy)

    for i, block_id in enumerate(block_order):
        block = block_map.get(block_id)
        component_count = len(block.component_ids) if block else 1
        region_width = max(component_count * COMPONENT_SPACING, MIN_REGION_WIDTH)

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
            width=max(total_components * COMPONENT_SPACING, MIN_REGION_WIDTH),
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
    region_cursors: dict[str, dict[str, int]] = {}
    for rid in regions:
        region_cursors[rid] = {
            "power_x": 0,
            "shunt_x": 0,
            "control_x": 0,
            "ground_x": 0,
            "misc_x": 0,
        }

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
            region, role, gc.type, region_cursors[region_id]
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
    """Determine component direction based on role, then type."""
    if role in _ROLE_DIRECTION_MAP:
        return _ROLE_DIRECTION_MAP[role]
    # Type-based defaults
    type_defaults: dict[str, int] = {
        "DC_Source": 0,
        "AC_Source": 0,
        "MOSFET": 0,
        "Diode": 0,
        "Inductor": 0,
        "Capacitor": 90,
        "Resistor": 90,
        "Transformer": 0,
        "IdealTransformer": 0,
        "DiodeBridge": 0,
        "PWM_Generator": 0,
        "Ground": 0,
    }
    return type_defaults.get(component_type, 0)


def _compute_position_in_region(
    region: LayoutRegion,
    role: str,
    component_type: str,
    cursors: dict[str, int],
) -> tuple[int, int]:
    """Compute (x, y) for a component within its region.

    Layout rows within a region:
      - Power path: top row (y = region.y)
      - Shunt: below power path (y = region.y + VERTICAL_SPACING)
      - Control: lower section (y = region.y + 2*VERTICAL_SPACING)
      - Ground: at ground rail (y = region.y + GROUND_RAIL_Y_OFFSET)
    """
    if role in GROUND_ROLES:
        x = region.x + cursors["ground_x"]
        y = region.y + GROUND_RAIL_Y_OFFSET
        cursors["ground_x"] += COMPONENT_SPACING
        return x, y

    if role in POWER_PATH_ROLES:
        x = region.x + cursors["power_x"]
        y = region.y
        cursors["power_x"] += COMPONENT_SPACING
        return x, y

    if role in SHUNT_ROLES:
        x = region.x + cursors["shunt_x"]
        y = region.y + VERTICAL_SPACING
        cursors["shunt_x"] += COMPONENT_SPACING
        return x, y

    if role in CONTROL_ROLES:
        x = region.x + cursors["control_x"]
        y = region.y + 2 * VERTICAL_SPACING
        cursors["control_x"] += COMPONENT_SPACING
        return x, y

    # Default: treat as power path
    x = region.x + cursors["misc_x"]
    y = region.y
    cursors["misc_x"] += COMPONENT_SPACING
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
    ground_rail_y = strategy.get("ground_rail_y", START_Y + GROUND_RAIL_Y_OFFSET)

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
) -> None:
    """Enforce placement constraints on components."""
    from psim_mcp.layout.constraint_solver import (
        enforce_rail_alignment,
        enforce_region_bounds,
        enforce_flow_order,
    )

    ground_rail_y = strategy.get("ground_rail_y", START_Y + GROUND_RAIL_Y_OFFSET)

    # Enforce ground rail alignment
    enforce_rail_alignment(components, GROUND_ROLES, ground_rail_y)

    # Enforce region bounds
    enforce_region_bounds(components, regions)

    # Enforce flow ordering
    block_order = strategy.get("block_order", [])
    enforce_flow_order(components, block_order, regions)


def _assign_symbol_variants(
    components: list[LayoutComponent],
    graph: CircuitGraph,
) -> None:
    """Assign symbol variant names based on component type and direction."""
    from psim_mcp.data.symbol_registry import SYMBOL_VARIANTS

    # Build component type lookup
    type_map = {gc.id: gc.type for gc in graph.components}

    for comp in components:
        comp_type = type_map.get(comp.id)
        if comp_type is None:
            continue

        # Try exact (type, direction) match first
        variant = _TYPE_DIR_TO_VARIANT.get((comp_type, comp.direction))
        if variant and variant in SYMBOL_VARIANTS:
            comp.symbol_variant = variant
            continue

        # Fall back to searching SYMBOL_VARIANTS
        for vname, vdata in SYMBOL_VARIANTS.items():
            if vdata["component_type"] == comp_type:
                if vdata["orientation"] == comp.direction:
                    comp.symbol_variant = vname
                    break
        else:
            # Use any variant for this type
            for vname, vdata in SYMBOL_VARIANTS.items():
                if vdata["component_type"] == comp_type:
                    comp.symbol_variant = vname
                    break
