"""Unit tests for SimulationService business logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.services.simulation_service import SimulationService


@pytest.fixture
def mock_adapter() -> MockPsimAdapter:
    return MockPsimAdapter()


@pytest.fixture
def service(mock_adapter: MockPsimAdapter, test_config: AppConfig) -> SimulationService:
    return SimulationService(adapter=mock_adapter, config=test_config)


class TestOpenProject:
    async def test_success(self, service: SimulationService, sample_project_path: Path):
        result = await service.open_project(str(sample_project_path))

        assert result["success"] is True
        assert "data" in result
        assert result["data"]["component_count"] > 0
        assert isinstance(result["data"]["components"], list)

    async def test_invalid_extension(self, service: SimulationService, tmp_path: Path):
        txt_file = tmp_path / "bad_file.txt"
        txt_file.write_text("not a psim file")
        result = await service.open_project(str(txt_file))

        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_EXTENSION"

    async def test_nonexistent_file(self, service: SimulationService, tmp_path: Path):
        result = await service.open_project(str(tmp_path / "nonexistent.psimsch"))

        assert result["success"] is False
        assert result["error"]["code"] == "FILE_NOT_FOUND"

    async def test_empty_path(self, service: SimulationService):
        result = await service.open_project("")

        assert result["success"] is False
        assert result["error"]["code"] == "EMPTY_PATH"


class TestSetParameter:
    async def test_success(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        result = await service.set_parameter("V1", "voltage", 99.0)

        assert result["success"] is True
        assert "previous_value" in result["data"]
        assert result["data"]["new_value"] == 99.0

    async def test_without_open_project(self, service: SimulationService):
        result = await service.set_parameter("V1", "voltage", 24.0)

        assert result["success"] is False
        assert result["error"]["code"] == "NO_PROJECT"

    async def test_invalid_component_id(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        result = await service.set_parameter("invalid!@#", "voltage", 24.0)

        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_ERROR"


class TestRunSimulation:
    async def test_success(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        result = await service.run_simulation()

        assert result["success"] is True
        assert result["data"]["status"] == "completed"
        assert "summary" in result["data"]

    async def test_without_open_project(self, service: SimulationService):
        result = await service.run_simulation()

        assert result["success"] is False
        assert result["error"]["code"] == "NO_PROJECT"


class TestExportResults:
    async def test_success(self, service: SimulationService, sample_project_path: Path, tmp_path: Path):
        await service.open_project(str(sample_project_path))
        await service.run_simulation()
        result = await service.export_results(str(tmp_path), format="json")

        assert result["success"] is True
        assert "exported_files" in result["data"]
        assert len(result["data"]["exported_files"]) > 0

    async def test_unsupported_format(self, service: SimulationService, sample_project_path: Path, tmp_path: Path):
        await service.open_project(str(sample_project_path))
        await service.run_simulation()
        result = await service.export_results(str(tmp_path), format="xlsx")

        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_FORMAT"


class TestGetStatus:
    async def test_mock_mode(self, service: SimulationService):
        result = await service.get_status()

        assert result["success"] is True
        assert result["data"]["mode"] == "mock"


class TestCreateCircuit:
    async def test_enriches_components_with_psim_element_type(
        self, service: SimulationService, tmp_path: Path
    ):
        save_path = tmp_path / "generated.psimsch"
        circuit_spec = {
            "components": [
                {
                    "id": "V1",
                    "type": "DC_Source",
                    "parameters": {"voltage": 48.0},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "R1",
                    "type": "Resistor",
                    "parameters": {"resistance": 10.0},
                    "position": {"x": 120, "y": 0},
                },
            ],
            "nets": [
                {"name": "vin", "pins": ["V1.positive", "R1.pin1"]},
                {"name": "gnd", "pins": ["V1.negative", "R1.pin2"]},
            ],
        }

        result = await service.create_circuit(
            circuit_type="custom",
            components=[],
            connections=[],
            save_path=str(save_path),
            circuit_spec=circuit_spec,
        )

        assert result["success"] is True
        assert result["data"]["component_count"] == 2
        assert result["data"]["components"][0]["psim_element_type"] == "VDC"
        assert result["data"]["components"][1]["psim_element_type"] == "MULTI_RESISTOR"

    async def test_rejects_save_path_outside_allowed_root(
        self, mock_adapter: MockPsimAdapter
    ):
        base = Path("output") / "simulation_service_path_guard"
        project_root = base / "projects"
        project_root.mkdir(parents=True, exist_ok=True)
        service = SimulationService(
            adapter=mock_adapter,
            config=AppConfig(psim_mode="mock", allowed_project_dirs=[str(project_root)]),
        )

        circuit_spec = {
            "components": [
                {
                    "id": "V1",
                    "type": "DC_Source",
                    "parameters": {"voltage": 48.0},
                    "position": {"x": 0, "y": 0},
                },
                {
                    "id": "R1",
                    "type": "Resistor",
                    "parameters": {"resistance": 10.0},
                    "position": {"x": 120, "y": 0},
                },
            ],
            "nets": [
                {"name": "vin", "pins": ["V1.positive", "R1.pin1"]},
                {"name": "gnd", "pins": ["V1.negative", "R1.pin2"]},
            ],
        }

        result = await service.create_circuit(
            circuit_type="custom",
            components=[],
            connections=[],
            save_path=str(base / "outside" / "generated.psimsch"),
            circuit_spec=circuit_spec,
        )

        assert result["success"] is False
        assert result["error"]["code"] == "PATH_NOT_ALLOWED"
