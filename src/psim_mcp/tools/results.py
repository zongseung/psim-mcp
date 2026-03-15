"""Result tools: export, compare, and query simulation results."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("psim_mcp.tools.results")


def _get_service():
    """Lazy import to avoid circular dependency with server.py."""
    from psim_mcp.server import mcp  # noqa: F811

    return mcp._psim_service


def register_tools(mcp, service=None):
    """Register result-related tools on the given MCP instance."""

    @mcp.tool(
        description="시뮬레이션 결과를 지정된 형식으로 내보냅니다.",
    )
    async def export_results(
        output_dir: str | None = None,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> str:
        """Export simulation results to the specified format and directory."""
        svc = service or _get_service()
        try:
            result = await svc.export_results(output_dir, format, signals)
            logger.info("Exported results (format=%s)", format)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error("Export failed: %s", exc)
            return json.dumps(
                {"success": False, "error": str(exc)},
                ensure_ascii=False,
            )

    @mcp.tool(
        description="두 시뮬레이션 결과를 비교합니다.",
    )
    async def compare_results(
        result_a: str,
        result_b: str,
        signals: list[str] | None = None,
    ) -> str:
        """Compare two simulation result sets and return a summary.

        This is a P1 feature with a basic implementation.
        """
        svc = service or _get_service()
        try:
            # Delegate to service if it has a compare method; otherwise
            # build a minimal comparison stub.
            if hasattr(svc, "compare_results"):
                result = await svc.compare_results(result_a, result_b, signals)
            else:
                result = {
                    "success": True,
                    "result_a": result_a,
                    "result_b": result_b,
                    "signals": signals,
                    "message": (
                        "Comparison is a P1 feature. "
                        "A detailed diff will be available in a future release."
                    ),
                }
            logger.info("Compared results: %s vs %s", result_a, result_b)
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error("Comparison failed: %s", exc)
            return json.dumps(
                {"success": False, "error": str(exc)},
                ensure_ascii=False,
            )

    @mcp.tool(
        description="서버 및 PSIM 연결 상태를 반환합니다.",
    )
    async def get_status() -> str:
        """Return current server and PSIM connection status."""
        svc = service or _get_service()
        try:
            result = await svc.get_status()
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.error("Status check failed: %s", exc)
            return json.dumps(
                {"success": False, "error": str(exc)},
                ensure_ascii=False,
            )
