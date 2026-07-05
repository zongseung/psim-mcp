"""Parse PSIM's PsimConvertToPython output into structured schematic data.

``PsimConvertToPython(psimsch_path, out_py)`` emits a Python script that
rebuilds the schematic through ``PsimCreateNewElement`` calls. That script is
the only complete, text-parseable representation of an existing ``.psimsch``
the PSIM API exposes — ``PsimGetElementList`` returns components and
parameters but omits wires, positions and node indices entirely.

The generated script is valid Python, so we parse it with ``ast`` instead of
regex: element calls become :class:`ParsedComponent` / :class:`ParsedWire` /
:class:`ParsedLabel`, and ``PsimSetElmValue(sch, None, key, value)`` calls
become simulation settings.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

Point = tuple[int, int]

# Annotation-only element types — no electrical meaning.
_SKIP_TYPES = {"TEXT", "TEXTLINK", "UTEXT"}

# Keyword arguments that describe layout/rendering, not electrical parameters.
_LAYOUT_KEYS = {
    "AREA",
    "DIRECTION",
    "PAGE",
    "XFLIP",
    "_OPTIONS_",
    "PORTS",
    "SubType",
    "_InputCount",
    "_OutputCount",
}

_COORD_KEY = re.compile(r"^[XY]\d+$")


@dataclass
class ParsedComponent:
    """An electrical component with pin coordinates and parameters."""

    id: str
    type: str
    name: str
    pins: list[Point]
    parameters: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ParsedWire:
    """A wire polyline; consecutive points form electrical segments."""

    points: list[Point]

    @property
    def segments(self) -> list[tuple[Point, Point]]:
        return list(zip(self.points, self.points[1:]))


@dataclass
class ParsedLabel:
    """A net label — same-named labels are electrically one net."""

    name: str
    point: Point
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ParsedSchematic:
    """Full parse result of one converted schematic script."""

    components: list[ParsedComponent] = field(default_factory=list)
    wires: list[ParsedWire] = field(default_factory=list)
    labels: list[ParsedLabel] = field(default_factory=list)
    simulation: dict[str, object] = field(default_factory=dict)


def _coord(value: object) -> int:
    """PSIM emits coordinates as strings ("930") or ints — normalize to int."""
    return int(float(str(value)))


class _Evaluator:
    """Evaluate ast nodes to constants, resolving module-level string vars."""

    def __init__(self, tree: ast.Module) -> None:
        self._vars: dict[str, object] = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                try:
                    self._vars[node.targets[0].id] = ast.literal_eval(node.value)
                except (ValueError, SyntaxError):
                    continue

    def eval(self, node: ast.expr) -> object:
        try:
            return ast.literal_eval(node)
        except (ValueError, SyntaxError):
            pass
        if isinstance(node, ast.Name):
            return self._vars.get(node.id)
        return None


def parse_converted_script(text: str) -> ParsedSchematic:
    """Parse a PsimConvertToPython-generated script into a ParsedSchematic."""
    tree = ast.parse(text)
    evaluator = _Evaluator(tree)

    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    calls.sort(key=lambda n: (n.lineno, n.col_offset))

    result = ParsedSchematic()
    used_ids: dict[str, int] = {}
    components_by_name: dict[str, ParsedComponent] = {}
    last_component: ParsedComponent | None = None

    for call in calls:
        func = call.func
        attr = (
            func.attr
            if isinstance(func, ast.Attribute)
            else (func.id if isinstance(func, ast.Name) else None)
        )

        if attr == "PsimSetElmValue":
            # PsimSetElmValue(sch, None, "TIMESTEP", "1E-06") — simulation control
            args = [evaluator.eval(a) for a in call.args]
            if len(args) >= 4 and args[1] is None and isinstance(args[2], str):
                result.simulation[args[2]] = args[3]
            continue

        if attr == "PsimSetElmValue2":
            # PsimSetElmValue2(sch, "CBLOCK", "SCB1", "CONTENT", strScript_var)
            args = [evaluator.eval(a) for a in call.args]
            if len(args) >= 5 and isinstance(args[2], str):
                comp = components_by_name.get(args[2])
                if comp is not None and isinstance(args[3], str):
                    comp.parameters[args[3]] = args[4]
            continue

        if attr == "PsimEnableElm3":
            # PsimEnableElm3(sch, nCreatedIndex, 0) — disables the element
            # created immediately before this call.
            args = [evaluator.eval(a) for a in call.args]
            if last_component is not None and len(args) >= 3 and args[2] == 0:
                last_component.metadata["enabled"] = False
            continue

        if attr != "PsimCreateNewElement":
            continue

        pos_args = [evaluator.eval(a) for a in call.args]
        elem_type = str(pos_args[1]) if len(pos_args) > 1 and pos_args[1] else ""
        elem_name = str(pos_args[2]) if len(pos_args) > 2 and pos_args[2] else ""
        kwargs = {kw.arg: evaluator.eval(kw.value) for kw in call.keywords if kw.arg}
        type_upper = elem_type.upper()

        if type_upper in _SKIP_TYPES:
            continue

        if type_upper == "WIRE":
            points: list[Point] = []
            i = 1
            while f"X{i}" in kwargs and f"Y{i}" in kwargs:
                points.append((_coord(kwargs[f"X{i}"]), _coord(kwargs[f"Y{i}"])))
                i += 1
            if len(points) >= 2:
                result.wires.append(ParsedWire(points=points))
            last_component = None
            continue

        if type_upper == "LABEL":
            ports = kwargs.get("PORTS") or []
            if isinstance(ports, (list, tuple)) and len(ports) >= 2:
                result.labels.append(
                    ParsedLabel(
                        name=elem_name,
                        point=(_coord(ports[0]), _coord(ports[1])),
                        metadata={"direction": kwargs.get("DIRECTION")},
                    )
                )
            last_component = None
            continue

        if type_upper == "SIMCONTROL":
            # Settings arrive via PsimSetElmValue(sch, None, ...) — see above.
            last_component = None
            continue

        # --- Electrical component ---
        ports = kwargs.get("PORTS") or []
        pins: list[Point] = []
        if isinstance(ports, (list, tuple)):
            for j in range(0, len(ports) - 1, 2):
                pins.append((_coord(ports[j]), _coord(ports[j + 1])))

        parameters = {
            k: v for k, v in kwargs.items() if k not in _LAYOUT_KEYS and not _COORD_KEY.match(k)
        }

        base_id = elem_name or elem_type or "elem"
        count = used_ids.get(base_id, 0)
        used_ids[base_id] = count + 1
        comp_id = base_id if count == 0 else f"{base_id}_{count + 1}"

        component = ParsedComponent(
            id=comp_id,
            type=elem_type,
            name=elem_name,
            pins=pins,
            parameters=parameters,
            metadata={
                "subtype": kwargs.get("SubType"),
                "direction": kwargs.get("DIRECTION"),
                "area": kwargs.get("AREA"),
                "xflip": kwargs.get("XFLIP"),
                "input_count": kwargs.get("_InputCount"),
                "output_count": kwargs.get("_OutputCount"),
                "enabled": True,
            },
        )
        result.components.append(component)
        if elem_name:
            components_by_name[elem_name] = component
        last_component = component

    return result
