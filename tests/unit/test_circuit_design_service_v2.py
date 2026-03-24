"""Phase 1-5 service integration tests: synthesis pipeline, V2 intent, fallback."""

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.services.circuit_design_service import (
    CircuitDesignService,
    _SYNTHESIS_PIPELINE_AVAILABLE,
    _INTENT_V2_AVAILABLE,
)
from psim_mcp.shared.state_store import StateStore


@pytest.fixture
def config():
    return AppConfig(psim_mode="mock")


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def state_store():
    return StateStore(default_ttl=3600)


@pytest.fixture
def service(mock_adapter, config, state_store):
    return CircuitDesignService(
        adapter=mock_adapter, config=config, state_store=state_store,
    )


# ---------------------------------------------------------------------------
# Payload version / graph / layout / routing in preview
# ---------------------------------------------------------------------------


class TestPayloadVersionInPreview:

    async def test_payload_version_v1_for_synthesis(self, service, state_store):
        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            pytest.skip("Synthesis pipeline not available")
        result = await service.preview_circuit(
            circuit_type="buck", specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"] is True
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert stored["payload_version"] == "v1"

    async def test_graph_stored_in_buck_preview(self, service, state_store):
        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            pytest.skip("Synthesis pipeline not available")
        result = await service.preview_circuit(
            circuit_type="buck", specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert "graph" in stored
        assert stored["graph"]["topology"] == "buck"

    async def test_layout_stored_in_buck_preview(self, service, state_store):
        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            pytest.skip("Synthesis pipeline not available")
        result = await service.preview_circuit(
            circuit_type="buck", specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert "layout" in stored
        assert stored["layout"]["topology"] == "buck"

    async def test_routing_stored_in_buck_preview(self, service, state_store):
        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            pytest.skip("Synthesis pipeline not available")
        result = await service.preview_circuit(
            circuit_type="buck", specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert "routing" in stored
        assert stored["routing"]["topology"] == "buck"
        assert isinstance(stored["routing"]["segments"], list)

    async def test_wire_segments_in_buck_preview(self, service, state_store):
        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            pytest.skip("Synthesis pipeline not available")
        result = await service.preview_circuit(
            circuit_type="buck", specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert "wire_segments" in stored
        assert isinstance(stored["wire_segments"], list)


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------


class TestFallbackToLegacy:

    async def test_template_fallback_no_graph(self, service, state_store):
        """Topologies without synthesis should not store graph."""
        result = await service.preview_circuit(circuit_type="buck")
        assert result["success"] is True
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        # Without specs, synthesis is not attempted
        assert "graph" not in stored or stored.get("graph") is None

    async def test_non_synthesis_topology(self, service):
        """Topology without synthesize() should still preview via generator/template."""
        result = await service.preview_circuit(
            circuit_type="boost", specs={"vin": 12, "vout_target": 48, "iout": 2},
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Confirm works with synthesis payload
# ---------------------------------------------------------------------------


class TestConfirmWithSynthesis:

    async def test_confirm_after_synthesis_preview(self, service):
        if not _SYNTHESIS_PIPELINE_AVAILABLE:
            pytest.skip("Synthesis pipeline not available")
        preview = await service.preview_circuit(
            circuit_type="buck", specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert preview["success"] is True
        token = preview["data"]["preview_token"]
        result = await service.confirm_circuit(
            save_path="/test/output.psimsch", preview_token=token,
        )
        assert result["success"] is True


# ---------------------------------------------------------------------------
# V2 Intent integration
# ---------------------------------------------------------------------------


class TestV2IntentIntegration:

    async def test_design_circuit_uses_v2(self, service):
        if not _INTENT_V2_AVAILABLE:
            pytest.skip("Intent V2 not available")
        result = await service.design_circuit("buck converter 48V 입력 12V 출력 5A")
        assert result["success"] is True

    async def test_v2_candidate_scores_in_confirm_intent(self, service):
        if not _INTENT_V2_AVAILABLE:
            pytest.skip("Intent V2 not available")
        result = await service.design_circuit("flyback 310V 입력")
        if result["success"] and result["data"].get("action") in ("confirm_intent", "need_specs"):
            assert "candidate_scores" in result["data"]

    async def test_v2_decision_trace_in_confirm_intent(self, service):
        if not _INTENT_V2_AVAILABLE:
            pytest.skip("Intent V2 not available")
        result = await service.design_circuit("flyback 310V 입력")
        if result["success"] and result["data"].get("action") in ("confirm_intent", "need_specs"):
            assert "decision_trace" in result["data"]

    async def test_design_session_token_still_works(self, service):
        """V2 integration must preserve design_session_token contract."""
        result = await service.design_circuit("boost 12V 입력")
        if result["success"] and "design_session_token" in result["data"]:
            token = result["data"]["design_session_token"]
            session = service._store.get(token)
            assert session is not None
            assert session.get("type") == "design_session"

    async def test_v2_fallback_preserves_response_shape(self, service, monkeypatch):
        """If V2 raises, legacy path still produces valid response."""
        if not _INTENT_V2_AVAILABLE:
            pytest.skip("Intent V2 not available")

        def bad_resolve(self, desc):
            raise RuntimeError("boom")

        monkeypatch.setattr(CircuitDesignService, "_resolve_intent_v2", bad_resolve)
        result = await service.design_circuit("buck 48V 12V")
        assert "success" in result
