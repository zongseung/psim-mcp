from psim_mcp.data.bridge_mapping_registry import get_parameter_mapping


def test_transformer_parameter_mapping_matches_converted_flyback_example():
    mapping = get_parameter_mapping("Transformer")

    assert mapping["turns_ratio"] is None
    assert mapping["np_turns"] == "Np__primary_"
    assert mapping["ns_turns"] == "Ns__secondary_"
    assert mapping["magnetizing_inductance"] == "Lm__magnetizing_"


def test_ideal_transformer_parameter_mapping_matches_converted_llc_example():
    mapping = get_parameter_mapping("IdealTransformer")

    assert mapping["turns_ratio"] is None
    assert mapping["np_turns"] == "Np__primary_"
    assert mapping["ns_turns"] == "Ns__secondary_"
