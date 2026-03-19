"""PSIM-MCP server entry point.

Provides an app-factory pattern (``create_app``) for testability while
keeping module-level ``mcp`` and ``config`` attributes for backward
compatibility with tool modules that do lazy imports like::

    from psim_mcp.server import mcp
    from psim_mcp.server import config
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


def create_services(config: AppConfig, adapter: BasePsimAdapter) -> dict:
    """Create all domain services with proper dependency injection.

    Returns a dict of service instances keyed by role.
    """
    from psim_mcp.services.project_service import ProjectService
    from psim_mcp.services.parameter_service import ParameterService
    from psim_mcp.services.simulation_service import SimulationService
    from psim_mcp.services.circuit_design_service import CircuitDesignService

    project_svc = ProjectService(adapter=adapter, config=config)
    parameter_svc = ParameterService(
        adapter=adapter, config=config, project_service=project_svc,
    )
    simulation_svc = SimulationService(
        adapter=adapter, config=config, project_service=project_svc,
    )
    circuit_design_svc = CircuitDesignService(
        adapter=adapter, config=config,
    )

    return {
        "project": project_svc,
        "parameter": parameter_svc,
        "simulation": simulation_svc,
        "circuit_design": circuit_design_svc,
        # Legacy: combined service for backward compat
        "_legacy": simulation_svc,
    }


def create_service(config: AppConfig):
    """Create a :class:`SimulationService` wired to the right adapter.

    Backward-compatible factory.  New code should use ``create_services()``.
    """
    from psim_mcp.services.simulation_service import SimulationService

    adapter = create_adapter(config)
    return SimulationService(adapter=adapter, config=config)


def register_all_tools(mcp: FastMCP, services: dict) -> None:
    """Register every tool module on *mcp* using domain services."""
    from psim_mcp.tools import circuit, design, parameter, project, results, simulation

    # Use dedicated services for each tool module
    project.register_tools(mcp, services["project"])
    parameter.register_tools(mcp, services["_legacy"])
    simulation.register_tools(mcp, services["simulation"])
    results.register_tools(mcp, services["_legacy"])
    circuit.register_tools(mcp, services["circuit_design"])
    design.register_tools(mcp, services["circuit_design"])


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

    # 서버 종료 시 adapter.shutdown() 호출을 위해 atexit 등록
    def _sync_shutdown_adapter():
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(adapter.shutdown())
            else:
                loop.run_until_complete(adapter.shutdown())
        except Exception:
            _shutdown_logger.debug("Adapter shutdown during atexit (best-effort)", exc_info=True)

    atexit.register(_sync_shutdown_adapter)

    app = FastMCP("psim-mcp")

    # Expose the legacy service so code that does ``mcp._psim_service`` still works.
    app._psim_service = services["_legacy"]  # type: ignore[attr-defined]

    register_all_tools(app, services)
    return app


# ---------------------------------------------------------------------------
# Module-level lazy singletons (backward compatibility)
# ---------------------------------------------------------------------------
# Tool modules do ``from psim_mcp.server import mcp`` and
# ``from psim_mcp.server import config`` inside lazy helpers.
# We satisfy those imports without triggering heavy initialisation at
# *import time* by using a module-level ``__getattr__``.

_app: FastMCP | None = None
_config: AppConfig | None = None


def _ensure_initialised() -> None:
    """Lazily initialise the module-level singletons on first access."""
    global _app, _config
    if _app is None:
        _config = AppConfig()
        _config.validate_real_mode()
        _app = create_app(_config)


def __getattr__(name: str):
    """Lazy module-level attribute access for ``mcp`` and ``config``."""
    if name == "mcp":
        _ensure_initialised()
        return _app
    if name == "config":
        _ensure_initialised()
        return _config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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

    # Also update the module-level singletons so any lazy imports from
    # tool code during the run see the same instances.
    global _app, _config
    _app = app
    _config = cfg

    app.run(transport=cfg.server_transport)


if __name__ == "__main__":
    main()
