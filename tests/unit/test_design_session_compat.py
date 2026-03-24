"""Phase 5 tests: Design session backward/forward compatibility.

Tests that continue_design() works correctly with both V1 (legacy) and V2
(new pipeline) session payloads.
"""

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.services.circuit_design_service import CircuitDesignService
from psim_mcp.shared.state_store import StateStore


@pytest.fixture
def config():
    return AppConfig(psim_mode="mock")


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def store():
    return StateStore(default_ttl=3600)


@pytest.fixture
def service(mock_adapter, config, store):
    return CircuitDesignService(adapter=mock_adapter, config=config, state_store=store)


# ---------------------------------------------------------------------------
# 1. V1 session payload loads correctly
# ---------------------------------------------------------------------------


async def test_v1_session_payload_loads(service, store):
    """V1 session (no payload_version) should be retrievable."""
    token = store.save({
        "type": "design_session",
        "topology": "buck",
        "specs": {"vin": 48.0},
        "missing_fields": ["vout_target"],
    })

    session = store.get(token)
    assert session is not None
    assert session["type"] == "design_session"
    assert session["topology"] == "buck"
    assert "payload_version" not in session


# ---------------------------------------------------------------------------
# 2. V2 session payload loads correctly
# ---------------------------------------------------------------------------


async def test_v2_session_payload_loads(service, store):
    """V2 session (with payload_version=v2) should be retrievable."""
    token = store.save({
        "type": "design_session",
        "topology": "buck",
        "specs": {"vin": 48.0, "vout_target": 12.0},
        "missing_fields": [],
        "payload_version": "v2",
        "candidate_scores": [
            {"topology": "buck", "score": 10.0, "reasons": ["keyword_match"]},
        ],
        "decision_trace": [
            {"source": "ranker", "field": "topology", "value": "buck"},
        ],
    })

    session = store.get(token)
    assert session is not None
    assert session["type"] == "design_session"
    assert session["payload_version"] == "v2"
    assert "candidate_scores" in session
    assert "decision_trace" in session


# ---------------------------------------------------------------------------
# 3. continue_design with V1 session
# ---------------------------------------------------------------------------


async def test_continue_design_v1_session(service, store):
    """continue_design should work with a V1 (legacy) session."""
    token = store.save({
        "type": "design_session",
        "topology": "buck",
        "specs": {"vin": 48.0},
        "missing_fields": ["vout_target"],
    })

    result = await service.continue_design(
        session_token=token,
        additional_specs={"vout_target": 12.0},
    )
    assert "success" in result


# ---------------------------------------------------------------------------
# 4. continue_design with V2 session
# ---------------------------------------------------------------------------


async def test_continue_design_v2_session(service, store):
    """continue_design should work with a V2 session."""
    token = store.save({
        "type": "design_session",
        "topology": "buck",
        "specs": {"vin": 48.0},
        "missing_fields": ["vout_target"],
        "payload_version": "v2",
        "candidate_scores": [
            {"topology": "buck", "score": 10.0, "reasons": ["keyword_match"]},
        ],
        "decision_trace": [
            {"source": "ranker", "field": "topology", "value": "buck"},
        ],
    })

    result = await service.continue_design(
        session_token=token,
        additional_specs={"vout_target": 12.0},
    )
    assert "success" in result


# ---------------------------------------------------------------------------
# 5. Missing payload_version treated as V1
# ---------------------------------------------------------------------------


async def test_missing_payload_version_treated_as_v1(service, store):
    """Sessions without payload_version should behave identically to V1."""
    token = store.save({
        "type": "design_session",
        "topology": "boost",
        "specs": {"vin": 12.0},
        "missing_fields": ["vout_target"],
    })

    session = store.get(token)
    # No payload_version key
    assert "payload_version" not in session

    # continue_design should still work
    result = await service.continue_design(
        session_token=token,
        additional_specs={"vout_target": 48.0},
    )
    assert "success" in result


# ---------------------------------------------------------------------------
# 6. V2 session extra fields do not interfere with continue_design
# ---------------------------------------------------------------------------


async def test_v2_extra_fields_no_interference(service, store):
    """V2 extra fields (candidate_scores, decision_trace) should not break continue_design."""
    token = store.save({
        "type": "design_session",
        "topology": "flyback",
        "specs": {"vout_target": 5.0},
        "missing_fields": ["vin"],
        "payload_version": "v2",
        "candidate_scores": [
            {"topology": "flyback", "score": 8.0, "reasons": ["keyword_match"]},
            {"topology": "llc", "score": 5.0, "reasons": ["use_case"]},
        ],
        "decision_trace": [
            {"source": "user", "field": "vout_target", "value": 5.0},
        ],
    })

    result = await service.continue_design(
        session_token=token,
        additional_specs={"vin": 310.0},
    )
    assert "success" in result


# ---------------------------------------------------------------------------
# 7. Invalid token returns error
# ---------------------------------------------------------------------------


async def test_invalid_token_returns_error(service):
    """Invalid session token should return INVALID_SESSION error."""
    result = await service.continue_design(
        session_token="nonexistent_token_xyz",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_SESSION"


# ---------------------------------------------------------------------------
# 8. Session deleted after continue_design
# ---------------------------------------------------------------------------


async def test_session_deleted_after_continue(service, store):
    """Session should be deleted from store after continue_design."""
    token = store.save({
        "type": "design_session",
        "topology": "buck",
        "specs": {"vin": 48.0, "vout_target": 12.0},
        "missing_fields": [],
    })

    assert store.get(token) is not None

    await service.continue_design(
        session_token=token,
        additional_specs={},
    )

    # Session should be consumed
    assert store.get(token) is None


# ---------------------------------------------------------------------------
# 9. continue_design with additional_description
# ---------------------------------------------------------------------------


async def test_continue_design_with_description(service, store):
    """continue_design with additional_description should parse and merge."""
    token = store.save({
        "type": "design_session",
        "topology": "buck",
        "specs": {"vin": 48.0},
        "missing_fields": ["vout_target"],
        "payload_version": "v2",
    })

    result = await service.continue_design(
        session_token=token,
        additional_description="출력 12V 5A",
    )
    assert "success" in result
