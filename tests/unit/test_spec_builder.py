"""Tests for canonical spec builder (spec_builder.py)."""

from psim_mcp.intent.models import IntentModel, TopologyCandidate
from psim_mcp.intent.spec_builder import build_canonical_spec


class TestBuildCanonicalSpec:
    def test_basic_spec_from_intent(self):
        intent = IntentModel(
            values={"vin": 48.0, "vout_target": 12.0, "iout": 5.0},
        )
        selected = TopologyCandidate(
            topology="buck",
            score=10.0,
            reasons=["keyword_match: buck"],
        )
        spec = build_canonical_spec(intent, selected)

        assert spec.topology == "buck"
        assert spec.requirements["vin"] == 48.0
        assert spec.requirements["vout_target"] == 12.0
        assert spec.requirements["iout"] == 5.0

    def test_user_values_in_trace(self):
        intent = IntentModel(values={"vin": 48.0, "vout_target": 12.0})
        selected = TopologyCandidate(topology="buck", score=10.0)
        spec = build_canonical_spec(intent, selected)

        user_traces = [t for t in spec.decision_trace if t["source"] == "user"]
        assert len(user_traces) == 2
        fields = {t["field"] for t in user_traces}
        assert "vin" in fields
        assert "vout_target" in fields

    def test_ranker_in_trace(self):
        intent = IntentModel(values={"vin": 48.0})
        selected = TopologyCandidate(
            topology="buck",
            score=8.0,
            reasons=["keyword_match: buck", "input_domain=dc"],
        )
        spec = build_canonical_spec(intent, selected)

        ranker_traces = [t for t in spec.decision_trace if t["source"] == "ranker"]
        assert len(ranker_traces) == 1
        assert ranker_traces[0]["value"] == "buck"
        assert ranker_traces[0]["confidence"] == 8.0

    def test_isolation_inferred(self):
        intent = IntentModel(
            isolation=True,
            values={"vin": 400.0, "vout_target": 48.0},
        )
        selected = TopologyCandidate(topology="flyback", score=8.0)
        spec = build_canonical_spec(intent, selected)

        assert spec.inferred_values.get("isolation") is True
        extractor_traces = [t for t in spec.decision_trace if t["source"] == "extractor"]
        assert len(extractor_traces) == 1

    def test_missing_fields_detected(self):
        intent = IntentModel(values={"vin": 48.0})
        selected = TopologyCandidate(topology="buck", score=8.0)
        spec = build_canonical_spec(intent, selected)

        # Buck requires vin and vout_target; vout_target is missing
        assert "vout_target" in spec.missing_fields

    def test_no_missing_fields_when_complete(self):
        intent = IntentModel(values={"vin": 48.0, "vout_target": 12.0})
        selected = TopologyCandidate(topology="buck", score=10.0)
        spec = build_canonical_spec(intent, selected)

        assert spec.missing_fields == []

    def test_additional_specs_merge(self):
        intent = IntentModel(values={"vin": 48.0})
        selected = TopologyCandidate(topology="buck", score=8.0)

        spec = build_canonical_spec(
            intent,
            selected,
            additional_specs={"vout_target": 12.0, "iout": 5.0},
        )

        assert spec.requirements["vout_target"] == 12.0
        assert spec.requirements["iout"] == 5.0
        # Additional specs should appear in trace
        followup_traces = [t for t in spec.decision_trace if t["source"] == "user_followup"]
        assert len(followup_traces) == 2

    def test_additional_specs_override_user_values(self):
        intent = IntentModel(values={"vin": 48.0, "vout_target": 12.0})
        selected = TopologyCandidate(topology="buck", score=10.0)

        spec = build_canonical_spec(
            intent,
            selected,
            additional_specs={"vout_target": 5.0},  # override
        )

        assert spec.requirements["vout_target"] == 5.0

    def test_inferred_domains(self):
        intent = IntentModel(
            input_domain="dc",
            output_domain="dc",
            conversion_goal="step_down",
            values={"vin": 48.0, "vout_target": 12.0},
        )
        selected = TopologyCandidate(topology="buck", score=10.0)
        spec = build_canonical_spec(intent, selected)

        assert spec.inferred_values.get("input_domain") == "dc"
        assert spec.inferred_values.get("output_domain") == "dc"
        assert spec.inferred_values.get("conversion_goal") == "step_down"

    def test_topology_with_no_required_fields(self):
        """Topologies like pv_mppt_boost have empty required_fields."""
        intent = IntentModel(values={"voc": 40.0, "isc": 10.0})
        selected = TopologyCandidate(topology="pv_mppt_boost", score=8.0)
        spec = build_canonical_spec(intent, selected)

        assert spec.missing_fields == []
        assert spec.requirements["voc"] == 40.0
