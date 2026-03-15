"""Common fixtures for PSIM-MCP tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from psim_mcp.config import AppConfig


@pytest.fixture
def test_config(tmp_path: Path) -> AppConfig:
    """AppConfig wired for mock mode with temporary directories."""
    return AppConfig(
        psim_mode="mock",
        psim_project_dir=tmp_path / "projects",
        psim_output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        allowed_project_dirs=[str(tmp_path)],
    )


@pytest.fixture
def sample_project_path(tmp_path: Path) -> Path:
    """Create a minimal .psimsch file and return its path."""
    project_file = tmp_path / "test_project.psimsch"
    project_file.write_text("<psim/>")
    return project_file


@pytest.fixture
def invalid_project_path(tmp_path: Path) -> Path:
    """Return a path to a nonexistent .psimsch file."""
    return tmp_path / "nonexistent.psimsch"
