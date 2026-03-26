"""Tests for tool_handler decorator and encode_response in psim_mcp.tools."""

from __future__ import annotations

import json

import pytest

from psim_mcp.tools import encode_response, tool_handler


# ------------------------------------------------------------------
# encode_response
# ------------------------------------------------------------------


def test_encode_response_serializes_dict():
    """encode_response should return a JSON string."""
    data = {"success": True, "data": {"value": 42}, "message": "ok"}
    result = encode_response(data)
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["data"]["value"] == 42


def test_encode_response_sanitizes_control_characters():
    """Control characters injected into the raw JSON string must be stripped."""
    # json.dumps escapes \x00 as \\u0000, so we test with a raw string
    # that has literal control chars post-serialization.
    from psim_mcp.utils.sanitize import sanitize_for_llm_context

    raw = '{"data": "hello\x00world\x07!"}'
    cleaned = sanitize_for_llm_context(raw)
    assert "\x00" not in cleaned
    assert "\x07" not in cleaned
    assert "helloworld!" in cleaned


def test_encode_response_truncates_large_responses():
    """Responses exceeding the 50KB limit should be truncated."""
    large_value = "x" * 100_000
    data = {"success": True, "data": large_value, "message": "big"}
    result = encode_response(data)
    assert len(result.encode("utf-8")) <= 50_000 + 200  # some headroom for the warning suffix
    assert "잘렸습니다" in result  # truncation warning present


# ------------------------------------------------------------------
# tool_handler — exception handling
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_handler_catches_exceptions():
    """When the wrapped function raises, tool_handler returns format_tool_error."""

    @tool_handler("failing_tool")
    async def boom():
        raise RuntimeError("kaboom")

    result = await boom()
    parsed = json.loads(result)
    assert parsed["success"] is False
    assert parsed["error"]["code"] == "INTERNAL_ERROR"


# ------------------------------------------------------------------
# tool_handler — success path
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_handler_encodes_successful_result():
    """On success the handler should encode_response the returned dict."""

    @tool_handler("ok_tool")
    async def ok():
        return {"success": True, "data": "hi", "message": "done"}

    result = await ok()
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["data"] == "hi"


# ------------------------------------------------------------------
# tool_handler — async function support
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_handler_works_with_async():
    """tool_handler must properly await async handlers."""
    import asyncio

    @tool_handler("async_tool")
    async def delayed():
        await asyncio.sleep(0)
        return {"success": True, "data": None, "message": "async ok"}

    result = await delayed()
    parsed = json.loads(result)
    assert parsed["success"] is True
    assert parsed["message"] == "async ok"
