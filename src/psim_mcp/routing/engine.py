"""Routing Engine -- dispatches to topology-specific routing strategies."""

from __future__ import annotations

from typing import Protocol

from psim_mcp.layout.models import SchematicLayout
from psim_mcp.synthesis.graph import CircuitGraph

from .anchors import resolve_pin_positions
from .models import RoutedSegment, RoutingPreference, WireRouting
from .trunk_branch import minimize_crossings, route_net_trunk_branch


class RoutingStrategy(Protocol):
    """Interface for topology-specific routing strategies."""

    def route(
        self,
        graph: CircuitGraph,
        layout: SchematicLayout,
        preferences: RoutingPreference | None = None,
    ) -> WireRouting: ...


_STRATEGIES: dict[str, RoutingStrategy] = {}


def register_routing_strategy(topology: str, strategy: RoutingStrategy) -> None:
    """Register a routing strategy for a given topology name."""
    _STRATEGIES[topology] = strategy


def generate_routing(
    graph: CircuitGraph,
    layout: SchematicLayout,
    preferences: RoutingPreference | None = None,
) -> WireRouting:
    """Main entry point. Dispatches to topology-specific strategy or falls back to generic."""
    strategy = _STRATEGIES.get(graph.topology)
    if strategy is None:
        return _generic_route(graph, layout, preferences)
    return strategy.route(graph, layout, preferences)


def _generic_route(
    graph: CircuitGraph,
    layout: SchematicLayout,
    preferences: RoutingPreference | None = None,
) -> WireRouting:
    """Generic routing fallback using trunk/branch for all nets.

    This wraps the existing routing logic pattern: resolve pin positions,
    then route each net independently using trunk-and-branch strategy.
    """
    prefs = preferences or RoutingPreference()
    pin_pos = resolve_pin_positions(graph, layout)

    per_net_segments: list[list[RoutedSegment]] = []
    all_junctions = []
    seg_counter = 1

    for net in graph.nets:
        pins = [pin_pos[p] for p in net.pins if p in pin_pos]
        if len(pins) < 2:
            continue

        segs, juncs = route_net_trunk_branch(
            net.id, pins, net.role, seg_counter,
        )
        per_net_segments.append(segs)
        all_junctions.extend(juncs)
        seg_counter += len(segs) + 1

    # Post-processing: crossing minimization
    if prefs.minimize_crossings:
        per_net_segments = minimize_crossings(per_net_segments)

    all_segments: list[RoutedSegment] = []
    for segs in per_net_segments:
        all_segments.extend(segs)

    return WireRouting(
        topology=graph.topology,
        segments=all_segments,
        junctions=all_junctions,
        metadata={"strategy": "generic_trunk_branch"},
    )
