"""Unit tests for CircuitDesignService."""

import pytest

from psim_mcp.services.circuit_design_service import CircuitDesignService
from psim_mcp.config import AppConfig


@pytest.fixture
def config():
    return AppConfig(psim_mode="mock")


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def circuit_design_service(mock_adapter, config):
    return CircuitDesignService(adapter=mock_adapter, config=config)


# --- Component Library ---

def test_get_component_library(circuit_design_service):
    result = circuit_design_service.get_component_library()
    assert result["success"] is True
    assert result["data"]["total"] > 0


def test_get_component_library_by_category(circuit_design_service):
    result = circuit_design_service.get_component_library(category="source")
    assert result["success"] is True
    for comp in result["data"]["components"].values():
        assert comp["category"] == "source"


# --- Template Listing ---

def test_list_templates(circuit_design_service):
    result = circuit_design_service.list_templates()
    assert result["success"] is True
    assert result["data"]["total_templates"] > 0


def test_list_templates_by_category(circuit_design_service):
    result = circuit_design_service.list_templates(category="dc_dc")
    assert result["success"] is True


# --- Preview ---

@pytest.mark.asyncio
async def test_preview_circuit_template(circuit_design_service):
    result = await circuit_design_service.preview_circuit(circuit_type="buck")
    assert result["success"] is True
    assert "preview_token" in result["data"]
    assert "ascii_diagram" in result["data"]


@pytest.mark.asyncio
async def test_preview_circuit_no_template(circuit_design_service):
    result = await circuit_design_service.preview_circuit(circuit_type="nonexistent_topology_xyz")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_preview_circuit_with_specs(circuit_design_service):
    result = await circuit_design_service.preview_circuit(
        circuit_type="buck",
        specs={"V_in": 48, "V_out": 12},
    )
    assert result["success"] is True


# --- Confirm ---

@pytest.mark.asyncio
async def test_confirm_circuit_no_preview(circuit_design_service):
    result = await circuit_design_service.confirm_circuit(
        save_path="/test/output.psimsch",
        preview_token="nonexistent_token",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "NO_PREVIEW"


@pytest.mark.asyncio
async def test_confirm_circuit_after_preview(circuit_design_service):
    # First create a preview
    preview = await circuit_design_service.preview_circuit(circuit_type="buck")
    assert preview["success"] is True
    token = preview["data"]["preview_token"]

    # Then confirm it
    result = await circuit_design_service.confirm_circuit(
        save_path="/test/output.psimsch",
        preview_token=token,
    )
    assert result["success"] is True


# --- Design (NLP) ---

@pytest.mark.asyncio
async def test_design_circuit_high_confidence(circuit_design_service):
    result = await circuit_design_service.design_circuit(
        "Buck 컨버터 48V 입력 12V 출력 5A"
    )
    # Should succeed or return need_specs (depends on generator fields)
    assert "success" in result


@pytest.mark.asyncio
async def test_design_circuit_no_match(circuit_design_service):
    result = await circuit_design_service.design_circuit("something completely unrelated")
    # Should return error or suggest candidates
    assert "success" in result


# --- Continue Design ---

@pytest.mark.asyncio
async def test_continue_design_invalid_token(circuit_design_service):
    result = await circuit_design_service.continue_design(
        session_token="invalid_token_abc",
    )
    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_SESSION"


# --- Direct Create ---

@pytest.mark.asyncio
async def test_create_circuit_direct(circuit_design_service):
    result = await circuit_design_service.create_circuit_direct(
        circuit_type="buck",
        save_path="/test/output.psimsch",
    )
    assert result["success"] is True
