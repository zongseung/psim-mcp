"""Shared routing helpers for preview and bridge geometry."""

from __future__ import annotations

import copy

from psim_mcp.data.component_library import (
    LEFT_PINS,
    RIGHT_PINS,
    build_port_pin_map,
    get_component,
    get_pin_side,
)

from .models import WireSegment

_BODY_W = 60
_TOTAL_W = 80
_BODY_H = 30
_MID_Y = 15

_PIN_ANCHOR_MAP: dict[str, dict[str, tuple[int, int]]] = {
    "Resistor": {"pin1": (0, _MID_Y), "input": (0, _MID_Y), "pin2": (_TOTAL_W, _MID_Y), "output": (_TOTAL_W, _MID_Y)},
    "Inductor": {"pin1": (0, _MID_Y), "input": (0, _MID_Y), "pin2": (_TOTAL_W, _MID_Y), "output": (_TOTAL_W, _MID_Y)},
    "Capacitor": {"positive": (0, _MID_Y), "pin1": (0, _MID_Y), "negative": (_TOTAL_W, _MID_Y), "pin2": (_TOTAL_W, _MID_Y)},
    "DC_Source": {"positive": (0, _MID_Y), "pin1": (0, _MID_Y), "negative": (_TOTAL_W, _MID_Y), "pin2": (_TOTAL_W, _MID_Y)},
    "AC_Source": {"positive": (0, _MID_Y), "pin1": (0, _MID_Y), "negative": (_TOTAL_W, _MID_Y), "pin2": (_TOTAL_W, _MID_Y)},
    "Battery": {"positive": (0, _MID_Y), "pin1": (0, _MID_Y), "negative": (_TOTAL_W, _MID_Y), "pin2": (_TOTAL_W, _MID_Y)},
    "Diode": {"anode": (0, _MID_Y), "pin1": (0, _MID_Y), "cathode": (_TOTAL_W, _MID_Y), "pin2": (_TOTAL_W, _MID_Y)},
    "MOSFET": {"drain": (0, _MID_Y), "source": (_TOTAL_W, _MID_Y), "gate": (25, _BODY_H)},
    "IGBT": {"collector": (0, _MID_Y), "emitter": (_TOTAL_W, _MID_Y), "gate": (25, _BODY_H)},
}

_PRIMARY_TERMINAL_ALIASES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "DC_Source": (("positive", "pin1"), ("negative", "pin2")),
    "AC_Source": (("positive", "pin1"), ("negative", "pin2")),
    "Battery": (("positive", "pin1"), ("negative", "pin2")),
    "Resistor": (("pin1", "input"), ("pin2", "output")),
    "Inductor": (("pin1", "input"), ("pin2", "output")),
    "Capacitor": (("positive", "pin1"), ("negative", "pin2")),
    "Diode": (("anode", "pin1"), ("cathode", "pin2")),
    "DIODE": (("anode", "pin1"), ("cathode", "pin2")),
}


def _spread_positions(count: int, start: int, end: int) -> list[int]:
    if count <= 0:
        return []
    if count == 1:
        return [round((start + end) / 2)]
    gap = (end - start) / (count + 1)
    return [round(start + gap * (i + 1)) for i in range(count)]


def _rotate_point(dx: int, dy: int, direction: int, cx: float, cy: float) -> tuple[int, int]:
    import math

    if direction in (0, None):
        return dx, dy
    rad = math.radians(direction)
    cos_a = round(math.cos(rad))
    sin_a = round(math.sin(rad))
    rx = cx + (dx - cx) * cos_a - (dy - cy) * sin_a
    ry = cy + (dx - cx) * sin_a + (dy - cy) * cos_a
    return round(rx), round(ry)


def build_pin_position_map(components: list[dict]) -> dict[str, tuple[int, int]]:
    """Resolve absolute coordinates for every known component pin."""

    pin_pos: dict[str, tuple[int, int]] = {}
    for comp in components:
        cid = comp.get("id", "")
        if not cid:
            continue
        comp_type = comp.get("type", "")
        pos = comp.get("position", {"x": 0, "y": 0})
        direction = comp.get("direction", 0)
        port_map = build_port_pin_map(comp)
        if port_map:
            pin_pos.update(port_map)
            continue

        cx = _TOTAL_W / 2
        cy = _MID_Y

        explicit_anchors = _PIN_ANCHOR_MAP.get(comp_type)
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


def _pin_position_for_direction(component: dict, pin_name: str, direction: int) -> tuple[int, int] | None:
    anchors = _PIN_ANCHOR_MAP.get(str(component.get("type", "")), {})
    anchor = anchors.get(pin_name)
    if anchor is None:
        return None
    pos = component.get("position", {"x": 0, "y": 0})
    rdx, rdy = _rotate_point(anchor[0], anchor[1], direction, _TOTAL_W / 2, _MID_Y)
    return pos["x"] + rdx, pos["y"] + rdy


def prepare_components_for_layout(
    components: list[dict],
    connections: list[dict] | None = None,
    nets: list[dict] | None = None,
) -> list[dict]:
    """Infer better directions for simple unported parts from wiring context."""

    prepared = copy.deepcopy(components)
    resolved_connections = list(connections or [])
    if nets and not resolved_connections:
        resolved_connections = nets_to_connection_pairs(nets)

    pin_pos = build_pin_position_map(prepared)
    for component in prepared:
        comp_type = str(component.get("type", ""))
        comp_id = str(component.get("id", ""))
        terminal_groups = _PRIMARY_TERMINAL_ALIASES.get(comp_type)
        if not comp_id or terminal_groups is None:
            continue
        if component.get("ports") or "direction" in component:
            continue

        terminal_peers: dict[str, list[tuple[int, int]]] = {terminal_groups[0][0]: [], terminal_groups[1][0]: []}
        for conn in resolved_connections:
            src = str(conn.get("from", ""))
            dst = str(conn.get("to", ""))
            for aliases in terminal_groups:
                primary = aliases[0]
                refs = {f"{comp_id}.{alias}" for alias in aliases}
                if src in refs and dst in pin_pos:
                    terminal_peers[primary].append(pin_pos[dst])
                elif dst in refs and src in pin_pos:
                    terminal_peers[primary].append(pin_pos[src])

        if not terminal_peers[terminal_groups[0][0]] and not terminal_peers[terminal_groups[1][0]]:
            continue

        best_direction = 0
        best_score: int | None = None
        for direction in (0, 90, 270, 180):
            score = 0
            valid = True
            for aliases in terminal_groups:
                terminal = aliases[0]
                pin_point = _pin_position_for_direction(component, terminal, direction)
                if pin_point is None:
                    valid = False
                    break
                score += sum(abs(pin_point[0] - peer[0]) + abs(pin_point[1] - peer[1]) for peer in terminal_peers[terminal])
            if not valid:
                continue
            if best_score is None or score < best_score:
                best_score = score
                best_direction = direction

        pos = component.get("position", {"x": 0, "y": 0})
        component_x = int(pos.get("x", 0))
        component_y = int(pos.get("y", 0))
        xs = sorted(int(item.get("position", {}).get("x", 0)) for item in prepared)
        ys = sorted(int(item.get("position", {}).get("y", 0)) for item in prepared)
        median_x = xs[len(xs) // 2] if xs else component_x
        median_y = ys[len(ys) // 2] if ys else component_y

        if best_direction == 0:
            if comp_type in {"DC_Source", "AC_Source", "Battery"}:
                best_direction = 90
            elif comp_type in {"Capacitor", "Resistor"} and component_x >= median_x:
                best_direction = 90
            elif comp_type in {"Diode", "DIODE"} and abs(component_y - median_y) >= 40:
                best_direction = 90

        if best_direction != 0:
            component["direction"] = best_direction
            pin_pos = build_pin_position_map(prepared)

    return prepared


def _make_segment(segment_id: str, net: str | None, x1: int, y1: int, x2: int, y2: int) -> WireSegment:
    return {
        "id": segment_id,
        "net": net,
        "x1": int(x1),
        "y1": int(y1),
        "x2": int(x2),
        "y2": int(y2),
    }


def _segment_key(segment: dict) -> tuple[str | None, tuple[int, int], tuple[int, int]]:
    start = (int(segment["x1"]), int(segment["y1"]))
    end = (int(segment["x2"]), int(segment["y2"]))
    ordered = tuple(sorted((start, end)))
    return segment.get("net"), ordered[0], ordered[1]


def _dedupe_segments(wire_segments: list[WireSegment]) -> list[WireSegment]:
    deduped: list[WireSegment] = []
    seen: set[tuple[str | None, tuple[int, int], tuple[int, int]]] = set()
    for segment in wire_segments:
        key = _segment_key(segment)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(segment)
    return deduped


def _orthogonal_segments(x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int, int, int]]:
    if x1 == x2 and y1 == y2:
        return []
    if x1 == x2 or y1 == y2:
        return [(x1, y1, x2, y2)]
    return [
        (x1, y1, x2, y1),
        (x2, y1, x2, y2),
    ]


def normalize_wire_segments(wire_segments: list[dict]) -> list[WireSegment]:
    """Fill missing ids and normalize coordinates on explicit segments."""

    normalized: list[WireSegment] = []
    for idx, segment in enumerate(wire_segments, start=1):
        normalized.append(
            _make_segment(
                str(segment.get("id") or f"wire_{idx}"),
                segment.get("net"),
                int(segment["x1"]),
                int(segment["y1"]),
                int(segment["x2"]),
                int(segment["y2"]),
            )
        )
    return _dedupe_segments(normalized)


def route_connections_to_segments(components: list[dict], connections: list[dict]) -> list[WireSegment]:
    """Convert point-to-point connections into orthogonal wire segments."""

    pin_pos = build_pin_position_map(components)
    segments: list[WireSegment] = []
    seg_idx = 1
    for conn in connections:
        if {"x1", "y1", "x2", "y2"}.issubset(conn):
            x1, y1, x2, y2 = int(conn["x1"]), int(conn["y1"]), int(conn["x2"]), int(conn["y2"])
        else:
            start = pin_pos.get(conn.get("from", ""))
            end = pin_pos.get(conn.get("to", ""))
            if start is None or end is None:
                continue
            x1, y1 = start
            x2, y2 = end
        for sx1, sy1, sx2, sy2 in _orthogonal_segments(x1, y1, x2, y2):
            segments.append(_make_segment(f"wire_{seg_idx}", conn.get("net"), sx1, sy1, sx2, sy2))
            seg_idx += 1
    return _dedupe_segments(segments)


def nets_to_connection_pairs(nets: list[dict]) -> list[dict]:
    """Convert nets to ordered point-to-point connection pairs."""

    connections: list[dict] = []
    for net in nets:
        pins = net.get("pins", [])
        for idx in range(len(pins) - 1):
            connections.append({
                "from": pins[idx],
                "to": pins[idx + 1],
                "net": net.get("name"),
            })
    return connections


def route_nets_to_segments(components: list[dict], nets: list[dict]) -> list[WireSegment]:
    """Convert ordered nets into orthogonal wire segments."""

    return route_connections_to_segments(components, nets_to_connection_pairs(nets))


def segments_to_junctions(wire_segments: list[dict]) -> list[tuple[int, int]]:
    """Return segment endpoints shared by 2+ segments."""

    counts: dict[tuple[int, int], int] = {}
    for segment in wire_segments:
        start = (int(segment["x1"]), int(segment["y1"]))
        end = (int(segment["x2"]), int(segment["y2"]))
        counts[start] = counts.get(start, 0) + 1
        counts[end] = counts.get(end, 0) + 1
    return sorted(point for point, count in counts.items() if count >= 2)


def resolve_wire_segments(
    components: list[dict],
    connections: list[dict] | None = None,
    nets: list[dict] | None = None,
    wire_segments: list[dict] | None = None,
) -> list[WireSegment]:
    """Return the canonical wire geometry for a circuit.

    PHASE 4 NOTE: This function is the legacy routing entry point.
    For topologies with graph+layout support, the routing engine
    (routing/engine.py -> generate_routing) produces WireRouting directly.
    resolve_wire_segments() remains as fallback for:
    - Topologies without layout strategies
    - Template-based circuits
    - Custom component paths
    The new routing engine does NOT call this function.
    """

    if wire_segments:
        return normalize_wire_segments(wire_segments)
    if nets:
        return route_nets_to_segments(components, nets)
    if connections:
        return route_connections_to_segments(components, connections)
    return []
