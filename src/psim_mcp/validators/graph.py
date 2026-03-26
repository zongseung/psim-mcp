"""Graph-level validation for CircuitGraph instances.

Validates structural integrity of a CircuitGraph before layout/materialization.
"""

from __future__ import annotations

from dataclasses import dataclass

from psim_mcp.synthesis.graph import CircuitGraph


@dataclass
class GraphValidationIssue:
    """A validation issue found in a CircuitGraph."""

    severity: str  # "error" or "warning"
    code: str
    message: str
    component_id: str | None = None


# Required roles per topology (at least one component must have each role).
_REQUIRED_ROLES: dict[str, list[str]] = {
    "buck": [
        "input_source", "ground_ref", "main_switch", "gate_drive",
        "freewheel_diode", "output_inductor", "output_capacitor", "load",
    ],
    "boost": [
        "input_source", "ground_ref", "output_inductor", "main_switch",
        "gate_drive", "boost_diode", "output_capacitor", "load",
    ],
    "buck_boost": [
        "input_source", "ground_ref", "main_switch", "gate_drive",
        "freewheel_diode", "output_inductor", "output_capacitor", "load",
    ],
    "flyback": [
        "input_source", "ground_ref", "isolation_transformer", "primary_switch",
        "gate_drive", "secondary_rectifier", "output_capacitor", "load",
    ],
    "forward": [
        "input_source", "ground_ref", "isolation_transformer", "primary_switch",
        "gate_drive", "secondary_rectifier", "freewheel_diode",
        "output_inductor", "output_capacitor", "load",
        "clamp_diode", "clamp_resistor", "clamp_capacitor",
    ],
    "llc": [
        "input_source", "ground_ref", "high_side_switch", "low_side_switch",
        "high_side_gate", "low_side_gate", "isolation_transformer",
        "resonant_inductor", "resonant_capacitor", "magnetizing_inductor",
        "output_rectifier", "output_capacitor", "load", "secondary_ground_ref",
    ],
    "half_bridge": [
        "input_source", "ground_ref", "high_side_switch", "low_side_switch",
        "gate_drive_high", "gate_drive_low", "dc_bus_cap_high", "dc_bus_cap_low",
        "output_filter_inductor", "output_filter_capacitor", "load",
    ],
    "full_bridge": [
        "input_source", "ground_ref",
        "switch_leg_a_high", "switch_leg_a_low",
        "switch_leg_b_high", "switch_leg_b_low",
        "gate_drive_leg_a_high", "gate_drive_leg_a_low",
        "gate_drive_leg_b_high", "gate_drive_leg_b_low",
        "output_filter_inductor", "output_filter_capacitor", "load",
    ],
    "cuk": [
        "input_source", "ground_ref", "input_inductor", "main_switch",
        "gate_drive", "coupling_capacitor", "output_diode",
        "output_inductor", "output_capacitor", "load",
    ],
    "sepic": [
        "input_source", "ground_ref", "input_inductor", "main_switch",
        "gate_drive", "coupling_capacitor", "output_diode",
        "output_inductor", "output_capacitor", "load",
    ],
    "push_pull": [
        "input_source", "ground_ref", "primary_switch_a", "primary_switch_b",
        "gate_drive_a", "gate_drive_b", "center_tap_transformer",
        "secondary_rectifier", "output_inductor", "output_capacitor", "load",
    ],
    "phase_shifted_full_bridge": [
        "input_source", "ground_ref", "primary_bridge_switches", "gate_drive",
        "isolation_transformer", "secondary_rectifier",
        "output_inductor", "output_capacitor", "load",
    ],
    "dab": [
        "input_source", "ground_ref", "primary_bridge_switches",
        "secondary_bridge_switches", "gate_drive", "isolation_transformer",
        "series_inductor", "output_capacitor", "load", "secondary_gnd_ref",
    ],
    "bidirectional_buck_boost": [
        "input_source", "ground_ref", "high_side_switch", "low_side_switch",
        "gate_drive_high", "gate_drive_low", "inductor",
        "capacitor_high", "capacitor_low", "load",
    ],
    "boost_pfc": [
        "ac_source", "ground_ref", "diode_bridge", "boost_inductor",
        "boost_switch", "gate_drive", "boost_diode",
        "output_capacitor", "load",
    ],
    "totem_pole_pfc": [
        "ac_source", "ground_ref", "boost_inductor",
        "high_freq_switch_a", "high_freq_switch_b",
        "low_freq_switch_a", "low_freq_switch_b",
        "hf_gate_drive", "lf_gate_drive",
        "output_capacitor", "load",
    ],
    "diode_bridge_rectifier": [
        "ac_source", "ground_ref", "diode_bridge",
        "output_capacitor", "load",
    ],
    "thyristor_rectifier": [
        "ac_source", "ground_ref", "thyristors",
        "output_inductor", "output_capacitor", "load",
    ],
    "cc_cv_charger": [
        "input_source", "ground_ref", "main_switch", "gate_drive",
        "freewheel_diode", "output_inductor", "output_capacitor", "battery",
    ],
    "three_phase_inverter": [
        "input_source", "ground_ref", "gate_drive",
        "switch_a_high", "switch_a_low",
        "switch_b_high", "switch_b_low",
        "switch_c_high", "switch_c_low", "load",
    ],
    "three_level_npc": [
        "input_source", "ground_ref", "npc_switches", "clamping_diodes",
        "gate_drive", "dc_bus_lower", "output_inductor", "load",
    ],
    "bldc_drive": [
        "input_source", "ground_ref", "inverter_switches",
        "gate_drive", "bldc_motor",
    ],
    "pmsm_foc_drive": [
        "input_source", "ground_ref", "inverter_switches",
        "gate_drive", "foc_controller", "pmsm_motor",
    ],
    "induction_motor_vf": [
        "input_source", "ground_ref", "inverter_switches",
        "gate_drive", "induction_motor",
    ],
    "lc_filter": [
        "input_source", "ground_ref", "inductor", "capacitor", "load",
    ],
    "lcl_filter": [
        "input_source", "ground_ref", "inductor_1", "inductor_2",
        "capacitor", "load",
    ],
    "pv_mppt_boost": [
        "pv_source", "ground_ref", "boost_inductor", "boost_switch",
        "gate_drive", "boost_diode", "output_capacitor", "load",
    ],
    "ev_obc": [
        "ac_source", "ground_ref", "input_rectifier",
        "pfc_inductor", "pfc_switch", "pfc_boost_diode",
        "dc_link_capacitor", "gate_drive", "isolation_transformer",
        "output_rectifier", "output_capacitor", "battery", "secondary_gnd_ref",
    ],
}


def validate_graph(graph: CircuitGraph) -> list[GraphValidationIssue]:
    """Validate a CircuitGraph and return a list of issues.

    Checks:
    - Components list is non-empty
    - Nets list is non-empty
    - No duplicate component IDs
    - No duplicate net IDs
    - All net pin references point to existing components
    - Orphan components (not referenced by any net)
    - Required roles per topology
    """
    issues: list[GraphValidationIssue] = []

    if not graph.components:
        issues.append(GraphValidationIssue(
            severity="error",
            code="EMPTY_COMPONENTS",
            message="CircuitGraph has no components.",
        ))

    if not graph.nets:
        issues.append(GraphValidationIssue(
            severity="error",
            code="EMPTY_NETS",
            message="CircuitGraph has no nets.",
        ))

    # Check for duplicate component IDs
    seen_comp_ids: set[str] = set()
    for comp in graph.components:
        if comp.id in seen_comp_ids:
            issues.append(GraphValidationIssue(
                severity="error",
                code="DUPLICATE_COMPONENT_ID",
                message=f"Duplicate component ID: '{comp.id}'.",
                component_id=comp.id,
            ))
        seen_comp_ids.add(comp.id)

    # Check for duplicate net IDs
    seen_net_ids: set[str] = set()
    for net in graph.nets:
        if net.id in seen_net_ids:
            issues.append(GraphValidationIssue(
                severity="error",
                code="DUPLICATE_NET_ID",
                message=f"Duplicate net ID: '{net.id}'.",
            ))
        seen_net_ids.add(net.id)

    # Check net pin references and collect referenced components
    referenced_comp_ids: set[str] = set()
    for net in graph.nets:
        for pin_ref in net.pins:
            parts = pin_ref.split(".", 1)
            if len(parts) != 2:
                issues.append(GraphValidationIssue(
                    severity="warning",
                    code="INVALID_PIN_FORMAT",
                    message=f"Pin reference '{pin_ref}' in net '{net.id}' has invalid format.",
                ))
                continue
            comp_id = parts[0]
            referenced_comp_ids.add(comp_id)
            if comp_id not in seen_comp_ids:
                issues.append(GraphValidationIssue(
                    severity="error",
                    code="DANGLING_PIN_REF",
                    message=f"Pin reference '{pin_ref}' in net '{net.id}' references non-existent component '{comp_id}'.",
                ))

    # Check for orphan components (not referenced by any net)
    for comp in graph.components:
        if comp.id not in referenced_comp_ids:
            issues.append(GraphValidationIssue(
                severity="warning",
                code="ORPHAN_COMPONENT",
                message=f"Component '{comp.id}' is not referenced by any net.",
                component_id=comp.id,
            ))

    # Check required roles per topology
    required_roles = _REQUIRED_ROLES.get(graph.topology, [])
    if required_roles:
        present_roles = {comp.role for comp in graph.components if comp.role}
        for role in required_roles:
            if role not in present_roles:
                issues.append(GraphValidationIssue(
                    severity="warning",
                    code="MISSING_REQUIRED_ROLE",
                    message=f"Topology '{graph.topology}' expects role '{role}' but no component has it.",
                ))

    return issues


def is_valid(graph: CircuitGraph) -> bool:
    """Return True if the graph has no errors."""
    issues = validate_graph(graph)
    return not any(i.severity == "error" for i in issues)
