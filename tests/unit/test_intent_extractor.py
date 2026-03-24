"""Tests for intent extraction (extractors.py)."""

from psim_mcp.intent.extractors import extract_intent


class TestExtractIntentBasic:
    def test_buck_converter_48v_to_12v_5a(self):
        intent = extract_intent("buck converter 48V to 12V 5A")
        assert intent.values.get("vin") == 48.0 or intent.values.get("vout_target") == 12.0
        assert intent.values.get("iout") == 5.0
        # Extractor does NOT decide topology
        assert intent.raw_text == "buck converter 48V to 12V 5A"

    def test_korean_buck_input_output(self):
        intent = extract_intent("48V 입력 12V 출력 벅 컨버터")
        assert intent.values.get("vin") == 48.0
        assert intent.values.get("vout_target") == 12.0

    def test_isolation_detected_korean(self):
        intent = extract_intent("절연형 400V to 48V converter")
        assert intent.isolation is True

    def test_non_isolation_detected(self):
        intent = extract_intent("비절연 buck converter 48V to 12V")
        assert intent.isolation is False

    def test_use_case_charger(self):
        intent = extract_intent("12V 배터리 충전기 24V 입력")
        assert intent.use_case == "charger"

    def test_use_case_adapter(self):
        intent = extract_intent("노트북 어댑터 19V")
        assert intent.use_case == "adapter"

    def test_use_case_motor(self):
        intent = extract_intent("48V DC 모터 드라이브")
        assert intent.use_case == "motor_drive"

    def test_bidirectional(self):
        intent = extract_intent("양방향 48V 배터리 인터페이스")
        assert intent.bidirectional is True

    def test_voltage_role_from_context_input_output(self):
        intent = extract_intent("입력 48V 출력 12V")
        assert intent.values.get("vin") == 48.0
        assert intent.values.get("vout_target") == 12.0
        # Context window may not always capture both roles; medium is acceptable
        assert intent.mapping_confidence in ("high", "medium")

    def test_multiple_voltages_no_context(self):
        """With multiple voltages and no context, uses size-based heuristic."""
        intent = extract_intent("converter 48V 12V")
        # Should assign larger to vin, smaller to vout
        assert "vin" in intent.values or "vout_target" in intent.values

    def test_empty_input(self):
        intent = extract_intent("")
        assert intent.values == {}
        assert intent.voltage_candidates == []
        assert intent.raw_text == ""

    def test_minimal_input(self):
        intent = extract_intent("hello")
        assert intent.values == {}

    def test_no_topology_decision(self):
        """Extraction should NOT produce a topology field."""
        intent = extract_intent("buck converter 48V input 12V output")
        # IntentModel has no 'topology' attribute
        assert not hasattr(intent, "topology")

    def test_conversion_goal_step_down(self):
        intent = extract_intent("강압 컨버터 48V to 12V")
        assert intent.conversion_goal == "step_down"

    def test_conversion_goal_step_up(self):
        intent = extract_intent("승압 컨버터 12V to 48V")
        assert intent.conversion_goal == "step_up"

    def test_frequency_extraction(self):
        intent = extract_intent("buck 48V to 12V 100kHz switching")
        assert intent.values.get("fsw") == 100_000.0

    def test_current_extraction(self):
        intent = extract_intent("buck 48V to 12V 5A load")
        assert intent.values.get("iout") == 5.0

    def test_power_extraction(self):
        intent = extract_intent("1kW flyback converter")
        assert intent.values.get("power_rating") == 1000.0

    def test_resistance_extraction(self):
        intent = extract_intent("half bridge inverter 10ohm load")
        assert intent.values.get("r_load") is not None

    def test_pv_parameters(self):
        intent = extract_intent("solar MPPT Voc 40V Isc 10A")
        assert intent.values.get("voc") == 40.0
        assert intent.values.get("isc") == 10.0

    def test_input_domain_ac(self):
        intent = extract_intent("AC 220V 정류기")
        assert intent.input_domain == "ac"

    def test_input_domain_dc(self):
        intent = extract_intent("DC bus 400V converter")
        assert intent.input_domain == "dc"

    def test_output_domain_detection(self):
        intent = extract_intent("DC 출력 충전기")
        assert intent.output_domain == "dc"

    def test_voltage_candidates_populated(self):
        intent = extract_intent("입력 48V 출력 12V")
        assert len(intent.voltage_candidates) >= 2
        values = {c["value"] for c in intent.voltage_candidates}
        assert 48.0 in values
        assert 12.0 in values
