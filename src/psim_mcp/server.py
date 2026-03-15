"""PSIM-MCP server entry point.

Provides an app-factory pattern (``create_app``) for testability while
keeping module-level ``mcp`` and ``config`` attributes for backward
compatibility with tool modules that do lazy imports like::

    from psim_mcp.server import mcp
    from psim_mcp.server import config
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.services.simulation_service import SimulationService

from mcp.server.fastmcp import FastMCP

from psim_mcp.config import AppConfig


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


def create_service(config: AppConfig) -> SimulationService:
    """Create a :class:`SimulationService` wired to the right adapter."""
    from psim_mcp.services.simulation_service import SimulationService

    adapter = create_adapter(config)
    return SimulationService(adapter=adapter, config=config)


def register_all_tools(mcp: FastMCP, service: SimulationService) -> None:
    """Register every tool module on *mcp*."""
    from psim_mcp.tools import circuit, design, parameter, project, results, simulation

    project.register_tools(mcp, service)
    parameter.register_tools(mcp, service)
    simulation.register_tools(mcp, service)
    results.register_tools(mcp, service)
    circuit.register_tools(mcp, service)
    design.register_tools(mcp, service)


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

    app = FastMCP("psim-mcp")
    service = create_service(config)

    # Expose the service so legacy tool code that does
    # ``mcp._psim_service`` still works.
    app._psim_service = service  # type: ignore[attr-defined]

    register_all_tools(app, service)
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
