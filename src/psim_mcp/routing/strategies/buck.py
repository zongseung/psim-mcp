"""Buck converter routing strategy -- ground rail + trunk/branch."""

from __future__ import annotations

from psim_mcp.data.routing_policy_registry import get_routing_policy
from psim_mcp.layout.models import SchematicLayout
from psim_mcp.routing.anchors import resolve_pin_positions
from psim_mcp.routing.models import RoutedSegment, RoutingPreference, WireRouting
from psim_mcp.routing.trunk_branch import minimize_crossings, route_net_trunk_branch
from psim_mcp.synthesis.graph import CircuitGraph


class BuckRoutingStrategy:
    """Routing strategy for buck converter topology.

    Uses horizontal trunk for ground rail and output nets,
    vertical trunk for switch node, and direct routing for gate signals.
    """

    def route(
        self,
        graph: CircuitGraph,
        layout: SchematicLayout,
        preferences: RoutingPreference | None = None,
    ) -> WireRouting:
        prefs = preferences or RoutingPreference()
        pin_pos = resolve_pin_positions(graph, layout)
        routing_policy = get_routing_policy("buck") or {}
        net_layers = routing_policy.get("net_layers", {})

        # Pre-compute per-net pin positions for collision avoidance.
        net_pin_positions: dict[str, list[tuple[int, int]]] = {}
        all_pin_positions: set[tuple[int, int]] = set()
        for net in graph.nets:
            pins = [pin_pos[p] for p in net.pins if p in pin_pos]
            net_pin_positions[net.id] = pins
            all_pin_positions.update(pins)

        per_net_segments: list[list[RoutedSegment]] = []
        all_junctions = []
        seg_counter = 1

        for net in graph.nets:
            pins = net_pin_positions.get(net.id, [])
            if len(pins) < 2:
                continue

            avoid = all_pin_positions - set(pins)
            segs, juncs = route_net_trunk_branch(
                net.id, pins, net.role, seg_counter, avoid,
            )

            # Tag layer metadata
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
            topology="buck",
            segments=all_segments,
            junctions=all_junctions,
            metadata={
                "strategy": "buck_trunk_branch",
                "ground_rail_y": prefs.ground_rail_y or 150,
                "routing_policy": routing_policy,
            },
        )
