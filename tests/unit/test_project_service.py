"""Unit tests for ProjectService."""


import pytest

from psim_mcp.services.project_service import ProjectService


@pytest.fixture
def mock_adapter():
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter
    return MockPsimAdapter()


@pytest.fixture
def project_service(mock_adapter, test_config):
    return ProjectService(adapter=mock_adapter, config=test_config)


@pytest.mark.asyncio
async def test_open_project_valid(project_service, sample_project_path):
    result = await project_service.open_project(str(sample_project_path))
    assert result["success"] is True


@pytest.mark.asyncio
async def test_open_project_empty_path(project_service):
    result = await project_service.open_project("")
    assert result["success"] is False


@pytest.mark.asyncio
async def test_get_project_info_no_project(project_service):
    result = await project_service.get_project_info()
    assert result["success"] is False
    assert result["error"]["code"] == "NO_PROJECT"


@pytest.mark.asyncio
async def test_get_project_info_after_open(project_service, sample_project_path):
    await project_service.open_project(str(sample_project_path))
    result = await project_service.get_project_info()
    assert result["success"] is True


@pytest.mark.asyncio
async def test_get_status(project_service):
    result = await project_service.get_status()
    assert result["success"] is True


def test_is_project_open_initial(project_service):
    assert project_service.is_project_open is False


@pytest.mark.asyncio
async def test_is_project_open_after_open(project_service, sample_project_path):
    await project_service.open_project(str(sample_project_path))
    assert project_service.is_project_open is True
