"""Tests for clarification policy (clarification.py)."""

from psim_mcp.intent.clarification import analyze_clarification_needs
from psim_mcp.intent.models import IntentModel, TopologyCandidate


class TestClarificationPolicy:
    def test_no_clarification_when_clear(self):
        """No clarification needed when topology is clear and specs complete."""
        intent = IntentModel(
            values={"vin": 48.0, "vout_target": 12.0},
            mapping_confidence="high",
            isolation=False,
        )
        candidates = [
            TopologyCandidate(topology="buck", score=10.0, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        assert len(needs) == 0

    def test_no_candidates_triggers_no_match(self):
        intent = IntentModel()
        needs = analyze_clarification_needs(intent, [])
        assert len(needs) == 1
        assert needs[0].kind == "no_match"
        assert needs[0].priority == "high"

    def test_ambiguous_topology_close_scores(self):
        """Top 2 candidates within 20% triggers ambiguous_topology."""
        intent = IntentModel(values={"vin": 48.0, "vout_target": 12.0})
        candidates = [
            TopologyCandidate(topology="buck", score=8.0, missing_fields=[]),
            TopologyCandidate(topology="forward", score=7.5, missing_fields=[]),
            TopologyCandidate(topology="flyback", score=5.0, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        ambiguous = [n for n in needs if n.kind == "ambiguous_topology"]
        assert len(ambiguous) == 1
        assert "buck" in ambiguous[0].options
        assert "forward" in ambiguous[0].options

    def test_no_ambiguity_when_clear_winner(self):
        """No ambiguity when top candidate clearly wins."""
        intent = IntentModel(values={"vin": 48.0, "vout_target": 12.0})
        candidates = [
            TopologyCandidate(topology="buck", score=10.0, missing_fields=[]),
            TopologyCandidate(topology="boost", score=3.0, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        ambiguous = [n for n in needs if n.kind == "ambiguous_topology"]
        assert len(ambiguous) == 0

    def test_missing_required_fields(self):
        intent = IntentModel(values={})
        candidates = [
            TopologyCandidate(
                topology="buck",
                score=5.0,
                missing_fields=["vin", "vout_target"],
            ),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        missing = [n for n in needs if n.kind == "missing_field"]
        assert len(missing) == 2
        fields = {n.field for n in missing}
        assert "vin" in fields
        assert "vout_target" in fields

    def test_ambiguous_voltage(self):
        intent = IntentModel(
            mapping_confidence="low",
            voltage_candidates=[
                {"value": 48.0, "role_hint": None},
                {"value": 24.0, "role_hint": None},
                {"value": 12.0, "role_hint": None},
            ],
        )
        candidates = [
            TopologyCandidate(topology="buck", score=5.0, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        voltage_needs = [n for n in needs if n.kind == "ambiguous_voltage"]
        assert len(voltage_needs) == 1
        assert voltage_needs[0].priority == "high"

    def test_no_voltage_ambiguity_when_high_confidence(self):
        intent = IntentModel(
            mapping_confidence="high",
            voltage_candidates=[
                {"value": 48.0, "role_hint": "vin"},
                {"value": 12.0, "role_hint": "vout_target"},
            ],
        )
        candidates = [
            TopologyCandidate(topology="buck", score=10.0, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        voltage_needs = [n for n in needs if n.kind == "ambiguous_voltage"]
        assert len(voltage_needs) == 0

    def test_isolation_ambiguity(self):
        """When isolation is unknown and candidates mix isolated/non-isolated."""
        intent = IntentModel(isolation=None)
        candidates = [
            TopologyCandidate(topology="flyback", score=8.0, missing_fields=[]),  # isolated
            TopologyCandidate(topology="buck", score=7.5, missing_fields=[]),  # non-isolated
            TopologyCandidate(topology="llc", score=6.0, missing_fields=[]),  # isolated
        ]
        needs = analyze_clarification_needs(intent, candidates)
        iso_needs = [n for n in needs if n.kind == "ambiguous_isolation"]
        assert len(iso_needs) == 1
        assert "절연" in iso_needs[0].options

    def test_no_isolation_ambiguity_when_all_same(self):
        """No isolation question when all top candidates have same isolation."""
        intent = IntentModel(isolation=None)
        candidates = [
            TopologyCandidate(topology="buck", score=8.0, missing_fields=[]),
            TopologyCandidate(topology="boost", score=7.0, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        iso_needs = [n for n in needs if n.kind == "ambiguous_isolation"]
        assert len(iso_needs) == 0

    def test_no_isolation_ambiguity_when_explicit(self):
        """No isolation question when user explicitly specified isolation."""
        intent = IntentModel(isolation=True)
        candidates = [
            TopologyCandidate(topology="flyback", score=8.0, missing_fields=[]),
            TopologyCandidate(topology="buck", score=7.5, missing_fields=[]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        iso_needs = [n for n in needs if n.kind == "ambiguous_isolation"]
        assert len(iso_needs) == 0

    def test_missing_field_has_question_message(self):
        intent = IntentModel(values={})
        candidates = [
            TopologyCandidate(topology="buck", score=5.0, missing_fields=["vin"]),
        ]
        needs = analyze_clarification_needs(intent, candidates)
        missing = [n for n in needs if n.kind == "missing_field"]
        assert len(missing) == 1
        assert missing[0].message is not None
        assert len(missing[0].message) > 0
