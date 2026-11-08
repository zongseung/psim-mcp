"""tool_handler 이미지 확장: _images → [TextContent, ImageContent...], 기존 응답 바이트 동일."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from psim_mcp.config import AppConfig
from psim_mcp.server import create_app
from psim_mcp.tools import (
    MAX_IMAGE_TOTAL_BYTES,
    build_tool_output,
    encode_response_json_safe,
    tool_handler,
)
from psim_mcp.utils.sanitize import MAX_RESPONSE_SIZE


def _old_encode(result: dict) -> str:
    """확장 전 tool_handler가 하던 그대로(json.dumps → sanitize → truncate)."""
    import re

    raw = json.dumps(result, ensure_ascii=False)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)
    text = re.sub(r"<\|.*?\|>", "", text)
    text = re.sub(r"\[INST\].*?\[/INST\]", "", text, flags=re.DOTALL)
    text = re.sub(r"<system>.*?</system>", "", text, flags=re.DOTALL)
    if len(text.encode("utf-8")) <= 50_000:
        return text
    return text[: 50_000 - 100] + "\n... [응답이 크기 제한(50KB)을 초과하여 잘렸습니다]"


_CASES = [
    {"success": True, "data": {"a": 1, "b": [1.5, None, "x"]}, "message": "ok"},
    {"success": True, "data": {"한글": "값", "path": "C:\\dir\\f.psimsch"}, "message": "성공"},
    {
        "success": False,
        "error": {"code": "E", "message": "bad\x01ctrl <|tag|>", "suggestion": None},
    },
    {
        "success": True,
        "data": {"rows": [{"i": i, "v": "x" * 50} for i in range(2000)]},
        "message": "big",
    },
    {"success": True, "data": {"_images_like": []}, "message": "no images key"},
]


@pytest.mark.parametrize("case", _CASES)
def test_without_images_is_byte_identical(case):
    out = build_tool_output(case)
    assert isinstance(out, str)
    assert out == _old_encode(case)


@pytest.mark.parametrize("case", _CASES)
async def test_wrapper_without_images_is_byte_identical(case):
    @tool_handler("t")
    async def fn() -> dict:
        return case

    assert await fn() == _old_encode(case)


def _png(n_bytes: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\0" * (n_bytes - 8)


def _mcp_with(result: dict) -> FastMCP:
    mcp = FastMCP("t")

    @mcp.tool()
    @tool_handler("img_tool")
    async def img_tool() -> dict:
        return result

    return mcp


async def test_fastmcp_passes_list_through():
    img = _png(1000)
    result = {
        "success": True,
        "data": {"x": 1},
        "message": "m",
        "_images": [{"data": img, "mime_type": "image/png", "name": "fig1"}],
    }
    out = await _mcp_with(result).call_tool("img_tool", {})
    blocks = out[0] if isinstance(out, tuple) else out
    assert len(blocks) == 2
    assert isinstance(blocks[0], TextContent) and isinstance(blocks[1], ImageContent)
    doc = json.loads(blocks[0].text)
    assert doc == {"success": True, "data": {"x": 1}, "message": "m"}
    assert blocks[1].mimeType == "image/png"
    assert base64.b64decode(blocks[1].data) == img


async def test_existing_app_tools_keep_single_text_block(tmp_path: Path):
    cfg = AppConfig(
        psim_mode="mock",
        psim_output_dir=tmp_path / "o",
        log_dir=tmp_path / "l",
        runs_dir=tmp_path / "r",
        parallel_settings_path=tmp_path / "p.json",
        parallel_idle_timeout=0,
    )
    app = create_app(cfg)
    try:
        for name in ("get_status", "run_simulation", "get_project_info"):
            out = await app.call_tool(name, {})
            blocks, structured = out if isinstance(out, tuple) else (out, None)
            assert len(blocks) == 1 and isinstance(blocks[0], TextContent)
            json.loads(blocks[0].text)
            # -> str 도구는 구조화 출력 {"result": 같은 문자열}도 그대로
            if structured is not None:
                assert structured == {"result": blocks[0].text}
    finally:
        await app._services["pool"].shutdown()


def test_image_total_limit_drops_extra_and_notes():
    size = 150_000
    images = [{"data": _png(size), "name": f"fig{i}"} for i in range(3)]
    result = {"success": True, "data": {"notes": ["기존"]}, "message": "m", "_images": images}
    out = build_tool_output(result)
    assert isinstance(out, list)
    imgs = [b for b in out if isinstance(b, ImageContent)]
    assert len(imgs) == MAX_IMAGE_TOTAL_BYTES // size  # 2장
    assert sum(len(base64.b64decode(b.data)) for b in imgs) <= MAX_IMAGE_TOTAL_BYTES
    doc = json.loads(out[0].text)
    assert doc["data"]["notes"][0] == "기존"
    assert "fig2" in doc["data"]["notes"][1]
    # 원래 dict는 바뀌지 않는다
    assert result["data"]["notes"] == ["기존"] and "_images" in result


def test_empty_images_returns_valid_json_text():
    out = build_tool_output({"success": True, "data": {"a": 1}, "message": "m", "_images": []})
    assert isinstance(out, str)
    assert json.loads(out) == {"success": True, "data": {"a": 1}, "message": "m"}


def test_large_text_with_images_stays_valid_json():
    rows = [{"run": i, "status": "ok", "v": "가" * 40} for i in range(3000)]
    result = {
        "success": True,
        "data": {"rows": rows, "study_dir": "x"},
        "message": "m",
        "_images": [{"data": _png(5000), "name": "fig1"}],
    }
    out = build_tool_output(result)
    text = out[0].text
    assert len(text.encode("utf-8")) <= MAX_RESPONSE_SIZE
    doc = json.loads(text)
    assert doc["data"]["study_dir"] == "x"
    assert 0 < len(doc["data"]["rows"]) < 3000
    assert doc["_truncated"]["lists"]["data.rows"] == 3000
    assert isinstance(out[1], ImageContent)
    assert len(result["data"]["rows"]) == 3000  # 원본 불변


def test_json_safe_fallback_when_no_list_to_shrink():
    result = {"success": True, "data": {"blob": "x" * 80_000}, "message": "m"}
    text = encode_response_json_safe(result)
    assert len(text.encode("utf-8")) <= MAX_RESPONSE_SIZE
    doc = json.loads(text)
    assert doc["success"] is True and doc["message"] == "m" and "_truncated" in doc
