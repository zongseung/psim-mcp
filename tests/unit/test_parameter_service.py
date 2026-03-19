"""Unit tests for ParameterService."""

import pytest

from psim_mcp.services.parameter_service import ParameterService
from psim_mcp.services.project_service import ProjectService


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def project_service(mock_adapter, test_config):
    return ProjectService(adapter=mock_adapter, config=test_config)


@pytest.fixture
def parameter_service(mock_adapter, test_config, project_service):
    return ParameterService(
        adapter=mock_adapter, config=test_config, project_service=project_service,
    )


@pytest.mark.asyncio
async def test_set_parameter_no_project(parameter_service):
    result = await parameter_service.set_parameter("R1", "resistance", 100.0)
    assert result["success"] is False
    assert result["error"]["code"] == "NO_PROJECT"


@pytest.mark.asyncio
async def test_set_parameter_success(parameter_service, project_service, sample_project_path):
    await project_service.open_project(str(sample_project_path))
    result = await parameter_service.set_parameter("R1", "resistance", 100.0)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_set_parameter_empty_id(parameter_service, project_service, sample_project_path):
    await project_service.open_project(str(sample_project_path))
    result = await parameter_service.set_parameter("", "resistance", 100.0)
    assert result["success"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_set_parameter_invalid_value_type(parameter_service, project_service, sample_project_path):
    await project_service.open_project(str(sample_project_path))
    result = await parameter_service.set_parameter("R1", "resistance", [1, 2, 3])
    assert result["success"] is False
    assert result["error"]["code"] == "VALIDATION_ERROR"
