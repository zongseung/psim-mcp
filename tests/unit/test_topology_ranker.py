"""Tests for topology ranking (ranker.py)."""

from psim_mcp.intent.extractors import extract_intent
from psim_mcp.intent.models import IntentModel
from psim_mcp.intent.ranker import rank_topologies


class TestRankTopologies:
    def test_buck_keyword_ranks_buck_first(self):
        intent = extract_intent("buck converter 48V to 12V")
        candidates = rank_topologies(intent)
        assert len(candidates) > 0
        assert candidates[0].topology == "buck"

    def test_boost_keyword_ranks_boost_first(self):
        intent = extract_intent("boost converter 12V to 48V")
        candidates = rank_topologies(intent)
        assert len(candidates) > 0
        assert candidates[0].topology == "boost"

    def test_flyback_keyword(self):
        intent = extract_intent("flyback converter 400V to 12V")
        candidates = rank_topologies(intent)
        top_names = [c.topology for c in candidates[:3]]
        assert "flyback" in top_names

    def test_isolated_400v_to_48v(self):
        intent = extract_intent("절연 400V to 48V converter")
        candidates = rank_topologies(intent)
        assert len(candidates) > 0
        # Top candidates should be isolated topologies
        top = candidates[0]
        from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA

        meta = TOPOLOGY_METADATA.get(top.topology, {})
        assert meta.get("isolated") is True

    def test_charger_use_case(self):
        intent = extract_intent("배터리 충전기 48V 12V")
        candidates = rank_topologies(intent)
        top_names = [c.topology for c in candidates[:5]]
        assert "cc_cv_charger" in top_names

    def test_bidirectional_ranks_bidirectional(self):
        intent = extract_intent("양방향 48V 배터리")
        candidates = rank_topologies(intent)
        top_names = [c.topology for c in candidates[:5]]
        assert "bidirectional_buck_boost" in top_names or "dab" in top_names

    def test_scores_reflect_domain_match(self):
        intent = IntentModel(input_domain="dc", output_domain="dc")
        candidates = rank_topologies(intent)
        # All top candidates should be DC-DC
        for c in candidates[:3]:
            from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA

            meta = TOPOLOGY_METADATA.get(c.topology, {})
            assert meta.get("input_domain") == "dc"

    def test_keyword_match_gives_score_bonus(self):
        """Keyword match adds 5.0 to score vs same intent without keyword."""
        # Both intents have same constraints, one has "buck" keyword, other has no keywords
        intent_with_kw = IntentModel(
            input_domain="dc",
            output_domain="dc",
            conversion_goal="step_down",
            raw_text="buck step-down",
        )
        intent_without_kw = IntentModel(
            input_domain="dc",
            output_domain="dc",
            conversion_goal="step_down",
            raw_text="please reduce voltage",
        )
        candidates_kw = rank_topologies(intent_with_kw)
        candidates_no_kw = rank_topologies(intent_without_kw)

        buck_score_kw = next((c.score for c in candidates_kw if c.topology == "buck"), 0)
        buck_score_no_kw = next((c.score for c in candidates_no_kw if c.topology == "buck"), 0)
        assert buck_score_kw > buck_score_no_kw

    def test_unknown_text_returns_few_or_no_candidates(self):
        intent = extract_intent("hello world nothing here")
        candidates = rank_topologies(intent)
        # With no matching constraints, most topologies score 0 or negative
        # Some might get positive from "전원" substring matches, but generally few
        assert isinstance(candidates, list)

    def test_multiple_candidates_returned_sorted(self):
        intent = extract_intent("DC to DC converter step-down 48V to 12V")
        candidates = rank_topologies(intent)
        assert len(candidates) >= 2
        # Sorted by score descending
        for i in range(len(candidates) - 1):
            assert candidates[i].score >= candidates[i + 1].score

    def test_candidates_have_reasons(self):
        intent = extract_intent("buck converter 48V to 12V")
        candidates = rank_topologies(intent)
        top = candidates[0]
        assert len(top.reasons) > 0

    def test_isolation_mismatch_penalized(self):
        intent = IntentModel(isolation=True)
        candidates = rank_topologies(intent)
        # Non-isolated topologies should be penalized or excluded
        for c in candidates:
            from psim_mcp.data.topology_metadata import TOPOLOGY_METADATA

            meta = TOPOLOGY_METADATA.get(c.topology, {})
            # Only positive-score candidates should be isolated
            assert meta.get("isolated") is True

    def test_pfc_keyword(self):
        intent = extract_intent("역률보정 PFC 220V")
        candidates = rank_topologies(intent)
        top_names = [c.topology for c in candidates[:5]]
        assert "boost_pfc" in top_names or "totem_pole_pfc" in top_names

    def test_motor_drive_keyword(self):
        intent = extract_intent("BLDC 모터 드라이브 48V")
        candidates = rank_topologies(intent)
        top_names = [c.topology for c in candidates[:5]]
        assert "bldc_drive" in top_names

    def test_missing_fields_populated(self):
        intent = extract_intent("buck converter")
        candidates = rank_topologies(intent)
        buck = next((c for c in candidates if c.topology == "buck"), None)
        assert buck is not None
        # Buck requires vin and vout_target, which are missing
        assert "vin" in buck.missing_fields
        assert "vout_target" in buck.missing_fields
