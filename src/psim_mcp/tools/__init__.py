"""PSIM-MCP tool modules."""

import json
import logging
from functools import wraps

from psim_mcp.utils.sanitize import truncate_response, sanitize_for_llm_context

logger = logging.getLogger("psim_mcp.tools")


def format_tool_error(code: str = "INTERNAL_ERROR", message: str = "내부 오류가 발생했습니다.") -> str:
    """Return a JSON string matching the standard error envelope."""
    return json.dumps(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
            },
        },
        ensure_ascii=False,
    )


def encode_response(result: dict) -> str:
    """Serialize, sanitize, and truncate a service response."""
    raw = json.dumps(result, ensure_ascii=False)
    return truncate_response(sanitize_for_llm_context(raw))


def tool_handler(tool_name: str):
    """Decorator that wraps a tool's async handler with standard error handling and encoding."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                result = await fn(*args, **kwargs)
                return encode_response(result)
            except Exception as e:
                logger.exception("Tool error in %s", tool_name)
                return format_tool_error(
                    code="INTERNAL_ERROR",
                    message=f"내부 오류: {type(e).__name__}: {e}",
                )
        return wrapper
    return decorator
