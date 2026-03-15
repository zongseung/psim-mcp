"""Regression tests for parser hardcoding fixes."""
import pytest
from psim_mcp.parsers.intent_parser import parse_circuit_intent


class TestContextAwareVoltageMapping:
    """7.2: Multi-voltage context handling."""

    def test_input_output_context(self):
        r = parse_circuit_intent("입력 400V, 출력 48V LLC 컨버터")
        assert r["specs"].get("vin") == 400.0
        assert r["specs"].get("vout_target") == 48.0

    def test_three_voltages_with_context(self):
        r = parse_circuit_intent("입력 400V, 출력 48V, 보조 15V")
        assert r["specs"].get("vin") == 400.0
        assert r["specs"].get("vout_target") == 48.0
        # 15V should be unassigned or extra

    def test_no_context_voltages_low_confidence(self):
        r = parse_circuit_intent("400V 48V 15V 컨버터")
        # With 3 voltages and no clear context, confidence should not be "high"
        assert r["confidence"] in ("low", "medium")


class TestFieldNameAliases:
    """7.1: Field name mismatches."""

    def test_iout_matches_iout_target(self):
        """Parser's 'iout' should satisfy metadata's 'iout_target'."""
        r = parse_circuit_intent("buck 48V 입력 12V 출력 5A")
        # iout should be in specs
        assert "iout" in r["specs"]

    def test_buck_without_current_still_works(self):
        """Buck should work with just vin + vout (iout optional)."""
        r = parse_circuit_intent("buck 컨버터 48V 입력 12V 출력")
        assert r["topology"] == "buck"
        assert r["confidence"] in ("high", "medium")


class TestTopologySpecificRequired:
    """7.1 + 4.3: Per-topology required fields."""

    def test_inverter_no_vout_needed(self):
        r = parse_circuit_intent("3상 인버터 600V")
        assert r["topology"] == "three_phase_inverter"
        assert "vout_target" not in r["missing_fields"]

    def test_flyback_specific_questions(self):
        r = parse_circuit_intent("flyback 컨버터")
        assert r["topology"] == "flyback"
        assert len(r["questions"]) > 0

    def test_pv_no_required_fields(self):
        r = parse_circuit_intent("태양광 MPPT 회로")
        assert r["topology"] == "pv_mppt_boost"
        # PV has no strict required fields
        assert len(r["missing_fields"]) == 0

    def test_pv_voc_isc_do_not_pollute_generic_slots(self):
        r = parse_circuit_intent("태양광 MPPT 회로 Voc 40V Isc 10A")
        specs = r["specs"]
        assert specs.get("voc") == 40.0
        assert specs.get("isc") == 10.0
        assert "vin" not in specs
        assert "iout" not in specs


class TestDescriptiveRequests:
    """7.4: Requests without explicit topology name."""

    def test_notebook_adapter(self):
        r = parse_circuit_intent("노트북 어댑터 19V")
        assert r["topology"] is not None
        assert len(r["topology_candidates"]) > 0
        assert r["specs"].get("vout_target") == 19.0
        assert "vin" not in r["specs"]

    def test_isolated_supply(self):
        r = parse_circuit_intent("절연형 5V 보조전원")
        candidates = r.get("topology_candidates", [])
        assert len(candidates) > 0

    def test_ev_charging(self):
        r = parse_circuit_intent("전기차 충전기 220V")
        assert r["topology"] is not None


class TestMultiFrequency:
    """7.3: Multi-frequency handling."""

    def test_single_frequency(self):
        r = parse_circuit_intent("buck 100kHz")
        assert r["specs"].get("fsw") == 100000.0

    def test_two_frequencies(self):
        r = parse_circuit_intent("출력 60Hz 스위칭 100kHz 인버터")
        specs = r["specs"]
        # Should have both frequencies mapped
        has_fsw = "fsw" in specs or "switching_frequency" in specs
        assert has_fsw
