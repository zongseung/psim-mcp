"""Validation result data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationIssue:
    """A single validation finding."""

    severity: str  # "error" or "warning"
    code: str
    message: str
    component_id: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Aggregated validation outcome."""

    is_valid: bool
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
