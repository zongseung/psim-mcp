"""Design tool: thin routing layer to CircuitDesignService."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def register_tools(mcp, service=None):
    """Register design_circuit and continue_design tools on *mcp*.

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
            "자연어 입력을 분석하여 회로 토폴로지와 사양을 추출합니다. "
            "확신도가 높으면 자동 미리보기를 생성하고, 낮으면 해석 결과를 반환합니다.\n\n"
            "지원 자동 계산: buck, boost, buck_boost (설계 공식 기반).\n"
            "다른 토폴로지: 템플릿 기반 fallback.\n"
            "커스텀/복잡한 회로: get_component_library() + preview_circuit()을 직접 사용하세요.\n\n"
            "참고: 이 도구는 자연어 파싱 기반이므로 복잡한 요청은 "
            "preview_circuit()에 components/connections를 직접 전달하는 것이 더 정확합니다."
        ),
    )
    @tool_handler("design_circuit")
    async def design_circuit(description: str) -> str:
        return await _svc().design_circuit(description)

    @mcp.tool(
        description=(
            "이전 design_circuit 세션을 이어서 진행합니다. "
            "design_circuit이 추가 정보를 요청했을 때, "
            "design_session_token과 추가 정보를 전달하여 설계를 계속합니다."
        ),
    )
    @tool_handler("continue_design")
    async def continue_design(
        design_session_token: str,
        additional_specs: dict | None = None,
        additional_description: str | None = None,
    ) -> str:
        return await _svc().continue_design(
            design_session_token, additional_specs, additional_description,
        )
