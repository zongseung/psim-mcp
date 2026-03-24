"""Unit tests for _build_need_specs_response versioned session payloads."""

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.services.circuit_design_service import (
    CircuitDesignService,
    _DESIGN_SESSION_KIND,
    _DESIGN_SESSION_VERSION,
    _make_design_session_payload,
)


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def service(mock_adapter):
    config = AppConfig(psim_mode="mock")
    return CircuitDesignService(adapter=mock_adapter, config=config)


def test_build_need_specs_stores_versioned_session(service):
    """_build_need_specs_response should save a versioned design session."""
    result = service._build_need_specs_response(
        topology="buck",
        specs={"vin": 48},
        missing_fields=["vout_target", "iout"],
        generation_mode="generator",
    )
    assert result["success"] is True
    token = result["data"]["design_session_token"]

    # Load from store and verify payload
    session = service._store.get(token)
    assert session is not None
    assert session["payload_kind"] == _DESIGN_SESSION_KIND
    assert session["payload_version"] == _DESIGN_SESSION_VERSION


def test_session_has_payload_kind_and_version(service):
    """Stored session should have both payload_kind and payload_version keys."""
    result = service._build_need_specs_response(
        topology="boost",
        specs={"vin": 12, "vout_target": 48},
        missing_fields=["iout"],
        generation_mode="generator",
    )
    token = result["data"]["design_session_token"]
    session = service._store.get(token)
    assert "payload_kind" in session
    assert "payload_version" in session
    assert session["topology"] == "boost"
    assert session["specs"] == {"vin": 12, "vout_target": 48}
    assert session["missing_fields"] == ["iout"]


def test_make_design_session_payload_structure():
    """_make_design_session_payload produces correct structure."""
    payload = _make_design_session_payload("flyback", {"vin": 310}, ["vout_target"])
    assert payload["type"] == _DESIGN_SESSION_KIND
    assert payload["payload_kind"] == _DESIGN_SESSION_KIND
    assert payload["payload_version"] == _DESIGN_SESSION_VERSION
    assert payload["topology"] == "flyback"
    assert payload["specs"] == {"vin": 310}
    assert payload["missing_fields"] == ["vout_target"]


def test_session_loadable_by_continue_design(service):
    """Stored design session should be loadable and usable for continuation."""
    result = service._build_need_specs_response(
        topology="buck",
        specs={"vin": 48},
        missing_fields=["vout_target"],
        generation_mode="generator",
    )
    token = result["data"]["design_session_token"]

    # Verify the session can be loaded and has all required fields
    session = service._store.get(token)
    assert session is not None
    assert "topology" in session
    assert "specs" in session
    assert "missing_fields" in session
    # The session type should be identifiable
    assert session.get("type") == _DESIGN_SESSION_KIND
