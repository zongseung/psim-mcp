"""Parameter-name mapping tests against the bridge's single source of truth."""

from psim_mcp.bridge.bridge_script import _get_parameter_name_mapping


def test_transformer_parameter_mapping_matches_converted_flyback_example():
    mapping = _get_parameter_name_mapping("TF_1F_1")

    assert mapping["turns_ratio"] is None
    assert mapping["np_turns"] == "Np__primary_"
    assert mapping["ns_turns"] == "Ns__secondary_"
    assert mapping["magnetizing_inductance"] == "Lm__magnetizing_"


def test_ideal_transformer_parameter_mapping_matches_converted_llc_example():
    mapping = _get_parameter_name_mapping("TF_IDEAL")

    assert mapping["turns_ratio"] is None
    assert mapping["np_turns"] == "Np__primary_"
    assert mapping["ns_turns"] == "Ns__secondary_"


def test_igbt_alias_uses_runtime_mapping():
    mapping = _get_parameter_name_mapping("MULTI_IGBT")

    assert mapping["on_resistance"] == "R_transistor"


def test_unknown_component_type_falls_back_to_flat_map():
    mapping = _get_parameter_name_mapping("SOME_UNKNOWN_TYPE")

    assert mapping["resistance"] == "Resistance"
    assert mapping["inductance"] == "Inductance"
