"""Circuit specification validation layer.

Usage::

    from psim_mcp.validators import validate_circuit

    result = validate_circuit(spec_dict)
    if not result.is_valid:
        for err in result.errors:
            print(err)
"""

from __future__ import annotations

from .models import ValidationIssue, ValidationResult
from .structural import validate_structural, validate_connections
from .electrical import validate_electrical
from .parameter import validate_parameters


def validate_circuit(spec: dict) -> ValidationResult:
    """Run all validations on *spec* and return a combined result."""
    # Normalize: ensure both connections and nets are available
    if spec.get("nets") and not spec.get("connections"):
        from psim_mcp.bridge.wiring import nets_to_connections
        spec = dict(spec)  # don't mutate original
        spec["connections"] = nets_to_connections(spec["nets"])
    elif spec.get("connections") and not spec.get("nets"):
        # connections-only is fine, structural validator uses connections
        pass

    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for validator_fn in (validate_structural, validate_electrical, validate_parameters):
        result = validator_fn(spec)
        errors.extend(result.errors)
        warnings.extend(result.warnings)

    # Connection validation (returns a flat list of ValidationIssue)
    conn_issues = validate_connections(spec)
    for issue in conn_issues:
        if issue.severity == "error":
            errors.append(issue)
        else:
            warnings.append(issue)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


__all__ = [
    "validate_circuit",
    "ValidationIssue",
    "ValidationResult",
]
