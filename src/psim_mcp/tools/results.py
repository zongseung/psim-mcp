"""Result tools: export, compare, and query simulation results."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def _get_service():
    """Lazy import to avoid circular dependency with server.py."""
    from psim_mcp.server import mcp  # noqa: F811

    return mcp._psim_service


def register_tools(mcp, service=None):
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
        svc = service or _get_service()
        return await svc.export_results(output_dir, format, signals)

    @mcp.tool(
        description="두 시뮬레이션 결과를 비교합니다.",
    )
    @tool_handler("compare_results")
    async def compare_results(
        result_a: str,
        result_b: str,
        signals: list[str] | None = None,
    ) -> str:
        """Compare two simulation result sets and return a summary.

        This is a P1 feature with a basic implementation.
        """
        svc = service or _get_service()
        # Delegate to service if it has a compare method; otherwise
        # build a minimal comparison stub.
        if hasattr(svc, "compare_results"):
            return await svc.compare_results(result_a, result_b, signals)
        else:
            return {
                "success": True,
                "data": {
                    "result_a": result_a,
                    "result_b": result_b,
                    "signals": signals,
                    "comparison": None,
                },
                "message": (
                    "결과 비교는 P1 기능입니다. "
                    "향후 버전에서 상세 비교가 제공될 예정입니다."
                ),
            }

    @mcp.tool(
        description="서버 및 PSIM 연결 상태를 반환합니다.",
    )
    @tool_handler("get_status")
    async def get_status() -> str:
        """Return current server and PSIM connection status."""
        svc = service or _get_service()
        return await svc.get_status()
