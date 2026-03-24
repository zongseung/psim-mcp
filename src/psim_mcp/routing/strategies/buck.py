"""Buck converter routing strategy -- ground rail + trunk/branch."""

from __future__ import annotations

from psim_mcp.layout.models import SchematicLayout
from psim_mcp.routing.anchors import resolve_pin_positions
from psim_mcp.routing.models import RoutedSegment, RoutingPreference, WireRouting
from psim_mcp.routing.trunk_branch import route_net_trunk_branch
from psim_mcp.synthesis.graph import CircuitGraph

# Net layer classification for buck topology
_NET_LAYERS: dict[str, str] = {
    "ground": "ground",
    "input_positive": "power",
    "output_positive": "power",
    "switch_node": "power",
    "drive_signal": "control",
}


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

        all_segments: list[RoutedSegment] = []
        all_junctions = []
        seg_counter = 1

        for net in graph.nets:
            pins = [pin_pos[p] for p in net.pins if p in pin_pos]
            if len(pins) < 2:
                continue

            segs, juncs = route_net_trunk_branch(
                net.id, pins, net.role, seg_counter,
            )

            # Tag layer metadata
            layer = _NET_LAYERS.get(net.role or "", None)
            for seg in segs:
                seg.layer = layer

            all_segments.extend(segs)
            all_junctions.extend(juncs)
            seg_counter += len(segs) + 1

        return WireRouting(
            topology="buck",
            segments=all_segments,
            junctions=all_junctions,
            metadata={
                "strategy": "buck_trunk_branch",
                "ground_rail_y": prefs.ground_rail_y or 150,
            },
        )
