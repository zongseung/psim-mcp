"""Auto-layout utilities for generated topologies.

Assigns positions to components based on topology flow:
- Main path:    horizontal, x spacing ~160 px
- Branch items: vertical,   y spacing ~140 px
- Source on left, load on right

PSIM-compatible layout uses 50px pin spacing with proper direction fields.
"""

from __future__ import annotations

X_SPACING = 160
Y_SPACING = 140
START_X = 40
START_Y = 120

# PSIM grid constants
PIN_SPACING = 50
MAIN_Y = 100
GND_Y = 150


def auto_layout(
    main_path: list[str],
    branches: dict[str, list[str]] | None = None,
) -> dict[str, dict[str, int]]:
    """Return ``{component_id: {"x": ..., "y": ...}}`` for every component.

    Parameters
    ----------
    main_path:
        Ordered list of component IDs that form the main horizontal path
        (source -> switch -> inductor -> load, etc.).
    branches:
        Mapping from a main-path component ID to a list of IDs that branch
        vertically below it.  Example: ``{"SW1": ["D1"]}``
    """
    branches = branches or {}
    positions: dict[str, dict[str, int]] = {}

    for idx, comp_id in enumerate(main_path):
        positions[comp_id] = {"x": START_X + idx * X_SPACING, "y": START_Y}

    for parent_id, children in branches.items():
        parent_pos = positions.get(parent_id)
        if parent_pos is None:
            continue
        for child_idx, child_id in enumerate(children):
            positions[child_id] = {
                "x": parent_pos["x"],
                "y": parent_pos["y"] + (child_idx + 1) * Y_SPACING,
            }

    return positions


# ---------------------------------------------------------------------------
# PSIM-compatible component type classification
# ---------------------------------------------------------------------------

# 2-pin passives that need position2
TWO_PIN_PASSIVES = {"Inductor", "Resistor", "Capacitor"}

# Components placed horizontally on main path (direction=0 for passives)
HORIZONTAL_PASSIVES = {"Inductor"}

# Components placed vertically (direction=90 for passives)
VERTICAL_PASSIVES = {"Capacitor", "Resistor"}

# Semiconductor switches with drain/source/gate
MOSFET_TYPES = {"MOSFET", "IGBT"}

# Diodes
DIODE_TYPES = {"Diode", "Schottky_Diode", "Zener_Diode"}

# Sources (vertical, direction=0)
SOURCE_TYPES = {"DC_Source", "AC_Source", "DC_Current_Source", "AC_Current_Source"}
