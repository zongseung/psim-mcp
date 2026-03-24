"""Tests for the app factory pattern in psim_mcp.server."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

from psim_mcp.adapters.mock_adapter import MockPsimAdapter
from psim_mcp.config import AppConfig
from psim_mcp.server import create_adapter, create_app, create_service
from psim_mcp.services.simulation_service import SimulationService


# ------------------------------------------------------------------
# create_app
# ------------------------------------------------------------------


def test_create_app_returns_fastmcp():
    """create_app() should return a FastMCP instance."""
    app = create_app(AppConfig(psim_mode="mock"))
    assert isinstance(app, FastMCP)


def test_create_app_registers_15_tools():
    """The factory must register exactly 15 tools."""
    app = create_app(AppConfig(psim_mode="mock"))
    tools = app._tool_manager._tools  # internal dict keyed by tool name
    assert len(tools) == 15, f"Expected 15 tools, got {len(tools)}: {list(tools.keys())}"


def test_create_app_with_explicit_config(tmp_path: Path):
    """When an explicit config is passed, the app should use it."""
    cfg = AppConfig(
        psim_mode="mock",
        psim_output_dir=tmp_path / "out",
        log_dir=tmp_path / "logs",
    )
    app = create_app(cfg)
    service: SimulationService = app._psim_service
    assert service._config is cfg


# ------------------------------------------------------------------
# create_adapter
# ------------------------------------------------------------------


def test_create_adapter_mock():
    """Mock mode should produce a MockPsimAdapter."""
    cfg = AppConfig(psim_mode="mock")
    adapter = create_adapter(cfg)
    assert isinstance(adapter, MockPsimAdapter)


def test_create_adapter_real_skipped_or_mocked(tmp_path: Path):
    """Real mode adapter creation — mock the import to avoid PSIM dependency."""
    cfg = AppConfig(
        psim_mode="real",
        psim_path=tmp_path / "psim.exe",
        psim_python_exe=tmp_path / "python.exe",
        psim_project_dir=tmp_path / "projects",
        psim_output_dir=tmp_path / "output",
    )
    # We mock RealPsimAdapter since it may not be importable everywhere.
    fake_adapter = object()
    with patch(
        "psim_mcp.server.create_adapter",
        return_value=fake_adapter,
    ):
        from psim_mcp.server import create_adapter as patched
        result = patched(cfg)
        assert result is fake_adapter


# ------------------------------------------------------------------
# create_service
# ------------------------------------------------------------------


def test_create_service_returns_simulation_service():
    """create_service should return a SimulationService."""
    cfg = AppConfig(psim_mode="mock")
    svc = create_service(cfg)
    assert isinstance(svc, SimulationService)


# ------------------------------------------------------------------
# real mode validation at app creation
# ------------------------------------------------------------------


def test_create_app_real_mode_missing_fields_raises(monkeypatch):
    """create_app with psim_mode='real' but missing paths must raise ValueError."""
    for var in ("PSIM_MODE", "PSIM_PATH", "PSIM_PYTHON_EXE", "PSIM_PROJECT_DIR", "PSIM_OUTPUT_DIR"):
        monkeypatch.delenv(var, raising=False)
    cfg = AppConfig(psim_mode="real", _env_file=None)
    with pytest.raises(ValueError, match="PSIM_MODE=real"):
        create_app(cfg)
