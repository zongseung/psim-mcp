"""SVG circuit diagram renderer for preview on any platform."""

from __future__ import annotations

from psim_mcp.data.component_library import (
    LEFT_PINS,
    RIGHT_PINS,
    build_port_pin_map,
    get_component,
    get_pin_side,
)
from psim_mcp.data.symbol_registry import (
    get_bounding_box,
    get_pin_anchors,
    get_symbol,
)

_BODY_W = 60
_TOTAL_W = 80
_BODY_H = 30
_MID_Y = 15


def _format_value(params: dict, key: str, unit: str) -> str:
    val = params.get(key, "")
    if not val:
        return ""
    if isinstance(val, (int, float)):
        if key in {"inductance", "capacitance"} and val < 1e-3:
            if val < 1e-9:
                return f"{val * 1e12:.1f}p{unit}"
            if val < 1e-6:
                return f"{val * 1e9:.1f}n{unit}"
            return f"{val * 1e6:.1f}u{unit}"
        if key == "switching_frequency" and val >= 1000:
            return f"{val / 1000:.0f}kHz"
        if float(val).is_integer():
            return f"{int(val)}{unit}"
    return f"{val}{unit}"


def _label(comp_id: str, params: dict, key: str | None = None, unit: str = "") -> str:
    if key is None:
        return comp_id
    value = _format_value(params, key, unit)
    return f"{comp_id}  {value}" if value else comp_id


def _line(x1: int, y1: int, x2: int, y2: int, color: str = "#333", width: float = 2) -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'


def _polyline(points: list[tuple[int, int]], color: str = "#333", width: float = 2) -> str:
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"/>'


def _pin_dot(x: int, y: int) -> str:
    return f'<circle cx="{x}" cy="{y}" r="3" fill="#e74c3c"/>'


def _text(x: int, y: int, content: str, anchor: str = "middle", size: int = 11, color: str = "#333") -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'font-size="{size}" font-family="sans-serif" fill="{color}">{content}</text>'
    )


def _svg_resistor(x: int, y: int, comp_id: str, params: dict) -> str:
    label = _label(comp_id, params, "resistance", "Ohm")
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 10, _MID_Y)}'
        f'<polyline points="10,{_MID_Y} 15,5 25,25 35,5 45,25 55,5 60,{_MID_Y} 70,{_MID_Y}" '
        f'fill="none" stroke="#333" stroke-width="2"/>'
        f'{_line(70, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -4, label)}'
        f'</g>'
    )


def _svg_capacitor(x: int, y: int, comp_id: str, params: dict) -> str:
    label = _label(comp_id, params, "capacitance", "F")
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 36, _MID_Y)}'
        f'{_line(36, 2, 36, 28, width=2.5)}'
        f'{_line(44, 2, 44, 28, width=2.5)}'
        f'{_line(44, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -4, label)}'
        f'</g>'
    )


def _svg_inductor(x: int, y: int, comp_id: str, params: dict) -> str:
    label = _label(comp_id, params, "inductance", "H")
    bumps = "".join(
        f'<path d="M {12 + i * 14} {_MID_Y} A 7 7 0 0 1 {26 + i * 14} {_MID_Y}" fill="none" stroke="#333" stroke-width="2"/>'
        for i in range(4)
    )
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 12, _MID_Y)}{bumps}{_line(68, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -4, label)}'
        f'</g>'
    )


def _svg_dc_source(x: int, y: int, comp_id: str, params: dict) -> str:
    label = _label(comp_id, params, "voltage", "V")
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 22, _MID_Y)}'
        f'<circle cx="40" cy="{_MID_Y}" r="18" fill="none" stroke="#333" stroke-width="2"/>'
        f'{_text(34, 19, "+", size=14)}{_text(46, 19, "-", size=14)}'
        f'{_line(58, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -6, label)}'
        f'</g>'
    )


def _svg_mosfet(x: int, y: int, comp_id: str, params: dict) -> str:
    label = _label(comp_id, params, "switching_frequency", "Hz")
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 15, _MID_Y)}'
        f'<rect x="15" y="2" width="50" height="26" rx="3" fill="#e8f4fd" stroke="#333" stroke-width="2"/>'
        f'{_text(40, 19, "MOS", size=9)}'
        f'{_line(25, 28, 25, 35, width=1.5)}{_text(20, 44, "G", anchor="start", size=8, color="#666")}'
        f'{_line(65, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -4, label)}'
        f'</g>'
    )


def _svg_diode(x: int, y: int, comp_id: str, params: dict) -> str:
    label = _label(comp_id, params, "forward_voltage", "V")
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 25, _MID_Y)}'
        f'<polygon points="25,4 25,26 48,{_MID_Y}" fill="none" stroke="#333" stroke-width="2"/>'
        f'{_line(48, 4, 48, 26, width=2.5)}'
        f'{_line(48, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -4, label)}'
        f'</g>'
    )


def _svg_generic(x: int, y: int, comp_id: str, comp_type: str, params: dict) -> str:
    return (
        f'<g transform="translate({x},{y})">'
        f'{_line(0, _MID_Y, 10, _MID_Y)}'
        f'<rect x="10" y="2" width="60" height="26" rx="3" fill="#f5f5f5" stroke="#333" stroke-width="2"/>'
        f'{_text(40, 19, comp_type[:8], size=9)}'
        f'{_line(70, _MID_Y, _TOTAL_W, _MID_Y)}'
        f'{_pin_dot(0, _MID_Y)}{_pin_dot(_TOTAL_W, _MID_Y)}'
        f'{_text(40, -4, comp_id)}'
        f'</g>'
    )


_RENDER_STYLE_MAP = {
    "Resistor": _svg_resistor,
    "Capacitor": _svg_capacitor,
    "Inductor": _svg_inductor,
    "DC_Source": _svg_dc_source,
    "AC_Source": _svg_dc_source,
    "Battery": _svg_dc_source,
    "MOSFET": _svg_mosfet,
    "IGBT": _svg_mosfet,
    "Diode": _svg_diode,
}


def _port_pin_map(comp: dict) -> dict[str, tuple[int, int]]:
    return build_port_pin_map(comp)


def _get_renderer(comp_type: str):
    symbol_info = get_symbol(comp_type) or {}
    render_style = symbol_info.get("render_style", comp_type)
    return _RENDER_STYLE_MAP.get(render_style, lambda x, y, i, p: _svg_generic(x, y, i, comp_type, p))


def _spread_positions(count: int, start: int, end: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [round((start + end) / 2)]
    gap = (end - start) / (count + 1)
    return [round(start + gap * (i + 1)) for i in range(count)]


def _rotate_point(dx: int, dy: int, direction: int, cx: float, cy: float) -> tuple[int, int]:
    """direction(0/90/180/270)에 따라 (dx, dy)를 (cx, cy) 중심으로 회전."""
    import math
    if direction in (0, None):
        return dx, dy
    rad = math.radians(direction)
    cos_a = round(math.cos(rad))
    sin_a = round(math.sin(rad))
    rx = cx + (dx - cx) * cos_a - (dy - cy) * sin_a
    ry = cy + (dx - cx) * sin_a + (dy - cy) * cos_a
    return round(rx), round(ry)


def _build_pin_positions(components: list[dict]) -> dict[str, tuple[int, int]]:
    pin_pos: dict[str, tuple[int, int]] = {}
    for comp in components:
        cid = comp.get("id", "")
        if not cid:
            continue
        comp_type = comp.get("type", "")
        pos = comp.get("position", {"x": 0, "y": 0})
        direction = comp.get("direction", 0)
        port_map = _port_pin_map(comp)
        if port_map:
            pin_pos.update(port_map)
            continue

        # 회전 중심 (심볼 로컬 좌표 기준)
        cx = _TOTAL_W / 2
        cy = _MID_Y

        explicit_anchors = get_pin_anchors(comp_type)
        if explicit_anchors:
            for pin_name, (dx, dy) in explicit_anchors.items():
                rdx, rdy = _rotate_point(dx, dy, direction, cx, cy)
                pin_pos[f"{cid}.{pin_name}"] = (pos["x"] + rdx, pos["y"] + rdy)
            continue

        lib_comp = get_component(comp_type)
        pins = list(lib_comp.get("pins", [])) if lib_comp else []
        if not pins:
            for pin in LEFT_PINS:
                rdx, rdy = _rotate_point(0, _MID_Y, direction, cx, cy)
                pin_pos[f"{cid}.{pin}"] = (pos["x"] + rdx, pos["y"] + rdy)
            for pin in RIGHT_PINS:
                rdx, rdy = _rotate_point(_TOTAL_W, _MID_Y, direction, cx, cy)
                pin_pos[f"{cid}.{pin}"] = (pos["x"] + rdx, pos["y"] + rdy)
            continue

        left_pins = [pin for pin in pins if get_pin_side(pin) == "left"]
        right_pins = [pin for pin in pins if get_pin_side(pin) == "right"]
        center_pins = [pin for pin in pins if get_pin_side(pin) == "center"]
        left_ys = _spread_positions(len(left_pins), 4, _BODY_H - 4)
        right_ys = _spread_positions(len(right_pins), 4, _BODY_H - 4)

        for pin, y in zip(left_pins, left_ys):
            rdx, rdy = _rotate_point(0, y, direction, cx, cy)
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + rdx, pos["y"] + rdy)
        for pin, y in zip(right_pins, right_ys):
            rdx, rdy = _rotate_point(_TOTAL_W, y, direction, cx, cy)
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + rdx, pos["y"] + rdy)

        bottom_pins = [pin for pin in center_pins if pin in {"gate", "control", "ground", "thermal_in", "secondary_center"}]
        top_pins = [pin for pin in center_pins if pin not in bottom_pins]
        top_xs = _spread_positions(len(top_pins), 12, _TOTAL_W - 12)
        bottom_xs = _spread_positions(len(bottom_pins), 12, _TOTAL_W - 12)
        for pin, x in zip(top_pins, top_xs):
            rdx, rdy = _rotate_point(x, 0, direction, cx, cy)
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + rdx, pos["y"] + rdy)
        for pin, x in zip(bottom_pins, bottom_xs):
            rdx, rdy = _rotate_point(x, _BODY_H, direction, cx, cy)
            pin_pos[f"{cid}.{pin}"] = (pos["x"] + rdx, pos["y"] + rdy)
    return pin_pos


def _draw_segment(x1: int, y1: int, x2: int, y2: int) -> str:
    if x1 == x2 or y1 == y2:
        return _line(x1, y1, x2, y2, color="#2980b9")
    mx = (x1 + x2) // 2
    return _polyline([(x1, y1), (mx, y1), (mx, y2), (x2, y2)], color="#2980b9")


def _render_connections(components: list[dict], connections: list[dict]) -> str:
    pin_pos = _build_pin_positions(components)
    return "".join(
        _draw_segment(*pin_pos[conn["from"]], *pin_pos[conn["to"]])
        for conn in connections
        if conn.get("from") in pin_pos and conn.get("to") in pin_pos
    )


def _render_wire_segments(wire_segments: list[dict]) -> str:
    return "".join(
        _draw_segment(
            int(segment["x1"]),
            int(segment["y1"]),
            int(segment["x2"]),
            int(segment["y2"]),
        )
        for segment in wire_segments
        if all(key in segment for key in ("x1", "y1", "x2", "y2"))
    )


def _render_nets(components: list[dict], nets: list[dict]) -> tuple[str, str]:
    pin_pos = _build_pin_positions(components)
    lines = ""
    dots = ""
    for net in nets:
        refs = net.get("pins", net.get("connections", []))
        points: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for ref in refs:
            point = pin_pos.get(ref)
            if point and point not in seen:
                seen.add(point)
                points.append(point)
        if len(points) < 2:
            continue
        if len(points) == 2:
            lines += _draw_segment(*points[0], *points[1])
            continue
        hub_x = round(sum(x for x, _ in points) / len(points))
        hub_y = round(sum(y for _, y in points) / len(points))
        for x, y in points:
            lines += _draw_segment(x, y, hub_x, hub_y)
        dots += f'<circle cx="{hub_x}" cy="{hub_y}" r="4" fill="#2980b9"/>'
    return lines, dots


def _render_junctions(components: list[dict], connections: list[dict]) -> str:
    pin_pos = _build_pin_positions(components)
    pos_count: dict[tuple[int, int], int] = {}
    for conn in connections:
        for key in ("from", "to"):
            point = pin_pos.get(conn.get(key, ""))
            if point:
                pos_count[point] = pos_count.get(point, 0) + 1
    return "".join(
        f'<circle cx="{x}" cy="{y}" r="4" fill="#2980b9"/>'
        for (x, y), count in pos_count.items()
        if count >= 2
    )


def _render_gnd_symbols(components: list[dict]) -> str:
    if any(comp.get("type") == "Ground" for comp in components):
        return ""
    gnd = ""
    for comp in components:
        if comp.get("type") != "DC_Source":
            continue
        ports = comp.get("ports", [])
        if len(ports) >= 4:
            gx, gy = ports[2], ports[3]
        else:
            pos = comp.get("position", {"x": 0, "y": 0})
            gx, gy = pos["x"] + _TOTAL_W, pos["y"] + _MID_Y
        gnd += (
            f'<g transform="translate({gx},{gy})">'
            f'{_line(0, 0, 0, 12)}{_line(-10, 12, 10, 12)}{_line(-6, 16, 6, 16, width=1.5)}{_line(-3, 20, 3, 20, width=1)}'
            f'</g>'
        )
    return gnd


def _render_two_terminal_with_ports(comp: dict, label: str, kind: str) -> str:
    ports = comp.get("ports", [])
    if len(ports) < 4:
        return ""
    x1, y1, x2, y2 = ports[:4]
    horizontal = y1 == y2
    parts = ['<g transform="translate(0,0)">']
    parts.append(_pin_dot(x1, y1))
    parts.append(_pin_dot(x2, y2))
    if horizontal:
        midx = (x1 + x2) // 2
        parts.append(_line(x1, y1, midx - 18, y1))
        parts.append(_line(midx + 18, y1, x2, y2))
        if kind == "resistor":
            parts.append(_polyline([(midx - 18, y1), (midx - 12, y1 - 10), (midx - 4, y1 + 10), (midx + 4, y1 - 10), (midx + 12, y1 + 10), (midx + 18, y1)]))
        elif kind == "inductor":
            for i in range(4):
                sx = midx - 16 + i * 8
                parts.append(f'<path d="M {sx} {y1} A 4 4 0 0 1 {sx + 8} {y1}" fill="none" stroke="#333" stroke-width="2"/>')
        elif kind == "capacitor":
            parts.append(_line(midx - 4, y1 - 12, midx - 4, y1 + 12, width=2.5))
            parts.append(_line(midx + 4, y1 - 12, midx + 4, y1 + 12, width=2.5))
        elif kind == "diode":
            parts.append(f'<polygon points="{midx - 12},{y1 - 11} {midx - 12},{y1 + 11} {midx + 8},{y1}" fill="none" stroke="#333" stroke-width="2"/>')
            parts.append(_line(midx + 8, y1 - 11, midx + 8, y1 + 11, width=2.5))
        elif kind == "source":
            parts.append(f'<circle cx="{midx}" cy="{y1}" r="16" fill="none" stroke="#333" stroke-width="2"/>')
            parts.append(_text(midx - 5, y1 + 4, "+", size=13))
            parts.append(_text(midx + 5, y1 + 4, "-", size=13))
        parts.append(_text(midx, y1 - 18, label))
    else:
        midy = (y1 + y2) // 2
        parts.append(_line(x1, y1, x1, midy - 18))
        parts.append(_line(x2, midy + 18, x2, y2))
        if kind == "resistor":
            parts.append(_polyline([(x1, midy - 18), (x1 - 10, midy - 12), (x1 + 10, midy - 4), (x1 - 10, midy + 4), (x1 + 10, midy + 12), (x1, midy + 18)]))
        elif kind == "inductor":
            for i in range(4):
                sy = midy - 16 + i * 8
                parts.append(f'<path d="M {x1} {sy} A 4 4 0 0 0 {x1} {sy + 8}" fill="none" stroke="#333" stroke-width="2"/>')
        elif kind == "capacitor":
            parts.append(_line(x1 - 12, midy - 4, x1 + 12, midy - 4, width=2.5))
            parts.append(_line(x1 - 12, midy + 4, x1 + 12, midy + 4, width=2.5))
        elif kind == "diode":
            parts.append(f'<polygon points="{x1 - 11},{midy + 12} {x1 + 11},{midy + 12} {x1},{midy - 8}" fill="none" stroke="#333" stroke-width="2"/>')
            parts.append(_line(x1 - 11, midy - 8, x1 + 11, midy - 8, width=2.5))
        elif kind == "source":
            parts.append(f'<circle cx="{x1}" cy="{midy}" r="16" fill="none" stroke="#333" stroke-width="2"/>')
            parts.append(_text(x1 - 4, midy - 3, "+", size=13))
            parts.append(_text(x1 - 4, midy + 13, "-", size=13))
        parts.append(_text(x1 + 20, midy - 20, label, anchor="start"))
    parts.append("</g>")
    return "".join(parts)


def _render_switch_with_ports(comp: dict) -> str:
    ports = comp.get("ports", [])
    if len(ports) < 6:
        return ""
    drain_x, drain_y, source_x, source_y, gate_x, gate_y = ports[:6]
    cid = comp.get("id", "?")
    label = _label(cid, comp.get("parameters", {}), "switching_frequency", "Hz")
    midx = (drain_x + source_x) // 2
    midy = (drain_y + source_y) // 2
    if drain_x == source_x:
        body = f'<rect x="{drain_x - 14}" y="{min(drain_y, source_y) + 12}" width="28" height="{abs(source_y - drain_y) - 24}" rx="3" fill="#e8f4fd" stroke="#333" stroke-width="2"/>'
        leads = _line(drain_x, drain_y, drain_x, min(drain_y, source_y) + 12) + _line(source_x, max(drain_y, source_y) - 12, source_x, source_y)
    else:
        body = f'<rect x="{min(drain_x, source_x) + 12}" y="{drain_y - 14}" width="{abs(source_x - drain_x) - 24}" height="28" rx="3" fill="#e8f4fd" stroke="#333" stroke-width="2"/>'
        leads = _line(drain_x, drain_y, min(drain_x, source_x) + 12, drain_y) + _line(max(drain_x, source_x) - 12, source_y, source_x, source_y)
    return (
        f'<g transform="translate(0,0)">'
        f'{leads}{body}{_line(gate_x, gate_y, midx if drain_x == source_x else gate_x, midy if drain_x == source_x else drain_y, width=1.5)}'
        f'{_pin_dot(drain_x, drain_y)}{_pin_dot(source_x, source_y)}{_pin_dot(gate_x, gate_y)}'
        f'{_text(midx, min(drain_y, source_y) - 8, label)}'
        f'</g>'
    )


def _render_transformer_with_ports(comp: dict, center_tap: bool = False) -> str:
    ports = comp.get("ports", [])
    cid = comp.get("id", "?")
    if center_tap and len(ports) < 12:
        return ""
    if not center_tap and len(ports) < 8:
        return ""
    if center_tap:
        p1x, p1y, pcx, pcy, p2x, p2y, s1x, s1y, scx, scy, s2x, s2y = ports[:12]
    else:
        p1x, p1y, p2x, p2y, s1x, s1y, s2x, s2y = ports[:8]
        pcx = pcy = scx = scy = None
    left_x = min(p1x, p2x) + 14
    right_x = max(s1x, s2x) - 14
    top_y = min(p1y, p2y, s1y, s2y)
    coils = []
    for i in range(3):
        sy = top_y + 5 + i * 8
        coils.append(f'<path d="M {left_x} {sy} A 5 4 0 0 1 {left_x} {sy + 8}" fill="none" stroke="#333" stroke-width="1.6"/>')
        coils.append(f'<path d="M {right_x} {sy} A 5 4 0 0 0 {right_x} {sy + 8}" fill="none" stroke="#333" stroke-width="1.6"/>')
    parts = [
        '<g transform="translate(0,0)">',
        _line(p1x, p1y, left_x, p1y),
        _line(p2x, p2y, left_x, p2y),
        _line(right_x, s1y, s1x, s1y),
        _line(right_x, s2y, s2x, s2y),
        _line((left_x + right_x) // 2 - 6, top_y, (left_x + right_x) // 2 - 6, top_y + 30, width=1.5),
        _line((left_x + right_x) // 2 + 6, top_y, (left_x + right_x) // 2 + 6, top_y + 30, width=1.5),
        "".join(coils),
        f'<circle cx="{left_x + 7}" cy="{top_y + 7}" r="2.5" fill="#333"/>',
        f'<circle cx="{right_x - 7}" cy="{top_y + 7}" r="2.5" fill="#333"/>',
        _pin_dot(p1x, p1y), _pin_dot(p2x, p2y), _pin_dot(s1x, s1y), _pin_dot(s2x, s2y),
        _text(left_x + 7, top_y - 6, "P", size=8),
        _text(right_x - 7, top_y - 6, "S", size=8),
        _text((left_x + right_x) // 2, top_y - 8, cid),
    ]
    if center_tap and pcx is not None and scx is not None:
        parts.extend([_line(pcx, pcy, left_x, pcy), _pin_dot(pcx, pcy), _line(right_x, scy, scx, scy), _pin_dot(scx, scy)])
    parts.append("</g>")
    return "".join(parts)


def _render_component(comp: dict) -> str:
    comp_type = comp.get("type", "Unknown")
    cid = comp.get("id", "?")
    params = comp.get("parameters", {})
    ports = comp.get("ports", [])
    if ports:
        if comp_type == "Ground" and len(ports) >= 2:
            return (
                f'<g transform="translate({ports[0]},{ports[1]})">'
                f'{_line(0, 0, 0, 10)}{_line(-10, 10, 10, 10)}{_line(-6, 14, 6, 14, width=1.5)}{_line(-3, 18, 3, 18, width=1)}'
                f'{_text(0, -6, cid)}'
                f'</g>'
            )
        if comp_type == "PWM_Generator" and len(ports) >= 2:
            x, y = ports[0], ports[1]
            return (
                f'<g transform="translate({x},{y})">'
                f'<rect x="-24" y="-14" width="48" height="28" rx="4" fill="#fff7e6" stroke="#333" stroke-width="2"/>'
                f'{_polyline([(-16, 4), (-8, -4), (0, 4), (8, -4), (16, 4)], width=1.5)}'
                f'{_line(24, 0, 36, 0)}{_pin_dot(36, 0)}{_text(0, -18, cid)}'
                f'</g>'
            )
        if comp_type == "Transformer":
            return _render_transformer_with_ports(comp)
        if comp_type == "Center_Tap_Transformer":
            return _render_transformer_with_ports(comp, center_tap=True)
        if comp_type == "Resistor":
            return _render_two_terminal_with_ports(comp, _label(cid, params, "resistance", "Ohm"), "resistor")
        if comp_type == "Inductor":
            return _render_two_terminal_with_ports(comp, _label(cid, params, "inductance", "H"), "inductor")
        if comp_type == "Capacitor":
            return _render_two_terminal_with_ports(comp, _label(cid, params, "capacitance", "F"), "capacitor")
        if comp_type in {"Diode", "DIODE"}:
            return _render_two_terminal_with_ports(comp, _label(cid, params, "forward_voltage", "V"), "diode")
        if comp_type in {"DC_Source", "AC_Source", "Battery"}:
            return _render_two_terminal_with_ports(comp, _label(cid, params, "voltage", "V"), "source")
        if comp_type in {"MOSFET", "IGBT"}:
            return _render_switch_with_ports(comp)

    pos = comp.get("position", {"x": 0, "y": 0})
    direction = comp.get("direction", 0)
    renderer = _get_renderer(comp_type)
    inner_svg = renderer(0, 0, cid, params)

    if direction in (0, None):
        # direction=0: 기본 수평 방향 — 변환 없이 위치만 이동
        return f'<g transform="translate({pos["x"]},{pos["y"]})">{inner_svg}</g>'

    # direction 90/180/270: 심볼 중심 기준 회전
    cx = _TOTAL_W / 2
    cy = _MID_Y
    return (
        f'<g transform="translate({pos["x"]},{pos["y"]})">'
        f'<g transform="rotate({direction},{cx},{cy})">'
        f'{inner_svg}'
        f'</g></g>'
    )


def _apply_layout_to_components(components: list[dict], layout: dict | object | None) -> list[dict]:
    if layout is None:
        return components

    layout_components = layout.get("components", []) if isinstance(layout, dict) else getattr(layout, "components", [])
    by_id: dict[str, dict] = {}
    for item in layout_components:
        if isinstance(item, dict):
            by_id[item.get("id", "")] = item
        else:
            by_id[getattr(item, "id", "")] = {
                "x": getattr(item, "x", 0),
                "y": getattr(item, "y", 0),
                "direction": getattr(item, "direction", 0),
            }

    normalized: list[dict] = []
    for comp in components:
        cid = comp.get("id", "")
        layout_item = by_id.get(cid)
        if not layout_item:
            normalized.append(comp)
            continue

        merged = dict(comp)
        merged["position"] = {
            "x": int(layout_item.get("x", comp.get("position", {}).get("x", 0))),
            "y": int(layout_item.get("y", comp.get("position", {}).get("y", 0))),
        }
        merged["direction"] = int(layout_item.get("direction", comp.get("direction", 0) or 0))
        normalized.append(merged)

    return normalized


def render_circuit_svg(
    circuit_type: str,
    components: list[dict],
    connections: list[dict],
    nets: list[dict] | None = None,
    wire_segments: list[dict] | None = None,
    layout: dict | object | None = None,
    title: str | None = None,
) -> str:
    components = _apply_layout_to_components(components, layout)
    max_x = max(
        (
            (c.get("position", {}).get("x", 0) + get_bounding_box(c.get("type", "")).get("width", 80))
            if not c.get("ports")
            else max(c.get("ports", [c.get("position", {}).get("x", 0)]))
            for c in components
        ),
        default=0,
    ) + 80
    max_y = max(
        (
            (c.get("position", {}).get("y", 0) + get_bounding_box(c.get("type", "")).get("height", 30))
            if not c.get("ports")
            else max(c.get("ports", [c.get("position", {}).get("y", 0)]))
            for c in components
        ),
        default=0,
    ) + 80
    width = max(max_x, 500)
    height = max(max_y, 250)
    display_title = title or f"{circuit_type.upper()} Converter Preview"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:#fafafa; border:1px solid #ddd; border-radius:8px;">',
        f'<text x="{width // 2}" y="25" text-anchor="middle" font-size="16" font-weight="bold" font-family="sans-serif" fill="#2c3e50">{display_title}</text>',
    ]
    if wire_segments:
        parts.append(_render_wire_segments(wire_segments))
    elif nets:
        net_lines, net_dots = _render_nets(components, nets)
        parts.extend([net_lines, net_dots])
    else:
        parts.extend([_render_connections(components, connections), _render_junctions(components, connections)])
    parts.extend(_render_component(comp) for comp in components)
    parts.append(_render_gnd_symbols(components))
    parts.append(
        f'<text x="10" y="{height - 15}" font-size="10" font-family="sans-serif" fill="#999">'
        f'Components: {len(components)} | Connections: {len(connections)} | Preview - confirm to generate .psimsch</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


_TRUTHY = {"1", "true", "yes", "on"}


def open_svg_in_browser(svg_path: str) -> None:
    """Open the SVG in the OS default viewer if PSIM_AUTO_OPEN_PREVIEW is set.

    Default is OFF: when the MCP server is driven from Claude Desktop the
    preview is already surfaced through the chat, and a second OS-level pop-up
    on every design iteration is noisy (especially during tests / rapid
    iteration). To opt in, set ``PSIM_AUTO_OPEN_PREVIEW=true`` in the env or
    ``.env`` file.
    """
    import os
    import platform
    import subprocess

    if os.environ.get("PSIM_AUTO_OPEN_PREVIEW", "").strip().lower() not in _TRUTHY:
        return

    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", svg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif system == "Windows":
            os.startfile(svg_path)
        elif system == "Linux":
            subprocess.Popen(["xdg-open", svg_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
