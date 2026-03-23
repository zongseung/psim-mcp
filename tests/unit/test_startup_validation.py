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
    psim_dir = tmp_path / "psim"
    psim_dir.mkdir()
    python_exe = psim_dir / "python.exe"
    python_exe.touch()
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    cfg = AppConfig(
        psim_mode="real",
        psim_path=psim_dir,
        psim_python_exe=python_exe,
        psim_project_dir=project_dir,
        psim_output_dir=output_dir,
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
    )
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_real_mode()

    msg = str(exc_info.value)
    assert "PSIM_PATH" not in msg
    assert "PSIM_PYTHON_EXE" in msg
    assert "PSIM_PROJECT_DIR" in msg
    assert "PSIM_OUTPUT_DIR" in msg


def test_real_mode_error_includes_example_values():
    """Validation errors should include example values."""
    cfg = AppConfig(psim_mode="real")
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_real_mode()

    msg = str(exc_info.value)
    assert "Powersim" in msg
    assert "python38" in msg


def test_real_mode_nonexistent_psim_path_raises(tmp_path: Path):
    """A nonexistent PSIM_PATH must raise ValueError."""
    fake_dir = tmp_path / "nonexistent_psim"
    python_exe = tmp_path / "python.exe"
    python_exe.touch()

    cfg = AppConfig(
        psim_mode="real",
        psim_path=fake_dir,
        psim_python_exe=python_exe,
        psim_project_dir=tmp_path,
        psim_output_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="PSIM_PATH"):
        cfg.validate_real_mode()


def test_real_mode_nonexistent_python_exe_raises(tmp_path: Path):
    """A nonexistent PSIM_PYTHON_EXE must raise ValueError."""
    psim_dir = tmp_path / "psim"
    psim_dir.mkdir()
    fake_exe = psim_dir / "nonexistent_python.exe"

    cfg = AppConfig(
        psim_mode="real",
        psim_path=psim_dir,
        psim_python_exe=fake_exe,
        psim_project_dir=tmp_path,
        psim_output_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="PSIM_PYTHON_EXE"):
        cfg.validate_real_mode()


def test_real_mode_inferrs_python_exe_from_psim_path(tmp_path: Path):
    """Infer PSIM_PYTHON_EXE from PSIM_PATH/python38/python.exe when available."""
    psim_dir = tmp_path / "psim"
    python_dir = psim_dir / "python38"
    python_dir.mkdir(parents=True)
    inferred_python = python_dir / "python.exe"
    inferred_python.touch()
    project_dir = tmp_path / "projects"
    project_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    cfg = AppConfig(
        psim_mode="real",
        psim_path=psim_dir,
        psim_project_dir=project_dir,
        psim_output_dir=output_dir,
    )

    cfg.validate_real_mode()

    assert cfg.psim_python_exe == inferred_python


def test_relative_log_dir_is_resolved_from_project_root():
    """Relative LOG_DIR should resolve from the repository root, not cwd."""
    cfg = AppConfig(log_dir=Path("./logs"))
    expected = Path(__file__).resolve().parents[2] / "logs"
    assert cfg.log_dir == expected
