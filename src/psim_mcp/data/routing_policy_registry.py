"""Routing policy registry -- topology-specific routing rules.

Declarative metadata extracted from ``routing/strategies/*.py`` and
``routing/trunk_branch.py``.  Each entry describes ground policy,
power trunk policy, net layer classification, and control signal
routing preferences for a topology.
"""

from __future__ import annotations

ROUTING_POLICIES: dict[str, dict] = {
    # ---- DC-DC non-isolated ------------------------------------------------
    "buck": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "switch_node": "power",
            "drive_signal": "control",
        },
    },
    "boost": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "switch_node": "power",
            "drive_signal": "control",
        },
    },
    "buck_boost": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "switch_node": "power",
            "drive_signal": "control",
        },
    },
    # ---- DC-DC isolated ----------------------------------------------------
    "flyback": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "primary_switch_node": "power",
            "secondary_ac": "power",
            "drive_signal": "control",
        },
    },
    "forward": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "drive_signal": "control",
        },
    },
    "llc": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "half_bridge_midpoint": "power",
            "resonant_series": "power",
            "resonant_node": "power",
            "secondary_ac_pos": "power",
            "secondary_ac_neg": "power",
            "high_side_drive": "control",
            "low_side_drive": "control",
        },
    },
    "dab": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
        },
    },
    "push_pull": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
        },
    },
    "phase_shifted_full_bridge": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
        },
    },
    # ---- DC-AC inverters ---------------------------------------------------
    "half_bridge": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "output_ac": "power",
            "drive_signal": "control",
        },
    },
    "full_bridge": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "output_ac": "power",
        },
    },
    "three_phase_inverter": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "phase_a": "power",
            "phase_b": "power",
            "phase_c": "power",
        },
    },
    "three_level_npc": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "dc_bus_neutral": "power",
            "output_ac": "power",
        },
    },
    # ---- AC-DC -------------------------------------------------------------
    "diode_bridge_rectifier": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "ac_input": "power",
            "dc_output": "power",
        },
    },
    "thyristor_rectifier": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "ac_input": "power",
            "dc_output": "power",
            "firing_signal": "control",
        },
    },
    # ---- PFC ---------------------------------------------------------------
    "boost_pfc": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "ac_input": "power",
            "rectified_dc": "power",
            "boost_output": "power",
            "drive_signal": "control",
        },
    },
    "totem_pole_pfc": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "ac_input": "power",
            "dc_output": "power",
        },
    },
    # ---- Renewable ---------------------------------------------------------
    "pv_mppt_boost": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "pv_positive": "power",
            "boost_output": "power",
            "drive_signal": "control",
        },
    },
    "pv_grid_tied": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "pv_positive": "power",
            "grid_ac": "power",
        },
    },
    # ---- Motor drives ------------------------------------------------------
    "bldc_drive": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "phase_a": "power",
            "phase_b": "power",
            "phase_c": "power",
        },
    },
    "pmsm_foc_drive": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "phase_a": "power",
            "phase_b": "power",
            "phase_c": "power",
        },
    },
    "induction_motor_vf": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "dc_bus_positive": "power",
            "phase_a": "power",
            "phase_b": "power",
            "phase_c": "power",
        },
    },
    # ---- Battery -----------------------------------------------------------
    "cc_cv_charger": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "drive_signal": "control",
        },
    },
    "ev_obc": {
        "ground_policy": "dual_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "primary_ground": "ground",
            "secondary_ground": "ground",
            "ac_input": "power",
            "dc_output": "power",
        },
    },
    # ---- Filters -----------------------------------------------------------
    "lc_filter": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_signal": "power",
            "output_signal": "power",
        },
    },
    "lcl_filter": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_signal": "power",
            "output_signal": "power",
        },
    },
    # ---- Bidirectional -----------------------------------------------------
    "bidirectional_buck_boost": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "high_side_positive": "power",
            "low_side_positive": "power",
            "switch_node": "power",
            "drive_signal": "control",
        },
    },
    # ---- Misc --------------------------------------------------------------
    "cuk": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "coupling_node": "power",
            "drive_signal": "control",
        },
    },
    "sepic": {
        "ground_policy": "bottom_rail",
        "power_trunk_policy": "left_to_right",
        "control_signal_policy": "shortest_direct",
        "crossing_policy": "minimize",
        "net_layers": {
            "ground": "ground",
            "input_positive": "power",
            "output_positive": "power",
            "coupling_node": "power",
            "drive_signal": "control",
        },
    },
}


# Net role -> preferred trunk axis, mirrored from trunk_branch.py for reference.
NET_ROLE_TRUNK_AXIS: dict[str, str] = {
    "ground": "horizontal",
    "primary_ground": "horizontal",
    "secondary_ground": "horizontal",
    "input_positive": "horizontal",
    "output_positive": "horizontal",
    "switch_node": "vertical",
    "half_bridge_midpoint": "vertical",
    "resonant_node": "vertical",
    "drive_signal": "direct",
    "high_side_drive": "direct",
    "low_side_drive": "direct",
}


def get_routing_policy(topology: str) -> dict | None:
    """Return routing policy metadata for *topology*, or None if unknown."""
    return ROUTING_POLICIES.get(topology.lower())


def get_net_layer(topology: str, net_role: str) -> str:
    """Return the net layer for a specific net role within a topology.

    Returns ``"unknown"`` if neither the topology nor the net role is registered.
    """
    policy = get_routing_policy(topology)
    if policy:
        return policy.get("net_layers", {}).get(net_role, "unknown")
    return "unknown"


def get_net_role_policy(topology: str, net_role: str) -> dict | None:
    """Return routing style for a specific net role within a topology.

    Looks up the net layer and trunk axis for a given net role, combining
    net_layers from the topology policy with NET_ROLE_TRUNK_AXIS.
    """
    policy = get_routing_policy(topology)
    if policy is None:
        return None
    layer = policy.get("net_layers", {}).get(net_role)
    axis = NET_ROLE_TRUNK_AXIS.get(net_role, "horizontal")
    if layer is None:
        return None
    return {"layer": layer, "axis": axis}
