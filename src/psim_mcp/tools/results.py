"""Result tools: export and query simulation results."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def register_tools(mcp, service):
    """Register result-related tools on the given MCP instance."""

    @mcp.tool(
        description="시뮬레이션 결과를 지정된 형식으로 내보냅니다.",
    )
    @tool_handler("export_results")
    async def export_results(
        output_dir: str | None = None,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> str:
        """Export simulation results to the specified format and directory."""
        return await service.export_results(output_dir, format, signals)

    @mcp.tool(
        description="서버 및 PSIM 연결 상태를 반환합니다.",
    )
    @tool_handler("get_status")
    async def get_status() -> str:
        """Return current server and PSIM connection status."""
        return await service.get_status()
