"""SVG circuit diagram renderer for preview on any platform (Mac/Windows).

Components are drawn horizontally (left-pin → body → right-pin) to match
standard schematic conventions.  Connection wires use Manhattan routing
(horizontal + vertical segments only).
"""

from __future__ import annotations

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
    if isinstance(val, float) and val < 1e-3:
        label = f"{comp_id}  {val*1e6:.0f}μF"
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
    if isinstance(val, float) and val < 1e-3:
        label = f"{comp_id}  {val*1e6:.0f}μH"
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


# ---------------------------------------------------------------------------
# Manhattan-routed wires
# ---------------------------------------------------------------------------

def _render_connections(components: list[dict], connections: list[dict]) -> str:
    """Render Manhattan-routed wires between component pins.

    Pin convention (horizontal components):
      - positive / drain / input / anode   → left pin  (x, y+15)
      - negative / source / output / cathode → right pin (x+80, y+15)
    """
    LEFT_PINS = {"positive", "drain", "input", "anode"}
    RIGHT_PINS = {"negative", "source", "output", "cathode"}

    pin_pos: dict[str, tuple[int, int]] = {}
    for comp in components:
        cid = comp["id"]
        pos = comp.get("position", {"x": 0, "y": 0})
        lx, ly = pos["x"], pos["y"] + _MID_Y
        rx, ry = pos["x"] + _TOTAL_W, pos["y"] + _MID_Y
        for pin in LEFT_PINS:
            pin_pos[f"{cid}.{pin}"] = (lx, ly)
        for pin in RIGHT_PINS:
            pin_pos[f"{cid}.{pin}"] = (rx, ry)

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
# Junction dots (where 3+ wires meet)
# ---------------------------------------------------------------------------

def _render_junctions(components: list[dict], connections: list[dict]) -> str:
    """Draw junction dots where multiple wires share a pin."""
    LEFT_PINS = {"positive", "drain", "input", "anode"}
    RIGHT_PINS = {"negative", "source", "output", "cathode"}

    pin_pos: dict[str, tuple[int, int]] = {}
    for comp in components:
        cid = comp["id"]
        pos = comp.get("position", {"x": 0, "y": 0})
        lx, ly = pos["x"], pos["y"] + _MID_Y
        rx, ry = pos["x"] + _TOTAL_W, pos["y"] + _MID_Y
        for pin in LEFT_PINS:
            pin_pos[f"{cid}.{pin}"] = (lx, ly)
        for pin in RIGHT_PINS:
            pin_pos[f"{cid}.{pin}"] = (rx, ry)

    # Count how many connections each position has
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

    # Wires (behind components)
    parts.append(_render_connections(components, connections))

    # Junction dots
    parts.append(_render_junctions(components, connections))

    # Components
    for comp in components:
        cid = comp["id"]
        ctype = comp["type"]
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
