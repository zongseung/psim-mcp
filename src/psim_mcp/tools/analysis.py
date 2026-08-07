"""Analysis and optimization tools."""

from __future__ import annotations

from psim_mcp.services.optimization_service import OptimizationService
from psim_mcp.tools import tool_handler


def register_tools(mcp, service, adapter, config):
    """Register analysis tools on the given MCP instance."""

    @mcp.tool(
        description=(
            "시뮬레이션을 실행하고 결과를 자동 분석하여 성능 지표 + 실제 신호 샘플 + 파형 PNG를 반환합니다. "
            "open_simview=True로 명시하면 PSIM Simview GUI를 추가로 띄우지만, Windows에서 GUI 띄우기에 수십 초 걸려 "
            "MCP 호출 타임아웃에 걸릴 수 있으므로 기본은 False입니다.\n\n"
            "응답의 ``signal_samples`` 필드에 각 신호의 실제 시간 시리즈(최대 100점) + 통계가 들어갑니다. "
            "**파형 설명 시 반드시 이 실데이터를 근거로 하세요**. 메트릭 스칼라(평균/리플/최종값)만으로 "
            "지수 수렴 envelope이나 리플 형태를 추론해서 그리면 실제 PSIM 결과와 동떨어진 가짜 파형이 됩니다.\n"
            "타임아웃 시 ``run_simulation(simview=false)`` → ``analyze_existing()`` 2단계로 우회 가능."
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

        adp = adapter
        analysis = AnalysisService(adp)

        # Run simulation first
        svc = service
        sim_result = await svc.run_simulation(options={"simview": 1 if open_simview else 0})

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
            "이미 존재하는 .smv 결과 파일을 읽어 메트릭 + 파형 PNG + 실제 신호 샘플을 반환합니다. "
            "시뮬레이션을 다시 돌리지 않으므로 빠릅니다 (5~10초). "
            "analyze_simulation이 타임아웃되는 경우 다음 흐름으로 우회하세요:\n"
            "  1) run_simulation(simview=false)으로 시뮬만 돌리고\n"
            "  2) analyze_existing(graph_file='...')로 분석만.\n"
            "graph_file이 비어있으면 가장 최근 run_simulation의 output_path를 자동 사용합니다.\n\n"
            "🚨 **topology 인자 선택 — 잘못 주면 메트릭이 비어서 가짜 진단으로 이어집니다**:\n"
            "  - 기존 또는 import한 실제 프로젝트를 열고 run_simulation으로 결과를 만드세요.\n"
            "  - topology는 실제 회로의 신호명에 맞추고, 메트릭이 비면 ``available_signals``를 먼저 확인하세요.\n\n"
            "응답의 ``signal_samples`` 필드에 각 신호의 실제 시간 시리즈(최대 100점 다운샘플) + "
            "통계(min/max/mean/first/last/rows_total/stride/time_step)가 포함됩니다. "
            "**파형을 사용자에게 설명할 때는 반드시 이 데이터의 mean 값을 근거로 하세요. "
            "last_value(순간값)는 스위칭 ripple 한 점이라 ±수십% 노이즈 — 정상상태 진단에 사용 금지**. "
            "metrics의 스칼라 값만으로 파형을 재구성하지도 마세요 — 지수 수렴 envelope / 리플 형태를 "
            "추론으로 그리면 실제 시뮬과 동떨어진 가짜 파형이 됩니다."
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

        adp = adapter
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
            {"graph_file": resolved_graph, **result},
            message,
        )

    @mcp.tool(
        description=(
            "사용자가 지정한 L/C 또는 설계용 R 소자값을 Optuna로 순차 최적화합니다. "
            "원본 대신 검증된 작업 사본만 변경하고, 각 측정은 명시한 파형 구간에서 계산합니다. "
            "time_budget_seconds는 다음 trial 시작 여부를 정하는 예산이며 실행 중인 PSIM을 중단하지 않습니다."
        ),
    )
    @tool_handler("optimize_circuit")
    async def optimize_circuit(request: dict) -> str:
        """Optimize a validated dynamic circuit request on safe working copies."""
        from pydantic import ValidationError

        from psim_mcp.models.optimization import OptimizationRequest
        from psim_mcp.shared.response import ResponseBuilder

        try:
            parsed = OptimizationRequest.model_validate(request)
        except ValidationError as exc:
            message = "; ".join(
                str(error["msg"]) for error in exc.errors(include_url=False, include_input=False)
            )
            return ResponseBuilder.error(
                code="VALIDATION_ERROR",
                message=message,
            )

        adp = adapter
        cfg = config
        result = await OptimizationService(adp, cfg).optimize(parsed)

        if not result.get("success"):
            response = ResponseBuilder.error(
                code="OPTIMIZATION_FAILED",
                message=result.get("error") or result.get("state", "최적화 실패"),
            )
            response["data"] = result
            return response

        message = f"최적화 완료: {result['trials_complete']}회 평가\n최적 파라미터:\n"
        for k, v in result["best_params"].items():
            message += f"  {k}: {v}\n"
        message += f"최종 비용: {result['best_cost']}"

        return ResponseBuilder.success(result, message)
