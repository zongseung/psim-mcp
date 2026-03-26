"""Synthesis pipeline helpers for circuit design.

Contains graph-based synthesis, layout, and routing logic extracted from
``circuit_design_service.py`` to reduce that module's size.  All public names
here are re-exported from ``circuit_design_service`` so existing imports do
not need to change.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from psim_mcp.data.capability_matrix import is_supported as _capability_is_supported
from psim_mcp.data.layout_strategy_registry import get_layout_strategy as _get_layout_strategy
from psim_mcp.data.routing_policy_registry import get_routing_policy as _get_routing_policy
from psim_mcp.data.topology_metadata import (
    get_bridge_constraints as _get_bridge_constraints,
    get_layout_family as _get_layout_family,
    get_required_blocks as _get_required_blocks,
    get_required_component_roles as _get_required_component_roles,
    get_required_net_roles as _get_required_net_roles,
    get_routing_family as _get_routing_family,
)
from psim_mcp.generators import get_generator

if TYPE_CHECKING:
    from psim_mcp.config import AppConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature flag: synthesis pipeline availability
# ---------------------------------------------------------------------------

try:
    from psim_mcp.synthesis.graph import CircuitGraph
    from psim_mcp.validators.graph import validate_graph
    from psim_mcp.layout.engine import generate_layout
    from psim_mcp.layout.materialize import materialize_to_legacy
    from psim_mcp.routing.engine import generate_routing
    from psim_mcp.routing.models import WireRouting as _WireRouting  # noqa: F401

    SYNTHESIS_PIPELINE_AVAILABLE = True
except ImportError:
    SYNTHESIS_PIPELINE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Payload kind / version constants
# ---------------------------------------------------------------------------

PREVIEW_PAYLOAD_KIND = "preview_payload"
PREVIEW_PAYLOAD_VERSION = "v1"
DESIGN_SESSION_KIND = "design_session"
DESIGN_SESSION_VERSION = "v2"


# ---------------------------------------------------------------------------
# Synthesis + layout + routing pipeline
# ---------------------------------------------------------------------------


def try_synthesize_and_layout(
    circuit_type: str,
    specs: dict | None,
    config: AppConfig | None = None,
) -> dict | None:
    """Graph -> layout -> routing -> legacy materialization.

    Returns a result dict with keys ``graph``, ``layout``, ``wire_routing``,
    ``components``, ``nets``, ``wire_segments``, or ``None`` on any failure.
    """
    if not SYNTHESIS_PIPELINE_AVAILABLE:
        return None
    if not specs:
        return None
    topology = circuit_type.lower()
    if not _capability_is_supported(topology, "synthesize"):
        return None
    if not _capability_is_supported(topology, "graph"):
        return None
    if config:
        graph_enabled = [t.lower() for t in config.psim_graph_enabled_topologies]
        if graph_enabled and topology not in graph_enabled:
            return None
    try:
        generator = get_generator(topology)
    except (KeyError, Exception):
        return None

    specs = dict(specs or {})
    if generator.missing_fields(specs):
        return None

    try:
        graph = generator.synthesize(specs)
    except (AttributeError, NotImplementedError):
        return None
    except Exception:
        return None

    try:
        issues = validate_graph(graph)
        if any(i.severity == "error" for i in issues):
            return None
    except Exception:
        return None

    graph_component_roles = {component.role for component in graph.components if component.role}
    graph_net_roles = {net.role for net in graph.nets if net.role}
    graph_block_ids = {block.id for block in graph.blocks}
    required_component_roles = set(_get_required_component_roles(topology))
    required_net_roles = set(_get_required_net_roles(topology))
    required_blocks = set(_get_required_blocks(topology))

    if required_component_roles and not required_component_roles.issubset(graph_component_roles):
        return None
    if required_net_roles and not required_net_roles.issubset(graph_net_roles):
        return None
    if required_blocks and not required_blocks.issubset(graph_block_ids):
        return None

    if not _capability_is_supported(topology, "layout"):
        return None
    if config:
        layout_enabled = [t.lower() for t in config.psim_layout_engine_enabled_topologies]
        if layout_enabled and topology not in layout_enabled:
            return None

    layout_preferences = dict(_get_layout_strategy(topology) or {})
    layout_family = _get_layout_family(topology)
    if layout_family:
        layout_preferences.setdefault("layout_family", layout_family)
    if required_blocks:
        layout_preferences.setdefault("required_blocks", sorted(required_blocks))

    try:
        layout = generate_layout(graph, preferences=layout_preferences or None)
    except (NotImplementedError, Exception):
        return None

    wire_routing = None
    routing_blocked = not _capability_is_supported(topology, "routing")
    if config:
        routing_enabled = [t.lower() for t in config.psim_routing_enabled_topologies]
        if routing_enabled and topology not in routing_enabled:
            routing_blocked = True

    if not routing_blocked:
        try:
            from psim_mcp.routing.models import RoutingPreference

            routing_policy = dict(_get_routing_policy(topology) or {})
            routing_family = _get_routing_family(topology)
            routing_preferences = RoutingPreference(
                use_ground_rail=routing_policy.get("ground_policy") in {"bottom_rail", "dual_rail"},
                minimize_crossings=routing_policy.get("crossing_policy") == "minimize",
                ground_rail_y=layout_preferences.get("ground_rail_y"),
            )
            wire_routing = generate_routing(graph, layout, routing_preferences)
            wire_routing.metadata.setdefault("routing_family", routing_family)
            wire_routing.metadata.setdefault("routing_policy", routing_policy)
        except Exception:
            pass  # routing failure is non-fatal

    try:
        legacy_components, legacy_nets = materialize_to_legacy(graph, layout)
    except Exception:
        return None

    wire_segments = wire_routing.to_legacy_segments() if wire_routing else []
    graph.metadata.setdefault("layout_family", layout_family)
    graph.metadata.setdefault("routing_family", _get_routing_family(topology))
    graph.metadata.setdefault("bridge_constraints", _get_bridge_constraints(topology))
    layout.metadata.setdefault("layout_family", layout_family)
    layout.metadata.setdefault("layout_strategy", layout_preferences)

    return {
        "graph": graph,
        "layout": layout,
        "wire_routing": wire_routing,
        "components": legacy_components,
        "nets": legacy_nets,
        "wire_segments": wire_segments,
    }


# ---------------------------------------------------------------------------
# Payload normalizers
# ---------------------------------------------------------------------------


def normalize_preview_payload(preview: dict) -> dict:
    """Ensure preview payload has expected keys regardless of version."""
    preview.setdefault("payload_kind", PREVIEW_PAYLOAD_KIND)
    preview.setdefault("payload_version", PREVIEW_PAYLOAD_VERSION)
    preview.setdefault("connections", [])
    preview.setdefault("nets", [])
    preview.setdefault("simulation_settings", None)
    preview.setdefault("wire_segments", [])
    return preview


def normalize_design_session_payload(session: dict) -> dict:
    """Ensure design session payload is readable across v1/v2 formats."""
    session.setdefault("type", DESIGN_SESSION_KIND)
    session.setdefault("payload_kind", DESIGN_SESSION_KIND)
    session.setdefault("payload_version", "v1")
    session.setdefault("specs", {})
    session.setdefault("missing_fields", [])
    return session


def load_graph_layout_routing(preview: dict) -> tuple:
    """Extract graph, layout, routing from preview data if present.

    Reconstructs typed objects from serialized dicts when possible.
    Returns (graph_or_None, layout_or_None, routing_or_None).
    """
    graph_data = preview.get("graph")
    layout_data = preview.get("layout")
    routing_data = preview.get("wire_routing")

    graph = None
    layout = None
    routing = None

    if graph_data is not None and SYNTHESIS_PIPELINE_AVAILABLE:
        try:
            graph = (
                CircuitGraph.from_dict(graph_data) if isinstance(graph_data, dict) else graph_data
            )
        except Exception:
            pass

    if layout_data is not None:
        try:
            from psim_mcp.layout.models import SchematicLayout

            layout = (
                SchematicLayout.from_dict(layout_data)
                if isinstance(layout_data, dict)
                else layout_data
            )
        except Exception:
            pass

    if routing_data is not None:
        try:
            from psim_mcp.routing.models import WireRouting as WR

            routing = (
                WR.from_dict(routing_data) if isinstance(routing_data, dict) else routing_data
            )
        except Exception:
            pass

    return graph, layout, routing


def make_design_session_payload(
    topology: str,
    specs: dict,
    missing_fields: list[str],
) -> dict:
    """Build a design session payload for the state store."""
    return {
        "type": DESIGN_SESSION_KIND,
        "payload_kind": DESIGN_SESSION_KIND,
        "payload_version": DESIGN_SESSION_VERSION,
        "topology": topology,
        "specs": specs,
        "missing_fields": missing_fields,
    }
