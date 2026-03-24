"""Layout strategy registry -- topology-specific placement rules.

Declarative metadata extracted from ``layout/strategies/*.py``.  Each entry
describes the flow direction, region template, block ordering, and rail
policies for a topology without importing the actual strategy classes.
"""

from __future__ import annotations

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
# Role classification for auto-placement within regions
# These categorise component roles by their placement row.
# ---------------------------------------------------------------------------

ROLE_PLACEMENT: dict[str, str] = {
    # Power path (top row, horizontal)
    "main_switch": "power_path",
    "output_inductor": "power_path",
    "resonant_capacitor": "power_path",
    "resonant_inductor": "power_path",
    "input_source": "power_path",
    "isolation_transformer": "power_path",
    "primary_switch": "power_path",
    "high_side_switch": "power_path",
    "low_side_switch": "power_path",
    "secondary_rectifier": "power_path",
    "bridge_rectifier": "power_path",
    "output_rectifier": "power_path",
    "magnetizing_inductor": "power_path",
    "boost_diode": "power_path",
    "boost_inductor": "power_path",
    # Shunt (below power path, vertical)
    "freewheel_diode": "shunt",
    "output_capacitor": "shunt",
    "load": "shunt",
    "magnetizing_inductance": "shunt",
    "coupling_capacitor": "shunt",
    "filter_capacitor": "shunt",
    "filter_inductor": "shunt",
    # Control (bottom)
    "gate_drive": "control",
    "high_side_gate": "control",
    "low_side_gate": "control",
    "pwm_controller": "control",
    "feedback_sensor": "control",
    # Ground (rail)
    "ground_ref": "ground",
    "primary_ground_ref": "ground",
    "secondary_ground_ref": "ground",
}

# ---------------------------------------------------------------------------
# Direction (orientation) per role
# ---------------------------------------------------------------------------

ROLE_DIRECTION: dict[str, int] = {
    # Horizontal passives
    "output_inductor": 0,
    "resonant_inductor": 0,
    "boost_inductor": 0,
    "filter_inductor": 0,
    # Vertical passives
    "output_capacitor": 90,
    "filter_capacitor": 90,
    "load": 90,
    "resonant_capacitor": 0,
    "coupling_capacitor": 0,
    # Sources
    "input_source": 0,
    # Switches
    "main_switch": 270,
    "primary_switch": 0,
    "high_side_switch": 0,
    "low_side_switch": 0,
    # Diodes
    "freewheel_diode": 270,
    "secondary_rectifier": 0,
    "boost_diode": 0,
    "output_rectifier": 0,
    "bridge_rectifier": 0,
    # Transformers
    "isolation_transformer": 0,
    "magnetizing_inductor": 90,
    # Control
    "gate_drive": 0,
    "high_side_gate": 0,
    "low_side_gate": 0,
    # Ground
    "ground_ref": 0,
    "primary_ground_ref": 0,
    "secondary_ground_ref": 0,
}


def get_role_placement(role: str) -> str:
    """Return placement category for a component role."""
    return ROLE_PLACEMENT.get(role, "power_path")


def get_role_direction(role: str) -> int | None:
    """Return preferred direction for a component role, or None if unknown."""
    return ROLE_DIRECTION.get(role)


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
