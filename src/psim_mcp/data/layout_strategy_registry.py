"""Layout strategy registry -- topology-specific placement rules.

Declarative metadata extracted from ``layout/strategies/*.py``.  Each entry
describes the flow direction, region template, block ordering, and rail
policies for a topology without importing the actual strategy classes.
"""

from __future__ import annotations

LAYOUT_DEFAULTS: dict[str, int] = {
    "component_spacing": 80,
    "vertical_spacing": 80,
    "ground_rail_y_offset": 150,
}


PLACEMENT_ROWS: dict[str, dict[str, object]] = {
    "power_path": {
        "cursor": "power_x",
        "y_offset": 0,
    },
    "shunt": {
        "cursor": "shunt_x",
        "y_offset_key": "vertical_spacing",
    },
    "control": {
        "cursor": "control_x",
        "y_offset_multiplier": 2,
        "y_offset_key": "vertical_spacing",
    },
    "ground": {
        "cursor": "ground_x",
        "y_offset_key": "ground_rail_y_offset",
    },
    "misc": {
        "cursor": "misc_x",
        "y_offset": 0,
    },
}

LAYOUT_STRATEGIES: dict[str, dict] = {
    # ---- DC-DC non-isolated (ground_rail family) ---------------------------
    "buck": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["input_region", "switch_region", "output_region"],
        "block_order": ["input_stage", "switch_stage", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "boost": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["input_region", "switch_region", "output_region"],
        "block_order": ["input_stage", "boost_stage", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "buck_boost": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["input_region", "switch_region", "output_region"],
        "block_order": ["input_stage", "switch_stage", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- DC-DC isolated (isolation_boundary family) ------------------------
    "flyback": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": ["primary_region", "secondary_region"],
        "block_order": ["primary_input", "switch_primary", "magnetic_transfer", "secondary_rectifier_block", "output_filter"],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
        "isolation_boundary_x": 250,
    },
    "forward": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": ["primary_region", "secondary_region"],
        "block_order": ["primary_input", "switch_primary", "magnetic_transfer", "secondary_rectifier_block", "output_filter"],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "llc": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": [
            "input_region", "half_bridge_region", "resonant_region",
            "magnetizing_region", "transformer_region", "secondary_region", "output_region",
        ],
        "block_order": [
            "input_stage", "half_bridge", "resonant_tank",
            "magnetizing_branch", "transformer_stage", "secondary_rectifier", "output_filter",
        ],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "dab": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": ["primary_bridge_region", "transformer_region", "secondary_bridge_region"],
        "block_order": ["primary_bridge", "transformer_stage", "secondary_bridge"],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "push_pull": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": ["primary_region", "secondary_region"],
        "block_order": ["primary_input", "push_pull_switches", "magnetic_transfer", "output_filter"],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "phase_shifted_full_bridge": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": ["primary_bridge_region", "transformer_region", "secondary_region"],
        "block_order": ["primary_bridge", "transformer_stage", "secondary_rectifier", "output_filter"],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- DC-AC inverters (three_phase family) ------------------------------
    "half_bridge": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 200,
        "region_template": ["dc_bus_region", "leg_region", "output_region"],
        "block_order": ["dc_bus", "half_bridge_leg", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "full_bridge": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 200,
        "region_template": ["dc_bus_region", "bridge_region", "output_region"],
        "block_order": ["dc_bus", "full_bridge_legs", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "three_phase_inverter": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 250,
        "region_template": ["dc_bus_region", "leg_a_region", "leg_b_region", "leg_c_region", "load_region"],
        "block_order": ["dc_bus", "leg_a", "leg_b", "leg_c", "load"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "three_level_npc": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 300,
        "region_template": ["dc_bus_region", "npc_leg_region", "output_region"],
        "block_order": ["dc_bus", "npc_legs", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- AC-DC (simple family) ---------------------------------------------
    "diode_bridge_rectifier": {
        "flow_direction": "left_to_right",
        "region_template": ["ac_source_region", "bridge_region", "dc_output_region"],
        "block_order": ["ac_source", "diode_bridge", "dc_output"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "thyristor_rectifier": {
        "flow_direction": "left_to_right",
        "region_template": ["ac_source_region", "bridge_region", "dc_output_region"],
        "block_order": ["ac_source", "thyristor_bridge", "dc_output"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- PFC ---------------------------------------------------------------
    "boost_pfc": {
        "flow_direction": "left_to_right",
        "region_template": ["ac_input_region", "rectifier_region", "boost_region", "dc_output_region"],
        "block_order": ["ac_input", "input_rectifier", "boost_stage", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "totem_pole_pfc": {
        "flow_direction": "left_to_right",
        "region_template": ["ac_input_region", "bridge_region", "dc_output_region"],
        "block_order": ["ac_input", "totem_pole_bridge", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- Renewable ---------------------------------------------------------
    "pv_mppt_boost": {
        "flow_direction": "left_to_right",
        "region_template": ["pv_source_region", "boost_region", "dc_output_region"],
        "block_order": ["pv_panel", "boost_stage", "output"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "pv_grid_tied": {
        "flow_direction": "left_to_right",
        "region_template": ["pv_source_region", "inverter_region", "grid_region"],
        "block_order": ["pv_panel", "inverter", "grid_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- Motor drives (three_phase family) ---------------------------------
    "bldc_drive": {
        "flow_direction": "left_to_right",
        "region_template": ["dc_bus_region", "inverter_region", "motor_region"],
        "block_order": ["dc_bus", "three_phase_inverter", "bldc_motor"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "pmsm_foc_drive": {
        "flow_direction": "left_to_right",
        "region_template": ["dc_bus_region", "inverter_region", "motor_region", "control_region"],
        "block_order": ["dc_bus", "three_phase_inverter", "pmsm_motor", "foc_controller"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "induction_motor_vf": {
        "flow_direction": "left_to_right",
        "region_template": ["dc_bus_region", "inverter_region", "motor_region"],
        "block_order": ["dc_bus", "three_phase_inverter", "induction_motor"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- Battery -----------------------------------------------------------
    "cc_cv_charger": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["input_region", "converter_region", "battery_region"],
        "block_order": ["input_stage", "buck_stage", "battery_output"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "ev_obc": {
        "flow_direction": "left_to_right",
        "primary_secondary_split": True,
        "region_template": ["ac_input_region", "pfc_region", "dcdc_region", "battery_region"],
        "block_order": ["ac_input", "pfc_stage", "isolated_dcdc", "battery_output"],
        "rail_policy": {"primary_ground": "bottom_horizontal", "secondary_ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- Filters -----------------------------------------------------------
    "lc_filter": {
        "flow_direction": "left_to_right",
        "region_template": ["input_region", "filter_region", "output_region"],
        "block_order": ["input", "lc_section", "output"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "lcl_filter": {
        "flow_direction": "left_to_right",
        "region_template": ["input_region", "filter_region", "output_region"],
        "block_order": ["input", "lcl_section", "output"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- Bidirectional -----------------------------------------------------
    "bidirectional_buck_boost": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["high_side_region", "switch_region", "low_side_region"],
        "block_order": ["high_side", "switch_stage", "low_side"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    # ---- Misc --------------------------------------------------------------
    "cuk": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["input_region", "switch_region", "coupling_region", "output_region"],
        "block_order": ["input_stage", "switch_stage", "coupling_capacitor", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
    "sepic": {
        "flow_direction": "left_to_right",
        "ground_rail_y": 150,
        "region_template": ["input_region", "switch_region", "coupling_region", "output_region"],
        "block_order": ["input_stage", "switch_stage", "coupling_capacitor", "output_filter"],
        "rail_policy": {"ground": "bottom_horizontal"},
        "preferred_block_ordering": "left_to_right",
    },
}


# ---------------------------------------------------------------------------
# Role classification — rule-based inference with explicit overrides.
#
# New roles are auto-classified by keyword patterns in the role name.
# Only roles that DON'T follow the naming convention need an explicit
# override entry. This means adding a new topology with standard role
# names requires ZERO changes to this file.
# ---------------------------------------------------------------------------

# =====================================================================
# ROLE NAMING CONVENTION
# =====================================================================
#
# New component roles are auto-classified by keyword patterns in the
# role name.  Follow these rules when naming roles to ensure automatic
# placement and direction assignment works without adding overrides.
#
# PLACEMENT (which row in the schematic):
#   ground   → name contains "ground" or "gnd"
#   control  → name contains "gate", "drive", "pwm", "controller",
#              "feedback", "sensor", or "control"
#   shunt    → name contains "capacitor" or "cap"
#   power_path → name contains "switch", "source", "inductor",
#                "transformer", "rectifier", "bridge", "diode", "boost"
#   (default) → power_path (if no keyword matched)
#
# DIRECTION (component orientation):
#   90  (vertical)   → name contains "capacitor" or "load"
#   0   (vertical)   → name contains "high_side", "low_side", "primary_switch"
#   270 (horizontal)  → name contains "switch" (but not high/low/primary)
#   0   (default)    → everything else
#
# EXCEPTIONS (roles that break convention → need explicit override):
#   "freewheel_diode"        → shunt (not power_path despite "diode")
#   "magnetizing_inductance" → shunt (not power_path despite "inductance")
#   "load"                   → shunt (generic name, no keyword match)
#   "resonant_capacitor"     → power_path (not shunt despite "capacitor")
#   "coupling_capacitor"     → shunt (matches "capacitor" rule, but explicit)
#   "main_switch"            → direction 270 (horizontal, override)
#   "freewheel_diode"        → direction 270 (vertical cathode-up, override)
#   "magnetizing_inductor"   → direction 90 (vertical shunt, override)
#   "resonant_capacitor"     → direction 0 (horizontal in resonant path)
#
# To add a new role that auto-classifies correctly:
#   Good: "output_inductor"     → power_path, direction 0 (keyword: "inductor")
#   Good: "secondary_rectifier" → power_path, direction 0 (keyword: "rectifier")
#   Good: "filter_capacitor"    → shunt, direction 90 (keyword: "capacitor")
#   Good: "primary_ground_ref"  → ground, direction 0 (keyword: "ground")
#   Bad:  "load_element"        → would default to power_path (no keyword match)
#         → add to _PLACEMENT_OVERRIDES if needed
# =====================================================================

# Explicit overrides (only for roles whose name doesn't match the rules)
_PLACEMENT_OVERRIDES: dict[str, str] = {
    "freewheel_diode": "shunt",       # contains "diode" but is shunt, not power_path
    "magnetizing_inductance": "shunt", # shunt branch of transformer
    "load": "shunt",                   # generic name, placed as shunt
    "resonant_capacitor": "power_path",  # "capacitor" keyword → shunt, but resonant is power_path
    "coupling_capacitor": "shunt",
    "main_switch": "power_path",       # "switch" → power_path (matches rule, but explicit for clarity)
}

# Keyword patterns → placement category (checked in order)
_PLACEMENT_RULES: list[tuple[list[str], str]] = [
    (["ground", "gnd"], "ground"),
    (["gate", "drive", "pwm", "controller", "feedback", "sensor", "control"], "control"),
    (["capacitor", "cap", "filter_capacitor"], "shunt"),
    (["switch", "source", "inductor", "transformer", "rectifier", "bridge", "diode", "boost", "motor", "thyristor", "battery"], "power_path"),
]


def _infer_placement(role: str) -> str:
    """Infer placement category from role name using keyword rules."""
    role_lower = role.lower()
    for keywords, category in _PLACEMENT_RULES:
        for kw in keywords:
            if kw in role_lower:
                return category
    return "power_path"  # default


def _build_role_placement() -> dict[str, str]:
    """Build the complete ROLE_PLACEMENT dict from overrides + all known roles.

    Scans topology_metadata.required_component_roles to discover all roles,
    then classifies each via override or keyword inference.
    """
    all_roles: set[str] = set()
    try:
        from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA
        for meta in TOPOLOGY_METADATA.values():
            all_roles.update(meta.get("required_component_roles", []))
    except ImportError:
        pass

    # Add override keys (they may not appear in metadata)
    all_roles.update(_PLACEMENT_OVERRIDES.keys())

    placement: dict[str, str] = {}
    for role in sorted(all_roles):
        if role in _PLACEMENT_OVERRIDES:
            placement[role] = _PLACEMENT_OVERRIDES[role]
        else:
            placement[role] = _infer_placement(role)
    return placement


ROLE_PLACEMENT: dict[str, str] = _build_role_placement()

# ---------------------------------------------------------------------------
# Direction — rule-based inference with explicit overrides.
#
# Directions are inferred from role name keywords:
#   - "inductor" in power_path → 0 (horizontal)
#   - "capacitor"/"load" in shunt → 90 (vertical)
#   - "switch" at top level → 270 (horizontal MOSFET)
#   - "switch" with "high_side"/"low_side"/"primary" → 0 (vertical)
#   - everything else → 0
# ---------------------------------------------------------------------------

_DIRECTION_OVERRIDES: dict[str, int] = {
    "main_switch": 270,
    "freewheel_diode": 270,
    "magnetizing_inductor": 90,
    "magnetizing_inductance": 90,
    "resonant_capacitor": 0,  # horizontal in resonant path
}


def _infer_direction(role: str) -> int:
    """Infer component direction from role name."""
    role_lower = role.lower()
    # Vertical shunt components
    if any(kw in role_lower for kw in ("capacitor", "load")):
        return 90
    # Vertical switches (half-bridge legs, primary side)
    if any(kw in role_lower for kw in ("high_side", "low_side", "primary_switch")):
        return 0
    # Horizontal switches
    if "switch" in role_lower:
        return 270
    return 0


def _build_role_direction() -> dict[str, int]:
    """Build ROLE_DIRECTION from overrides + inferred for all known roles."""
    direction: dict[str, int] = {}
    for role in ROLE_PLACEMENT:
        if role in _DIRECTION_OVERRIDES:
            direction[role] = _DIRECTION_OVERRIDES[role]
        else:
            direction[role] = _infer_direction(role)
    return direction


ROLE_DIRECTION: dict[str, int] = _build_role_direction()


def get_role_placement(role: str) -> str:
    """Return placement category for a component role."""
    return ROLE_PLACEMENT.get(role, "power_path")


def get_role_direction(role: str) -> int | None:
    """Return preferred direction for a component role, or None if unknown."""
    return ROLE_DIRECTION.get(role)


def get_layout_defaults() -> dict[str, int]:
    """Return default spacing/offset settings for algorithmic layout."""
    return dict(LAYOUT_DEFAULTS)


def get_placement_rows() -> dict[str, dict[str, object]]:
    """Return declarative placement row definitions."""
    return {name: dict(value) for name, value in PLACEMENT_ROWS.items()}


def get_role_row(role: str) -> dict[str, object]:
    """Return row configuration for a component role.

    The row is derived from the role's placement category. Falls back to
    the ``misc`` row when unknown.
    """
    category = get_role_placement(role)
    row = PLACEMENT_ROWS.get(category)
    if row is None:
        row = PLACEMENT_ROWS["misc"]
    return dict(row)


# ---------------------------------------------------------------------------
# Validation — detect roles that fell through to defaults
# ---------------------------------------------------------------------------

def validate_role_classifications() -> list[dict[str, str]]:
    """Check all known roles for suspicious default-only classifications.

    Returns a list of issues. Each issue is a dict with:
    - ``role``: the role name
    - ``field``: "placement" or "direction"
    - ``value``: the assigned value
    - ``reason``: why it's suspicious

    Use this in tests to catch roles that weren't intentionally classified.
    """
    issues: list[dict[str, str]] = []

    for role in ROLE_PLACEMENT:
        # Placement: flagged if not in overrides AND no keyword matched
        # (i.e., fell through to the default "power_path")
        if role not in _PLACEMENT_OVERRIDES:
            inferred = _infer_placement(role)
            if inferred == "power_path":
                # Check if any placement keyword actually matched
                role_lower = role.lower()
                matched = False
                for keywords, _cat in _PLACEMENT_RULES:
                    for kw in keywords:
                        if kw in role_lower:
                            matched = True
                            break
                    if matched:
                        break
                if not matched:
                    issues.append({
                        "role": role,
                        "field": "placement",
                        "value": "power_path",
                        "reason": "no keyword matched — fell to default",
                    })

        # Direction: only flag roles where direction=0 is likely WRONG.
        # direction=0 is the correct default for most components (sources,
        # transformers, horizontal passives, diodes). Only flag roles where
        # the component type typically needs non-zero direction but got 0.
        if role not in _DIRECTION_OVERRIDES:
            inferred_dir = _infer_direction(role)
            # Only suspicious if role name suggests vertical (capacitor/load)
            # but somehow got direction=0, or vice versa.
            role_lower = role.lower()
            if inferred_dir == 90 and "capacitor" not in role_lower and "load" not in role_lower:
                issues.append({
                    "role": role,
                    "field": "direction",
                    "value": str(inferred_dir),
                    "reason": "inferred 90 (vertical) but role name lacks capacitor/load keyword",
                })

    return issues


def get_layout_strategy(topology: str) -> dict | None:
    """Return layout strategy metadata for *topology*, or None if unknown."""
    return LAYOUT_STRATEGIES.get(topology.lower())


def get_flow_direction(topology: str) -> str:
    """Return flow direction for *topology*. Defaults to 'left_to_right'."""
    strategy = get_layout_strategy(topology)
    return strategy["flow_direction"] if strategy else "left_to_right"


def get_region_template(topology: str) -> list[str]:
    """Return ordered region template names for *topology*."""
    strategy = get_layout_strategy(topology)
    if strategy:
        return list(strategy.get("region_template", []))
    return []
