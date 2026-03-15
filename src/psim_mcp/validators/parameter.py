"""Parameter range validation for circuit specifications."""

from __future__ import annotations

from .models import ValidationIssue, ValidationResult

# Parameters that must not be negative
_NON_NEGATIVE_PARAMS = {"resistance", "inductance", "capacitance"}

# Switching frequency reasonable range (Hz)
_FSW_MIN = 100
_FSW_MAX = 10_000_000  # 10 MHz

# Voltage reasonable range (V)
_VOLTAGE_MAX = 100_000  # 100 kV


def validate_parameters(spec: dict) -> ValidationResult:
    """Check parameter values are within reasonable ranges."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    components = spec.get("components", [])

    for comp in components:
        comp_id = comp.get("id", "unknown")
        params = comp.get("parameters", {})
        if not isinstance(params, dict):
            continue

        for param_name, value in params.items():
            if not isinstance(value, (int, float)):
                continue

            # --- Non-negative checks ---
            if param_name in _NON_NEGATIVE_PARAMS and value < 0:
                errors.append(
                    ValidationIssue(
                        severity="error",
                        code="PARAM_NEGATIVE",
                        message=f"'{param_name}' = {value} is negative in component '{comp_id}'.",
                        component_id=comp_id,
                        suggestion=f"Set '{param_name}' to a non-negative value.",
                    )
                )

            # --- Switching frequency range ---
            if param_name == "switching_frequency":
                if value < _FSW_MIN or value > _FSW_MAX:
                    warnings.append(
                        ValidationIssue(
                            severity="warning",
                            code="PARAM_FSW_RANGE",
                            message=(
                                f"Switching frequency = {value} Hz in '{comp_id}' "
                                f"is outside typical range ({_FSW_MIN} Hz ~ {_FSW_MAX/1e6:.0f} MHz)."
                            ),
                            component_id=comp_id,
                            suggestion=f"Use a value between {_FSW_MIN} Hz and {_FSW_MAX/1e6:.0f} MHz.",
                        )
                    )

            # --- Voltage range ---
            if param_name == "voltage":
                if value < 0:
                    errors.append(
                        ValidationIssue(
                            severity="error",
                            code="PARAM_VOLTAGE_NEGATIVE",
                            message=f"Voltage = {value} V is negative in component '{comp_id}'.",
                            component_id=comp_id,
                            suggestion="Use a non-negative voltage value.",
                        )
                    )
                elif value > _VOLTAGE_MAX:
                    warnings.append(
                        ValidationIssue(
                            severity="warning",
                            code="PARAM_VOLTAGE_HIGH",
                            message=f"Voltage = {value} V in '{comp_id}' exceeds {_VOLTAGE_MAX/1e3:.0f} kV.",
                            component_id=comp_id,
                            suggestion=f"Typical range is 0 ~ {_VOLTAGE_MAX/1e3:.0f} kV.",
                        )
                    )

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
