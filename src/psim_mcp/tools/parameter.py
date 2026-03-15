"""Parameter tools: set individual parameters and run parameter sweeps."""

from __future__ import annotations

import math

from psim_mcp.tools import tool_handler


def _get_service():
    """Lazy import to avoid circular dependency with server.py."""
    from psim_mcp.server import mcp  # noqa: F811

    return mcp._psim_service


def _get_config():
    """Lazy import for config."""
    from psim_mcp.server import config

    return config


def register_tools(mcp, service=None):
    """Register parameter-related tools on the given MCP instance."""

    @mcp.tool(
        description="열린 프로젝트의 컴포넌트 파라미터를 변경합니다.",
    )
    @tool_handler("set_parameter")
    async def set_parameter(
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> str:
        """Set a single component parameter and return the change summary."""
        svc = service or _get_service()
        return await svc.set_parameter(component_id, parameter_name, value)

    @mcp.tool(
        description="파라미터를 범위 내에서 변경하며 반복 시뮬레이션을 실행합니다.",
    )
    @tool_handler("sweep_parameter")
    async def sweep_parameter(
        component_id: str,
        parameter_name: str,
        start: float,
        end: float,
        step: float,
        metrics: list[str] | None = None,
    ) -> str:
        """Run a parameter sweep: iterate over a value range, simulate, collect results."""
        svc = service or _get_service()
        cfg = _get_config()

        # --- Validate step size and count --------------------------------
        if step <= 0:
            return {
                "success": False,
                "error": {"code": "INVALID_INPUT", "message": "step은 0보다 커야 합니다.", "suggestion": None},
            }

        num_steps = math.ceil((end - start) / step) + 1
        if num_steps > cfg.max_sweep_steps:
            return {
                "success": False,
                "error": {
                    "code": "SWEEP_LIMIT_EXCEEDED",
                    "message": f"스윕에 {num_steps}단계가 필요하지만 최대 허용 단계는 {cfg.max_sweep_steps}입니다.",
                    "suggestion": None,
                },
            }

        # --- Sweep loop --------------------------------------------------
        sweep_results: list[dict] = []
        current = start
        while current <= end + 1e-12:  # small epsilon for float rounding
            # Set parameter
            await svc.set_parameter(component_id, parameter_name, current)

            # Run simulation
            sim_result = await svc.run_simulation()

            step_data: dict = {
                "value": round(current, 10),
                "simulation": sim_result,
            }

            # Collect specific metrics if requested
            if metrics and isinstance(sim_result, dict):
                # Service returns {success, data: {summary: {...}}}
                data = sim_result.get("data", {}) or {}
                summary = data.get("summary", {}) or {}
                step_data["metrics"] = {
                    m: summary.get(m) for m in metrics
                }

            sweep_results.append(step_data)
            current += step

        return {
            "success": True,
            "data": {
                "component_id": component_id,
                "parameter_name": parameter_name,
                "range": {"start": start, "end": end, "step": step},
                "total_steps": len(sweep_results),
                "results": sweep_results,
            },
            "message": f"파라미터 스윕 완료: {len(sweep_results)}단계 실행.",
        }
