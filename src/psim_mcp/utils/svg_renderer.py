"""SVG circuit diagram renderer for preview on any platform (Mac/Windows).

Components are drawn horizontally (left-pin → body → right-pin) to match
standard schematic conventions.  Connection wires use Manhattan routing
(horizontal + vertical segments only).
"""

from __future__ import annotations

from psim_mcp.data.component_library import LEFT_PINS, RIGHT_PINS, get_component, get_pin_side

# Component body width — all symbols are 60px wide with pins at x=0 and x=80
_BODY_W = 60
_TOTAL_W = 80  # pin-to-pin
_BODY_H = 30
_MID_Y = 15  # vertical centre of the body


# ---------------------------------------------------------------------------
# Component symbol helpers (horizontal orientation)
# ---------------------------------------------------------------------------

def _svg_resistor(x: int, y: int, comp_id: str, params: dict) -> str:
    val = params.get("resistance", "")
    label = f"{comp_id}  {val}Ω" if val else comp_id
    return (
        f'<g transform="translate({x},{y})">'
        # left lead
        f'<line x1="0" y1="{_MID_Y}" x2="10" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        # zigzag
        f'<polyline points="10,{_MID_Y} 15,5 25,25 35,5 45,25 55,5 60,{_MID_Y} 70,{_MID_Y}" '
        f'fill="none" stroke="#333" stroke-width="2"/>'
        # right lead
        f'<line x1="70" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        # pins
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        # label
        f'<text x="40" y="-4" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{label}</text>'
        f'</g>'
    )


def _svg_capacitor(x: int, y: int, comp_id: str, params: dict) -> str:
    val = params.get("capacitance", "")
    if isinstance(val, (int, float)):
        if val < 1e-9:
            label = f"{comp_id}  {val*1e12:.1f}pF"
        elif val < 1e-6:
            label = f"{comp_id}  {val*1e9:.1f}nF"
        elif val < 1e-3:
            label = f"{comp_id}  {val*1e6:.0f}μF"
        else:
            label = f"{comp_id}  {val*1e3:.0f}mF"
    else:
        label = f"{comp_id}  {val}F" if val else comp_id
    cx = 40
    return (
        f'<g transform="translate({x},{y})">'
        f'<line x1="0" y1="{_MID_Y}" x2="{cx-4}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<line x1="{cx-4}" y1="2" x2="{cx-4}" y2="28" stroke="#333" stroke-width="2.5"/>'
        f'<line x1="{cx+4}" y1="2" x2="{cx+4}" y2="28" stroke="#333" stroke-width="2.5"/>'
        f'<line x1="{cx+4}" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<text x="40" y="-4" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{label}</text>'
        f'</g>'
    )


def _svg_inductor(x: int, y: int, comp_id: str, params: dict) -> str:
    val = params.get("inductance", "")
    if isinstance(val, (int, float)):
        if val < 1e-9:
            label = f"{comp_id}  {val*1e12:.1f}pH"
        elif val < 1e-6:
            label = f"{comp_id}  {val*1e9:.1f}nH"
        elif val < 1e-3:
            label = f"{comp_id}  {val*1e6:.0f}μH"
        else:
            label = f"{comp_id}  {val*1e3:.0f}mH"
    else:
        label = f"{comp_id}  {val}H" if val else comp_id
    bumps = ""
    for i in range(4):
        sx = 12 + i * 14
        bumps += f'<path d="M {sx} {_MID_Y} A 7 7 0 0 1 {sx+14} {_MID_Y}" fill="none" stroke="#333" stroke-width="2"/>'
    return (
        f'<g transform="translate({x},{y})">'
        f'<line x1="0" y1="{_MID_Y}" x2="12" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'{bumps}'
        f'<line x1="68" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<text x="40" y="-4" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{label}</text>'
        f'</g>'
    )


def _svg_dc_source(x: int, y: int, comp_id: str, params: dict) -> str:
    val = params.get("voltage", "")
    label = f"{comp_id}  {val}V" if val else comp_id
    cx = 40
    return (
        f'<g transform="translate({x},{y})">'
        f'<line x1="0" y1="{_MID_Y}" x2="{cx-18}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="{cx}" cy="{_MID_Y}" r="18" fill="none" stroke="#333" stroke-width="2"/>'
        f'<text x="{cx-6}" y="{_MID_Y+1}" font-size="14" font-family="sans-serif" fill="#333">+</text>'
        f'<text x="{cx+3}" y="{_MID_Y+1}" font-size="14" font-family="sans-serif" fill="#333">−</text>'
        f'<line x1="{cx+18}" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<text x="40" y="-6" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{label}</text>'
        f'</g>'
    )


def _svg_mosfet(x: int, y: int, comp_id: str, params: dict) -> str:
    freq = params.get("switching_frequency", "")
    if isinstance(freq, (int, float)) and freq >= 1000:
        label = f"{comp_id}  {freq/1000:.0f}kHz"
    else:
        label = f"{comp_id}" if not freq else f"{comp_id}  {freq}Hz"
    return (
        f'<g transform="translate({x},{y})">'
        f'<line x1="0" y1="{_MID_Y}" x2="15" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<rect x="15" y="2" width="50" height="26" rx="3" fill="#e8f4fd" stroke="#333" stroke-width="2"/>'
        f'<text x="40" y="19" text-anchor="middle" font-size="9" font-family="sans-serif" fill="#333">MOS</text>'
        # gate tick
        f'<line x1="25" y1="28" x2="25" y2="35" stroke="#333" stroke-width="1.5"/>'
        f'<text x="20" y="44" font-size="8" font-family="sans-serif" fill="#666">G</text>'
        f'<line x1="65" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<text x="40" y="-4" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{label}</text>'
        f'</g>'
    )


def _svg_diode(x: int, y: int, comp_id: str, params: dict) -> str:
    val = params.get("forward_voltage", "")
    label = f"{comp_id}  {val}V" if val else comp_id
    return (
        f'<g transform="translate({x},{y})">'
        f'<line x1="0" y1="{_MID_Y}" x2="25" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        # triangle pointing right
        f'<polygon points="25,4 25,26 48,{_MID_Y}" fill="none" stroke="#333" stroke-width="2"/>'
        # bar
        f'<line x1="48" y1="4" x2="48" y2="26" stroke="#333" stroke-width="2.5"/>'
        f'<line x1="48" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<text x="40" y="-4" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{label}</text>'
        f'</g>'
    )


def _svg_generic(x: int, y: int, comp_id: str, comp_type: str, params: dict) -> str:
    return (
        f'<g transform="translate({x},{y})">'
        f'<line x1="0" y1="{_MID_Y}" x2="10" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<rect x="10" y="2" width="60" height="26" rx="3" fill="#f5f5f5" stroke="#333" stroke-width="2"/>'
        f'<text x="40" y="19" text-anchor="middle" font-size="9" font-family="sans-serif" fill="#333">{comp_type[:8]}</text>'
        f'<line x1="70" y1="{_MID_Y}" x2="{_TOTAL_W}" y2="{_MID_Y}" stroke="#333" stroke-width="2"/>'
        f'<circle cx="0" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<circle cx="{_TOTAL_W}" cy="{_MID_Y}" r="3" fill="#e74c3c"/>'
        f'<text x="40" y="-4" text-anchor="middle" font-size="11" font-family="sans-serif" fill="#333">{comp_id}</text>'
        f'</g>'
    )


_SYMBOL_MAP = {
    "Resistor": _svg_resistor,
    "Capacitor": _svg_capacitor,
    "Inductor": _svg_inductor,
    "DC_Source": _svg_dc_source,
    "MOSFET": _svg_mosfet,
    "Diode": _svg_diode,
}

_PIN_ANCHOR_MAP: dict[str, dict[str, tuple[int, int]]] = {
    "Resistor": {
        "pin1": (0, _MID_Y),
        "input": (0, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
        "output": (_TOTAL_W, _MID_Y),
    },
    "Inductor": {
        "pin1": (0, _MID_Y),
        "input": (0, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
        "output": (_TOTAL_W, _MID_Y),
    },
    "Capacitor": {
        "positive": (0, _MID_Y),
        "pin1": (0, _MID_Y),
        "negative": (_TOTAL_W, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
    },
    "DC_Source": {
        "positive": (0, _MID_Y),
        "pin1": (0, _MID_Y),
        "negative": (_TOTAL_W, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
    },
    "AC_Source": {
        "positive": (0, _MID_Y),
        "pin1": (0, _MID_Y),
        "negative": (_TOTAL_W, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
    },
    "Battery": {
        "positive": (0, _MID_Y),
        "pin1": (0, _MID_Y),
        "negative": (_TOTAL_W, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
    },
    "Diode": {
        "anode": (0, _MID_Y),
        "pin1": (0, _MID_Y),
        "cathode": (_TOTAL_W, _MID_Y),
        "pin2": (_TOTAL_W, _MID_Y),
    },
    "MOSFET": {
        "drain": (0, _MID_Y),
        "source": (_TOTAL_W, _MID_Y),
        "gate": (25, _BODY_H),
    },
    "IGBT": {
        "collector": (0, _MID_Y),
        "emitter": (_TOTAL_W, _MID_Y),
        "gate": (25, _BODY_H),
    },
    "Transformer": {
        "primary_in": (0, 8),
        "primary_out": (0, 22),
        "secondary_out": (_TOTAL_W, 8),
        "secondary_in": (_TOTAL_W, 22),
    },
    "Center_Tap_Transformer": {
        "primary_top": (0, 6),
        "primary_center": (0, _MID_Y),
        "primary_bottom": (0, 24),
        "secondary_top": (_TOTAL_W, 6),
        "secondary_center": (_TOTAL_W, _MID_Y),
        "secondary_bottom": (_TOTAL_W, 24),
    },
}


# ---------------------------------------------------------------------------
# Pin geometry
# ---------------------------------------------------------------------------

def _spread_positions(count: int, start: int, end: int) -> list[int]:
    """Return *count* evenly spread integer positions between *start* and *end*."""
    if count <= 0:
        return []
    if count == 1:
        return [round((start + end) / 2)]
    gap = (end - start) / (count + 1)
    return [round(start + gap * (i + 1)) for i in range(count)]


def _build_pin_positions(components: list[dict]) -> dict[str, tuple[int, int]]:
    """Build pin reference -> SVG coordinate map from component metadata."""
    pin_pos: dict[str, tuple[int, int]] = {}
    for comp in components:
        cid = comp.get("id", "")
        if not cid:
            continue
        comp_type = comp.get("type", "")
        pos = comp.get("position", {"x": 0, "y": 0})
        explicit_anchors = _PIN_ANCHOR_MAP.get(comp_type)
        if explicit_anchors:
            for pin_name, (dx, dy) in explicit_anchors.items():
                pin_pos[f"{cid}.{pin_name}"] = (pos["x"] + dx, pos["y"] + dy)
            continue

        lib_comp = get_component(comp_type)
        pins = list(lib_comp.get("pins", [])) if lib_comp else []

        if not pins:
            for pin in LEFT_PINS:
                pin_pos[f"{cid}.{pin}"] = (pos["x"], pos["y"] + _MID_Y)
            for pin in RIGHT_PINS:
                pin_pos[f"{cid}.{pin}"] = (pos["x"] + _TOTAL_W, pos["y"] + _MID_Y)
            continue

        left_pins = [pin for pin in pins if get_pin_side(pin) == "left"]
        right_pins = [pin for pin in pins if get_pin_side(pin) == "right"]
        center_pins = [pin for pin in pins if get_pin_side(pin) == "center"]

        left_ys = _spread_positions(len(left_pins), 4, _BODY_H - 4)
        right_ys = _spread_positions(len(right_pins), 4, _BODY_H - 4)

        for pin, y in zip(left_pins, left_ys):
            pin_pos[f"{cid}.{pin}"] = (pos["x"], pos["y"] + y)
        for pin, y in zip(right_pins, right_ys):
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + _TOTAL_W, pos["y"] + y)

        bottom_pins = [
            pin for pin in center_pins
            if pin in {"gate", "control", "ground", "thermal_in", "secondary_center"}
        ]
        top_pins = [pin for pin in center_pins if pin not in bottom_pins]

        top_xs = _spread_positions(len(top_pins), 12, _TOTAL_W - 12)
        bottom_xs = _spread_positions(len(bottom_pins), 12, _TOTAL_W - 12)

        for pin, x in zip(top_pins, top_xs):
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + x, pos["y"])
        for pin, x in zip(bottom_pins, bottom_xs):
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + x, pos["y"] + _BODY_H)

    return pin_pos


def _draw_segment(x1: int, y1: int, x2: int, y2: int) -> str:
    """Draw a straight or Manhattan-routed wire segment."""
    if x1 == x2 or y1 == y2:
        return (
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="#2980b9" stroke-width="2"/>'
        )
    mx = (x1 + x2) // 2
    return (
        f'<polyline points="{x1},{y1} {mx},{y1} {mx},{y2} {x2},{y2}" '
        f'fill="none" stroke="#2980b9" stroke-width="2"/>'
    )


# ---------------------------------------------------------------------------
# Manhattan-routed wires
# ---------------------------------------------------------------------------

def _render_connections(components: list[dict], connections: list[dict]) -> str:
    """Render point-to-point wires between component pins."""
    pin_pos = _build_pin_positions(components)

    lines = ""
    for conn in connections:
        p1 = pin_pos.get(conn.get("from", ""))
        p2 = pin_pos.get(conn.get("to", ""))
        if not p1 or not p2:
            continue

        x1, y1 = p1
        x2, y2 = p2

        if y1 == y2:
            # Straight horizontal
            lines += (
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                f'stroke="#2980b9" stroke-width="2"/>'
            )
        else:
            # Manhattan: horizontal to midpoint, then vertical, then horizontal
            mx = (x1 + x2) // 2
            lines += (
                f'<polyline points="{x1},{y1} {mx},{y1} {mx},{y2} {x2},{y2}" '
                f'fill="none" stroke="#2980b9" stroke-width="2"/>'
            )

    return lines


# ---------------------------------------------------------------------------
# Net-based wires and junction dots
# ---------------------------------------------------------------------------

def _render_nets(components: list[dict], nets: list[dict]) -> tuple[str, str]:
    """Render shared nets directly instead of flattening them into chains."""
    pin_pos = _build_pin_positions(components)
    lines = ""
    dots = ""
    for net in nets:
        refs = net.get("pins", net.get("connections", []))
        points = []
        seen = set()
        for ref in refs:
            point = pin_pos.get(ref)
            if point and point not in seen:
                seen.add(point)
                points.append(point)
        if len(points) < 2:
            continue
        if len(points) == 2:
            (x1, y1), (x2, y2) = points
            lines += _draw_segment(x1, y1, x2, y2)
            continue

        hub_x = round(sum(x for x, _ in points) / len(points))
        hub_y = round(sum(y for _, y in points) / len(points))
        for x, y in points:
            lines += _draw_segment(x, y, hub_x, hub_y)
        dots += f'<circle cx="{hub_x}" cy="{hub_y}" r="4" fill="#2980b9"/>'

    return lines, dots


def _render_junctions(components: list[dict], connections: list[dict]) -> str:
    """Draw junction dots where multiple wires share a pin."""
    pin_pos = _build_pin_positions(components)

    pos_count: dict[tuple[int, int], int] = {}
    for conn in connections:
        for key in ("from", "to"):
            p = pin_pos.get(conn.get(key, ""))
            if p:
                pos_count[p] = pos_count.get(p, 0) + 1

    dots = ""
    for (x, y), count in pos_count.items():
        if count >= 2:
            dots += f'<circle cx="{x}" cy="{y}" r="4" fill="#2980b9"/>'
    return dots


# ---------------------------------------------------------------------------
# GND symbol
# ---------------------------------------------------------------------------

def _render_gnd_symbols(components: list[dict]) -> str:
    """Draw GND symbols at negative pins of voltage sources."""
    gnd = ""
    for comp in components:
        if comp["type"] != "DC_Source":
            continue
        pos = comp.get("position", {"x": 0, "y": 0})
        # Right pin is negative for horizontal DC source
        gx = pos["x"] + _TOTAL_W
        gy = pos["y"] + _MID_Y
        gnd += (
            f'<g transform="translate({gx},{gy})">'
            f'<line x1="0" y1="0" x2="0" y2="12" stroke="#333" stroke-width="2"/>'
            f'<line x1="-10" y1="12" x2="10" y2="12" stroke="#333" stroke-width="2"/>'
            f'<line x1="-6" y1="16" x2="6" y2="16" stroke="#333" stroke-width="1.5"/>'
            f'<line x1="-3" y1="20" x2="3" y2="20" stroke="#333" stroke-width="1"/>'
            f'</g>'
        )
    return gnd


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_circuit_svg(
    circuit_type: str,
    components: list[dict],
    connections: list[dict],
    nets: list[dict] | None = None,
    title: str | None = None,
) -> str:
    """Render a circuit diagram as an SVG string."""
    # Canvas size from component positions
    max_x = max((c.get("position", {}).get("x", 0) for c in components), default=0) + _TOTAL_W + 80
    max_y = max((c.get("position", {}).get("y", 0) for c in components), default=0) + 80
    width = max(max_x, 500)
    height = max(max_y, 250)

    display_title = title or f"{circuit_type.upper()} Converter — Preview"

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" '
        f'style="background:#fafafa; border:1px solid #ddd; border-radius:8px;">'
    )

    # Title
    parts.append(
        f'<text x="{width//2}" y="25" text-anchor="middle" font-size="16" '
        f'font-weight="bold" font-family="sans-serif" fill="#2c3e50">{display_title}</text>'
    )

    if nets:
        net_lines, net_dots = _render_nets(components, nets)
        parts.append(net_lines)
        parts.append(net_dots)
    else:
        # Wires (behind components)
        parts.append(_render_connections(components, connections))

        # Junction dots
        parts.append(_render_junctions(components, connections))

    # Components
    for comp in components:
        cid = comp.get("id", "?")
        ctype = comp.get("type", "Unknown")
        params = comp.get("parameters", {})
        pos = comp.get("position", {"x": 0, "y": 0})
        renderer = _SYMBOL_MAP.get(ctype, lambda x, y, i, p: _svg_generic(x, y, i, ctype, p))
        parts.append(renderer(pos["x"], pos["y"], cid, params))

    # GND symbols
    parts.append(_render_gnd_symbols(components))

    # Legend
    legend_y = height - 15
    parts.append(
        f'<text x="10" y="{legend_y}" font-size="10" font-family="sans-serif" fill="#999">'
        f'Components: {len(components)} | Connections: {len(connections)} | '
        f'Preview — confirm to generate .psimsch</text>'
    )

    parts.append('</svg>')
    return "\n".join(parts)


def open_svg_in_browser(svg_path: str) -> None:
    """Attempt to open an SVG file in the default browser.

    This is a best-effort operation — failures are silently ignored
    since the user can always open the file manually.
    """
    import os
    import platform
    import subprocess

    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", svg_path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            os.startfile(svg_path)
        elif system == "Linux":
            subprocess.Popen(["xdg-open", svg_path],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
