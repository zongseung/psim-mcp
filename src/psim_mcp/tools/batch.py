"""병렬 실행 도구: run_batch, benchmark_parallel, open_in_viewer."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def register_tools(mcp, batch_service):
    """Register parallel batch tools."""

    @mcp.tool(
        description=(
            "같은 회로를 조건 여러 개로 병렬 실행하고 조건별 요약 표만 반환합니다(파형 원본 없음). "
            'conditions 예: [{"Lx": 0.001}, {"L1.Inductance": 0.002, "C2.Capacitance": "220u"}]. '
            "점이 없는 키는 회로 변수(파일 복제 없이 덮어쓰기), '소자.파라미터' 키는 run 폴더의 회로 사본을 수정합니다. "
            "숫자로 적힌 소자 값(예: L1 Inductance=0.002)은 변수 덮어쓰기로 바뀌지 않으므로 'L1.Inductance' 형식을 쓰세요. "
            "schematic_path를 생략하면 열린 회로를 쓰며, 원본 파일은 수정하지 않습니다. "
            "표에는 신호별 정상상태(앞 skip_ratio 제외) 평균·리플(p-p)·최대·최소가 들어가고, "
            "형식이 틀린 조건(회로가 참조하지 않는 변수, 없는 소자·파라미터 등)은 실행하지 않고 그 행을 "
            "status 오류·executed=false로 표시하며, 응답의 invalid_conditions(run·code·message)와 "
            "suggestions(오류 코드별 고치는 방법)에 담습니다. 나머지 조건은 실행합니다. "
            "모든 조건이 틀렸거나 strict=true면 실행 전에 배치 전체를 거부합니다. "
            "실행 중 실패한 조건도 status에 오류로 표시됩니다. 개수는 succeeded(성공)·failed(실행했지만 실패)·"
            "invalid(형식 오류로 미실행)로 나뉘며 합계는 조건 수와 같습니다. 뷰어는 띄우지 않습니다(Simview=0). "
            "workers 생략 시 저장된 벤치마크 값 또는 물리 코어 수를 씁니다. "
            "결과 폴더: runs/<study_id>/run_000/ (config.json, summary.json, result.smv), 전체 표는 results.csv. "
            "저장 정책: rank_by(표 열 이름 '신호.지표', 예 'I(L1).ripple' 오름차순, '-Vo1.mean' 내림차순, "
            "지표는 mean·ripple·max·min)로 순위를 매기고 표에 rank 열을 붙입니다. "
            "keep_smv는 'all'(파형 전부 보존)·'top_k'(순위 상위 top_k개만, 기본 3)·'none'(파형 안 남김) 중 하나이며, "
            "생략하면 rank_by가 있을 때 'top_k', 없을 때 'none'입니다 — 즉 기본적으로 파형(.smv)은 "
            "전부 남지 않습니다. 파형이 모두 필요하면 keep_smv='all'을 주세요. "
            "동점은 run 번호가 작은 쪽이 앞이고, 실패·형식 오류 행과 값이 없거나 NaN인 행은 순위에서 빠집니다. "
            "rank_by가 있으면 응답 top에 상위 top_k행 요약(run·입력값·rank_by 값)이 붙습니다. "
            "plot=true면 그림을 PNG로 만들어 응답에 이미지로 첨부하고 study 폴더 plots/에도 저장합니다: "
            "그림 1 조건-지표 그래프(입력 하나만 바뀌면 x축=그 입력, 아니면 run 번호; "
            "y=rank_by 지표, 없으면 첫 신호의 평균·리플), "
            "그림 2 상위 run 파형 겹쳐 그리기(.smv가 남은 run만, 측정 구간). "
            "max_images(1~4, 기본 2)는 응답에 첨부할 그림 수입니다. 그림 생성이 실패해도 결과 표는 그대로 반환합니다."
        ),
    )
    @tool_handler("run_batch")
    async def run_batch(
        conditions: list[dict],
        schematic_path: str | None = None,
        signals: list[str] | None = None,
        total_time: float | None = None,
        time_step: float | None = None,
        workers: int | None = None,
        study_name: str | None = None,
        skip_ratio: float = 0.5,
        strict: bool = False,
        rank_by: str | None = None,
        top_k: int = 3,
        keep_smv: str | None = None,
        plot: bool = False,
        max_images: int = 2,
    ) -> dict:
        return await batch_service.run_batch(
            conditions,
            schematic_path=schematic_path,
            signals=signals,
            total_time=total_time,
            time_step=time_step,
            workers=workers,
            study_name=study_name,
            skip_ratio=skip_ratio,
            strict=strict,
            rank_by=rank_by,
            top_k=top_k,
            keep_smv=keep_smv,
            plot=plot,
            max_images=max_images,
        )

    @mcp.tool(
        description=(
            "이 PC에서 최적 동시 실행 수를 측정해 설정에 저장합니다. 지정한 회로의 측정용 사본만 사용합니다. "
            "동시 실행 수 1·2·4·물리 코어·논리 코어(levels로 변경 가능)마다 같은 조건 runs개를 돌려 "
            "처리량(runs/min)과 순차 대비 배율, 결과 일치 여부를 표로 반환합니다. "
            "워커 시작(라이선스) 오류나 실행 실패가 나면 거기서 멈춥니다. "
            "기본값으로 저장하는 값은 물리 코어 수 이하에서 처리량이 가장 높은 동시 실행 수입니다. "
            "실행당 시간이 실제 작업과 비슷한 회로로 측정하세요(수 초 이상 권장). 수 분이 걸릴 수 있습니다."
        ),
    )
    @tool_handler("benchmark_parallel")
    async def benchmark_parallel(
        schematic_path: str | None = None,
        levels: list[int] | None = None,
        runs: int | None = None,
        conditions: list[dict] | None = None,
        save: bool = True,
    ) -> dict:
        return await batch_service.benchmark(
            schematic_path=schematic_path,
            levels=levels,
            runs=runs,
            conditions=conditions,
            save=save,
        )

    @mcp.tool(
        description=(
            "지정한 결과 파일(.smv) 하나를 PSIM Simview 창으로 엽니다. "
            "자동·병렬 실행은 뷰어를 띄우지 않으므로, 파형을 직접 봐야 할 때만 사용하세요."
        ),
    )
    @tool_handler("open_in_viewer")
    async def open_in_viewer(graph_file: str) -> dict:
        return await batch_service.open_in_viewer(graph_file)
