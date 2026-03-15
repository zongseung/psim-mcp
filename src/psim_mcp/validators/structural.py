"""Structural validation for circuit specifications."""

from __future__ import annotations

from .models import ValidationIssue, ValidationResult

# Import the canonical component set from the library when available.
try:
    from psim_mcp.data.component_library import COMPONENTS as _LIBRARY

    _KNOWN_KINDS: set[str] = set(_LIBRARY)
except Exception:  # pragma: no cover
    _KNOWN_KINDS = set()


def validate_structural(spec: dict) -> ValidationResult:
    """Check structural integrity of a circuit spec dict."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    components = spec.get("components", [])

    # --- Empty component list ---
    if not components:
        errors.append(
            ValidationIssue(
                severity="error",
                code="STRUCT_EMPTY",
                message="Circuit has no components.",
                suggestion="Add at least one component to the circuit.",
            )
        )
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # --- Duplicate component IDs ---
    seen_ids: set[str] = set()
    for comp in components:
        comp_id = comp.get("id", "")
        if comp_id in seen_ids:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="STRUCT_DUP_ID",
                    message=f"Duplicate component ID: '{comp_id}'.",
                    component_id=comp_id,
                    suggestion="Ensure every component has a unique ID.",
                )
            )
        seen_ids.add(comp_id)

    # --- Component kind exists in library ---
    if _KNOWN_KINDS:
        for comp in components:
            kind = comp.get("type", "")
            if kind and kind not in _KNOWN_KINDS:
                warnings.append(
                    ValidationIssue(
                        severity="warning",
                        code="STRUCT_UNKNOWN_KIND",
                        message=f"Component type '{kind}' is not in the component library.",
                        component_id=comp.get("id"),
                        suggestion=f"Valid types include: {', '.join(sorted(_KNOWN_KINDS)[:10])} ...",
                    )
                )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
