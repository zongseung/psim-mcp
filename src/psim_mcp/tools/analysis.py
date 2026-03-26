"""Analysis and optimization tools."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def _get_service():
    from psim_mcp.server import mcp

    return mcp._psim_service


def _get_adapter():
    from psim_mcp.server import mcp

    return mcp._adapter


def register_tools(mcp, service=None, adapter=None):
    """Register analysis tools on the given MCP instance."""

    @mcp.tool(
        description=(
            "시뮬레이션을 실행하고 결과를 자동 분석하여 성능 지표를 반환합니다. "
            "파형 이미지도 생성할 수 있습니다. "
            "open_simview=True이면 PSIM Simview에서 파형 그래프를 자동으로 엽니다."
        ),
    )
    @tool_handler("analyze_simulation")
    async def analyze_simulation(
        topology: str = "buck",
        targets: dict | None = None,
        show_waveform: bool = True,
        open_simview: bool = True,
    ) -> str:
        """Run simulation and analyze results with topology-specific metrics."""
        from psim_mcp.services.analysis_service import AnalysisService
        from psim_mcp.shared.response import ResponseBuilder

        adp = adapter or _get_adapter()
        analysis = AnalysisService(adp)

        # Run simulation first
        svc = service or _get_service()
        sim_result = await svc.run_simulation(
            options={"simview": 1 if open_simview else 0}
        )

        if not isinstance(sim_result, dict) or not sim_result.get("success"):
            return sim_result

        graph_file = sim_result.get("data", {}).get("output_path", "")

        result = await analysis.analyze(
            topology=topology,
            targets=targets,
            graph_file=graph_file,
            show_waveform=show_waveform,
        )

        message = f"'{topology}' 시뮬레이션 분석 완료.\n"
        for name, val in result.get("metrics", {}).items():
            if isinstance(val, (int, float)):
                message += f"  {name}: {val}\n"

        if result.get("comparison"):
            message += "\n목표 대비:\n"
            for name, comp in result["comparison"].items():
                status = "PASS" if comp["pass"] else "FAIL"
                message += f"  [{status}] {name}: 목표={comp['target']}, 실제={comp['actual']}\n"

        if result.get("waveform_path"):
            message += f"\n파형: {result['waveform_path']}"

        return ResponseBuilder.success(
            {
                "simulation": sim_result.get("data", {}),
                **result,
            },
            message,
        )

    @mcp.tool(
        description=(
            "회로 파라미터를 자동으로 최적화합니다 (Bayesian optimization). "
            "50~100회 시뮬레이션을 반복하여 최적값을 찾습니다."
        ),
    )
    @tool_handler("optimize_circuit")
    async def optimize_circuit(
        topology: str = "buck",
        targets: dict | None = None,
        n_trials: int = 50,
    ) -> str:
        """Optimize circuit parameters using Bayesian optimization."""
        from psim_mcp.services.optimization_service import OptimizationService
        from psim_mcp.shared.response import ResponseBuilder

        if not targets:
            return ResponseBuilder.error(
                code="NO_TARGETS",
                message=(
                    "최적화 목표가 필요합니다. 예: "
                    "targets={'output_voltage_mean': 12.0, 'output_voltage_ripple_pct': 1.0}"
                ),
            )

        adp = adapter or _get_adapter()
        opt = OptimizationService(adp)

        result = await opt.optimize(
            topology=topology,
            targets=targets,
            n_trials=n_trials,
        )

        if not result.get("success"):
            return ResponseBuilder.error(
                code="OPTIMIZATION_FAILED",
                message=result.get("error", "최적화 실패"),
            )

        message = (
            f"최적화 완료: {result['trials_completed']}회 시뮬레이션\n"
            f"최적 파라미터:\n"
        )
        for k, v in result["best_params"].items():
            message += f"  {k}: {v}\n"
        message += f"최종 비용: {result['best_cost']}"

        return ResponseBuilder.success(result, message)
