"""Project management tools: open and inspect PSIM projects."""

from __future__ import annotations

from psim_mcp.tools import tool_handler


def register_tools(mcp, service):
    """Register project-related tools on the given MCP instance."""

    @mcp.tool(
        description="PSIM 프로젝트 파일(.psimsch)을 열고 프로젝트 정보를 반환합니다.",
    )
    @tool_handler("open_project")
    async def open_project(path: str) -> str:
        """Open a PSIM project file and return project metadata."""
        return await service.open_project(path)

    @mcp.tool(
        description="열린 프로젝트의 상세 구조 정보를 반환합니다.",
    )
    @tool_handler("get_project_info")
    async def get_project_info() -> str:
        """Return detailed structural information about the open project."""
        return await service.get_project_info()

    @mcp.tool(
        description=(
            "기존 .psimsch 회로 파일의 **완전한 구조**(소자 + 전기적 연결/넷 + 파라미터 + "
            "시뮬레이션 설정)를 복원합니다. get_project_info와 달리 넷(어느 핀들이 서로 "
            "연결됐는지)까지 알 수 있습니다 — 사용자가 가진 기존 회로를 이해/설명/수정할 때 "
            "이 툴을 먼저 호출하세요.\n"
            "응답: components(id/type/parameters/enabled), nets(id/pins/labels/role — "
            "pins는 'L1.0' 형식 = 소자ID.핀번호), dangling_pins(미연결 핀 — disabled 소자나 "
            "미사용 출력이면 정상), stats, simulation(TIMESTEP/TOTALTIME 등).\n"
            "이후 set_parameter로 파라미터를 수정하고 run_simulation으로 재실행하는 "
            "동적 수정 루프에 연결됩니다. include_graph=true면 전체 CircuitGraph dict도 반환."
        ),
    )
    @tool_handler("import_circuit")
    async def import_circuit(path: str, include_graph: bool = False) -> str:
        """Reconstruct components + nets of an existing .psimsch schematic."""
        return await service.import_circuit(path, include_graph=include_graph)
