"""Standard response envelope builders."""

from typing import Any


class ResponseBuilder:
    """Creates standardized success/error response dicts."""

    @staticmethod
    def success(data: Any, message: str) -> dict:
        return {"success": True, "data": data, "message": message}

    @staticmethod
    def error(code: str, message: str, suggestion: str | None = None) -> dict:
        return {
            "success": False,
            "error": {"code": code, "message": message, "suggestion": suggestion},
        }
