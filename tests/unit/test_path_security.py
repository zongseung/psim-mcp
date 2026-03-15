"""Tests for psim_mcp.utils.paths — path security utilities."""

from __future__ import annotations

from pathlib import Path

import pytest

from psim_mcp.utils.paths import (
    is_path_allowed,
    resolve_safe_path,
    validate_file_extension,
)


# ---------------------------------------------------------------------------
# resolve_safe_path
# ---------------------------------------------------------------------------


class TestResolveSafePath:
    def test_absolute_path_unchanged(self, tmp_path: Path) -> None:
        p = str(tmp_path / "file.psimsch")
        assert resolve_safe_path(p) == p

    def test_relative_path_resolved(self) -> None:
        result = resolve_safe_path("some/relative/path.psimsch")
        assert Path(result).is_absolute()

    def test_parent_traversal_normalised(self, tmp_path: Path) -> None:
        raw = str(tmp_path / "a" / "b" / ".." / ".." / "file.psimsch")
        resolved = resolve_safe_path(raw)
        assert ".." not in resolved
        expected = str((tmp_path / "file.psimsch").resolve())
        assert resolved == expected


# ---------------------------------------------------------------------------
# is_path_allowed
# ---------------------------------------------------------------------------


class TestIsPathAllowed:
    def test_allowed_path(self, tmp_path: Path) -> None:
        target = tmp_path / "projects" / "demo.psimsch"
        assert is_path_allowed(str(target), [str(tmp_path)]) is True

    def test_disallowed_path(self, tmp_path: Path) -> None:
        assert is_path_allowed("/etc/passwd", [str(tmp_path)]) is False

    def test_traversal_escape_blocked(self, tmp_path: Path) -> None:
        """A path that uses .. to escape the allowed dir is rejected."""
        escape = str(tmp_path / ".." / "etc" / "passwd")
        assert is_path_allowed(escape, [str(tmp_path)]) is False

    def test_empty_allowed_dirs_dev_mode(self) -> None:
        """Empty allowed_dirs means dev/unrestricted mode -- everything allowed."""
        assert is_path_allowed("/any/path", []) is True

    def test_multiple_allowed_dirs(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        target = dir_b / "test.psimsch"
        assert is_path_allowed(str(target), [str(dir_a), str(dir_b)]) is True


# ---------------------------------------------------------------------------
# validate_file_extension
# ---------------------------------------------------------------------------


class TestValidateFileExtension:
    def test_psimsch_accepted(self) -> None:
        assert validate_file_extension("project.psimsch") is True

    def test_wrong_extension_rejected(self) -> None:
        assert validate_file_extension("project.txt") is False

    def test_no_extension_rejected(self) -> None:
        assert validate_file_extension("project") is False

    def test_case_insensitive(self) -> None:
        assert validate_file_extension("project.PSIMSCH") is True
        assert validate_file_extension("project.Psimsch") is True

    def test_custom_allowed_extensions(self) -> None:
        assert validate_file_extension("data.csv", {".csv", ".json"}) is True
        assert validate_file_extension("data.xml", {".csv", ".json"}) is False

    def test_full_path(self) -> None:
        assert validate_file_extension("/home/user/project.psimsch") is True
