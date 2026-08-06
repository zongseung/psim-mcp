"""Knowledge resources (guidelines://) 등록 및 내용 테스트."""

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.server import create_app

EXPECTED = ["workflow", "gotchas", "templates", "control-patterns"]


@pytest.fixture
def app():
    return create_app(AppConfig(psim_mode="mock"))


async def test_all_knowledge_resources_registered(app):
    uris = {str(r.uri) for r in await app.list_resources()}
    for name in EXPECTED:
        assert f"guidelines://{name}" in uris


async def test_resources_return_markdown_content(app):
    for name in EXPECTED:
        contents = await app.read_resource(f"guidelines://{name}")
        text = list(contents)[0].content
        assert text.startswith("#"), f"{name}: markdown 헤더로 시작해야 함"
        assert len(text) > 200, f"{name}: 내용이 비어 있음"
