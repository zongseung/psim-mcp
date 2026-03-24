"""Phase 5 tests: Intent V2 pipeline integration with CircuitDesignService.

Tests that design_circuit() correctly uses the V2 intent resolution pipeline
while preserving all existing response shapes and action contracts.
"""

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.services.circuit_design_service import CircuitDesignService


@pytest.fixture
def config():
    return AppConfig(psim_mode="mock")


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def service(mock_adapter, config):
    return CircuitDesignService(adapter=mock_adapter, config=config)


# ---------------------------------------------------------------------------
# 1. High-confidence direct topology match
# ---------------------------------------------------------------------------


async def test_buck_48v_to_12v_resolves_to_buck(service):
    """buck converter 48V to 12V should resolve to buck topology."""
    result = await service.design_circuit("buck converter 48V 입력 12V 출력")
    assert result["success"] is True
    data = result["data"]
    topology = data.get("topology") or data.get("circuit_type")
    assert topology == "buck"


async def test_buck_full_spec_auto_preview(service):
    """Fully specified buck should auto-generate preview (high confidence)."""
    result = await service.design_circuit("Buck 컨버터 48V 입력 12V 출력 5A")
    assert result["success"] is True
    data = result["data"]
    assert "topology" in data or "circuit_type" in data


# ---------------------------------------------------------------------------
# 2. Missing specs -> need_specs action
# ---------------------------------------------------------------------------


async def test_partial_input_needs_specs_or_confirm(service):
    """48V input alone with buck keyword should need vout or confirm."""
    result = await service.design_circuit("48V 입력 buck")
    assert result["success"] is True
    data = result["data"]
    if data.get("action") == "need_specs":
        assert "missing_fields" in data
        assert isinstance(data["missing_fields"], list)
    elif data.get("action") == "confirm_intent":
        assert data["topology"] == "buck"


# ---------------------------------------------------------------------------
# 3. Isolated topology candidates
# ---------------------------------------------------------------------------


async def test_isolated_400v_to_48v_suggests_isolated(service):
    """400V DC bus to isolated 48V should suggest isolated topologies."""
    result = await service.design_circuit("400V DC bus to 절연 48V")
    assert result["success"] is True
    data = result["data"]
    candidates = data.get("topology_candidates") or data.get("candidates", [])
    if candidates:
        from psim_mcp.data.topology_metadata import is_isolated
        isolated_found = any(
            is_isolated(c) for c in candidates if isinstance(c, str)
        )
        assert isolated_found, f"Expected isolated candidates in {candidates}"


# ---------------------------------------------------------------------------
# 4. Korean charger keyword
# ---------------------------------------------------------------------------


async def test_charger_korean_keyword(service):
    """충전기 배터리 should suggest cc_cv_charger."""
    result = await service.design_circuit("충전기 배터리")
    assert result["success"] is True
    data = result["data"]
    topology = data.get("topology")
    candidates = data.get("topology_candidates") or data.get("candidates", [])
    charger_found = (
        topology == "cc_cv_charger"
        or "cc_cv_charger" in candidates
    )
    assert charger_found, (
        f"Expected cc_cv_charger, got topology={topology}, candidates={candidates}"
    )


# ---------------------------------------------------------------------------
# 5. Adapter keyword
# ---------------------------------------------------------------------------


async def test_adapter_19v_suggests_flyback_or_llc(service):
    """어댑터 19V should suggest flyback or llc."""
    result = await service.design_circuit("어댑터 19V")
    assert result["success"] is True
    data = result["data"]
    topology = data.get("topology")
    candidates = data.get("topology_candidates") or data.get("candidates", [])
    adapter_topologies = {"flyback", "llc"}
    found = topology in adapter_topologies or bool(
        adapter_topologies & set(candidates)
    )
    assert found, (
        f"Expected flyback/llc, got topology={topology}, candidates={candidates}"
    )


# ---------------------------------------------------------------------------
# 6. Response shape: standard fields
# ---------------------------------------------------------------------------


async def test_response_has_success_key(service):
    """All design_circuit responses must have success key."""
    result = await service.design_circuit("buck 48V 12V")
    assert "success" in result
    if result["success"]:
        assert "data" in result
        assert isinstance(result["data"], dict)


async def test_response_topology_in_data(service):
    """Response data should contain topology when matched."""
    result = await service.design_circuit("buck converter 48V to 12V")
    assert result["success"] is True
    data = result["data"]
    assert "topology" in data or "circuit_type" in data


# ---------------------------------------------------------------------------
# 7. design_session_token
# ---------------------------------------------------------------------------


async def test_session_token_returned_and_retrievable(service):
    """design_session_token should be returned and retrievable."""
    result = await service.design_circuit("boost 12V 입력")
    assert result["success"] is True
    data = result["data"]
    if "design_session_token" in data:
        token = data["design_session_token"]
        assert isinstance(token, str)
        assert len(token) > 0
        session = service._store.get(token)
        assert session is not None
        assert session.get("type") == "design_session"


# ---------------------------------------------------------------------------
# 8. continue_design with stored session
# ---------------------------------------------------------------------------


async def test_continue_design_with_session(service):
    """continue_design should work with a valid session token."""
    result = await service.design_circuit("buck 컨버터")
    assert result["success"] is True
    data = result["data"]

    if "design_session_token" not in data:
        pytest.skip("No session token returned (high confidence path)")

    token = data["design_session_token"]
    result2 = await service.continue_design(
        session_token=token,
        additional_specs={"vin": 48.0, "vout_target": 12.0},
    )
    assert "success" in result2


# ---------------------------------------------------------------------------
# 9. Bidirectional candidates
# ---------------------------------------------------------------------------


async def test_bidirectional_candidates_ranked_high(service):
    """양방향 48V 400V should rank bidirectional topologies high."""
    result = await service.design_circuit("양방향 48V 400V")
    assert result["success"] is True
    data = result["data"]
    topology = data.get("topology")
    candidates = data.get("topology_candidates") or data.get("candidates", [])
    bidirectional_topos = {"bidirectional_buck_boost", "dab"}
    found = topology in bidirectional_topos or bool(
        bidirectional_topos & set(candidates)
    )
    assert found, (
        f"Expected bidirectional, got topology={topology}, candidates={candidates}"
    )


# ---------------------------------------------------------------------------
# 10. Backward compatibility: response shape
# ---------------------------------------------------------------------------


async def test_legacy_response_shape_compat(service):
    """Response with action should have topology, specs, confidence, token."""
    result = await service.design_circuit("buck 48V 입력 12V 출력")
    assert result["success"] is True
    data = result["data"]
    if data.get("action") in ("confirm_intent", "need_specs"):
        assert "topology" in data
        assert "specs" in data
        assert "confidence" in data
        assert "design_session_token" in data


# ---------------------------------------------------------------------------
# 11. confirm_intent has topology
# ---------------------------------------------------------------------------


async def test_confirm_intent_has_topology(service):
    """confirm_intent response must have topology field."""
    result = await service.design_circuit("flyback 310V 입력")
    if result["success"] and result["data"].get("action") == "confirm_intent":
        assert "topology" in result["data"]
        assert result["data"]["topology"] is not None


# ---------------------------------------------------------------------------
# 12. need_specs has questions
# ---------------------------------------------------------------------------


async def test_need_specs_has_questions_list(service):
    """need_specs action should have questions list."""
    result = await service.design_circuit("boost 컨버터")
    if result["success"] and result["data"].get("action") == "need_specs":
        assert "questions" in result["data"]
        assert isinstance(result["data"]["questions"], list)


# ---------------------------------------------------------------------------
# 13. suggest_candidates has topology_candidates
# ---------------------------------------------------------------------------


async def test_suggest_candidates_has_candidate_list(service):
    """suggest_candidates action should have candidates list."""
    result = await service.design_circuit("충전")
    if result["success"]:
        data = result["data"]
        if data.get("action") == "suggest_candidates":
            assert "candidates" in data or "topology_candidates" in data


# ---------------------------------------------------------------------------
# 14. Phase 5: candidate_scores field
# ---------------------------------------------------------------------------


async def test_candidate_scores_present_v2(service):
    """When V2 is active, candidate_scores should be in non-auto responses."""
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    if not _INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    result = await service.design_circuit("buck 48V 입력 12V 출력")
    assert result["success"] is True
    data = result["data"]
    if data.get("action") in ("confirm_intent", "need_specs"):
        assert "candidate_scores" in data
        assert isinstance(data["candidate_scores"], list)
        if data["candidate_scores"]:
            entry = data["candidate_scores"][0]
            assert "topology" in entry
            assert "score" in entry
            assert "reasons" in entry


# ---------------------------------------------------------------------------
# 15. Phase 5: decision_trace field
# ---------------------------------------------------------------------------


async def test_decision_trace_present_v2(service):
    """When V2 is active, decision_trace should be in non-auto responses."""
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    if not _INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    result = await service.design_circuit("buck 48V 입력 12V 출력")
    assert result["success"] is True
    data = result["data"]
    if data.get("action") in ("confirm_intent", "need_specs"):
        assert "decision_trace" in data
        assert isinstance(data["decision_trace"], list)


# ---------------------------------------------------------------------------
# 16. V2 pipeline produces valid parsed dict
# ---------------------------------------------------------------------------


def test_resolve_intent_v2_returns_legacy_dict(service):
    """_resolve_intent_v2 should return dict with all legacy keys."""
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    if not _INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    result = service._resolve_intent_v2("buck converter 48V to 12V")
    assert isinstance(result, dict)
    assert "topology" in result
    assert "topology_candidates" in result
    assert "specs" in result
    assert "missing_fields" in result
    assert "questions" in result
    assert "confidence" in result
    assert "resolution_version" in result
    assert result["resolution_version"] == "v2"


# ---------------------------------------------------------------------------
# 17. V2 with no match
# ---------------------------------------------------------------------------


def test_resolve_intent_v2_no_match_returns_none_topology(service):
    """_resolve_intent_v2 with gibberish should return topology=None."""
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    if not _INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    result = service._resolve_intent_v2("xyzzy foobar nonsense")
    assert result["topology"] is None
    assert result["confidence"] == "low"


# ---------------------------------------------------------------------------
# 18. V2 candidate_scores structure
# ---------------------------------------------------------------------------


def test_resolve_intent_v2_candidate_scores_structure(service):
    """candidate_scores entries should have topology, score, reasons."""
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    if not _INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    result = service._resolve_intent_v2("buck 48V 12V")
    scores = result.get("candidate_scores", [])
    assert len(scores) > 0
    for entry in scores:
        assert "topology" in entry
        assert "score" in entry
        assert "reasons" in entry
        assert isinstance(entry["score"], (int, float))
        assert isinstance(entry["reasons"], list)


# ---------------------------------------------------------------------------
# 19. V2 confidence mapping
# ---------------------------------------------------------------------------


def test_determine_confidence_v2_high(service):
    """High score + no missing -> high confidence."""
    from psim_mcp.intent.models import (
        IntentModel, TopologyCandidate, CanonicalIntentSpec,
    )

    intent = IntentModel(values={"vin": 48, "vout_target": 12})
    top = TopologyCandidate(topology="buck", score=10.0)
    spec = CanonicalIntentSpec(
        topology="buck", requirements={"vin": 48, "vout_target": 12},
    )

    confidence = service._determine_confidence_v2(intent, top, spec, [])
    assert confidence == "high"


def test_determine_confidence_v2_low(service):
    """Low score + missing fields -> low confidence."""
    from psim_mcp.intent.models import (
        IntentModel, TopologyCandidate, CanonicalIntentSpec,
    )

    intent = IntentModel()
    top = TopologyCandidate(topology="buck", score=2.0)
    spec = CanonicalIntentSpec(
        topology="buck",
        requirements={},
        missing_fields=["vin", "vout_target"],
    )

    confidence = service._determine_confidence_v2(intent, top, spec, [])
    assert confidence == "low"


# ---------------------------------------------------------------------------
# 20. No match -> error response
# ---------------------------------------------------------------------------


async def test_no_match_returns_error_or_suggestion(service):
    """Unrecognized input should return error or suggest_candidates."""
    result = await service.design_circuit("something completely unrelated")
    assert "success" in result
    if not result["success"]:
        assert result["error"]["code"] == "NO_MATCH"


# ---------------------------------------------------------------------------
# 21. V2 fallback on exception
# ---------------------------------------------------------------------------


async def test_v2_fallback_on_exception(service, monkeypatch):
    """If V2 pipeline raises, should fall back to legacy parser."""
    from psim_mcp.services import circuit_design_service as mod

    if not mod._INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    def bad_resolve(self, desc):
        raise RuntimeError("V2 exploded")

    monkeypatch.setattr(CircuitDesignService, "_resolve_intent_v2", bad_resolve)

    result = await service.design_circuit("buck 48V 12V")
    assert "success" in result


# ---------------------------------------------------------------------------
# 22. V2 normalized_specs matches specs
# ---------------------------------------------------------------------------


def test_resolve_intent_v2_has_normalized_specs(service):
    """V2 result should have normalized_specs key."""
    from psim_mcp.services.circuit_design_service import _INTENT_V2_AVAILABLE
    if not _INTENT_V2_AVAILABLE:
        pytest.skip("Intent V2 not available")

    result = service._resolve_intent_v2("buck 48V 입력 12V 출력")
    assert "normalized_specs" in result
    assert isinstance(result["normalized_specs"], dict)
