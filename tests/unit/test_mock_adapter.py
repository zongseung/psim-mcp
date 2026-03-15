"""Unit tests for MockPsimAdapter."""

from __future__ import annotations

import pytest

from psim_mcp.adapters.mock_adapter import MockPsimAdapter


@pytest.fixture
def mock_adapter() -> MockPsimAdapter:
    return MockPsimAdapter()


class TestOpenProject:
    async def test_returns_project_metadata(self, mock_adapter: MockPsimAdapter):
        result = await mock_adapter.open_project("/tmp/demo.psimsch")

        assert result["name"] == "demo"
        assert isinstance(result["components"], list)
        assert result["component_count"] == len(result["components"])
        assert result["component_count"] > 0
        assert "parameter_count" in result

    async def test_path_is_preserved(self, mock_adapter: MockPsimAdapter):
        path = "/some/path/project.psimsch"
        result = await mock_adapter.open_project(path)
        assert result["path"] == path

    async def test_windows_path(self, mock_adapter: MockPsimAdapter):
        result = await mock_adapter.open_project(r"C:\Users\test\project.psimsch")
        assert result["name"] == "project"


class TestSetParameter:
    async def test_success_after_open(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.set_parameter("V1", "voltage", 24.0)

        assert result["component_id"] == "V1"
        assert result["parameter_name"] == "voltage"
        assert result["previous_value"] == 48.0
        assert result["new_value"] == 24.0
        assert "unit" in result

    async def test_raises_without_open_project(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No project"):
            await mock_adapter.set_parameter("V1", "voltage", 24.0)

    async def test_raises_for_unknown_component(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        with pytest.raises(ValueError, match="not found"):
            await mock_adapter.set_parameter("NONEXISTENT", "voltage", 1.0)

    async def test_raises_for_unknown_parameter(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        with pytest.raises(ValueError, match="not found"):
            await mock_adapter.set_parameter("V1", "nonexistent_param", 1.0)


class TestRunSimulation:
    async def test_returns_completed_status(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.run_simulation()

        assert result["status"] == "completed"
        assert "duration_seconds" in result
        assert "summary" in result
        assert isinstance(result["summary"], dict)

    async def test_raises_without_open_project(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No project"):
            await mock_adapter.run_simulation()


class TestExportResults:
    async def test_returns_exported_files(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        await mock_adapter.run_simulation()
        result = await mock_adapter.export_results("/tmp/output", "json")

        assert "exported_files" in result
        assert isinstance(result["exported_files"], list)
        assert len(result["exported_files"]) > 0

    async def test_raises_without_simulation(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No simulation"):
            await mock_adapter.export_results("/tmp/output")


class TestGetStatus:
    async def test_returns_status_dict(self, mock_adapter: MockPsimAdapter):
        result = await mock_adapter.get_status()

        assert result["mode"] == "mock"
        assert result["psim_connected"] is False
        assert result["current_project"] is None
        assert result["last_simulation"] is None
        assert "server" in result

    async def test_status_reflects_open_project(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.get_status()

        assert result["current_project"] is not None
        assert result["current_project"]["name"] == "demo"


class TestGetProjectInfo:
    async def test_returns_project_info_after_open(self, mock_adapter: MockPsimAdapter):
        await mock_adapter.open_project("/tmp/demo.psimsch")
        result = await mock_adapter.get_project_info()

        assert result["name"] == "demo"
        assert "components" in result
        assert result["component_count"] == len(result["components"])
        assert "parameter_count" in result

    async def test_raises_without_open_project(self, mock_adapter: MockPsimAdapter):
        with pytest.raises(RuntimeError, match="No project"):
            await mock_adapter.get_project_info()
