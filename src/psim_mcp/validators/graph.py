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
    "buck": ["input_source", "ground_ref", "main_switch", "output_inductor", "load"],
    "flyback": ["input_source", "ground_ref", "isolation_transformer", "primary_switch", "load"],
    "llc": ["input_source", "ground_ref", "high_side_switch", "low_side_switch", "isolation_transformer", "load"],
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
