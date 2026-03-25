"""Validation utility functions for the service layer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from psim_mcp.utils.sanitize import sanitize_path_for_display

# Pre-compiled patterns
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_VALID_FORMATS = frozenset({"json", "csv"})


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of a validation check."""

    is_valid: bool
    error_code: str | None = None
    error_message: str | None = None


def validate_project_path(
    path: str,
    allowed_dirs: list[str] | None = None,
) -> ValidationResult:
    """Validate a PSIM project file path.

    Checks performed (in order):
    1. Non-empty string.
    2. Extension is ``.psimsch``.
    3. File exists on disk.
    4. Path falls within *allowed_dirs* (if the list is non-empty).
    """
    if not path or not path.strip():
        return ValidationResult(
            is_valid=False,
            error_code="EMPTY_PATH",
            error_message="Project path must not be empty.",
        )

    p = Path(path)

    if p.suffix.lower() != ".psimsch":
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_EXTENSION",
            error_message=(
                f"Expected a '.psimsch' file, got '{p.suffix}'. "
                "Please provide a valid PSIM schematic file."
            ),
        )

    if not p.exists():
        return ValidationResult(
            is_valid=False,
            error_code="FILE_NOT_FOUND",
            error_message=f"프로젝트 파일을 찾을 수 없습니다: {sanitize_path_for_display(path)}",
        )

    if allowed_dirs:
        resolved = p.resolve()
        if not any(
            _is_subpath(resolved, Path(d).resolve()) for d in allowed_dirs
        ):
            return ValidationResult(
                is_valid=False,
                error_code="PATH_NOT_ALLOWED",
                error_message="지정된 경로가 허용된 디렉터리 범위를 벗어났습니다.",
            )

    return ValidationResult(is_valid=True)


def validate_save_path(
    path: str,
    allowed_dirs: list[str] | None = None,
) -> ValidationResult:
    """Validate an output path for a new PSIM schematic file.

    Checks performed (in order):
    1. Non-empty string.
    2. Extension is ``.psimsch``.
    3. Parent directory falls within *allowed_dirs* (if the list is non-empty).
    """
    if not path or not path.strip():
        return ValidationResult(
            is_valid=False,
            error_code="EMPTY_PATH",
            error_message="Project path must not be empty.",
        )

    p = Path(path)

    if p.suffix.lower() != ".psimsch":
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_EXTENSION",
            error_message=(
                f"Expected a '.psimsch' file, got '{p.suffix}'. "
                "Please provide a valid PSIM schematic file."
            ),
        )

    if allowed_dirs:
        candidate = p.resolve()
        if not any(
            _is_subpath(candidate, Path(d).resolve()) for d in allowed_dirs
        ):
            return ValidationResult(
                is_valid=False,
                error_code="PATH_NOT_ALLOWED",
                error_message="지정한 저장 경로가 허용된 디렉터리 범위를 벗어났습니다.",
            )

    return ValidationResult(is_valid=True)


def validate_component_id(component_id: str) -> bool:
    """Return *True* if *component_id* matches ``^[A-Za-z][A-Za-z0-9_]{0,63}$``."""
    return bool(_IDENTIFIER_RE.match(component_id))


def validate_parameter_name(name: str) -> bool:
    """Return *True* if *name* matches ``^[A-Za-z][A-Za-z0-9_]{0,63}$``."""
    return bool(_IDENTIFIER_RE.match(name))


def validate_parameter_value(value: object) -> bool:
    """Accept ``int``, ``float``, or ``str``.  Reject ``None`` and other types."""
    return isinstance(value, (int, float, str)) and not isinstance(value, bool)


def validate_output_format(format: str) -> bool:
    """Return *True* if *format* is in the supported whitelist."""
    return format in _VALID_FORMATS


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------


def _is_subpath(child: Path, parent: Path) -> bool:
    """Check whether *child* is equal to or a descendant of *parent*."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------
# Extended validators
# ------------------------------------------------------------------


def validate_simulation_options(options: dict | None, max_timeout: int = 300) -> ValidationResult:
    """Validate simulation parameters."""
    if options is None:
        return ValidationResult(is_valid=True)

    time_step = options.get("time_step")
    if time_step is not None:
        if not isinstance(time_step, (int, float)) or time_step <= 0 or time_step < 1e-12:
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_INPUT",
                error_message="time_step은 1e-12 이상의 양수여야 합니다.",
            )

    total_time = options.get("total_time")
    if total_time is not None:
        if not isinstance(total_time, (int, float)) or total_time <= 0 or total_time > 3600:
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_INPUT",
                error_message="total_time은 0 초과, 3600초 이하여야 합니다.",
            )

    timeout = options.get("timeout")
    if timeout is not None:
        if not isinstance(timeout, (int, float)) or timeout <= 0 or timeout > max_timeout:
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_INPUT",
                error_message=f"timeout은 0 초과, {max_timeout}초 이하여야 합니다.",
            )

    return ValidationResult(is_valid=True)


def validate_output_dir(output_dir: str) -> ValidationResult:
    """Validate output directory exists and is writable."""
    if not output_dir or not output_dir.strip():
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_INPUT",
            error_message="출력 디렉터리가 지정되지 않았습니다.",
        )

    dir_path = Path(output_dir).resolve()

    if not dir_path.exists():
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_INPUT",
            error_message="출력 디렉터리가 존재하지 않습니다.",
        )

    if not dir_path.is_dir():
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_INPUT",
            error_message="지정된 경로가 디렉터리가 아닙니다.",
        )

    import os
    if not os.access(dir_path, os.W_OK):
        return ValidationResult(
            is_valid=False,
            error_code="PERMISSION_DENIED",
            error_message="출력 디렉터리에 쓰기 권한이 없습니다.",
        )

    return ValidationResult(is_valid=True)


def validate_signals_list(signals: list[str] | None, max_signals: int = 100) -> ValidationResult:
    """Validate signals list for export."""
    if signals is None:
        return ValidationResult(is_valid=True)

    if len(signals) > max_signals:
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_INPUT",
            error_message=f"신호 목록은 최대 {max_signals}개까지 지정할 수 있습니다.",
        )

    for sig in signals:
        if not isinstance(sig, str) or not sig.strip():
            return ValidationResult(
                is_valid=False,
                error_code="INVALID_INPUT",
                error_message="신호 이름은 비어있지 않은 문자열이어야 합니다.",
            )

    return ValidationResult(is_valid=True)


def validate_string_length(value: str, max_length: int = 1024, field_name: str = "값") -> ValidationResult:
    """Validate string value doesn't exceed max length."""
    if isinstance(value, str) and len(value) > max_length:
        return ValidationResult(
            is_valid=False,
            error_code="INVALID_INPUT",
            error_message=f"{field_name}이(가) 최대 길이({max_length}자)를 초과했습니다.",
        )
    return ValidationResult(is_valid=True)
