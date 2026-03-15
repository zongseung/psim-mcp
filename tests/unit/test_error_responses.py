"""Unit tests for error response format consistency."""

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


KNOWN_ERROR_CODES = {
    "EMPTY_PATH",
    "INVALID_EXTENSION",
    "FILE_NOT_FOUND",
    "PATH_NOT_ALLOWED",
    "VALIDATION_ERROR",
    "NO_PROJECT",
    "NO_SIMULATION",
    "INVALID_FORMAT",
    "OPEN_PROJECT_FAILED",
    "SET_PARAMETER_FAILED",
    "SIMULATION_FAILED",
    "EXPORT_FAILED",
    "STATUS_FAILED",
    "COMPONENT_NOT_FOUND",
}


class TestErrorResponseFormat:
    """All error responses must have success=False plus error.code and error.message."""

    async def test_empty_path_error_format(self, service: SimulationService):
        result = await service.open_project("")
        _assert_error_response(result)

    async def test_invalid_extension_error_format(self, service: SimulationService, tmp_path: Path):
        f = tmp_path / "bad.txt"
        f.write_text("x")
        result = await service.open_project(str(f))
        _assert_error_response(result)

    async def test_file_not_found_error_format(self, service: SimulationService, tmp_path: Path):
        result = await service.open_project(str(tmp_path / "missing.psimsch"))
        _assert_error_response(result)

    async def test_no_project_set_parameter_format(self, service: SimulationService):
        result = await service.set_parameter("V1", "voltage", 1.0)
        _assert_error_response(result)

    async def test_no_project_run_simulation_format(self, service: SimulationService):
        result = await service.run_simulation()
        _assert_error_response(result)

    async def test_invalid_format_export_error(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        await service.run_simulation()
        result = await service.export_results("/tmp/out", format="xlsx")
        _assert_error_response(result)

    async def test_validation_error_special_chars(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        result = await service.set_parameter("bad!id", "voltage", 1.0)
        _assert_error_response(result)


class TestSuccessResponseFormat:
    """All success responses must have success=True and a data field."""

    async def test_open_project_success_format(self, service: SimulationService, sample_project_path: Path):
        result = await service.open_project(str(sample_project_path))
        _assert_success_response(result)

    async def test_set_parameter_success_format(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        result = await service.set_parameter("V1", "voltage", 24.0)
        _assert_success_response(result)

    async def test_run_simulation_success_format(self, service: SimulationService, sample_project_path: Path):
        await service.open_project(str(sample_project_path))
        result = await service.run_simulation()
        _assert_success_response(result)

    async def test_get_status_success_format(self, service: SimulationService):
        result = await service.get_status()
        _assert_success_response(result)


class TestErrorCodeValidity:
    """Error codes should come from the known standard set."""

    async def test_all_error_codes_are_known(self, service: SimulationService, sample_project_path: Path, tmp_path: Path):
        error_results = []

        # Collect various error responses
        error_results.append(await service.open_project(""))
        error_results.append(await service.set_parameter("V1", "voltage", 1.0))
        error_results.append(await service.run_simulation())

        txt = tmp_path / "x.txt"
        txt.write_text("x")
        error_results.append(await service.open_project(str(txt)))
        error_results.append(await service.open_project(str(tmp_path / "no.psimsch")))

        for r in error_results:
            assert r["success"] is False
            assert r["error"]["code"] in KNOWN_ERROR_CODES, (
                f"Unknown error code: {r['error']['code']}"
            )


class TestServerStability:
    """Server should not crash after multiple error calls."""

    async def test_multiple_errors_then_success(self, service: SimulationService, sample_project_path: Path):
        # Fire several errors first
        for _ in range(5):
            await service.open_project("")
            await service.set_parameter("V1", "voltage", 1.0)
            await service.run_simulation()

        # Then a valid sequence should still work
        result = await service.open_project(str(sample_project_path))
        assert result["success"] is True

        result = await service.run_simulation()
        assert result["success"] is True


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _assert_error_response(result: dict) -> None:
    assert result["success"] is False, f"Expected failure, got: {result}"
    assert "error" in result, f"Missing 'error' key: {result}"
    assert "code" in result["error"], f"Missing 'error.code': {result}"
    assert "message" in result["error"], f"Missing 'error.message': {result}"
    assert isinstance(result["error"]["code"], str)
    assert isinstance(result["error"]["message"], str)
    assert len(result["error"]["message"]) > 0


def _assert_success_response(result: dict) -> None:
    assert result["success"] is True, f"Expected success, got: {result}"
    assert "data" in result, f"Missing 'data' key: {result}"
