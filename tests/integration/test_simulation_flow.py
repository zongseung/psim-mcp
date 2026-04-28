"""Integration tests: project open → simulate → export pipeline.

Exercises the full service stack with MockPsimAdapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


class TestOpenSimulateExport:
    """End-to-end: open project → run simulation → export results."""

    async def test_open_simulate_export(
        self, project_service, simulation_service, project_file: Path, tmp_path: Path,
    ):
        # Step 1: Open project
        open_result = await project_service.open_project(str(project_file))
        assert open_result["success"] is True
        assert open_result["data"]["component_count"] > 0

        # Step 2: Run simulation
        sim_result = await simulation_service.run_simulation()
        assert sim_result["success"] is True
        assert sim_result["data"]["status"] == "completed"
        assert sim_result["data"]["duration_seconds"] > 0

        # Step 3: Export results
        output_dir = str(tmp_path / "output")
        export_result = await simulation_service.export_results(output_dir)
        assert export_result["success"] is True
        assert len(export_result["data"]["exported_files"]) > 0

    async def test_open_set_parameter_simulate(
        self, project_service, simulation_service, project_file: Path,
    ):
        """Open → change parameter → simulate successfully."""
        await project_service.open_project(str(project_file))

        # Change voltage via legacy delegate
        param_result = await simulation_service.set_parameter("V1", "voltage", 24.0)
        assert param_result["success"] is True
        assert param_result["data"]["new_value"] == 24.0
        assert param_result["data"]["previous_value"] == 48.0

        # Simulate with updated parameter
        sim_result = await simulation_service.run_simulation()
        assert sim_result["success"] is True


class TestSimulationGuardRails:
    """Verify that guard-rail error codes work correctly through the stack."""

    async def test_simulate_without_open_project(self, simulation_service):
        result = await simulation_service.run_simulation()

        assert result["success"] is False
        assert result["error"]["code"] == "NO_PROJECT"

    async def test_export_without_simulation(
        self, project_service, simulation_service, project_file: Path, tmp_path: Path,
    ):
        await project_service.open_project(str(project_file))

        result = await simulation_service.export_results(str(tmp_path / "output"))

        assert result["success"] is False
        assert result["error"]["code"] == "NO_SIMULATION"

    async def test_set_parameter_without_open_project(self, simulation_service):
        result = await simulation_service.set_parameter("V1", "voltage", 12.0)

        assert result["success"] is False
        assert result["error"]["code"] == "NO_PROJECT"


class TestProjectInfo:
    """Verify project info retrieval through the full stack."""

    async def test_get_project_info_after_open(
        self, project_service, project_file: Path,
    ):
        await project_service.open_project(str(project_file))

        info = await project_service.get_project_info()
        assert info["success"] is True
        assert info["data"]["component_count"] > 0
        assert isinstance(info["data"]["components"], list)

    async def test_get_status(self, project_service, project_file: Path):
        await project_service.open_project(str(project_file))

        status = await project_service.get_status()
        assert status["success"] is True
        assert status["data"]["mode"] == "mock"
