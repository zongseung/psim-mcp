"""Symbol registry -- component symbol variants, pin anchors, bounding boxes.

Centralises the scattered pin anchor data that currently lives in
``routing/router.py`` (_PIN_ANCHOR_MAP) and ``routing/anchors.py``
(_ANCHOR_OFFSETS) into a single queryable registry.  Downstream code
can look up symbol variants and pin positions without importing layout
or routing internals.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Symbol variants
# Each variant captures the component type, canonical orientation (direction),
# approximate bounding box (x, y, width, height), and named pin offsets
# relative to the component origin.
# ---------------------------------------------------------------------------

SYMBOL_VARIANTS: dict[str, dict] = {
    # Sources
    "dc_source_vertical": {
        "component_type": "DC_Source",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 50),
        "pins": {"positive": (0, 0), "negative": (0, 50)},
    },
    "ac_source_vertical": {
        "component_type": "AC_Source",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 50),
        "pins": {"positive": (0, 0), "negative": (0, 50)},
    },
    # Switches
    "mosfet_horizontal": {
        "component_type": "MOSFET",
        "orientation": 270,
        "bounding_box": (0, 0, 50, 20),
        "pins": {"drain": (0, 0), "source": (50, 0), "gate": (30, 20)},
    },
    "mosfet_vertical": {
        "component_type": "MOSFET",
        "orientation": 0,
        "bounding_box": (0, 0, 20, 50),
        "pins": {"drain": (0, 0), "source": (0, 50), "gate": (-20, 30)},
    },
    # Diodes
    "diode_horizontal": {
        "component_type": "Diode",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 10),
        "pins": {"anode": (0, 0), "cathode": (50, 0)},
    },
    "diode_vertical_cathode_up": {
        "component_type": "Diode",
        "orientation": 270,
        "bounding_box": (0, -50, 10, 50),
        "pins": {"anode": (0, 0), "cathode": (0, -50)},
    },
    # Passives
    "inductor_horizontal": {
        "component_type": "Inductor",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 10),
        "pins": {"pin1": (0, 0), "pin2": (50, 0)},
    },
    "inductor_vertical": {
        "component_type": "Inductor",
        "orientation": 90,
        "bounding_box": (0, 0, 10, 50),
        "pins": {"pin1": (0, 0), "pin2": (0, 50)},
    },
    "capacitor_vertical": {
        "component_type": "Capacitor",
        "orientation": 90,
        "bounding_box": (0, 0, 10, 50),
        "pins": {"positive": (0, 0), "negative": (0, 50)},
    },
    "capacitor_horizontal": {
        "component_type": "Capacitor",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 10),
        "pins": {"positive": (0, 0), "negative": (50, 0)},
    },
    "resistor_vertical": {
        "component_type": "Resistor",
        "orientation": 90,
        "bounding_box": (0, 0, 10, 50),
        "pins": {"pin1": (0, 0), "pin2": (0, 50)},
    },
    # Transformers
    "transformer_vertical": {
        "component_type": "Transformer",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 50),
        "pins": {
            "primary1": (0, 0), "primary2": (0, 50),
            "secondary1": (50, 50), "secondary2": (50, 0),
        },
    },
    "ideal_transformer": {
        "component_type": "IdealTransformer",
        "orientation": 0,
        "bounding_box": (0, 0, 50, 50),
        "pins": {
            "primary1": (0, 0), "primary2": (0, 50),
            "secondary1": (50, 0), "secondary2": (50, 50),
        },
    },
    # Rectifiers
    "diode_bridge": {
        "component_type": "DiodeBridge",
        "orientation": 0,
        "bounding_box": (0, 0, 80, 60),
        "pins": {
            "ac_pos": (0, 0), "ac_neg": (0, 60),
            "dc_pos": (80, 0), "dc_neg": (80, 60),
        },
    },
    # Control
    "pwm_block": {
        "component_type": "PWM_Generator",
        "orientation": 0,
        "bounding_box": (0, 0, 30, 20),
        "pins": {"output": (0, 0)},
    },
    # Special
    "ground": {
        "component_type": "Ground",
        "orientation": 0,
        "bounding_box": (0, 0, 10, 10),
        "pins": {"pin1": (0, 0)},
    },
}


# ---------------------------------------------------------------------------
# Pin anchor map -- canonical pin offsets per component type.
# Combines data from routing/router.py _PIN_ANCHOR_MAP (DIR=0 base)
# and routing/anchors.py _ANCHOR_OFFSETS (per-direction overrides).
# ---------------------------------------------------------------------------

_BODY_W = 60
_TOTAL_W = 80
_MID_Y = 15

PIN_ANCHOR_MAP: dict[str, dict[str, tuple[int, int]]] = {
    "DC_Source": {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
    "AC_Source": {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
    "Ground": {"pin1": (0, 0)},
    "MOSFET": {
        "drain": (0, 0), "source": (0, 50), "gate": (-20, 30),
    },
    "Diode": {
        "anode": (0, 0), "pin1": (0, 0),
        "cathode": (50, 0), "pin2": (50, 0),
    },
    "Inductor": {
        "pin1": (0, 0), "input": (0, 0),
        "pin2": (50, 0), "output": (50, 0),
    },
    "Capacitor": {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
    "Resistor": {
        "pin1": (0, 0), "input": (0, 0),
        "pin2": (0, 50), "output": (0, 50),
    },
    "PWM_Generator": {"output": (0, 0)},
    "Transformer": {
        "primary1": (0, 0), "primary_in": (0, 0),
        "primary2": (0, 50), "primary_out": (0, 50),
        "secondary1": (50, 50), "secondary_in": (50, 50),
        "secondary2": (50, 0), "secondary_out": (50, 0),
    },
    "IdealTransformer": {
        "primary1": (0, 0), "primary_in": (0, 0),
        "primary2": (0, 50), "primary_out": (0, 50),
        "secondary1": (50, 0), "secondary_in": (50, 0),
        "secondary2": (50, 50), "secondary_out": (50, 50),
    },
    "DiodeBridge": {
        "ac_pos": (0, 0), "ac_neg": (0, 60),
        "dc_pos": (80, 0), "dc_neg": (80, 60),
    },
    "IGBT": {
        "collector": (0, 0), "emitter": (0, 50), "gate": (-20, 30),
    },
    "Battery": {
        "positive": (0, 0), "pin1": (0, 0),
        "negative": (0, 50), "pin2": (0, 50),
    },
}

# Per-direction overrides -- key is (component_type, direction).
PIN_ANCHOR_MAP_BY_DIRECTION: dict[tuple[str, int], dict[str, tuple[int, int]]] = {
    ("MOSFET", 270): {"drain": (0, 0), "source": (50, 0), "gate": (30, 20)},
    ("MOSFET", 0): {"drain": (0, 0), "source": (0, 50), "gate": (-20, 30)},
    ("Diode", 0): {"anode": (0, 0), "cathode": (50, 0)},
    ("Diode", 270): {"anode": (0, 0), "cathode": (0, -50)},
    ("Inductor", 0): {"pin1": (0, 0), "pin2": (50, 0)},
    ("Inductor", 90): {"pin1": (0, 0), "pin2": (0, 50)},
    ("Capacitor", 90): {"positive": (0, 0), "negative": (0, 50)},
    ("Capacitor", 0): {"positive": (0, 0), "negative": (50, 0)},
    ("Resistor", 90): {"pin1": (0, 0), "pin2": (0, 50)},
}


def get_symbol_variant(variant_name: str) -> dict | None:
    """Return symbol variant metadata by name, or None if unknown."""
    return SYMBOL_VARIANTS.get(variant_name)


def get_pin_anchors(component_type: str) -> dict[str, tuple[int, int]]:
    """Return default pin anchor offsets for *component_type*.

    Returns an empty dict if the component type is not registered.
    """
    return dict(PIN_ANCHOR_MAP.get(component_type, {}))


def get_pin_anchors_for_direction(
    component_type: str, direction: int,
) -> dict[str, tuple[int, int]]:
    """Return pin anchors for a specific (type, direction) pair.

    Falls back to direction=0 defaults if the specific direction is not
    registered.
    """
    overrides = PIN_ANCHOR_MAP_BY_DIRECTION.get((component_type, direction))
    if overrides is not None:
        return dict(overrides)
    return get_pin_anchors(component_type)


def get_symbol(component_type: str) -> dict | None:
    """Return consolidated symbol metadata for *component_type*.

    Searches SYMBOL_VARIANTS for all variants matching the component type
    and returns a summary dict with variants list, default variant, bounding
    box, and pin anchors.  Returns None if no variant is found.
    """
    variants = []
    default_variant = None
    for vname, vdata in SYMBOL_VARIANTS.items():
        if vdata["component_type"] == component_type:
            variants.append(vname)
            if default_variant is None:
                default_variant = vname

    if not variants:
        return None

    # Use the first variant's bounding box as the default
    first = SYMBOL_VARIANTS[variants[0]]
    return {
        "variants": variants,
        "default_variant": default_variant,
        "bounding_box": {
            "x": first["bounding_box"][0],
            "y": first["bounding_box"][1],
            "width": first["bounding_box"][2],
            "height": first["bounding_box"][3],
        },
        "default_orientation": first.get("orientation", 0),
        "pin_anchors": get_pin_anchors(component_type),
    }


def get_bounding_box(component_type: str) -> dict:
    """Return bounding box dict for *component_type*.

    Returns a default 80x30 box if not found.
    """
    info = get_symbol(component_type)
    if info:
        return info["bounding_box"]
    return {"x": 0, "y": 0, "width": _TOTAL_W, "height": _MID_Y * 2}
