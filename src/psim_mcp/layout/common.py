"""Shared layout utilities and constants."""

# PSIM grid
PIN_SPACING = 50


def position2_for_horizontal(x: int, y: int) -> dict[str, int]:
    """position2 for horizontal 2-pin passives (Inductor)."""
    return {"x": x + PIN_SPACING, "y": y}


def position2_for_vertical(x: int, y: int) -> dict[str, int]:
    """position2 for vertical 2-pin passives (Capacitor, Resistor)."""
    return {"x": x, "y": y + PIN_SPACING}
