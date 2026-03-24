"""Tests for intent resolution data models."""

from psim_mcp.intent.models import (
    CanonicalIntentSpec,
    ClarificationNeed,
    DesignResolutionResult,
    IntentModel,
    TopologyCandidate,
)


class TestIntentModel:
    def test_default_creation(self):
        model = IntentModel()
        assert model.input_domain is None
        assert model.output_domain is None
        assert model.conversion_goal is None
        assert model.use_case is None
        assert model.isolation is None
        assert model.bidirectional is None
        assert model.values == {}
        assert model.voltage_candidates == []
        assert model.constraints == {}
        assert model.raw_text == ""
        assert model.mapping_confidence == "high"

    def test_creation_with_values(self):
        model = IntentModel(
            input_domain="dc",
            output_domain="dc",
            conversion_goal="step_down",
            values={"vin": 48.0, "vout_target": 12.0},
            raw_text="buck 48V to 12V",
        )
        assert model.input_domain == "dc"
        assert model.output_domain == "dc"
        assert model.conversion_goal == "step_down"
        assert model.values["vin"] == 48.0
        assert model.values["vout_target"] == 12.0

    def test_isolation_explicit(self):
        model = IntentModel(isolation=True)
        assert model.isolation is True

        model2 = IntentModel(isolation=False)
        assert model2.isolation is False

    def test_bidirectional(self):
        model = IntentModel(bidirectional=True)
        assert model.bidirectional is True

    def test_voltage_candidates(self):
        candidates = [
            {"value": 400, "role_hint": "vin"},
            {"value": 48, "role_hint": "vout_target"},
        ]
        model = IntentModel(voltage_candidates=candidates)
        assert len(model.voltage_candidates) == 2
        assert model.voltage_candidates[0]["value"] == 400


class TestTopologyCandidate:
    def test_default_creation(self):
        tc = TopologyCandidate(topology="buck", score=8.0)
        assert tc.topology == "buck"
        assert tc.score == 8.0
        assert tc.reasons == []
        assert tc.missing_fields == []
        assert tc.conflicts == []

    def test_with_reasons_and_conflicts(self):
        tc = TopologyCandidate(
            topology="flyback",
            score=6.0,
            reasons=["keyword_match: flyback", "isolation=isolated"],
            missing_fields=["vout_target"],
            conflicts=["output_domain mismatch"],
        )
        assert len(tc.reasons) == 2
        assert "vout_target" in tc.missing_fields
        assert len(tc.conflicts) == 1

    def test_score_comparison(self):
        c1 = TopologyCandidate(topology="buck", score=8.0)
        c2 = TopologyCandidate(topology="boost", score=6.0)
        assert c1.score > c2.score


class TestClarificationNeed:
    def test_missing_field(self):
        cn = ClarificationNeed(
            kind="missing_field",
            field="vin",
            message="입력 전압은 몇 V인가요?",
        )
        assert cn.kind == "missing_field"
        assert cn.field == "vin"
        assert cn.priority == "normal"

    def test_ambiguous_topology(self):
        cn = ClarificationNeed(
            kind="ambiguous_topology",
            message="Which topology?",
            options=["buck", "boost", "buck_boost"],
            priority="high",
        )
        assert len(cn.options) == 3
        assert cn.priority == "high"

    def test_default_priority(self):
        cn = ClarificationNeed(kind="no_match")
        assert cn.priority == "normal"
        assert cn.field is None
        assert cn.message is None
        assert cn.options == []


class TestCanonicalIntentSpec:
    def test_creation(self):
        spec = CanonicalIntentSpec(
            topology="buck",
            requirements={"vin": 48.0, "vout_target": 12.0},
        )
        assert spec.topology == "buck"
        assert spec.requirements["vin"] == 48.0
        assert spec.inferred_values == {}
        assert spec.missing_fields == []
        assert spec.decision_trace == []

    def test_with_trace(self):
        trace = [
            {"source": "user", "field": "vin", "value": 48.0},
            {"source": "ranker", "field": "topology", "value": "buck"},
        ]
        spec = CanonicalIntentSpec(
            topology="buck",
            requirements={"vin": 48.0},
            decision_trace=trace,
        )
        assert len(spec.decision_trace) == 2
        assert spec.decision_trace[0]["source"] == "user"

    def test_with_missing_fields(self):
        spec = CanonicalIntentSpec(
            topology="buck",
            requirements={"vin": 48.0},
            missing_fields=["vout_target"],
        )
        assert "vout_target" in spec.missing_fields


class TestDesignResolutionResult:
    def test_confirm_intent(self):
        result = DesignResolutionResult(
            action="confirm_intent",
            selected_topology="buck",
            confidence="high",
        )
        assert result.action == "confirm_intent"
        assert result.selected_topology == "buck"
        assert result.confidence == "high"

    def test_need_specs(self):
        result = DesignResolutionResult(
            action="need_specs",
            selected_topology="buck",
            missing_fields=["vin", "vout_target"],
            questions=["입력 전압은 몇 V인가요?", "출력 전압은 몇 V인가요?"],
            confidence="low",
        )
        assert result.action == "need_specs"
        assert len(result.missing_fields) == 2
        assert len(result.questions) == 2

    def test_suggest_candidates(self):
        candidates = [
            TopologyCandidate(topology="buck", score=8.0),
            TopologyCandidate(topology="boost", score=6.0),
        ]
        result = DesignResolutionResult(
            action="suggest_candidates",
            candidates=candidates,
        )
        assert result.action == "suggest_candidates"
        assert len(result.candidates) == 2
        assert result.selected_topology is None

    def test_defaults(self):
        result = DesignResolutionResult(action="confirm_intent")
        assert result.candidates == []
        assert result.canonical_spec is None
        assert result.missing_fields == []
        assert result.questions == []
        assert result.confidence == "low"
        assert result.design_session_payload is None
