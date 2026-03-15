"""Tests for psim_mcp.services.validators."""

from __future__ import annotations

from pathlib import Path

import pytest

from psim_mcp.services.validators import (
    ValidationResult,
    validate_component_id,
    validate_output_format,
    validate_parameter_name,
    validate_parameter_value,
    validate_project_path,
)


# ---------------------------------------------------------------------------
# validate_project_path
# ---------------------------------------------------------------------------


class TestValidateProjectPath:
    """validate_project_path returns a ValidationResult."""

    def test_valid_path(self, sample_project_path: Path) -> None:
        result = validate_project_path(str(sample_project_path))
        assert result.is_valid is True
        assert result.error_code is None

    def test_invalid_extension(self, tmp_path: Path) -> None:
        bad = tmp_path / "project.txt"
        bad.write_text("data")
        result = validate_project_path(str(bad))
        assert result.is_valid is False
        assert result.error_code == "INVALID_EXTENSION"

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.psimsch"
        result = validate_project_path(str(missing))
        assert result.is_valid is False
        assert result.error_code == "FILE_NOT_FOUND"

    @pytest.mark.parametrize("empty", ["", "   "])
    def test_empty_path(self, empty: str) -> None:
        result = validate_project_path(empty)
        assert result.is_valid is False
        assert result.error_code == "EMPTY_PATH"

    def test_path_within_allowed_dirs(self, sample_project_path: Path) -> None:
        allowed = [str(sample_project_path.parent)]
        result = validate_project_path(str(sample_project_path), allowed_dirs=allowed)
        assert result.is_valid is True

    def test_path_outside_allowed_dirs(self, sample_project_path: Path) -> None:
        allowed = ["/some/other/dir"]
        result = validate_project_path(str(sample_project_path), allowed_dirs=allowed)
        assert result.is_valid is False
        assert result.error_code == "PATH_NOT_ALLOWED"

    def test_path_traversal_blocked_by_allowed_dirs(
        self, sample_project_path: Path
    ) -> None:
        """Parent-dir traversal that escapes allowed_dirs is rejected."""
        allowed = [str(sample_project_path.parent / "subdir")]
        result = validate_project_path(str(sample_project_path), allowed_dirs=allowed)
        assert result.is_valid is False
        assert result.error_code == "PATH_NOT_ALLOWED"

    def test_no_allowed_dirs_skips_check(self, sample_project_path: Path) -> None:
        """When allowed_dirs is None or empty, path restriction is skipped."""
        result = validate_project_path(str(sample_project_path), allowed_dirs=None)
        assert result.is_valid is True

        result2 = validate_project_path(str(sample_project_path), allowed_dirs=[])
        assert result2.is_valid is True


# ---------------------------------------------------------------------------
# validate_component_id
# ---------------------------------------------------------------------------


class TestValidateComponentId:
    @pytest.mark.parametrize("cid", ["V1", "SW1", "R_load", "A" + "b" * 63])
    def test_valid_ids(self, cid: str) -> None:
        assert validate_component_id(cid) is True

    @pytest.mark.parametrize(
        "cid",
        [
            "",            # empty
            "1abc",        # starts with digit
            "a; DROP",     # injection attempt
            "A" + "b" * 64,  # 65 chars total — too long
        ],
    )
    def test_invalid_ids(self, cid: str) -> None:
        assert validate_component_id(cid) is False


# ---------------------------------------------------------------------------
# validate_parameter_name
# ---------------------------------------------------------------------------


class TestValidateParameterName:
    @pytest.mark.parametrize("name", ["Resistance", "V_out", "X1"])
    def test_valid_names(self, name: str) -> None:
        assert validate_parameter_name(name) is True

    @pytest.mark.parametrize("name", ["", "123", "a b", "x" * 65])
    def test_invalid_names(self, name: str) -> None:
        assert validate_parameter_name(name) is False


# ---------------------------------------------------------------------------
# validate_parameter_value
# ---------------------------------------------------------------------------


class TestValidateParameterValue:
    @pytest.mark.parametrize("val", [0, 42, 3.14, -1.0, "hello"])
    def test_accepted_types(self, val: object) -> None:
        assert validate_parameter_value(val) is True

    @pytest.mark.parametrize("val", [None, True, False, [1, 2], {"a": 1}])
    def test_rejected_types(self, val: object) -> None:
        assert validate_parameter_value(val) is False


# ---------------------------------------------------------------------------
# validate_output_format
# ---------------------------------------------------------------------------


class TestValidateOutputFormat:
    @pytest.mark.parametrize("fmt", ["json", "csv"])
    def test_accepted_formats(self, fmt: str) -> None:
        assert validate_output_format(fmt) is True

    @pytest.mark.parametrize("fmt", ["xml", "JSON", "CSV", "", "parquet"])
    def test_rejected_formats(self, fmt: str) -> None:
        assert validate_output_format(fmt) is False
