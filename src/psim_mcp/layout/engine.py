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
    """Main entry point. Dispatches to topology strategy.

    Falls back to algorithmic auto-layout when no dedicated strategy
    is registered for the given topology.
    """
    strategy = _STRATEGIES.get(graph.topology)
    if strategy is not None:
        return strategy.build_layout(graph, preferences)
    # Generic fallback: algorithmic auto-layout
    from .auto_placer import auto_place

    return auto_place(graph, preferences)
