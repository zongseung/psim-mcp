"""Shared routing helpers and models."""

from .models import (
    JunctionPoint,
    RoutedSegment,
    RoutingPreference,
    WireRouting,
    WireSegment,
)
from .router import (
    build_pin_position_map,
    nets_to_connection_pairs,
    normalize_wire_segments,
    prepare_components_for_layout,
    resolve_wire_segments,
    route_connections_to_segments,
    route_nets_to_segments,
    segments_to_junctions,
)

# Register topology-specific routing strategies
from .engine import register_routing_strategy
from .strategies.buck import BuckRoutingStrategy
from .strategies.flyback import FlybackRoutingStrategy
from .strategies.llc import LlcRoutingStrategy

register_routing_strategy("buck", BuckRoutingStrategy())
register_routing_strategy("flyback", FlybackRoutingStrategy())
register_routing_strategy("llc", LlcRoutingStrategy())

__all__ = [
    "JunctionPoint",
    "RoutedSegment",
    "RoutingPreference",
    "WireRouting",
    "WireSegment",
    "build_pin_position_map",
    "nets_to_connection_pairs",
    "normalize_wire_segments",
    "prepare_components_for_layout",
    "resolve_wire_segments",
    "route_connections_to_segments",
    "route_nets_to_segments",
    "segments_to_junctions",
]
