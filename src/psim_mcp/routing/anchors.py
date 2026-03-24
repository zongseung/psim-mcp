"""Pin anchor resolution -- maps component pins to absolute coordinates.

Uses layout positions and component type pin definitions to determine
where each pin physically sits on the schematic.

The offsets here are derived from ``generators/layout.py`` factory helpers
which define the canonical port positions for each component type and
orientation (direction).
"""

from __future__ import annotations

from psim_mcp.layout.models import SchematicLayout
from psim_mcp.synthesis.graph import CircuitGraph

PIN_SPACING = 50

# ---------------------------------------------------------------------------
# Pin anchor offsets by (component_type, direction) -> {pin_name: (dx, dy)}
#
# These are derived from the layout.py factory helpers:
#   make_vdc:           positive(x,y), negative(x, y+50)  DIR=0
#   make_ground:        pin1(x,y)                          DIR=0
#   make_mosfet_h:      drain(x,y), source(x+50,y), gate(x+30,y+20)  DIR=270
#   make_mosfet_v:      drain(x,y), source(x,y+50), gate(x-20,y+30)  DIR=0
#   make_diode_h:       anode(x,y), cathode(x+50,y)       DIR=0
#   make_diode_v:       anode(x,y), cathode(x,y-50)       DIR=270
#   make_inductor:      pin1(x,y), pin2(x+50,y)           DIR=0
#   make_inductor_v:    pin1(x,y), pin2(x,y+50)           DIR=90
#   make_capacitor:     positive(x,y), negative(x,y+50)   DIR=90
#   make_capacitor_h:   positive(x,y), negative(x+50,y)   DIR=0
#   make_resistor:      pin1(x,y), pin2(x,y+50)           DIR=90
#   make_gating:        output(x,y)                        DIR=0
#   make_transformer:   primary1(p1x,p1y), primary2(p2x,p2y),
#                       secondary1(s1x,s1y), secondary2(s2x,s2y)  DIR=0
#   make_ideal_transformer: same layout                    DIR=0
#   make_diode_bridge:  ac_pos(x,y), ac_neg(x,y+60),
#                       dc_pos(x+80,y), dc_neg(x+80,y+60) DIR=0
# ---------------------------------------------------------------------------

# Key: (component_type, direction)
# Value: {pin_name: (dx, dy)} where dx,dy are offsets from component position
_ANCHOR_OFFSETS: dict[tuple[str, int], dict[str, tuple[int, int]]] = {
    # DC Source (make_vdc): DIR=0
    ("DC_Source", 0): {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
    # AC Source (make_vac): DIR=0
    ("AC_Source", 0): {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
    # Ground: DIR=0
    ("Ground", 0): {"pin1": (0, 0)},
    # MOSFET horizontal (make_mosfet_h): DIR=270
    ("MOSFET", 270): {
        "drain": (0, 0), "source": (50, 0), "gate": (30, 20),
    },
    # MOSFET vertical (make_mosfet_v): DIR=0
    ("MOSFET", 0): {
        "drain": (0, 0), "source": (0, 50), "gate": (-20, 30),
    },
    # PWM Generator: DIR=0
    ("PWM_Generator", 0): {"output": (0, 0)},
    # Diode horizontal (make_diode_h): DIR=0
    ("Diode", 0): {
        "anode": (0, 0), "pin1": (0, 0),
        "cathode": (50, 0), "pin2": (50, 0),
    },
    # Diode vertical cathode up (make_diode_v): DIR=270
    ("Diode", 270): {
        "anode": (0, 0), "pin1": (0, 0),
        "cathode": (0, -50), "pin2": (0, -50),
    },
    # Inductor horizontal (make_inductor): DIR=0
    ("Inductor", 0): {
        "pin1": (0, 0), "input": (0, 0),
        "pin2": (50, 0), "output": (50, 0),
    },
    # Inductor vertical (make_inductor_v): DIR=90
    ("Inductor", 90): {
        "pin1": (0, 0), "input": (0, 0),
        "pin2": (0, 50), "output": (0, 50),
    },
    # Capacitor vertical (make_capacitor): DIR=90
    ("Capacitor", 90): {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
    # Capacitor horizontal (make_capacitor_h): DIR=0
    ("Capacitor", 0): {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (50, 0), "pin2": (50, 0),
    },
    # Resistor vertical (make_resistor): DIR=90
    ("Resistor", 90): {
        "pin1": (0, 0), "input": (0, 0),
        "pin2": (0, 50), "output": (0, 50),
    },
    # Transformer (make_transformer): DIR=0
    # Ports: primary1(p1x,p1y) primary2(p2x,p2y) secondary1(s1x,s1y) secondary2(s2x,s2y)
    # Standard pattern: pri1(x,y) pri2(x,y+50) sec1(x+50,y+50) sec2(x+50,y)
    ("Transformer", 0): {
        "primary1": (0, 0), "primary_in": (0, 0),
        "primary2": (0, 50), "primary_out": (0, 50),
        "secondary1": (50, 50), "secondary_in": (50, 50),
        "secondary2": (50, 0), "secondary_out": (50, 0),
    },
    # IdealTransformer (make_ideal_transformer): DIR=0
    # Standard pattern: p1(x,y) p2(x,y+50) s1(x+50,y) s2(x+50,y+50)
    ("IdealTransformer", 0): {
        "primary1": (0, 0), "primary_in": (0, 0),
        "primary2": (0, 50), "primary_out": (0, 50),
        "secondary1": (50, 0), "secondary_in": (50, 0),
        "secondary2": (50, 50), "secondary_out": (50, 50),
    },
    # DiodeBridge (make_diode_bridge): DIR=0
    # Ports: ac+(x,y) ac-(x,y+60) dc+(x+80,y) dc-(x+80,y+60)
    ("DiodeBridge", 0): {
        "ac_pos": (0, 0),
        "ac_neg": (0, 60),
        "dc_pos": (80, 0),
        "dc_neg": (80, 60),
    },
}


def resolve_pin_positions(
    graph: CircuitGraph,
    layout: SchematicLayout,
) -> dict[str, tuple[int, int]]:
    """Resolve absolute pin positions from graph + layout.

    Returns: {"component_id.pin_name": (abs_x, abs_y), ...}
    """
    layout_map = {lc.id: lc for lc in layout.components}
    pin_positions: dict[str, tuple[int, int]] = {}

    for gc in graph.components:
        lc = layout_map.get(gc.id)
        if lc is None:
            continue

        offsets = _ANCHOR_OFFSETS.get((gc.type, lc.direction))
        if offsets is None:
            # Try direction=0 as fallback
            offsets = _ANCHOR_OFFSETS.get((gc.type, 0), {})

        for pin_name, (dx, dy) in offsets.items():
            pin_positions[f"{gc.id}.{pin_name}"] = (lc.x + dx, lc.y + dy)

    return pin_positions
