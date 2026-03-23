"""Auto-layout utilities for generated topologies.

Assigns positions to components based on topology flow:
- Main path:    horizontal, x spacing ~160 px
- Branch items: vertical,   y spacing ~140 px
- Source on left, load on right

PSIM-compatible layout uses 50px pin spacing with proper direction fields.
"""

from __future__ import annotations

from psim_mcp.data.component_library import get_port_pin_groups

X_SPACING = 160
Y_SPACING = 140
START_X = 40
START_Y = 120

# PSIM grid constants
PIN_SPACING = 50
MAIN_Y = 100
GND_Y = 150


def _flatten_points(*points: tuple[int, int]) -> list[int]:
    ports: list[int] = []
    for x, y in points:
        ports.extend([x, y])
    return ports


def _build_component(
    comp_id: str,
    comp_type: str,
    position: dict[str, int],
    direction: int,
    port_points: list[tuple[int, int]],
    parameters: dict | None = None,
    position2: dict[str, int] | None = None,
) -> dict:
    expected_terminals = len(get_port_pin_groups(comp_type))
    if expected_terminals and len(port_points) != expected_terminals:
        raise ValueError(
            f"{comp_type} expects {expected_terminals} terminals, got {len(port_points)}"
        )

    comp = {
        "id": comp_id,
        "type": comp_type,
        "parameters": parameters or {},
        "position": position,
        "direction": direction,
        "ports": _flatten_points(*port_points),
    }
    if position2 is not None:
        comp["position2"] = position2
    return comp


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


# ---------------------------------------------------------------------------
# PSIM component factory helpers (DRY: eliminates duplication across generators)
# ---------------------------------------------------------------------------


def make_vdc(comp_id: str, x: int, y: int, voltage: float) -> dict:
    """VDC source: positive at (x,y), negative at (x, y+50)."""
    return _build_component(
        comp_id,
        "DC_Source",
        {"x": x, "y": y},
        0,
        [(x, y), (x, y + 50)],
        parameters={"voltage": voltage},
    )


def make_vac(comp_id: str, x: int, y: int, voltage: float, frequency: float = 60.0) -> dict:
    """VAC source: positive at (x,y), negative at (x, y+50)."""
    return _build_component(
        comp_id,
        "AC_Source",
        {"x": x, "y": y},
        0,
        [(x, y), (x, y + 50)],
        parameters={"voltage": voltage, "frequency": frequency},
    )


def make_ground(comp_id: str, x: int, y: int) -> dict:
    """Ground symbol at (x,y)."""
    return _build_component(comp_id, "Ground", {"x": x, "y": y}, 0, [(x, y)])


def make_mosfet_h(comp_id: str, x: int, y: int, **params) -> dict:
    """Horizontal MOSFET (DIR=270): drain(x,y) source(x+50,y) gate(x+30,y+20)."""
    return _build_component(
        comp_id, "MOSFET", {"x": x, "y": y}, 270, [(x, y), (x + 50, y), (x + 30, y + 20)], parameters=params
    )


def make_mosfet_v(comp_id: str, x: int, y: int, **params) -> dict:
    """Vertical MOSFET (DIR=0): drain(x,y) source(x,y+50) gate(x-20,y+30)."""
    return _build_component(
        comp_id, "MOSFET", {"x": x, "y": y}, 0, [(x, y), (x, y + 50), (x - 20, y + 30)], parameters=params
    )


def make_igbt_v(comp_id: str, x: int, y: int, **params) -> dict:
    """Vertical IGBT (DIR=0): collector(x,y) emitter(x,y+50) gate(x-20,y+30)."""
    return _build_component(
        comp_id, "IGBT", {"x": x, "y": y}, 0, [(x, y), (x, y + 50), (x - 20, y + 30)], parameters=params
    )


def make_thyristor_v(comp_id: str, x: int, y: int, **params) -> dict:
    """Vertical thyristor (DIR=0): anode(x,y) cathode(x,y+50) gate(x-20,y+30)."""
    return _build_component(
        comp_id, "Thyristor", {"x": x, "y": y}, 0, [(x, y), (x, y + 50), (x - 20, y + 30)], parameters=params
    )


def make_induction_motor(comp_id: str, x: int, y: int, **params) -> dict:
    """Induction motor: phase_a(x,y) phase_b(x,y+50) phase_c(x,y+100)."""
    return _build_component(
        comp_id, "Induction_Motor", {"x": x, "y": y}, 0,
        [(x, y), (x, y + 50), (x, y + 100)], parameters=params
    )


def make_pmsm(comp_id: str, x: int, y: int, **params) -> dict:
    """PMSM motor: phase_a(x,y) phase_b(x,y+50) phase_c(x,y+100)."""
    return _build_component(
        comp_id, "PMSM", {"x": x, "y": y}, 0,
        [(x, y), (x, y + 50), (x, y + 100)], parameters=params
    )


def make_bldc_motor(comp_id: str, x: int, y: int, **params) -> dict:
    """BLDC motor: phase_a(x,y) phase_b(x,y+50) phase_c(x,y+100)."""
    return _build_component(
        comp_id, "BLDC_Motor", {"x": x, "y": y}, 0,
        [(x, y), (x, y + 50), (x, y + 100)], parameters=params
    )


def make_diode_h(comp_id: str, x: int, y: int, **params) -> dict:
    """Horizontal diode (DIR=0): anode(x,y) cathode(x+50,y)."""
    return _build_component(comp_id, "Diode", {"x": x, "y": y}, 0, [(x, y), (x + 50, y)], parameters=params)


def make_diode_v(comp_id: str, x: int, y: int, **params) -> dict:
    """Vertical diode (DIR=270): anode(x,y) cathode(x, y-50). Cathode UP."""
    return _build_component(comp_id, "Diode", {"x": x, "y": y}, 270, [(x, y), (x, y - 50)], parameters=params)


def make_inductor(comp_id: str, x: int, y: int, inductance: float, current_flag: int = 0) -> dict:
    """Horizontal inductor: pin1(x,y) pin2(x+50,y)."""
    params: dict = {"inductance": round(inductance, 9)}
    if current_flag:
        params["CurrentFlag"] = current_flag
    return _build_component(
        comp_id,
        "Inductor",
        {"x": x, "y": y},
        0,
        [(x, y), (x + 50, y)],
        parameters=params,
        position2={"x": x + 50, "y": y},
    )


def make_capacitor(comp_id: str, x: int, y: int, capacitance: float) -> dict:
    """Vertical capacitor: positive(x,y) negative(x, y+50)."""
    return _build_component(
        comp_id,
        "Capacitor",
        {"x": x, "y": y},
        90,
        [(x, y), (x, y + 50)],
        parameters={"capacitance": round(capacitance, 9)},
        position2={"x": x, "y": y + 50},
    )


def make_capacitor_h(comp_id: str, x: int, y: int, capacitance: float) -> dict:
    """Horizontal capacitor: pin1(x,y) pin2(x+50,y).

    Reference: converted_ResonantLLC Cs PORTS=[660,170, 710,170] DIR=0.
    """
    return _build_component(
        comp_id,
        "Capacitor",
        {"x": x, "y": y},
        0,
        [(x, y), (x + 50, y)],
        parameters={"capacitance": round(capacitance, 9)},
        position2={"x": x + 50, "y": y},
    )


def make_resistor(comp_id: str, x: int, y: int, resistance: float, voltage_flag: int = 0) -> dict:
    """Vertical resistor: pin1(x,y) pin2(x, y+50)."""
    params: dict = {"resistance": round(resistance, 4)}
    if voltage_flag:
        params["VoltageFlag"] = voltage_flag
    return _build_component(
        comp_id,
        "Resistor",
        {"x": x, "y": y},
        90,
        [(x, y), (x, y + 50)],
        parameters=params,
        position2={"x": x, "y": y + 50},
    )


def make_gating(comp_id: str, x: int, y: int, fsw: float, duty_degrees: str) -> dict:
    """PWM gating block at (x,y)."""
    return _build_component(
        comp_id,
        "PWM_Generator",
        {"x": x, "y": y},
        0,
        [(x, y)],
        parameters={
            "Frequency": fsw,
            "NoOfPoints": 2,
            "Switching_Points": duty_degrees,
        },
    )


def make_transformer(
    comp_id: str,
    p1x: int, p1y: int, p2x: int, p2y: int,
    s1x: int, s1y: int, s2x: int, s2y: int,
    **params,
) -> dict:
    """Transformer (TF_1F_1): primary(p1,p2) secondary(s1,s2).

    PORTS layout verified against PSIM reference
    (converted_Flyback_converter_with_peak_current_mode_control.py):

        PORTS = [pri1_x, pri1_y, pri2_x, pri2_y, sec1_x, sec1_y, sec2_x, sec2_y]

        pri1 (primary top)     sec2 (secondary top)
              |    ~~~~             |
        pri2 (primary bottom)  sec1 (secondary bottom)

    Standard call pattern (DIR=0, vertical orientation)::

        make_transformer(id, px, top_y, px, bot_y, sx, bot_y, sx, top_y)

    where ``sx = px + 50`` (PIN_SPACING) and ``bot_y = top_y + 50``.
    """
    return _build_component(
        comp_id,
        "Transformer",
        {"x": p1x, "y": p1y},
        0,
        [(p1x, p1y), (p2x, p2y), (s1x, s1y), (s2x, s2y)],
        parameters=params,
    )


def make_ideal_transformer(
    comp_id: str,
    p1x: int, p1y: int, p2x: int, p2y: int,
    s1x: int, s1y: int, s2x: int, s2y: int,
    **params,
) -> dict:
    """Ideal transformer (TF_IDEAL): primary(p1,p2) secondary(s1,s2).

    Reference: converted_ResonantLLC PORTS=[860,170, 860,220, 910,170, 910,220] DIR=0
    Pin order: primary1(top), primary2(bot), secondary1(top), secondary2(bot)
    """
    return _build_component(
        comp_id,
        "IdealTransformer",
        {"x": p1x, "y": p1y},
        0,
        [(p1x, p1y), (p2x, p2y), (s1x, s1y), (s2x, s2y)],
        parameters=params,
    )


def make_inductor_v(comp_id: str, x: int, y: int, inductance: float, current_flag: int = 0) -> dict:
    """Vertical inductor: pin1(x,y) pin2(x, y+50)."""
    params: dict = {"inductance": round(inductance, 9)}
    if current_flag:
        params["CurrentFlag"] = current_flag
    return _build_component(
        comp_id,
        "Inductor",
        {"x": x, "y": y},
        90,
        [(x, y), (x, y + 50)],
        parameters=params,
        position2={"x": x, "y": y + 50},
    )


def make_diode_bridge(comp_id: str, x: int, y: int, **params) -> dict:
    """Diode bridge rectifier (BDIODE1).

    Reference: converted_ResonantLLC BDIODE1 PORTS=[940,170, 940,230, 1020,170, 1020,230]
    Ports: ac+(x,y), ac-(x,y+60), dc+(x+80,y), dc-(x+80,y+60).
    """
    return _build_component(
        comp_id,
        "DiodeBridge",
        {"x": x, "y": y},
        0,
        [(x, y), (x, y + 60), (x + 80, y), (x + 80, y + 60)],
        parameters=params,
    )
