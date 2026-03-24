"""Phase 3: Layout Engine integration tests for CircuitDesignService."""

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
def state_store():
    return StateStore(default_ttl=3600)


@pytest.fixture
def service(mock_adapter, config, state_store):
    return CircuitDesignService(
        adapter=mock_adapter, config=config, state_store=state_store,
    )


class TestPreviewPayloadGraphLayout:

    async def test_preview_buck_contains_layout_key(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"] is True
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert stored is not None
        assert "layout" in stored

    async def test_preview_buck_contains_graph_key(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"] is True
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert stored is not None
        assert "graph" in stored

    async def test_stored_layout_has_buck_topology(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert stored["layout"]["topology"] == "buck"

    async def test_layout_components_have_positions(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        for lc in stored["layout"]["components"]:
            assert "x" in lc
            assert "y" in lc
            assert isinstance(lc["x"], int)
            assert isinstance(lc["y"], int)


class TestLegacyComponentFormat:

    async def test_legacy_components_have_position_direction_ports(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        for comp in stored["components"]:
            cid = comp.get("id", "?")
            assert "position" in comp, f"Component {cid} missing position"
            assert "direction" in comp, f"Component {cid} missing direction"
            assert "ports" in comp, f"Component {cid} missing ports"
            assert isinstance(comp["position"], dict)
            assert "x" in comp["position"]

    async def test_legacy_components_have_expected_count(self, service):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"] is True
        assert result["data"]["component_count"] == 8


class TestPayloadVersioning:

    async def test_payload_version_present(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert stored["payload_version"] == "v1"
        assert stored["payload_kind"] == "preview_payload"


class TestNoRegression:

    async def test_preview_buck_without_specs_still_works(self, service):
        result = await service.preview_circuit(circuit_type="buck")
        assert result["success"] is True
        assert "preview_token" in result["data"]

    async def test_preview_custom_components_still_works(self, service):
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

    async def test_preview_nonexistent_topology_fails(self, service):
        result = await service.preview_circuit(circuit_type="nonexistent_xyz")
        assert result["success"] is False

    async def test_svg_generation_not_broken(self, service):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"] is True
        assert result["data"]["svg_path"].endswith(".svg")


class TestConfirmWithLayout:

    async def test_confirm_circuit_with_layout_enriched_payload(self, service):
        preview = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert preview["success"] is True
        token = preview["data"]["preview_token"]
        result = await service.confirm_circuit(
            save_path="/test/output.psimsch",
            preview_token=token,
        )
        assert result["success"] is True


class TestFallbackBehavior:

    async def test_boost_falls_back_to_legacy(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="boost",
            specs={"vin": 12, "vout_target": 48, "iout": 2},
        )
        assert result["success"] is True
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        assert stored is not None
        assert stored["circuit_type"] == "boost"

    async def test_flyback_falls_back_to_legacy(self, service):
        result = await service.preview_circuit(
            circuit_type="flyback",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        assert result["success"] is True


class TestGraphDataIntegrity:

    async def test_graph_has_components_and_nets(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        graph_data = stored["graph"]
        assert len(graph_data["components"]) == 8
        assert len(graph_data["nets"]) == 5
        assert graph_data["topology"] == "buck"

    async def test_graph_components_have_roles(self, service, state_store):
        result = await service.preview_circuit(
            circuit_type="buck",
            specs={"vin": 48, "vout_target": 12, "iout": 5},
        )
        token = result["data"]["preview_token"]
        stored = state_store.get(token)
        for comp in stored["graph"]["components"]:
            assert comp["role"] is not None
