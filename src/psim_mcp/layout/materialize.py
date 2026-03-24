"""Materialize CircuitGraph + SchematicLayout to legacy component/net format.

The output format matches generators/buck.py generate() output exactly,
so the existing SVG renderer, routing, and bridge pipeline work unchanged.
"""

from __future__ import annotations

from psim_mcp.layout.models import SchematicLayout
from psim_mcp.synthesis.graph import CircuitGraph

# Port calculation rules per component type + direction.
# Each entry maps (type, direction) -> callable(x, y) -> ports list.
# These mirror the logic in generators/layout.py make_* helpers.

_PIN_SPACING = 50


def _ports_dc_source(x: int, y: int, direction: int) -> list[int]:
    """VDC: positive(x,y) negative(x,y+50), direction=0."""
    return [x, y, x, y + _PIN_SPACING]


def _ports_ground(x: int, y: int, direction: int) -> list[int]:
    """Ground: single pin at (x,y)."""
    return [x, y]


def _ports_mosfet(x: int, y: int, direction: int) -> list[int]:
    """MOSFET ports depend on direction."""
    if direction == 270:
        # Horizontal: drain(x,y) source(x+50,y) gate(x+30,y+20)
        return [x, y, x + 50, y, x + 30, y + 20]
    # Vertical (direction=0): drain(x,y) source(x,y+50) gate(x-20,y+30)
    return [x, y, x, y + 50, x - 20, y + 30]


def _ports_pwm_generator(x: int, y: int, direction: int) -> list[int]:
    """PWM gating block: output at (x,y)."""
    return [x, y]


def _ports_diode(x: int, y: int, direction: int) -> list[int]:
    """Diode ports depend on direction."""
    if direction == 270:
        # anode(x,y) cathode(x,y-50) — cathode UP
        return [x, y, x, y - 50]
    if direction == 0:
        # Horizontal: anode(x,y) cathode(x+50,y)
        return [x, y, x + 50, y]
    # direction 90
    return [x, y, x, y + 50]


def _ports_inductor(x: int, y: int, direction: int) -> list[int]:
    """Inductor (2-pin passive)."""
    if direction == 0:
        return [x, y, x + _PIN_SPACING, y]
    # direction 90
    return [x, y, x, y + _PIN_SPACING]


def _ports_capacitor(x: int, y: int, direction: int) -> list[int]:
    """Capacitor (2-pin passive)."""
    if direction == 90:
        return [x, y, x, y + _PIN_SPACING]
    # direction 0
    return [x, y, x + _PIN_SPACING, y]


def _ports_resistor(x: int, y: int, direction: int) -> list[int]:
    """Resistor (2-pin passive)."""
    if direction == 90:
        return [x, y, x, y + _PIN_SPACING]
    # direction 0
    return [x, y, x + _PIN_SPACING, y]


def _ports_ac_source(x: int, y: int, direction: int) -> list[int]:
    """VAC: positive(x,y) negative(x,y+50), direction=0."""
    return [x, y, x, y + _PIN_SPACING]


def _ports_igbt(x: int, y: int, direction: int) -> list[int]:
    """IGBT: collector(x,y) emitter(x,y+50) gate(x-20,y+30)."""
    return [x, y, x, y + 50, x - 20, y + 30]


def _ports_transformer(x: int, y: int, direction: int) -> list[int]:
    """Transformer: pri1(x,y) pri2(x,y+50) sec1(x+50,y+50) sec2(x+50,y)."""
    sx = x + _PIN_SPACING
    by = y + _PIN_SPACING
    return [x, y, x, by, sx, by, sx, y]


def _ports_ideal_transformer(x: int, y: int, direction: int) -> list[int]:
    """IdealTransformer: pri1(x,y) pri2(x,y+50) sec1(x+50,y) sec2(x+50,y+50)."""
    sx = x + _PIN_SPACING
    by = y + _PIN_SPACING
    return [x, y, x, by, sx, y, sx, by]


def _ports_diode_bridge(x: int, y: int, direction: int) -> list[int]:
    """DiodeBridge: ac+(x,y) ac-(x,y+60) dc+(x+80,y) dc-(x+80,y+60)."""
    return [x, y, x, y + 60, x + 80, y, x + 80, y + 60]


_PORT_CALCULATORS: dict[str, object] = {
    "DC_Source": _ports_dc_source,
    "AC_Source": _ports_ac_source,
    "Ground": _ports_ground,
    "MOSFET": _ports_mosfet,
    "IGBT": _ports_igbt,
    "PWM_Generator": _ports_pwm_generator,
    "Diode": _ports_diode,
    "Inductor": _ports_inductor,
    "Capacitor": _ports_capacitor,
    "Resistor": _ports_resistor,
    "Transformer": _ports_transformer,
    "IdealTransformer": _ports_ideal_transformer,
    "DiodeBridge": _ports_diode_bridge,
}

# Two-pin passives that need position2
_TWO_PIN_PASSIVES = {"Inductor", "Capacitor", "Resistor"}


def _calculate_position2(comp_type: str, x: int, y: int, direction: int) -> dict[str, int] | None:
    """Calculate position2 for two-pin passives."""
    if comp_type not in _TWO_PIN_PASSIVES:
        return None
    if direction == 0:
        return {"x": x + _PIN_SPACING, "y": y}
    if direction == 90:
        return {"x": x, "y": y + _PIN_SPACING}
    return None


def materialize_to_legacy(
    graph: CircuitGraph,
    layout: SchematicLayout,
) -> tuple[list[dict], list[dict]]:
    """Convert graph + layout into legacy component dicts and net dicts.

    Returns (components_list, nets_list) matching the format produced by
    generators/buck.py generate().
    """
    components: list[dict] = []

    for gc in graph.components:
        lc = layout.get_component(gc.id)
        if lc is None:
            continue

        x, y, direction = lc.x, lc.y, lc.direction

        port_fn = _PORT_CALCULATORS.get(gc.type)
        if port_fn is not None:
            ports = port_fn(x, y, direction)
        else:
            # Fallback: single port at position
            ports = [x, y]

        comp_dict: dict = {
            "id": gc.id,
            "type": gc.type,
            "parameters": dict(gc.parameters),
            "position": {"x": x, "y": y},
            "direction": direction,
            "ports": ports,
        }

        position2 = _calculate_position2(gc.type, x, y, direction)
        if position2 is not None:
            comp_dict["position2"] = position2

        components.append(comp_dict)

    # Convert graph nets to legacy format
    nets: list[dict] = []
    for gn in graph.nets:
        nets.append({
            "name": gn.id,
            "pins": list(gn.pins),
        })

    return components, nets
