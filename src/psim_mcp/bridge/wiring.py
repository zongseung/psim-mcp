"""Wire plan generation for PSIM bridge.

Converts net-based circuit representation to concrete wire segments.
"""
from __future__ import annotations

from psim_mcp.data.component_library import LEFT_PINS as _LEFT_PINS, RIGHT_PINS as _RIGHT_PINS

# Pin position offsets relative to component position.
# For horizontal layout: left pins at (0, 15), right pins at (80, 15)
_TOTAL_W = 80
_MID_Y = 15


def nets_to_wire_plan(nets: list[dict], component_positions: dict) -> list[dict]:
    """Convert net definitions to executable wire segments.

    Args:
        nets: List of {"name": str, "pins": [str]} dicts.
        component_positions: {"V1": {"x": 100, "y": 200}, ...}

    Returns:
        List of wire segment dicts with coordinates.
    """
    wire_plan = []
    for net in nets:
        pins = net.get("pins", [])
        name = net.get("name", "unnamed")
        # Chain: connect pin[0]→pin[1], pin[1]→pin[2], ...
        for i in range(len(pins) - 1):
            from_pin = pins[i]
            to_pin = pins[i + 1]
            from_pos = resolve_pin_position(from_pin, component_positions)
            to_pos = resolve_pin_position(to_pin, component_positions)
            wire_plan.append({
                "net": name,
                "from": from_pin,
                "to": to_pin,
                "from_pos": from_pos,
                "to_pos": to_pos,
            })
    return wire_plan


def resolve_pin_position(pin_ref: str, component_positions: dict) -> tuple[int, int] | None:
    """Resolve 'V1.positive' to absolute (x, y) coordinates.

    Args:
        pin_ref: "ComponentID.pin_name" format.
        component_positions: {"V1": {"x": 100, "y": 200}, ...}
    """
    parts = pin_ref.split(".", 1)
    if len(parts) != 2:
        return None
    comp_id, pin_name = parts
    pos = component_positions.get(comp_id)
    if pos is None:
        return None

    cx = pos.get("x", 0)
    cy = pos.get("y", 0)

    if pin_name in _LEFT_PINS:
        return (cx, cy + _MID_Y)
    elif pin_name in _RIGHT_PINS:
        return (cx + _TOTAL_W, cy + _MID_Y)
    else:
        # Unknown pin — place at component center
        return (cx + _TOTAL_W // 2, cy + _MID_Y)


def nets_to_connections(nets: list[dict]) -> list[dict]:
    """Convert nets to legacy point-to-point connections format.

    This is used for backward compatibility with adapters that
    still expect {"from": ..., "to": ...} connections.
    """
    connections = []
    for net in nets:
        pins = net.get("pins", [])
        for i in range(len(pins) - 1):
            connections.append({"from": pins[i], "to": pins[i + 1]})
    return connections
