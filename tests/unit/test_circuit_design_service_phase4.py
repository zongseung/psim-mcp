"""Phase 4: Routing Engine integration tests.

Tests that the routing engine is connected to the circuit design service
pipeline and that routing results are stored in preview payloads while
maintaining full backward compatibility with the legacy path.
"""

from __future__ import annotations

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
# Helper: create a buck preview with specs that trigger the synthesis path
# ---------------------------------------------------------------------------

async def _create_buck_preview(service: CircuitDesignService) -> dict:
    return await service.preview_circuit(
        circuit_type="buck",
        specs={"vin": 48, "vout_target": 12, "iout": 5},
    )


def _get_stored_payload(service: CircuitDesignService, token: str) -> dict | None:
    return service._store.get(token)


# ---------------------------------------------------------------------------
# Test: Preview payload structure
# ---------------------------------------------------------------------------

class TestPreviewPayloadStructure:
    """Verify that preview payload contains routing data."""

    async def test_payload_has_payload_kind(self, service):
        result = await _create_buck_preview(service)
        assert result["success"] is True
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        assert payload is not None
        assert payload["payload_kind"] == "preview_payload"

    async def test_payload_has_payload_version(self, service):
        result = await _create_buck_preview(service)
        assert result["success"] is True
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        assert payload["payload_version"] == "v1"

    async def test_payload_has_wire_segments(self, service):
        """wire_segments must be present in preview for SVG compatibility."""
        result = await _create_buck_preview(service)
        assert result["success"] is True
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        assert "wire_segments" in payload

    async def test_payload_has_components_and_nets(self, service):
        result = await _create_buck_preview(service)
        assert result["success"] is True
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        assert isinstance(payload["components"], list)
        assert len(payload["components"]) > 0
        assert isinstance(payload["nets"], list)


# ---------------------------------------------------------------------------
# Test: Routing engine integration (if synthesis path is available)
# ---------------------------------------------------------------------------

class TestRoutingEngineIntegration:
    """Tests for routing engine integration in the synthesis path.

    These tests check routing data when the layout engine is available.
    If _LAYOUT_ENGINE_AVAILABLE is False, routing won't be attempted
    and these tests verify graceful fallback.
    """

    async def test_routing_stored_when_synthesis_available(self, service):
        """If synthesis path works, routing key should be in payload."""
        from psim_mcp.services.circuit_design_service import _LAYOUT_ENGINE_AVAILABLE

        result = await _create_buck_preview(service)
        assert result["success"] is True
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)

        if _LAYOUT_ENGINE_AVAILABLE:
            # Routing should be attempted
            # It may or may not succeed depending on engine availability
            # but if layout is available, routing engine should also be available
            from psim_mcp.services.circuit_design_service import _ROUTING_ENGINE_AVAILABLE
            if _ROUTING_ENGINE_AVAILABLE:
                assert "routing" in payload
                routing = payload["routing"]
                assert routing["topology"] == "buck"
                assert isinstance(routing["segments"], list)
        else:
            # Legacy path: routing key may not be present
            pass

    async def test_routing_has_segments_list(self, service):
        """If routing is present, it must have a segments list."""
        from psim_mcp.services.circuit_design_service import (
            _LAYOUT_ENGINE_AVAILABLE,
            _ROUTING_ENGINE_AVAILABLE,
        )
        if not (_LAYOUT_ENGINE_AVAILABLE and _ROUTING_ENGINE_AVAILABLE):
            pytest.skip("Requires layout+routing engines")

        result = await _create_buck_preview(service)
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        routing = payload.get("routing")
        assert routing is not None
        assert isinstance(routing["segments"], list)
        assert len(routing["segments"]) > 0

    async def test_routing_segments_have_required_fields(self, service):
        """Each routing segment must have id, net_id, x1, y1, x2, y2."""
        from psim_mcp.services.circuit_design_service import (
            _LAYOUT_ENGINE_AVAILABLE,
            _ROUTING_ENGINE_AVAILABLE,
        )
        if not (_LAYOUT_ENGINE_AVAILABLE and _ROUTING_ENGINE_AVAILABLE):
            pytest.skip("Requires layout+routing engines")

        result = await _create_buck_preview(service)
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        routing = payload["routing"]
        for seg in routing["segments"]:
            assert "id" in seg
            assert "net_id" in seg
            assert "x1" in seg
            assert "y1" in seg
            assert "x2" in seg
            assert "y2" in seg

    async def test_routing_metadata_stored(self, service):
        """Routing metadata should be stored."""
        from psim_mcp.services.circuit_design_service import (
            _LAYOUT_ENGINE_AVAILABLE,
            _ROUTING_ENGINE_AVAILABLE,
        )
        if not (_LAYOUT_ENGINE_AVAILABLE and _ROUTING_ENGINE_AVAILABLE):
            pytest.skip("Requires layout+routing engines")

        result = await _create_buck_preview(service)
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        routing = payload["routing"]
        assert "metadata" in routing

    async def test_graph_stored_in_payload(self, service):
        """If synthesis succeeded, graph should be in payload."""
        from psim_mcp.services.circuit_design_service import _LAYOUT_ENGINE_AVAILABLE
        if not _LAYOUT_ENGINE_AVAILABLE:
            pytest.skip("Requires layout engine")

        result = await _create_buck_preview(service)
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        assert "graph" in payload
        assert payload["graph"]["topology"] == "buck"

    async def test_layout_stored_in_payload(self, service):
        """If synthesis succeeded, layout should be in payload."""
        from psim_mcp.services.circuit_design_service import _LAYOUT_ENGINE_AVAILABLE
        if not _LAYOUT_ENGINE_AVAILABLE:
            pytest.skip("Requires layout engine")

        result = await _create_buck_preview(service)
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        assert "layout" in payload


# ---------------------------------------------------------------------------
# Test: Legacy compatibility
# ---------------------------------------------------------------------------

class TestLegacyCompatibility:
    """Verify that SVG preview and confirm_circuit still work."""

    async def test_svg_preview_still_works(self, service):
        """SVG preview generation must not break."""
        result = await _create_buck_preview(service)
        assert result["success"] is True
        assert "svg_path" in result["data"]
        assert result["data"]["svg_path"].endswith(".svg")

    async def test_ascii_diagram_still_present(self, service):
        """ASCII diagram must still be returned."""
        result = await _create_buck_preview(service)
        assert result["success"] is True
        assert "ascii_diagram" in result["data"]
        assert len(result["data"]["ascii_diagram"]) > 0

    async def test_confirm_circuit_works_with_routing_payload(self, service):
        """confirm_circuit must work with routing-enriched payload."""
        result = await _create_buck_preview(service)
        assert result["success"] is True
        token = result["data"]["preview_token"]

        confirm = await service.confirm_circuit(
            save_path="/test/output.psimsch",
            preview_token=token,
        )
        assert confirm["success"] is True

    async def test_non_synthesis_topology_uses_legacy(self, service):
        """A topology without synthesis (e.g. boost) should still work via legacy."""
        result = await service.preview_circuit(
            circuit_type="boost",
            specs={"vin": 12, "vout_target": 48, "iout": 2},
        )
        assert result["success"] is True
        assert "preview_token" in result["data"]

    async def test_template_path_unaffected(self, service):
        """Template-based preview must work without routing engine."""
        result = await service.preview_circuit(circuit_type="buck")
        assert result["success"] is True

    async def test_custom_components_path_unaffected(self, service):
        """Custom components path must remain unaffected."""
        result = await service.preview_circuit(
            circuit_type="custom",
            components=[
                {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 0, "y": 0}},
                {"id": "R1", "type": "Resistor", "parameters": {"resistance": 10.0}, "position": {"x": 120, "y": 0}},
            ],
            connections=[
                {"from": "V1.positive", "to": "R1.pin1"},
                {"from": "V1.negative", "to": "R1.pin2"},
            ],
        )
        assert result["success"] is True
        token = result["data"]["preview_token"]
        payload = _get_stored_payload(service, token)
        # Custom path should not have routing key
        assert "routing" not in payload


# ---------------------------------------------------------------------------
# Test: Response shape unchanged
# ---------------------------------------------------------------------------

class TestResponseShapeUnchanged:
    """Verify that public API response shapes are not modified."""

    async def test_preview_response_has_expected_keys(self, service):
        result = await _create_buck_preview(service)
        assert result["success"] is True
        data = result["data"]
        assert "ascii_diagram" in data
        assert "svg_path" in data
        assert "circuit_type" in data
        assert "preview_token" in data
        assert "component_count" in data
        assert "generation_mode" in data

    async def test_preview_response_message_present(self, service):
        result = await _create_buck_preview(service)
        assert "message" in result
        assert isinstance(result["message"], str)
