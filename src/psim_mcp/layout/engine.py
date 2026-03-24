"""Layout Engine — dispatches to topology-specific strategies."""

from __future__ import annotations

from typing import Protocol

from psim_mcp.synthesis.graph import CircuitGraph

from .models import SchematicLayout


class LayoutStrategy(Protocol):
    """Interface for topology-specific layout strategies."""

    def build_layout(
        self,
        graph: CircuitGraph,
        preferences: dict[str, object] | None = None,
    ) -> SchematicLayout: ...


# Strategy registry
_STRATEGIES: dict[str, LayoutStrategy] = {}


def register_strategy(topology: str, strategy: LayoutStrategy) -> None:
    """Register a layout strategy for a given topology name."""
    _STRATEGIES[topology] = strategy


def generate_layout(
    graph: CircuitGraph,
    preferences: dict[str, object] | None = None,
) -> SchematicLayout:
    """Main entry point. Dispatches to topology strategy."""
    strategy = _STRATEGIES.get(graph.topology)
    if strategy is None:
        raise NotImplementedError(
            f"No layout strategy registered for topology '{graph.topology}'. "
            f"Available: {sorted(_STRATEGIES.keys())}"
        )
    return strategy.build_layout(graph, preferences)
