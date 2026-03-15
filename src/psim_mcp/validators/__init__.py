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
from .structural import validate_structural
from .electrical import validate_electrical
from .parameter import validate_parameters


def validate_circuit(spec: dict) -> ValidationResult:
    """Run all validations on *spec* and return a combined result."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for validator_fn in (validate_structural, validate_electrical, validate_parameters):
        result = validator_fn(spec)
        errors.extend(result.errors)
        warnings.extend(result.warnings)

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
