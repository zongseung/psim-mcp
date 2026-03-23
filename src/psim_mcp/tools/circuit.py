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
            "모드 1 (템플릿): circuit_type='buck' + specs={'V_in': 48, 'V_out': 12} 형태로 간편 생성.\n\n"
            "모드 2 (커스텀 설계): 임의 회로를 직접 설계. components와 connections를 직접 전달.\n"
            "get_component_library()로 부품 타입과 핀 이름을 먼저 확인하세요.\n"
            "components: [{\"id\": \"V1\", \"type\": \"DC_Source\", \"parameters\": {\"voltage\": 310}, \"position\": {\"x\": 0, \"y\": 0}}, ...]\n"
            "connections: [{\"from\": \"V1.positive\", \"to\": \"SW1.drain\"}, ...]\n\n"
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
