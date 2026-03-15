"""Project management tools: open and inspect PSIM projects."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


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
    @tool_handler("open_project")
    async def open_project(path: str) -> str:
        """Open a PSIM project file and return project metadata."""
        svc = service or _get_service()
        return await svc.open_project(path)

    @mcp.tool(
        description="열린 프로젝트의 상세 구조 정보를 반환합니다.",
    )
    @tool_handler("get_project_info")
    async def get_project_info() -> str:
        """Return detailed structural information about the open project."""
        svc = service or _get_service()
        return await svc.get_project_info()
