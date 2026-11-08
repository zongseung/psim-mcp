"""PSIM-MCP tool modules."""

import base64
import json
import logging
from functools import wraps

from mcp.types import ImageContent, TextContent

from psim_mcp.utils.sanitize import (
    MAX_RESPONSE_SIZE,
    sanitize_for_llm_context,
    truncate_response,
)

logger = logging.getLogger("psim_mcp.tools")

# 결과 dict에 이 키가 있으면 [TextContent, ImageContent...]로 반환한다.
IMAGES_KEY = "_images"
# 응답 하나에 첨부하는 이미지 합계 상한(원본 PNG 바이트 기준). 텍스트 50 KB 제한과 별개.
MAX_IMAGE_TOTAL_BYTES = 400_000
# JSON을 깨지 않고 줄일 때 목록을 몇 번까지 절반으로 줄여 볼지
_MAX_SHRINK_STEPS = 60


def format_tool_error(
    code: str = "INTERNAL_ERROR", message: str = "내부 오류가 발생했습니다."
) -> str:
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


def _encoded_size(text: str) -> int:
    return len(text.encode("utf-8"))


def _largest_list(node, path=()):
    """가장 긴 목록(원소 2개 이상)의 (길이, 경로)를 찾는다."""
    best = None
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        if len(node) >= 2:
            best = (len(node), path)
        items = enumerate(node)
    else:
        return None
    for key, child in items:
        found = _largest_list(child, (*path, key))
        if found and (best is None or found[0] > best[0]):
            best = found
    return best


def _get_path(node, path):
    for key in path:
        node = node[key]
    return node


def encode_response_json_safe(result: dict, max_size: int = MAX_RESPONSE_SIZE) -> str:
    """크기 제한을 넘어도 **유효한 JSON**으로 줄여서 직렬화한다.

    가장 긴 목록을 절반씩 줄이고 ``_truncated``에 원래 길이를 기록한다. 그래도 넘으면
    success·message와 잘림 안내만 남긴다. 이미지가 붙는 응답에서만 쓴다(기존 도구 응답은
    :func:`encode_response` 그대로).
    """
    text = sanitize_for_llm_context(json.dumps(result, ensure_ascii=False))
    if _encoded_size(text) <= max_size:
        return text
    doc = json.loads(json.dumps(result, ensure_ascii=False))  # 깊은 복사
    truncated: dict[str, int] = {}
    for _ in range(_MAX_SHRINK_STEPS):
        found = _largest_list({k: v for k, v in doc.items() if k != "_truncated"})
        if found is None:
            break
        length, path = found
        label = ".".join(str(p) for p in path)
        truncated.setdefault(label, length)
        target = _get_path(doc, path)
        del target[max(1, length // 2) :]
        doc["_truncated"] = {
            "lists": truncated,
            "note": "응답이 크기 제한(50KB)을 넘어 목록 일부를 줄였습니다. 전체 결과는 파일을 보세요.",
        }
        text = sanitize_for_llm_context(json.dumps(doc, ensure_ascii=False))
        if _encoded_size(text) <= max_size:
            return text
    fallback = {
        "success": result.get("success"),
        "message": str(result.get("message", ""))[:2000],
        "_truncated": {"note": "응답이 크기 제한(50KB)을 넘어 본문을 생략했습니다."},
    }
    return sanitize_for_llm_context(json.dumps(fallback, ensure_ascii=False))


def _image_blocks(images, result: dict) -> list[ImageContent]:
    """이미지 목록을 ImageContent로 바꾼다. 합계 한도를 넘는 이미지는 빼고 안내를 붙인다."""
    blocks: list[ImageContent] = []
    total = 0
    dropped: list[str] = []
    for i, img in enumerate(images or []):
        data = img.get("data") if isinstance(img, dict) else None
        name = str(img.get("name") or f"image_{i}") if isinstance(img, dict) else f"image_{i}"
        if not isinstance(data, (bytes, bytearray)) or not data:
            dropped.append(name)
            continue
        if total + len(data) > MAX_IMAGE_TOTAL_BYTES:
            dropped.append(name)
            continue
        total += len(data)
        blocks.append(
            ImageContent(
                type="image",
                data=base64.b64encode(bytes(data)).decode("ascii"),
                mimeType=str(img.get("mime_type") or "image/png"),
            )
        )
    if dropped:
        note = (
            f"이미지 {len(dropped)}개({', '.join(dropped)})는 응답 이미지 한도"
            f"({MAX_IMAGE_TOTAL_BYTES // 1000} KB)를 넘거나 비어 있어 첨부하지 않았습니다."
        )
        # 호출한 쪽의 dict를 바꾸지 않도록 복사해서 붙인다.
        data = result.get("data")
        if isinstance(data, dict):
            result["data"] = {**data, "notes": [*data.get("notes", []), note]}
        else:
            result["notes"] = [*result.get("notes", []), note]
    return blocks


def build_tool_output(result):
    """서비스 결과를 MCP 출력으로 바꾼다.

    - ``_images`` 키가 없으면 기존과 바이트 단위로 같은 JSON 문자열.
    - 있으면 ``[TextContent(JSON), ImageContent...]``. 텍스트 50 KB 제한은 텍스트에만
      적용하되 JSON이 깨지지 않게 줄이고, 이미지는 합계 :data:`MAX_IMAGE_TOTAL_BYTES` 한도.

    목록 반환은 출력 스키마가 없는 도구(반환 주석 ``-> dict``)에서만 쓴다. ``-> str`` 도구는
    FastMCP가 ``{"result": str}`` 구조화 출력을 검증하므로 ``_images``를 넣으면 안 된다.
    """
    if not isinstance(result, dict) or IMAGES_KEY not in result:
        return encode_response(result)
    result = dict(result)
    images = result.pop(IMAGES_KEY)
    blocks = _image_blocks(images, result)
    text = encode_response_json_safe(result)
    if not blocks:
        return text
    return [TextContent(type="text", text=text), *blocks]


def tool_handler(tool_name: str):
    """Decorator that wraps a tool's async handler with standard error handling and encoding."""

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                result = await fn(*args, **kwargs)
                return build_tool_output(result)
            except Exception as e:
                logger.exception("Tool error in %s", tool_name)
                return format_tool_error(
                    code="INTERNAL_ERROR",
                    message=f"내부 오류: {type(e).__name__}: {e}",
                )

        return wrapper

    return decorator
