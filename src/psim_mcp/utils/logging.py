"""Structured logging setup for the PSIM-MCP server."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

_STANDARD_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_STANDARD_DATEFMT = "%Y-%m-%d %H:%M:%S"

_JSON_FORMAT = (
    '{"time": "%(asctime)s", "level": "%(levelname)s", '
    '"logger": "%(name)s", "message": "%(message)s"}'
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_logging(log_dir: Path, log_level: str = "INFO") -> logging.Logger:
    """Initialise application-wide logging with file and console handlers.

    Creates three log files under *log_dir*:

    * ``server.log``  -- standard format, all messages
    * ``tools.log``   -- JSON-like structured format, tool-specific messages
    * ``psim.log``    -- standard format, adapter / bridge messages

    Parameters
    ----------
    log_dir:
        Directory where log files are written.  Created if it does not exist.
    log_level:
        Minimum log level (``DEBUG``, ``INFO``, ``WARNING``, etc.).

    Returns
    -------
    logging.Logger
        The root ``psim_mcp`` logger.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Root logger for the package
    root_logger = logging.getLogger("psim_mcp")
    root_logger.setLevel(level)

    # Prevent duplicate handlers on repeated calls
    if root_logger.handlers:
        return root_logger

    # --- Console handler (standard format) --------------------------------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(
        logging.Formatter(_STANDARD_FORMAT, datefmt=_STANDARD_DATEFMT),
    )
    root_logger.addHandler(console_handler)

    # --- server.log (standard format, all messages) -----------------------
    server_handler = logging.FileHandler(log_dir / "server.log", encoding="utf-8")
    server_handler.setLevel(level)
    server_handler.setFormatter(
        logging.Formatter(_STANDARD_FORMAT, datefmt=_STANDARD_DATEFMT),
    )
    root_logger.addHandler(server_handler)

    # --- tools.log (JSON structured, only tools.* loggers) ----------------
    tools_logger = logging.getLogger("psim_mcp.tools")
    tools_handler = logging.FileHandler(log_dir / "tools.log", encoding="utf-8")
    tools_handler.setLevel(level)
    tools_handler.setFormatter(
        logging.Formatter(_JSON_FORMAT, datefmt=_STANDARD_DATEFMT),
    )
    tools_logger.addHandler(tools_handler)

    # --- psim.log (standard format, adapters / bridge) --------------------
    psim_logger = logging.getLogger("psim_mcp.adapters")
    psim_handler = logging.FileHandler(log_dir / "psim.log", encoding="utf-8")
    psim_handler.setLevel(level)
    psim_handler.setFormatter(
        logging.Formatter(_STANDARD_FORMAT, datefmt=_STANDARD_DATEFMT),
    )
    psim_logger.addHandler(psim_handler)

    # Also capture bridge logs in psim.log
    bridge_logger = logging.getLogger("psim_mcp.bridge")
    bridge_logger.addHandler(psim_handler)

    # --- security.log (security audit events) ----------------------------
    security_logger = logging.getLogger("psim_mcp.security")
    security_handler = logging.FileHandler(log_dir / "security.log", encoding="utf-8")
    security_handler.setLevel(logging.DEBUG)
    security_handler.setFormatter(
        logging.Formatter(_STANDARD_FORMAT, datefmt=_STANDARD_DATEFMT),
    )
    security_logger.addHandler(security_handler)

    return root_logger


# ---------------------------------------------------------------------------
# Security audit utilities
# ---------------------------------------------------------------------------


def hash_input(value: str) -> str:
    """Hash sensitive input for audit logging."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


class SecurityAuditLogger:
    """Logger for security-relevant events."""

    def __init__(self, logger_name: str = "psim_mcp.security"):
        self._logger = logging.getLogger(logger_name)

    def log_tool_call(
        self,
        tool_name: str,
        input_summary: dict,
        duration_ms: float,
        success: bool,
    ):
        """Log a tool call with timing and hashed inputs."""
        self._logger.info(
            "tool_call | tool=%s | duration_ms=%.1f | success=%s | input_hash=%s",
            tool_name,
            duration_ms,
            success,
            hash_input(str(input_summary)),
        )

    def log_path_blocked(self, path: str, reason: str):
        """Log a blocked path access attempt."""
        self._logger.warning(
            "path_blocked | path_hash=%s | reason=%s",
            hash_input(path),
            reason,
        )

    def log_invalid_input(self, tool_name: str, field: str, reason: str):
        """Log an invalid input attempt."""
        self._logger.warning(
            "invalid_input | tool=%s | field=%s | reason=%s",
            tool_name,
            field,
            reason,
        )

    def log_subprocess_event(
        self,
        action: str,
        duration_ms: float,
        success: bool,
        error: str | None = None,
    ):
        """Log subprocess execution events."""
        msg = "subprocess | action=%s | duration_ms=%.1f | success=%s"
        args: list[object] = [action, duration_ms, success]
        if error:
            msg += " | error=%s"
            args.append(error)
        self._logger.info(msg, *args)

    def log_rate_limit(self, tool_name: str, reason: str):
        """Log rate limiting events."""
        self._logger.warning(
            "rate_limit | tool=%s | reason=%s",
            tool_name,
            reason,
        )


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``psim_mcp`` namespace.

    Parameters
    ----------
    name:
        Logger name.  Will be used as-is; callers typically pass a
        dotted path like ``"psim_mcp.tools.project"``.

    Returns
    -------
    logging.Logger
    """
    return logging.getLogger(name)
