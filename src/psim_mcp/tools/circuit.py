"""Circuit creation tools: thin routing layer to CircuitDesignService."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def register_tools(mcp, service=None):
    """Register circuit creation tools on the given MCP instance.

    Parameters
    ----------
    service:
        A ``CircuitDesignServiceProtocol`` implementation.  When *None*
        falls back to ``mcp._psim_service`` for backward compatibility.
    """

    def _get_service():
        from psim_mcp.server import mcp as _mcp
        return _mcp._psim_service

    def _svc():
        return service or _get_service()

    @mcp.tool(
        description=(
            "PSIM 부품 라이브러리를 반환합니다. "
            "회로를 직접 설계할 때 사용 가능한 부품 타입, 핀 이름, 기본 파라미터를 확인할 수 있습니다. "
            "preview_circuit에 커스텀 components/connections를 전달하기 전에 이 도구로 부품 정보를 확인하세요."
        ),
    )
    @tool_handler("get_component_library")
    async def get_component_library(category: str | None = None) -> str:
        return _svc().get_component_library(category)

    @mcp.tool(
        description=(
            "회로도 SVG 미리보기를 생성합니다. 두 가지 모드:\n\n"
            "**모드 1 — 토폴로지 + specs (권장, 폐루프/c_code는 무조건 이 경로)**\n"
            "  circuit_type='buck' + specs={'vin': 48, 'vout_target': 12, 'iout': 2, ...}\n"
            "  generator가 파라미터를 계산하고 컴포넌트를 합성하거나, 폐루프인 경우 PSIM 검증된 chassis를 가져옴.\n\n"
            "**모드 2 — 커스텀 components/connections (개루프 실험용)**\n"
            "  임의 회로를 직접 설계. components와 connections를 직접 전달.\n"
            "  get_component_library()로 부품 타입과 핀 이름을 먼저 확인하세요.\n"
            "  components: [{\"id\":\"V1\",\"type\":\"DC_Source\",\"parameters\":{\"voltage\":310},\"position\":{\"x\":0,\"y\":0}}, ...]\n"
            "  connections: [{\"from\":\"V1.positive\",\"to\":\"SW1.drain\"}, ...]\n"
            "  ⚠️ 폐루프(`closed_loop=True`)에는 모드 2를 쓰지 마세요 — PSIM 2026의 SIMPLECBLOCK↔ONCTRL 노드 병합 quirk 때문에 시뮬이 안 됩니다.\n\n"
            "**폐루프 + 커스텀 컨트롤러 (모드 1만 가능)**\n"
            "  specs에 'closed_loop': True와 'c_code': '<C 소스>'를 함께 넣으면 PSIM SIMPLECBLOCK의 CONTENT를 LLM이 작성한 C 코드로 교체합니다 (PI/MPC/데드비트 등 자유 작성).\n"
            "  응답의 component_count=0은 의도된 동작 — confirm_circuit이 chassis 파일을 통째로 복사합니다.\n\n"
            "  토폴로지별 chassis와 SIMPLECBLOCK 호출 규약:\n"
            "  - buck (closed_loop=True): chassis 'examples\\C Block\\buck converter - digital control - C block.psimsch'\n"
            "    기본 타깃 SSCB7 (PI 컴펜세이터). 입력: x1=IL_ref, x2=IL_sense, x3=Kp, x4=Ti, x5=Fsamp, x6=upper_limit, x7=lower_limit, x8=ap_start. 출력: y1=duty word, y2=integ state.\n"
            "  - boost (closed_loop=True): chassis 'Boost converter with peak current mode control' (analog, SIMPLECBLOCK 없음 → c_code 무시).\n"
            "  다른 블록을 노리려면 'c_block_name': 'SSCB5' 같이 지정 (SSCB5=PWM, SSCB6=ADC).\n"
            "  예: specs={'vin':48, 'vout_target':12, 'iout':2, 'closed_loop':True, "
            "'c_code':'float e = x1 - x2; static float i=0; i += x3*e*1e-6; y1 = x3*e + i;'}\n\n"
            "검증 결과가 응답에 포함됩니다. 핀 이름 오류 시 올바른 핀 목록이 제안됩니다.\n"
            "확정하려면 confirm_circuit(preview_token=..., save_path=...)을 호출하세요."
        ),
    )
    @tool_handler("preview_circuit")
    async def preview_circuit(
        circuit_type: str,
        specs: dict | None = None,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> str:
        return await _svc().preview_circuit(
            circuit_type, specs, components, connections, simulation_settings,
        )

    @mcp.tool(
        description=(
            "미리보기로 확인한 회로를 확정하여 실제 .psimsch 파일을 생성합니다. "
            "preview_circuit 호출 후 사용합니다."
        ),
    )
    @tool_handler("confirm_circuit")
    async def confirm_circuit(
        save_path: str,
        preview_token: str | None = None,
        modifications: dict | None = None,
    ) -> str:
        return await _svc().confirm_circuit(save_path, preview_token, modifications)

    @mcp.tool(
        description=(
            "PSIM 회로를 자동으로 생성합니다. "
            "템플릿(buck, boost, half_bridge, full_bridge) 또는 커스텀 회로를 지원합니다."
        ),
    )
    @tool_handler("create_circuit")
    async def create_circuit(
        circuit_type: str,
        save_path: str,
        specs: dict | None = None,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> str:
        return await _svc().create_circuit_direct(
            circuit_type, save_path, specs, components, connections, simulation_settings,
        )

    @mcp.tool(
        description=(
            "사용 가능한 회로 템플릿 목록을 반환합니다. "
            "카테고리(dc_dc, dc_ac, ac_dc, pfc, renewable, motor_drive, battery, filter)로 필터링 가능."
        ),
    )
    @tool_handler("list_circuit_templates")
    async def list_circuit_templates(category: str | None = None) -> str:
        return _svc().list_templates(category)
