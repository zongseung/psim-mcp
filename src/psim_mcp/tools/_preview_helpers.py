"""Shared helpers for circuit preview rendering and storage.

Consolidates the render-ASCII / render-SVG / save-SVG / open-browser /
save-to-preview-store pipeline that was duplicated across circuit.py
and design.py.
"""

from __future__ import annotations

import glob as _glob
import hashlib
import os
import tempfile
from dataclasses import dataclass

from psim_mcp.services.preview_store import get_preview_store
from psim_mcp.utils.ascii_renderer import render_circuit_ascii
from psim_mcp.utils.svg_renderer import render_circuit_svg, open_svg_in_browser
from psim_mcp.validators import validate_circuit


@dataclass
class ValidationSummary:
    """Lightweight container for serialized validation issues."""

    issues: list[dict]
    has_errors: bool


def run_validation(
    components: list[dict],
    connections: list[dict],
    nets: list[dict],
) -> ValidationSummary:
    """Validate a circuit and return serialized issues."""
    validation_input = {
        "components": components,
        "connections": connections,
        "nets": nets,
    }
    result = validate_circuit(validation_input)
    issues = [
        {
            "code": issue.code,
            "message": issue.message,
            "component_id": issue.component_id,
            "suggestion": issue.suggestion,
        }
        for issue in (result.errors + result.warnings)
    ]
    return ValidationSummary(issues=issues, has_errors=bool(result.errors))


def render_and_store_preview(
    circuit_type: str,
    components: list[dict],
    connections: list[dict],
    nets: list[dict],
    simulation_settings: dict | None = None,
) -> dict:
    """Render ASCII + SVG, open browser, save to preview store.

    Returns a dict with keys: ascii_diagram, svg_path, preview_token.
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
    )

    svg_dir = tempfile.gettempdir()
    content_hash = hashlib.sha256(svg_content.encode()).hexdigest()[:8]
    svg_path = os.path.join(svg_dir, f"psim_preview_{circuit_type}_{content_hash}.svg")

    # Remove stale previews across ALL topologies to prevent accumulation.
    for stale in _glob.glob(os.path.join(svg_dir, "psim_preview_*.svg")):
        if stale != svg_path:
            try:
                os.remove(stale)
            except OSError:
                pass

    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    open_svg_in_browser(svg_path)

    store = get_preview_store()
    token = store.save({
        "circuit_type": circuit_type,
        "components": components,
        "connections": connections,
        "nets": nets,
        "simulation_settings": simulation_settings,
        "svg_path": svg_path,
    })

    return {
        "ascii_diagram": ascii_diagram,
        "svg_path": svg_path,
        "preview_token": token,
    }


def convert_nets_to_connections(nets: list[dict]) -> list[dict]:
    """Convert net-based wiring to point-to-point connections."""
    from psim_mcp.bridge.wiring import nets_to_connections
    return nets_to_connections(nets)
