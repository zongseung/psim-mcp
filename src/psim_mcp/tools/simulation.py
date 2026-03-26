"""Simulation tool: run a PSIM transient simulation."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def _get_service():
    """Lazy import to avoid circular dependency with server.py."""
    from psim_mcp.server import mcp  # noqa: F811

    return mcp._psim_service


def register_tools(mcp, service=None):
    """Register simulation-related tools on the given MCP instance."""

    @mcp.tool(
        description=(
            "현재 열린 프로젝트의 시뮬레이션을 실행합니다. "
            "simview=True이면 PSIM Simview에서 파형 그래프를 자동으로 엽니다."
        ),
    )
    @tool_handler("run_simulation")
    async def run_simulation(
        time_step: float | None = None,
        total_time: float | None = None,
        timeout: int | None = None,
        simview: bool = True,
    ) -> str:
        """Execute the simulation with optional parameter overrides."""
        svc = service or _get_service()
        # Build options dict from non-None parameters only
        options: dict = {}
        if time_step is not None:
            options["time_step"] = time_step
        if total_time is not None:
            options["total_time"] = total_time
        if timeout is not None:
            options["timeout"] = timeout
        options["simview"] = 1 if simview else 0

        return await svc.run_simulation(options if options else None)
