"""Tests for startup and config validation (validate_real_mode)."""

from __future__ import annotations

from pathlib import Path

import pytest

from psim_mcp.config import AppConfig


def test_mock_mode_passes_validation():
    """Mock mode should pass validate_real_mode without error."""
    cfg = AppConfig(psim_mode="mock")
    cfg.validate_real_mode()  # should not raise


def test_real_mode_without_paths_raises(tmp_path: Path):
    """Real mode with no paths set must raise ValueError."""
    cfg = AppConfig(psim_mode="real")
    with pytest.raises(ValueError, match="PSIM_MODE=real"):
        cfg.validate_real_mode()


def test_real_mode_with_all_paths_passes(tmp_path: Path):
    """Real mode with all required paths should pass validation."""
    cfg = AppConfig(
        psim_mode="real",
        psim_path=tmp_path / "psim.exe",
        psim_python_exe=tmp_path / "python.exe",
        psim_project_dir=tmp_path / "projects",
        psim_output_dir=tmp_path / "output",
    )
    cfg.validate_real_mode()  # should not raise


def test_real_mode_error_lists_all_missing_fields():
    """The error message should contain all missing field names."""
    cfg = AppConfig(psim_mode="real")
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_real_mode()

    msg = str(exc_info.value)
    for field in ("PSIM_PATH", "PSIM_PYTHON_EXE", "PSIM_PROJECT_DIR", "PSIM_OUTPUT_DIR"):
        assert field in msg, f"Missing field '{field}' not found in error message"


def test_real_mode_partial_paths_raises():
    """Real mode with only some paths set should still raise for the missing ones."""
    cfg = AppConfig(
        psim_mode="real",
        psim_path=Path("/some/psim.exe"),
        # psim_python_exe, psim_project_dir, psim_output_dir are missing
    )
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_real_mode()

    msg = str(exc_info.value)
    assert "PSIM_PATH" not in msg  # it IS set
    assert "PSIM_PYTHON_EXE" in msg
    assert "PSIM_PROJECT_DIR" in msg
    assert "PSIM_OUTPUT_DIR" in msg
