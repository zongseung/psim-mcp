"""Tests for role classification rules in layout_strategy_registry.

Ensures:
1. Override roles are classified correctly (regression guard)
2. No role falls to default without a keyword match (suspicious detection)
3. Naming convention rules work for standard role patterns
"""

import pytest

from psim_mcp.data.layout_strategy_registry import (
    ROLE_DIRECTION,
    ROLE_PLACEMENT,
    _infer_direction,
    _infer_placement,
    validate_role_classifications,
)


# --- Override regression tests ---
# These roles break naming conventions and MUST be explicitly overridden.
# If any of these fail, someone removed an override entry.


class TestPlacementOverrides:
    """Regression: roles that need explicit placement overrides."""

    def test_freewheel_diode_is_shunt(self):
        assert ROLE_PLACEMENT.get("freewheel_diode") == "shunt"

    def test_magnetizing_inductance_is_shunt(self):
        assert ROLE_PLACEMENT.get("magnetizing_inductance") == "shunt"

    def test_load_is_shunt(self):
        assert ROLE_PLACEMENT.get("load") == "shunt"

    def test_resonant_capacitor_is_power_path(self):
        assert ROLE_PLACEMENT.get("resonant_capacitor") == "power_path"

    def test_coupling_capacitor_is_shunt(self):
        assert ROLE_PLACEMENT.get("coupling_capacitor") == "shunt"


class TestDirectionOverrides:
    """Regression: roles that need explicit direction overrides."""

    def test_main_switch_direction_270(self):
        assert ROLE_DIRECTION.get("main_switch") == 270

    def test_freewheel_diode_direction_270(self):
        assert ROLE_DIRECTION.get("freewheel_diode") == 270

    def test_magnetizing_inductor_direction_90(self):
        assert ROLE_DIRECTION.get("magnetizing_inductor") == 90

    def test_magnetizing_inductance_direction_90(self):
        assert ROLE_DIRECTION.get("magnetizing_inductance") == 90

    def test_resonant_capacitor_direction_0(self):
        assert ROLE_DIRECTION.get("resonant_capacitor") == 0


# --- Keyword inference tests ---
# Standard role names should auto-classify without overrides.


class TestPlacementInference:
    """Naming convention: standard patterns auto-classify."""

    def test_ground_ref(self):
        assert _infer_placement("ground_ref") == "ground"

    def test_secondary_ground_ref(self):
        assert _infer_placement("secondary_ground_ref") == "ground"

    def test_gate_drive(self):
        assert _infer_placement("gate_drive") == "control"

    def test_high_side_gate(self):
        assert _infer_placement("high_side_gate") == "control"

    def test_output_capacitor(self):
        assert _infer_placement("output_capacitor") == "shunt"

    def test_output_inductor(self):
        assert _infer_placement("output_inductor") == "power_path"

    def test_isolation_transformer(self):
        assert _infer_placement("isolation_transformer") == "power_path"

    def test_bridge_rectifier(self):
        assert _infer_placement("bridge_rectifier") == "power_path"

    def test_boost_diode(self):
        assert _infer_placement("boost_diode") == "power_path"

    def test_input_source(self):
        assert _infer_placement("input_source") == "power_path"

    def test_unknown_role_defaults_to_power_path(self):
        assert _infer_placement("totally_unknown_thing") == "power_path"


class TestDirectionInference:
    """Naming convention: standard patterns auto-set direction."""

    def test_output_capacitor_90(self):
        assert _infer_direction("output_capacitor") == 90

    def test_filter_capacitor_90(self):
        assert _infer_direction("filter_capacitor") == 90

    def test_load_90(self):
        assert _infer_direction("load") == 90

    def test_high_side_switch_0(self):
        assert _infer_direction("high_side_switch") == 0

    def test_low_side_switch_0(self):
        assert _infer_direction("low_side_switch") == 0

    def test_generic_switch_270(self):
        assert _infer_direction("some_switch") == 270

    def test_unknown_defaults_to_0(self):
        assert _infer_direction("mystery_component") == 0


# --- Suspicious role detection ---


class TestValidateClassifications:
    """Ensure no role silently fell to defaults without matching a keyword."""

    def test_no_suspicious_roles(self):
        issues = validate_role_classifications()
        if issues:
            msg = "Roles with suspicious default-only classification:\n"
            for issue in issues:
                msg += f"  {issue['role']}: {issue['field']}={issue['value']} ({issue['reason']})\n"
            pytest.fail(msg)

    def test_validation_returns_list(self):
        result = validate_role_classifications()
        assert isinstance(result, list)
