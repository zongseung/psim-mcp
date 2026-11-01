"""Parameter tools: set individual parameters and run parameter sweeps."""

from __future__ import annotations

import math

from psim_mcp.tools import tool_handler


def register_tools(mcp, service, config, batch_service=None):
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
        return await service.set_parameter(component_id, parameter_name, value)

    @mcp.tool(
        description=(
            "파라미터를 범위 내에서 변경하며 반복 시뮬레이션을 실행합니다. "
            "parallel=true이면 워커 풀로 동시에 실행하고(열린 회로 파일은 바꾸지 않고 run 폴더 사본을 수정, "
            "뷰어 없음) 단계별 요약을 반환합니다. 기본값(false)은 기존 순차 동작입니다."
        ),
    )
    @tool_handler("sweep_parameter")
    async def sweep_parameter(
        component_id: str,
        parameter_name: str,
        start: float,
        end: float,
        step: float,
        metrics: list[str] | None = None,
        parallel: bool = False,
        workers: int | None = None,
    ) -> str:
        """Run a parameter sweep: iterate over a value range, simulate, collect results."""
        # --- Validate step size and count --------------------------------
        if step <= 0:
            return {
                "success": False,
                "error": {
                    "code": "INVALID_INPUT",
                    "message": "step은 0보다 커야 합니다.",
                    "suggestion": None,
                },
            }

        num_steps = math.ceil((end - start) / step) + 1
        if num_steps > config.max_sweep_steps:
            return {
                "success": False,
                "error": {
                    "code": "SWEEP_LIMIT_EXCEEDED",
                    "message": f"스윕에 {num_steps}단계가 필요하지만 최대 허용 단계는 {config.max_sweep_steps}입니다.",
                    "suggestion": None,
                },
            }

        # --- Parallel sweep (worker pool) -------------------------------
        if parallel:
            if batch_service is None:
                return {
                    "success": False,
                    "error": {
                        "code": "NOT_SUPPORTED",
                        "message": "병렬 실행 엔진이 구성되지 않았습니다.",
                        "suggestion": None,
                    },
                }
            values = [start + i * step for i in range(num_steps)]
            values = [v for v in values if v <= end + 1e-12]
            return await batch_service.sweep(
                component_id, parameter_name, values, metrics=metrics, workers=workers
            )

        # --- Sweep loop --------------------------------------------------
        sweep_results: list[dict] = []
        failed_steps = 0
        consecutive_failures = 0
        early_stopped = False
        current = start
        while current <= end + 1e-12:  # small epsilon for float rounding
            step_data: dict = {
                "value": round(current, 10),
            }

            try:
                # Set parameter
                await service.set_parameter(component_id, parameter_name, current)

                # Run simulation
                sim_result = await service.run_simulation()
                step_data["simulation"] = sim_result

                # Collect specific metrics if requested
                if metrics and isinstance(sim_result, dict):
                    # Service returns {success, data: {summary: {...}}}
                    data = sim_result.get("data", {}) or {}
                    summary = data.get("summary", {}) or {}
                    step_data["metrics"] = {m: summary.get(m) for m in metrics}

                # 성공 시 연속 실패 카운터 리셋
                consecutive_failures = 0

            except Exception as e:
                failed_steps += 1
                consecutive_failures += 1
                step_data["error"] = str(e)
                step_data["simulation"] = None

                # 연속 3회 실패 시 조기 중단
                if consecutive_failures >= 3:
                    sweep_results.append(step_data)
                    early_stopped = True
                    break

            sweep_results.append(step_data)
            current += step

        result_data = {
            "component_id": component_id,
            "parameter_name": parameter_name,
            "range": {"start": start, "end": end, "step": step},
            "total_steps": len(sweep_results),
            "failed_steps": failed_steps,
            "results": sweep_results,
        }

        if early_stopped:
            result_data["early_stopped"] = True
            result_data["early_stop_reason"] = "연속 3회 실패로 스윕을 조기 중단했습니다."

        message = f"파라미터 스윕 완료: {len(sweep_results)}단계 실행"
        if failed_steps > 0:
            message += f" (실패 {failed_steps}건)"
        if early_stopped:
            message += " — 연속 실패로 조기 중단"
        message += "."

        return {
            "success": True,
            "data": result_data,
            "message": message,
        }
