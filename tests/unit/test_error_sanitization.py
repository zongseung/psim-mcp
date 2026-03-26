"""Tests that error messages from SimulationService do NOT expose sensitive info."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.services.simulation_service import SimulationService


@pytest.fixture
def service(test_config: AppConfig) -> SimulationService:
    """SimulationService backed by a real MockPsimAdapter."""
    adapter = MockPsimAdapter()
    return SimulationService(adapter=adapter, config=test_config)


@pytest.fixture
def service_with_failing_adapter(test_config: AppConfig) -> SimulationService:
    """SimulationService whose adapter raises internal exceptions."""
    adapter = MockPsimAdapter()
    return SimulationService(adapter=adapter, config=test_config)


# ------------------------------------------------------------------
# open_project: nonexistent file
# ------------------------------------------------------------------


class TestOpenProjectErrorSanitization:
    """Error messages must NOT leak full filesystem paths."""

    @pytest.mark.asyncio
    async def test_nonexistent_file_no_full_path(self, service: SimulationService, tmp_path: Path):
        """Error for a missing file should not contain the full directory path."""
        fake_path = str(tmp_path / "subdir" / "deep" / "secret.psimsch")
        result = await service.open_project(fake_path)

        assert result["success"] is False
        error_msg = result["error"]["message"]
        # The message should NOT contain the parent directory structure
        assert "subdir" not in error_msg
        assert "deep" not in error_msg
        # It may contain the filename but not the full path
        assert str(tmp_path) not in error_msg

    @pytest.mark.asyncio
    async def test_disallowed_path_no_allowed_dirs_leaked(self, tmp_path: Path):
        """Error for a path outside allowed_dirs should NOT reveal the allowed dirs."""
        allowed = str(tmp_path / "safe_zone")
        (tmp_path / "safe_zone").mkdir()
        config = AppConfig(
            psim_mode="mock",
            log_dir=tmp_path / "logs",
            allowed_project_dirs=[allowed],
        )
        adapter = MockPsimAdapter()
        svc = SimulationService(adapter=adapter, config=config)

        # Create file outside allowed dir
        outside_file = tmp_path / "outside" / "test.psimsch"
        outside_file.parent.mkdir(parents=True, exist_ok=True)
        outside_file.write_text("<psim/>")

        result = await svc.open_project(str(outside_file))
        assert result["success"] is False
        error_msg = result["error"]["message"]
        # Must NOT reveal the allowed directories
        assert "safe_zone" not in error_msg
        assert allowed not in error_msg


# ------------------------------------------------------------------
# set_parameter: invalid chars
# ------------------------------------------------------------------


class TestSetParameterErrorSanitization:
    """Validation errors should be generic and not echo raw bad input."""

    @pytest.mark.asyncio
    async def test_invalid_component_id_generic_error(
        self, service: SimulationService, sample_project_path: Path,
    ):
        """set_parameter with invalid component_id should return a validation error."""
        # First open a project so the service allows set_parameter
        await service.open_project(str(sample_project_path))
        result = await service.set_parameter(
            component_id="<script>alert(1)</script>",
            parameter_name="voltage",
            value=10.0,
        )
        assert result["success"] is False
        # The error code should indicate validation failure
        assert result["error"]["code"] == "VALIDATION_ERROR"


# ------------------------------------------------------------------
# Internal exception: error is generic
# ------------------------------------------------------------------


class TestInternalExceptionSanitization:
    """When the adapter throws, the service must return a generic error, not str(exc)."""

    @pytest.mark.asyncio
    async def test_adapter_exception_not_leaked(self, test_config: AppConfig, sample_project_path: Path):
        """An internal adapter exception message must NOT appear in the response."""
        adapter = MockPsimAdapter()
        svc = SimulationService(adapter=adapter, config=test_config)

        # Open project successfully first
        await svc.open_project(str(sample_project_path))

        # Now monkey-patch the adapter to raise an internal error with sensitive info
        secret_msg = "ConnectionError: database password is hunter2 at /etc/secrets/db.conf"
        adapter.run_simulation = AsyncMock(side_effect=RuntimeError(secret_msg))

        result = await svc.run_simulation({"time_step": 1e-6})
        assert result["success"] is False
        error_msg = result["error"]["message"]
        # The secret message must NOT appear in the response
        assert "hunter2" not in error_msg
        assert "db.conf" not in error_msg
        assert "/etc/secrets" not in error_msg
        # It should be a generic Korean error message
        assert "오류" in error_msg

    @pytest.mark.asyncio
    async def test_set_parameter_adapter_exception_not_leaked(
        self, test_config: AppConfig, sample_project_path: Path,
    ):
        """set_parameter adapter errors must not leak internal details."""
        adapter = MockPsimAdapter()
        svc = SimulationService(adapter=adapter, config=test_config)

        await svc.open_project(str(sample_project_path))

        secret = "ODBC connection string: Server=10.0.0.1;Database=prod"
        adapter.set_parameter = AsyncMock(side_effect=Exception(secret))

        result = await svc.set_parameter("V1", "voltage", 24.0)
        assert result["success"] is False
        error_msg = result["error"]["message"]
        assert "10.0.0.1" not in error_msg
        assert "ODBC" not in error_msg
