"""Wire plan generation for PSIM bridge.

Converts net-based circuit representation to concrete wire segments
that the PSIM bridge can execute. This module handles:
- Net -> wire segment conversion
- Manhattan routing coordinate calculation
- Pin position resolution

Note: Actual PSIM API calls are in bridge_script.py.
      This module only prepares the wire plan.
"""

from __future__ import annotations


def nets_to_wire_plan(nets: list[dict], component_positions: dict) -> list[dict]:
    """Convert net definitions to executable wire segments.

    Args:
        nets: List of net dicts with 'name' and 'pins' keys.
        component_positions: Dict mapping component_id to position dict.

    Returns:
        List of wire segment dicts:
        [{"net": "VIN", "from": "V1.positive", "to": "SW1.drain",
          "coords": {"x1": ..., "y1": ..., "x2": ..., "y2": ...}}]

    Note:
        Actual coordinate calculation depends on PSIM element placement,
        which can only be verified on Windows. This function provides
        the structural conversion; coordinates may need adjustment.
    """
    wire_plan = []
    for net in nets:
        pins = net.get("pins", [])
        name = net.get("name", "unnamed")
        # Chain connection: pin[0]->pin[1], pin[1]->pin[2], ...
        for i in range(len(pins) - 1):
            wire_plan.append({
                "net": name,
                "from": pins[i],
                "to": pins[i + 1],
                "coords": None,  # To be calculated with actual PSIM positions
            })
    return wire_plan


def resolve_pin_position(component_id: str, pin_name: str,
                          component_positions: dict) -> tuple[int, int] | None:
    """Resolve the absolute position of a component pin.

    Args:
        component_id: ID of the component (e.g., "V1").
        pin_name: Name of the pin (e.g., "positive").
        component_positions: Dict mapping component_id to {"x": int, "y": int}.

    Returns:
        (x, y) tuple or None if component not found.

    Note:
        Pin offsets relative to component position depend on PSIM's
        internal element geometry. These offsets must be determined
        from "Save as Python Code" analysis on Windows.
    """
    pos = component_positions.get(component_id)
    if pos is None:
        return None
    # Placeholder: return component center position
    # Real offsets need PSIM geometry data from Windows testing
    return (pos.get("x", 0), pos.get("y", 0))
