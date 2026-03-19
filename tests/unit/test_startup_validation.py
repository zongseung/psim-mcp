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
    # 경로 존재 검증이 추가되었으므로 실제 디렉터리/파일을 생성
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
        # psim_python_exe, psim_project_dir, psim_output_dir are missing
    )
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_real_mode()

    msg = str(exc_info.value)
    assert "PSIM_PATH" not in msg  # it IS set
    assert "PSIM_PYTHON_EXE" in msg
    assert "PSIM_PROJECT_DIR" in msg
    assert "PSIM_OUTPUT_DIR" in msg


def test_real_mode_error_includes_example_values():
    """에러 메시지에 각 필드의 예시값이 포함되어야 한다."""
    cfg = AppConfig(psim_mode="real")
    with pytest.raises(ValueError) as exc_info:
        cfg.validate_real_mode()

    msg = str(exc_info.value)
    # 예시값 포함 여부 확인
    assert "Powersim" in msg
    assert "python38" in msg


def test_real_mode_nonexistent_psim_path_raises(tmp_path: Path):
    """PSIM_PATH가 존재하지 않는 디렉터리이면 ValueError를 발생시켜야 한다."""
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
    """PSIM_PYTHON_EXE가 존재하지 않는 파일이면 ValueError를 발생시켜야 한다."""
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
