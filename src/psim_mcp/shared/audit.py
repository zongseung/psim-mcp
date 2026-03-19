"""Audit logging middleware.

Provides a reusable execute-with-audit pattern used by all domain services.
Wraps the existing ``SecurityAuditLogger`` from ``utils.logging``.
"""

from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable

from psim_mcp.utils.logging import SecurityAuditLogger, hash_input  # noqa: F401


class AuditMiddleware:
    """Applies timing and audit logging around service method execution."""

    def __init__(self) -> None:
        self._audit = SecurityAuditLogger()
        self._logger = logging.getLogger(__name__)

    async def execute_with_audit(
        self,
        tool_name: str,
        input_summary: dict,
        handler: Callable[[], Awaitable[dict]],
    ) -> dict:
        """Execute *handler* with timing and audit logging.

        Parameters
        ----------
        tool_name:
            Logical name of the operation (used in audit logs).
        input_summary:
            Dict of non-sensitive metadata to include in the log entry.
        handler:
            Async callable that performs the actual work and returns a
            response dict with at least a ``"success"`` key.
        """
        start = time.monotonic()
        success = False
        try:
            result = await handler()
            success = result.get("success", False)
            return result
        except Exception:
            self._logger.exception("Audit-wrapped error in %s", tool_name)
            raise
        finally:
            duration = (time.monotonic() - start) * 1000
            self._audit.log_tool_call(tool_name, input_summary, duration, success)

    def log_path_blocked(self, path: str, reason: str) -> None:
        """Record a blocked path access attempt."""
        self._audit.log_path_blocked(path, reason)

    def log_invalid_input(self, tool: str, field: str, reason: str) -> None:
        """Record an invalid input event."""
        self._audit.log_invalid_input(tool, field, reason)
