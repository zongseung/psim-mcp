"""Standard response envelope builders."""

from typing import Any


class ResponseBuilder:
    """Creates standardized success/error response dicts."""

    @staticmethod
    def success(data: Any, message: str) -> dict:
        return {"success": True, "data": data, "message": message}

    @staticmethod
    def error(
        code: str,
        message: str,
        suggestion: str | None = None,
        details: dict | None = None,
    ) -> dict:
        error: dict = {"code": code, "message": message, "suggestion": suggestion}
        if details:
            error["details"] = details
        return {"success": False, "error": error}
