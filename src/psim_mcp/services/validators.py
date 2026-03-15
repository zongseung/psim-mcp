"""Validation utility functions for the service layer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

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
            error_message=f"Project file not found: {path}",
        )

    if allowed_dirs:
        resolved = p.resolve()
        if not any(
            _is_subpath(resolved, Path(d).resolve()) for d in allowed_dirs
        ):
            return ValidationResult(
                is_valid=False,
                error_code="PATH_NOT_ALLOWED",
                error_message=(
                    f"Path '{path}' is outside the allowed project directories. "
                    f"Allowed: {allowed_dirs}"
                ),
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
