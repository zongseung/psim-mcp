"""PSIM-MCP server entry point.

Provides an app-factory pattern (``create_app``) for testability.
"""

from __future__ import annotations

import asyncio
import atexit
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter

from mcp.server.fastmcp import FastMCP

from psim_mcp.config import AppConfig

_shutdown_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def create_adapter(config: AppConfig) -> BasePsimAdapter:
    """Create the appropriate adapter based on *config.psim_mode*."""
    if config.psim_mode == "mock":
        from psim_mcp.adapters.mock_adapter import MockPsimAdapter

        return MockPsimAdapter()
    else:
        from psim_mcp.adapters.real_adapter import RealPsimAdapter

        return RealPsimAdapter(config=config)


def create_worker_pool(config: AppConfig):
    """병렬 워커 풀. 워커는 첫 병렬 요청 때 띄운다(서버 시작 때 띄우지 않음)."""
    from psim_mcp.parallel import settings as parallel_settings
    from psim_mcp.parallel.pool import BridgeWorker, MockWorker, WorkerPool

    if config.psim_mode == "mock":

        def factory(wid: int):
            return MockWorker(wid)

    else:
        from psim_mcp.adapters.real_adapter import _BRIDGE_SCRIPT, build_bridge_env

        python_exe = str(config.psim_python_exe) if config.psim_python_exe else "python"
        env = build_bridge_env(config.psim_path)

        def factory(wid: int):
            return BridgeWorker(
                wid, python_exe, _BRIDGE_SCRIPT, env, low_priority=config.parallel_low_priority
            )

    return WorkerPool(
        factory,
        idle_timeout=float(config.parallel_idle_timeout),
        job_timeout=float(config.simulation_timeout),
        max_workers=parallel_settings.max_workers(),
    )


def create_services(config: AppConfig, adapter: BasePsimAdapter) -> dict:
    """Create all domain services with proper dependency injection.

    Returns a dict of service instances keyed by role.
    """
    from psim_mcp.services.batch_service import BatchService
    from psim_mcp.services.project_service import ProjectService
    from psim_mcp.services.simulation_service import SimulationService
    from psim_mcp.services.vault_service import VaultService

    project_svc = ProjectService(adapter=adapter, config=config)
    simulation_svc = SimulationService(
        adapter=adapter,
        config=config,
        project_service=project_svc,
    )

    vault_svc = VaultService(
        drive_root=config.vault_drive_root,
        local_root=config.vault_local_root,
    )

    pool = create_worker_pool(config)
    batch_svc = BatchService(config=config, adapter=adapter, pool=pool)

    return {
        "project": project_svc,
        "batch": batch_svc,
        "pool": pool,
        "simulation": simulation_svc,
        "vault": vault_svc,
        "_adapter": adapter,
        # Legacy: combined service for backward compat
        "_legacy": simulation_svc,
    }


def register_all_tools(mcp: FastMCP, services: dict, config: AppConfig) -> None:
    """Register every tool module on *mcp* using domain services."""
    from psim_mcp.tools import analysis, batch, parameter, project, results, simulation, vault

    # Use dedicated services for each tool module
    project.register_tools(mcp, services["project"])
    parameter.register_tools(mcp, services["_legacy"], config, services.get("batch"))
    simulation.register_tools(mcp, services["simulation"])
    results.register_tools(mcp, services["_legacy"])
    analysis.register_tools(mcp, services["simulation"], services["_adapter"], config)
    vault.register_tools(mcp, services, services["vault"])
    batch.register_tools(mcp, services["batch"])


def register_knowledge_resources(mcp: FastMCP) -> None:
    """Expose the knowledge markdown files as MCP resources.

    Clients (Claude Desktop/Code 등)이 ``guidelines://…`` 리소스로 워크플로우·함정·
    템플릿 지식을 읽어갈 수 있다 (MATLAB MCP 서버의 guidelines 패턴과 동일).
    """
    from pathlib import Path

    knowledge_dir = Path(__file__).parent / "knowledge"
    resources = {
        "workflow": "PSIM-MCP 도구 사용 순서와 표준 워크플로우",
        "gotchas": "PSIM 파라미터 이름 함정과 검증 방법",
        "templates": "검증된 회로 템플릿 카탈로그 — 새 회로는 생성 대신 복사",
        "control-patterns": "C-Block 제어 설계 패턴과 실검증 교훈",
    }

    def _make_reader(path: Path):
        def _read() -> str:
            return path.read_text(encoding="utf-8")

        return _read

    for name, description in resources.items():
        path = knowledge_dir / f"{name.replace('-', '_')}.md"
        mcp.resource(
            f"guidelines://{name}",
            name=name,
            description=description,
            mime_type="text/markdown",
        )(_make_reader(path))


def create_app(config: AppConfig | None = None) -> FastMCP:
    """Application factory.  Creates and wires everything.

    Parameters
    ----------
    config:
        Optional configuration.  When *None* a fresh :class:`AppConfig` is
        created from the environment / ``.env`` file.

    Returns
    -------
    FastMCP
        A fully-configured MCP application ready to run.
    """
    if config is None:
        config = AppConfig()
    config.validate_real_mode()

    adapter = create_adapter(config)
    services = create_services(config, adapter)

    pool = services["pool"]

    # 서버 종료 시 adapter.shutdown()·워커 풀 정리를 위해 atexit 등록
    # (풀은 자기가 띄운 워커만 종료한다. 워커는 서버가 죽어도 stdin이 닫히면 스스로 끝난다.)
    def _sync_shutdown_adapter():
        for close in (adapter.shutdown, pool.shutdown):
            try:
                loop = asyncio.get_event_loop()
                if not loop.is_closed():
                    if loop.is_running():
                        loop.create_task(close())
                    else:
                        loop.run_until_complete(close())
            except Exception:
                pass  # best-effort shutdown, silently ignore all errors

    atexit.register(_sync_shutdown_adapter)

    app = FastMCP(
        "psim-mcp",
        instructions=(
            "Altair PSIM 전력전자 회로 시뮬레이션 자동화 서버. "
            "기존 .psimsch 회로 워크플로: import_circuit(회로 구조·넷 파악) → "
            "open_project → set_parameter(파라미터 수정) → run_simulation → "
            "analyze_simulation / sweep_parameter(분석·스윕). "
            "get_status로 현재 모드(mock/real)와 열린 프로젝트를 확인. "
            "회로 최적화는 optimize_circuit 사용. "
            "드라이브 원본/로컬 사본 저장 루틴: 신규는 vault_register, "
            "수정·실행·저장을 한 번에 하려면 vault_edit_and_run(원본 보호·버전 기록). "
            "조건 여러 개는 run_batch(병렬, 요약 표만 반환), 동시 실행 수 측정은 benchmark_parallel. "
            "자동·병렬 실행은 뷰어를 띄우지 않으며, 파형 창은 open_in_viewer로 파일 하나만 연다."
        ),
    )

    # Expose the legacy service so code that does ``mcp._psim_service`` still works.
    app._psim_service = services["_legacy"]  # type: ignore[attr-defined]
    app._adapter = adapter  # type: ignore[attr-defined]

    app._services = services  # type: ignore[attr-defined]
    register_all_tools(app, services, config)
    register_knowledge_resources(app)
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the MCP server (used by the ``psim-mcp`` console script)."""
    from psim_mcp.utils.logging import setup_logging

    cfg = AppConfig()
    cfg.validate_real_mode()
    setup_logging(cfg.log_dir, cfg.log_level)

    app = create_app(cfg)
    app.run(transport=cfg.server_transport)


if __name__ == "__main__":
    main()
