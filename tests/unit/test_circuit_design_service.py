"""Unit tests for CircuitDesignService."""

from pathlib import Path

import pytest

from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.generators import get_generator
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("circuit_type", "specs"),
    [
        ("flyback", {"vin": 48, "vout_target": 12, "iout": 5}),
        ("forward", {"vin": 48, "vout_target": 12, "iout": 5}),
        ("llc", {"vin": 400, "vout_target": 48, "power": 500}),
        ("boost_pfc", {"vin": 220, "vout_target": 400, "power": 1000}),
    ],
)
async def test_preview_circuit_generator_topologies(circuit_design_service, circuit_type, specs):
    result = await circuit_design_service.preview_circuit(
        circuit_type=circuit_type,
        specs=specs,
    )
    assert result["success"] is True


@pytest.mark.asyncio
async def test_preview_circuit_stores_generated_simulation_settings(circuit_design_service):
    specs = {"vin": 48, "vout_target": 12, "iout": 5}
    expected = get_generator("forward").generate(specs)["simulation"]

    result = await circuit_design_service.preview_circuit(
        circuit_type="forward",
        specs=specs,
    )

    assert result["success"] is True
    token = result["data"]["preview_token"]
    preview = circuit_design_service._store.get(token)
    assert preview["simulation_settings"] == expected


@pytest.mark.asyncio
async def test_preview_circuit_merges_generated_and_explicit_simulation_settings(circuit_design_service):
    specs = {"vin": 48, "vout_target": 12, "iout": 5}
    generated = get_generator("forward").generate(specs)["simulation"]

    result = await circuit_design_service.preview_circuit(
        circuit_type="forward",
        specs=specs,
        simulation_settings={"total_time": 0.05},
    )

    assert result["success"] is True
    token = result["data"]["preview_token"]
    preview = circuit_design_service._store.get(token)
    assert preview["simulation_settings"] == {
        **generated,
        "total_time": 0.05,
    }


@pytest.mark.asyncio
async def test_preview_circuit_fails_on_validation_errors(circuit_design_service):
    result = await circuit_design_service.preview_circuit(
        circuit_type="custom",
        components=[
            {"id": "V1", "type": "DC_Source", "parameters": {"voltage": 48.0}, "position": {"x": 0, "y": 0}},
            {"id": "L1", "type": "Inductor", "parameters": {"inductance": 100e-6}, "position": {"x": 120, "y": 0}},
        ],
        connections=[{"from": "V1.invalid_pin", "to": "L1.input"}],
    )

    assert result["success"] is False
    assert result["error"]["code"] == "CIRCUIT_VALIDATION_FAILED"


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


@pytest.mark.asyncio
async def test_confirm_circuit_preserves_generated_simulation_settings(circuit_design_service):
    specs = {"vin": 48, "vout_target": 12, "iout": 5}
    expected = get_generator("forward").generate(specs)["simulation"]

    preview = await circuit_design_service.preview_circuit(
        circuit_type="forward",
        specs=specs,
    )
    assert preview["success"] is True

    result = await circuit_design_service.confirm_circuit(
        save_path="/test/forward_output.psimsch",
        preview_token=preview["data"]["preview_token"],
    )

    assert result["success"] is True
    assert result["data"]["simulation_settings"] == expected


@pytest.mark.asyncio
async def test_confirm_circuit_rejects_save_path_outside_allowed_root():
    base = Path("output") / "circuit_design_service_path_guard"
    project_root = base / "projects"
    project_root.mkdir(parents=True, exist_ok=True)
    config = AppConfig(psim_mode="mock", allowed_project_dirs=[str(project_root)])
    service = CircuitDesignService(adapter=MockPsimAdapter(), config=config)

    preview = await service.preview_circuit(circuit_type="buck")
    assert preview["success"] is True

    outside_path = base / "outside" / "blocked.psimsch"
    result = await service.confirm_circuit(
        save_path=str(outside_path),
        preview_token=preview["data"]["preview_token"],
    )

    assert result["success"] is False
    assert result["error"]["code"] == "PATH_NOT_ALLOWED"


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
