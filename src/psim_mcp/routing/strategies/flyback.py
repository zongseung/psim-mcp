"""Flyback converter routing strategy -- isolated primary/secondary routing."""

from __future__ import annotations

from psim_mcp.data.routing_policy_registry import get_routing_policy
from psim_mcp.layout.models import SchematicLayout
from psim_mcp.routing.anchors import resolve_pin_positions
from psim_mcp.routing.models import RoutedSegment, RoutingPreference, WireRouting
from psim_mcp.routing.trunk_branch import minimize_crossings, route_net_trunk_branch
from psim_mcp.synthesis.graph import CircuitGraph


class FlybackRoutingStrategy:
    """Routing strategy for flyback converter topology.

    Handles primary and secondary ground rails separately,
    and uses trunk/branch for multi-pin nets.
    """

    def route(
        self,
        graph: CircuitGraph,
        layout: SchematicLayout,
        preferences: RoutingPreference | None = None,
    ) -> WireRouting:
        prefs = preferences or RoutingPreference()
        pin_pos = resolve_pin_positions(graph, layout)
        routing_policy = get_routing_policy("flyback") or {}
        net_layers = routing_policy.get("net_layers", {})

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

            layer = net_layers.get(net.role or "", None)
            for seg in segs:
                seg.layer = layer

            per_net_segments.append(segs)
            all_junctions.extend(juncs)
            seg_counter += len(segs) + 1

        if prefs.minimize_crossings:
            per_net_segments = minimize_crossings(per_net_segments)

        all_segments: list[RoutedSegment] = []
        for segs in per_net_segments:
            all_segments.extend(segs)

        return WireRouting(
            topology="flyback",
            segments=all_segments,
            junctions=all_junctions,
            metadata={
                "strategy": "flyback_trunk_branch",
                "primary_ground_y": 230,
                "isolation_boundary_x": 250,
                "routing_policy": routing_policy,
            },
        )
