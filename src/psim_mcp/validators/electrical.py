"""Electrical validation for circuit specifications."""

from __future__ import annotations

from .models import ValidationIssue, ValidationResult

_SOURCE_TYPES = {"DC_Source", "AC_Source", "PV_Panel", "Battery"}
_LOAD_TYPES = {"Resistor", "DC_Motor", "Induction_Motor", "PMSM", "BLDC_Motor", "SRM"}


def validate_electrical(spec: dict) -> ValidationResult:
    """Check electrical sanity of a circuit spec dict."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    components = spec.get("components", [])
    comp_types = {comp.get("type", "") for comp in components}

    # --- At least one source ---
    if not comp_types & _SOURCE_TYPES:
        errors.append(
            ValidationIssue(
                severity="error",
                code="ELEC_NO_SOURCE",
                message="Circuit has no power source.",
                suggestion=f"Add a source component (e.g. {', '.join(sorted(_SOURCE_TYPES))}).",
            )
        )

    # --- At least one load ---
    if not comp_types & _LOAD_TYPES:
        warnings.append(
            ValidationIssue(
                severity="warning",
                code="ELEC_NO_LOAD",
                message="Circuit has no obvious load component.",
                suggestion=f"Consider adding a load (e.g. {', '.join(sorted(_LOAD_TYPES)[:4])}).",
            )
        )

    # --- Short-circuit check: source positive and negative in same net ---
    nets = spec.get("nets", [])
    # Build a lookup: component_id -> type
    comp_type_map: dict[str, str] = {}
    for comp in components:
        comp_type_map[comp.get("id", "")] = comp.get("type", "")

    for net in nets:
        net_pins = net.get("pins", net.get("connections", []))
        # Parse connection strings like "V1.positive"
        pos_sources: set[str] = set()
        neg_sources: set[str] = set()
        for conn in net_pins:
            parts = conn.rsplit(".", 1)
            if len(parts) != 2:
                continue
            comp_id, pin = parts
            comp_type = comp_type_map.get(comp_id, "")
            if comp_type in _SOURCE_TYPES:
                if pin in ("positive", "plus", "p"):
                    pos_sources.add(comp_id)
                elif pin in ("negative", "minus", "n"):
                    neg_sources.add(comp_id)

        # If same source has both positive and negative in this net => short
        shorted = pos_sources & neg_sources
        for src_id in shorted:
            errors.append(
                ValidationIssue(
                    severity="error",
                    code="ELEC_SHORT",
                    message=f"Source '{src_id}' has positive and negative terminals in the same net '{net.get('name', net.get('id', ''))}'.",
                    component_id=src_id,
                    suggestion="Separate source terminals into different nets.",
                )
            )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
