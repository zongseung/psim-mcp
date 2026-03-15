"""Tests for security-focused validators."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from psim_mcp.services.validators import (
    validate_simulation_options,
    validate_output_dir,
    validate_signals_list,
    validate_string_length,
)


# ------------------------------------------------------------------
# validate_simulation_options
# ------------------------------------------------------------------


class TestValidateSimulationOptions:
    """Ensure simulation parameters are bounded to safe ranges."""

    def test_none_options_valid(self):
        result = validate_simulation_options(None)
        assert result.is_valid

    def test_valid_time_step(self):
        result = validate_simulation_options({"time_step": 1e-6})
        assert result.is_valid

    def test_time_step_zero_invalid(self):
        result = validate_simulation_options({"time_step": 0})
        assert not result.is_valid

    def test_time_step_negative_invalid(self):
        result = validate_simulation_options({"time_step": -1})
        assert not result.is_valid

    def test_time_step_too_small_invalid(self):
        result = validate_simulation_options({"time_step": 1e-15})
        assert not result.is_valid

    def test_valid_total_time(self):
        result = validate_simulation_options({"total_time": 0.1})
        assert result.is_valid

    def test_total_time_exceeds_max_invalid(self):
        result = validate_simulation_options({"total_time": 3601})
        assert not result.is_valid

    def test_total_time_zero_invalid(self):
        result = validate_simulation_options({"total_time": 0})
        assert not result.is_valid

    def test_total_time_negative_invalid(self):
        result = validate_simulation_options({"total_time": -5})
        assert not result.is_valid

    def test_valid_timeout(self):
        result = validate_simulation_options({"timeout": 60})
        assert result.is_valid

    def test_timeout_exceeds_max_invalid(self):
        result = validate_simulation_options({"timeout": 500}, max_timeout=300)
        assert not result.is_valid

    def test_timeout_zero_invalid(self):
        result = validate_simulation_options({"timeout": 0})
        assert not result.is_valid

    def test_timeout_negative_invalid(self):
        result = validate_simulation_options({"timeout": -10})
        assert not result.is_valid


# ------------------------------------------------------------------
# validate_output_dir
# ------------------------------------------------------------------


class TestValidateOutputDir:
    """Ensure output directory validation catches bad paths."""

    def test_existing_writable_dir_valid(self, tmp_path: Path):
        result = validate_output_dir(str(tmp_path))
        assert result.is_valid

    def test_nonexistent_dir_invalid(self, tmp_path: Path):
        result = validate_output_dir(str(tmp_path / "does_not_exist"))
        assert not result.is_valid

    def test_file_path_not_dir_invalid(self, tmp_path: Path):
        file = tmp_path / "a_file.txt"
        file.write_text("data")
        result = validate_output_dir(str(file))
        assert not result.is_valid

    def test_empty_string_invalid(self):
        result = validate_output_dir("")
        assert not result.is_valid

    def test_whitespace_only_invalid(self):
        result = validate_output_dir("   ")
        assert not result.is_valid


# ------------------------------------------------------------------
# validate_signals_list
# ------------------------------------------------------------------


class TestValidateSignalsList:
    """Ensure signal lists are bounded and well-formed."""

    def test_none_valid(self):
        result = validate_signals_list(None)
        assert result.is_valid

    def test_small_list_valid(self):
        result = validate_signals_list(["Vout", "Iload", "Vdc"])
        assert result.is_valid

    def test_too_many_signals_invalid(self):
        signals = [f"sig_{i}" for i in range(101)]
        result = validate_signals_list(signals)
        assert not result.is_valid

    def test_empty_string_in_list_invalid(self):
        result = validate_signals_list(["Vout", ""])
        assert not result.is_valid

    def test_whitespace_only_signal_invalid(self):
        result = validate_signals_list(["Vout", "   "])
        assert not result.is_valid

    def test_exactly_max_valid(self):
        signals = [f"sig_{i}" for i in range(100)]
        result = validate_signals_list(signals)
        assert result.is_valid


# ------------------------------------------------------------------
# validate_string_length
# ------------------------------------------------------------------


class TestValidateStringLength:
    """Ensure strings are bounded to configured max length."""

    def test_short_string_valid(self):
        result = validate_string_length("hello")
        assert result.is_valid

    def test_at_max_length_valid(self):
        result = validate_string_length("a" * 1024)
        assert result.is_valid

    def test_over_max_length_invalid(self):
        result = validate_string_length("a" * 1025)
        assert not result.is_valid

    def test_custom_max_length(self):
        result = validate_string_length("abcdef", max_length=5)
        assert not result.is_valid

    def test_custom_max_length_valid(self):
        result = validate_string_length("abc", max_length=5)
        assert result.is_valid
