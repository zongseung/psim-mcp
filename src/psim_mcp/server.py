"""PSIM-MCP server entry point.

Creates the FastMCP instance, wires up the adapter + service layer,
and registers all tool modules.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from psim_mcp.config import AppConfig

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
config = AppConfig()

# ---------------------------------------------------------------------------
# FastMCP instance
# ---------------------------------------------------------------------------
mcp = FastMCP("psim-mcp")

# ---------------------------------------------------------------------------
# Adapter / Service wiring
# ---------------------------------------------------------------------------
if config.psim_mode == "mock":
    from psim_mcp.adapters.mock_adapter import MockPsimAdapter

    adapter = MockPsimAdapter()
else:
    from psim_mcp.adapters.real_adapter import RealPsimAdapter

    adapter = RealPsimAdapter(config=config)

from psim_mcp.services.simulation_service import SimulationService

service = SimulationService(adapter=adapter, config=config)

# Expose the service so that tool modules can access it via `mcp._psim_service`.
mcp._psim_service = service  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------
from psim_mcp.tools import parameter, project, results, simulation  # noqa: E402

project.register_tools(mcp, service)
parameter.register_tools(mcp, service)
simulation.register_tools(mcp, service)
results.register_tools(mcp, service)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Run the MCP server."""
    mcp.run(transport=config.server_transport)


if __name__ == "__main__":
    main()
