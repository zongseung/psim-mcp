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
            "파형 PNG 이미지를 함께 생성합니다 (show_waveform=True 기본). "
            "open_simview=True로 명시하면 PSIM Simview GUI를 추가로 띄우지만, "
            "Windows에서 GUI 띄우기에 수십 초 걸려 MCP 호출 타임아웃에 걸릴 수 "
            "있으므로 기본은 False입니다. 파형을 PSIM Simview에서 보고 싶으면 "
            "별도로 run_simulation(simview=true)을 직접 호출하세요."
        ),
    )
    @tool_handler("analyze_simulation")
    async def analyze_simulation(
        topology: str = "buck",
        targets: dict | None = None,
        show_waveform: bool = True,
        open_simview: bool = False,
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
            "이미 존재하는 .smv 결과 파일을 읽어 메트릭 + 파형 PNG를 생성합니다. "
            "시뮬레이션을 다시 돌리지 않으므로 빠릅니다 (5~10초). "
            "analyze_simulation이 타임아웃되는 경우 다음 흐름으로 우회하세요:\n"
            "  1) run_simulation(simview=false)으로 시뮬만 돌리고\n"
            "  2) analyze_existing(graph_file='...')로 분석만.\n"
            "graph_file이 비어있으면 가장 최근 run_simulation의 output_path를 자동 사용합니다."
        ),
    )
    @tool_handler("analyze_existing")
    async def analyze_existing(
        graph_file: str = "",
        topology: str = "buck",
        targets: dict | None = None,
        show_waveform: bool = True,
    ) -> str:
        """Analyze an existing .smv graph file without re-running simulation."""
        from psim_mcp.services.analysis_service import AnalysisService
        from psim_mcp.shared.response import ResponseBuilder

        adp = adapter or _get_adapter()
        analysis = AnalysisService(adp)

        # If graph_file not provided, try to auto-detect the most recent
        # simulation result. ``RealPsimAdapter`` caches the last sim
        # output path in ``_last_output_path``; ``MockPsimAdapter`` skips
        # this hint and just runs with empty graph_file (mock signals).
        resolved_graph = graph_file
        if not resolved_graph:
            resolved_graph = getattr(adp, "_last_output_path", "") or ""

        if not resolved_graph:
            return ResponseBuilder.error(
                code="NO_GRAPH_FILE",
                message=(
                    "graph_file이 지정되지 않았고 최근 시뮬레이션 결과도 없습니다. "
                    "먼저 run_simulation을 호출하거나 .smv 파일 경로를 직접 전달하세요."
                ),
            )

        result = await analysis.analyze(
            topology=topology,
            targets=targets,
            graph_file=resolved_graph,
            show_waveform=show_waveform,
        )

        message = f"'{topology}' 분석 완료 ({resolved_graph}).\n"
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
            {"graph_file": resolved_graph, **result}, message,
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
