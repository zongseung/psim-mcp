"""Tests for ResponseBuilder in psim_mcp.services.response."""

from __future__ import annotations

from psim_mcp.services.response import ResponseBuilder


def test_success_returns_correct_envelope():
    """success() must return {success: True, data: ..., message: ...}."""
    result = ResponseBuilder.success(data={"v": 1}, message="ok")
    assert result == {"success": True, "data": {"v": 1}, "message": "ok"}


def test_error_returns_correct_envelope():
    """error() must return {success: False, error: {code, message, suggestion}}."""
    result = ResponseBuilder.error(
        code="NOT_FOUND", message="missing", suggestion="try again",
    )
    assert result == {
        "success": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "missing",
            "suggestion": "try again",
        },
    }


def test_error_with_no_suggestion():
    """When suggestion is None it should still appear in the dict as None."""
    result = ResponseBuilder.error(code="ERR", message="oops")
    assert result["error"]["suggestion"] is None


def test_success_data_can_be_dict():
    result = ResponseBuilder.success(data={"a": 1}, message="m")
    assert isinstance(result["data"], dict)


def test_success_data_can_be_list():
    result = ResponseBuilder.success(data=[1, 2, 3], message="m")
    assert isinstance(result["data"], list)


def test_success_data_can_be_none():
    result = ResponseBuilder.success(data=None, message="m")
    assert result["data"] is None
