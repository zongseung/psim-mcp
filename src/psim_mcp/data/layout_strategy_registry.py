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
