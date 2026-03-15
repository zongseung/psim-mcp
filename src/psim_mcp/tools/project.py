"""Project management tools: open and inspect PSIM projects."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("psim_mcp.tools.project")


def _get_service():
    """Lazy import to avoid circular dependency with server.py."""
    from psim_mcp.server import mcp  # noqa: F811

    return mcp._psim_service


def register_tools(mcp, service=None):
    """Register project-related tools on the given MCP instance.

    Parameters
    ----------
    mcp:
        The FastMCP application instance.
    service:
        Optional explicit service reference.  When *None* the service is
        resolved lazily from ``mcp._psim_service``.
    """

    @mcp.tool(
        description="PSIM 프로젝트 파일(.psimsch)을 열고 프로젝트 정보를 반환합니다.",
    )
    async def open_project(path: str) -> str:
        """Open a PSIM project file and return project metadata."""
        svc = service or _get_service()
        try:
            result = await svc.open_project(path)
            logger.info("Opened project: %s", path)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error("Failed to open project '%s': %s", path, exc)
            return json.dumps(
                {"success": False, "error": str(exc)},
                ensure_ascii=False,
            )

    @mcp.tool(
        description="열린 프로젝트의 상세 구조 정보를 반환합니다.",
    )
    async def get_project_info() -> str:
        """Return detailed structural information about the open project."""
        svc = service or _get_service()
        try:
            result = await svc.adapter.get_project_info()
            logger.info("Retrieved project info")
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error("Failed to get project info: %s", exc)
            return json.dumps(
                {"success": False, "error": str(exc)},
                ensure_ascii=False,
            )
