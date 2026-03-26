"""Render and validation helpers for circuit design previews.

Extracted from ``circuit_design_service.py`` to reduce module size.
Re-exported from ``circuit_design_service`` so existing imports are unaffected.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from typing import Any

from psim_mcp.data.component_library import resolve_psim_element_type
from psim_mcp.shared.state_store import StateStore
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg, open_svg_in_browser
from psim_mcp.validators import validate_circuit as validate_circuit_spec

from psim_mcp.services._circuit_pipeline import PREVIEW_PAYLOAD_KIND, PREVIEW_PAYLOAD_VERSION

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def run_validation(
    components: list[dict],
    connections: list[dict],
    nets: list[dict],
) -> tuple[list[dict], bool]:
    """Validate circuit and return (issues, has_errors)."""
    validation_input = {
        "components": components,
        "connections": connections,
        "nets": nets,
    }
    result = validate_circuit_spec(validation_input)
    issues = [
        {
            "code": issue.code,
            "message": issue.message,
            "component_id": issue.component_id,
            "suggestion": issue.suggestion,
        }
        for issue in (result.errors + result.warnings)
    ]
    return issues, bool(result.errors)


def convert_nets_to_connections(nets: list[dict]) -> list[dict]:
    """Convert net-based wiring to point-to-point connections."""
    from psim_mcp.bridge.wiring import nets_to_connections

    return nets_to_connections(nets)


def nets_to_connections_simple(nets: list[dict]) -> list[dict]:
    """Convert net-based representation to point-to-point connections (simple)."""
    connections = []
    for net in nets:
        pins = net.get("pins", [])
        for i in range(len(pins) - 1):
            connections.append({"from": pins[i], "to": pins[i + 1]})
    return connections


def _generate_ports_from_position(comp_type: str, x: int, y: int, direction: int = 0) -> list[int]:
    """Generate PSIM PORTS list from a single position coordinate.

    When legacy generators only provide ``position: {x, y}`` instead of a
    full ``ports`` list, this function calculates pin coordinates using
    standard PSIM component dimensions.
    """
    # Standard PSIM component pin spacing
    _PIN_OFFSETS: dict[str, list[tuple[int, int]]] = {
        # 2-pin vertical (positive top, negative bottom)
        "DC_Source":  [(0, 0), (0, 50)],
        "AC_Source":  [(0, 0), (0, 50)],
        "Battery":    [(0, 0), (0, 50)],
        "Capacitor":  [(0, 0), (0, 50)],
        # 2-pin horizontal
        "Inductor":   [(0, 0), (50, 0)],
        "Resistor":   [(0, 0), (50, 0)],
        # 3-pin (drain/source vertical, gate offset)
        "MOSFET":    [(0, 0), (0, 50), (-20, 30)],
        "IGBT":      [(0, 0), (0, 50), (-20, 30)],
        "Thyristor": [(0, 0), (0, 50), (-20, 30)],
        # 2-pin vertical (anode top, cathode bottom)
        "Diode":         [(0, 0), (0, 50)],
        "Schottky_Diode": [(0, 0), (0, 50)],
        # 1-pin
        "Ground":        [(0, 0)],
        "Voltage_Probe": [(0, 0)],
        # PWM / Gating
        "PWM_Generator": [(0, 0)],
        "GATING":        [(0, 0)],
        # 4-pin bridge
        "DiodeBridge": [(0, 0), (0, 60), (80, 0), (80, 60)],
        # Transformers
        "Transformer":      [(0, 0), (0, 50), (80, 0), (80, 50)],
        "IdealTransformer": [(0, 0), (0, 50), (80, 0), (80, 50)],
        "Center_Tap_Transformer": [(0, 0), (0, 50), (0, 100), (80, 0), (80, 50), (80, 100)],
        # Motors (3-phase terminals)
        "Induction_Motor": [(0, 0), (0, 50), (0, 100)],
        "PMSM":            [(0, 0), (0, 50), (0, 100)],
        "BLDC_Motor":      [(0, 0), (0, 50), (0, 100)],
    }

    offsets = _PIN_OFFSETS.get(comp_type, [(0, 0)])
    ports: list[int] = []
    for dx, dy in offsets:
        ports.extend([x + dx, y + dy])
    return ports


def enrich_components_for_bridge(components: list[dict]) -> list[dict]:
    """Attach bridge-facing metadata expected by the real adapter.

    In addition to resolving the PSIM element type, this function generates
    a ``ports`` list for components that only have a ``position`` dict.
    Without ``ports``, the bridge cannot resolve pin positions for wiring.
    """
    enriched: list[dict] = []
    for component in components:
        item = dict(component)
        item_type = str(item.get("type", ""))
        item["psim_element_type"] = resolve_psim_element_type(item_type)

        # Generate ports from position if not already present
        if not item.get("ports"):
            pos = item.get("position", {})
            if isinstance(pos, dict) and ("x" in pos or "y" in pos):
                x = int(pos.get("x", 0))
                y = int(pos.get("y", 0))
                direction = int(item.get("direction", 0))
                item["ports"] = _generate_ports_from_position(item_type, x, y, direction)

        enriched.append(item)
    return enriched


# ---------------------------------------------------------------------------
# Render + store helper
# ---------------------------------------------------------------------------


def render_and_store(
    store: StateStore,
    circuit_type: str,
    components: list[dict],
    connections: list[dict],
    nets: list[dict],
    simulation_settings: dict | None = None,
    psim_template: dict | None = None,
    wire_segments: list[dict] | None = None,
    graph: object | None = None,
    layout: object | None = None,
    wire_routing: object | None = None,
) -> dict:
    """Render ASCII + SVG, open browser, save to store.

    Accepts optional graph/layout/routing from the synthesis pipeline
    so they can be persisted in the preview payload for confirm_circuit.
    """
    ascii_diagram = render_circuit_ascii(
        circuit_type=circuit_type,
        components=components,
        connections=connections,
    )

    svg_content = render_circuit_svg(
        circuit_type=circuit_type,
        components=components,
        connections=connections,
        nets=nets,
        wire_segments=wire_segments,
        layout=layout,
    )

    svg_dir = tempfile.gettempdir()
    # Use content hash to deduplicate identical previews.
    content_hash = hashlib.sha256(svg_content.encode()).hexdigest()[:8]
    svg_path = os.path.join(svg_dir, f"psim_preview_{circuit_type}_{content_hash}.svg")

    # Remove stale previews across ALL topologies before writing a new one so
    # that temp dir does not accumulate SVG files across design iterations.
    import glob as _glob

    all_previews = _glob.glob(os.path.join(svg_dir, "psim_preview_*.svg"))
    for stale in all_previews:
        if stale != svg_path:
            try:
                os.remove(stale)
            except OSError:
                pass

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    open_svg_in_browser(svg_path)

    store_data: dict[str, Any] = {
        "payload_kind": PREVIEW_PAYLOAD_KIND,
        "payload_version": PREVIEW_PAYLOAD_VERSION,
        "circuit_type": circuit_type,
        "components": components,
        "connections": connections,
        "nets": nets,
        "simulation_settings": simulation_settings,
        "svg_path": svg_path,
    }
    if psim_template:
        store_data["psim_template"] = psim_template
    if wire_segments:
        store_data["wire_segments"] = wire_segments
    if graph is not None:
        store_data["graph"] = graph.to_dict() if hasattr(graph, "to_dict") else graph
    if layout is not None:
        store_data["layout"] = layout.to_dict() if hasattr(layout, "to_dict") else layout
    if wire_routing is not None:
        serialized_routing = (
            wire_routing.to_dict() if hasattr(wire_routing, "to_dict") else wire_routing
        )
        store_data["wire_routing"] = serialized_routing
        store_data["routing"] = serialized_routing

    token = store.save(store_data)

    return {
        "ascii_diagram": ascii_diagram,
        "svg_path": svg_path,
        "preview_token": token,
    }
