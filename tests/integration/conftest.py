"""Shared fixtures for integration tests.

These tests exercise the full service stack (server.py → services → MockPsimAdapter)
wired through the app factory, without requiring a real PSIM installation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.server import create_app


@pytest.fixture
def integration_config(tmp_path: Path) -> AppConfig:
    """AppConfig in mock mode with isolated temp directories."""
    (tmp_path / "output").mkdir()
    (tmp_path / "projects").mkdir()
    return AppConfig(
        psim_mode="mock",
        psim_project_dir=tmp_path / "projects",
        psim_output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        allowed_project_dirs=[str(tmp_path)],
    )


@pytest.fixture
def app(integration_config: AppConfig):
    """Fully wired FastMCP app created through the production factory."""
    return create_app(integration_config)


@pytest.fixture
def circuit_design_service(app):
    return app._services["circuit_design"]


@pytest.fixture
def simulation_service(app):
    return app._services["simulation"]


@pytest.fixture
def project_service(app):
    return app._services["project"]


@pytest.fixture
def project_file(tmp_path: Path) -> Path:
    """Create a minimal .psimsch fixture file."""
    f = tmp_path / "test_project.psimsch"
    f.write_text("<psim/>")
    return f
