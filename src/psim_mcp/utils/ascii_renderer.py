"""ASCII circuit diagram renderer for inline display in chat."""

from __future__ import annotations


def _format_value(param_name: str, value) -> str:
    """Format a parameter value with appropriate unit and SI prefix."""
    units = {
        "voltage": "V", "resistance": "Ω", "inductance": "H",
        "capacitance": "F", "switching_frequency": "Hz",
        "forward_voltage": "V", "on_resistance": "Ω",
    }
    unit = units.get(param_name, "")

    if isinstance(value, (int, float)):
        if param_name in ("inductance", "capacitance") and value < 1e-3:
            if value < 1e-9:
                return f"{value*1e12:.1f}p{unit}"
            if value < 1e-6:
                return f"{value*1e9:.1f}n{unit}"
            if value < 1e-3:
                return f"{value*1e6:.1f}μ{unit}"
        if param_name in ("switching_frequency",) and value >= 1000:
            if value >= 1e6:
                return f"{value/1e6:.0f}MHz"
            return f"{value/1000:.0f}kHz"
        if isinstance(value, float) and value == int(value):
            return f"{int(value)}{unit}"
        return f"{value}{unit}"
    return f"{value}{unit}"


def _comp_label(comp: dict) -> str:
    """Build a short label like 'V1 48V' or 'R1 10Ω'."""
    cid = comp.get("id", "?")
    params = comp.get("parameters", {})
    # Pick the most representative parameter
    for key in ("voltage", "resistance", "inductance", "capacitance",
                "switching_frequency", "forward_voltage"):
        if key in params:
            return f"{cid} {_format_value(key, params[key])}"
    return cid


def render_buck_ascii(components: list[dict]) -> str:
    """Render a Buck converter ASCII diagram."""
    labels = {c.get("id", ""): _comp_label(c) for c in components}
    v1 = labels.get("V1", "V1")
    sw1 = labels.get("SW1", "SW1")
    d1 = labels.get("D1", "D1")
    l1 = labels.get("L1", "L1")
    c1 = labels.get("C1", "C1")
    r1 = labels.get("R1", "R1")

    return f"""\
  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ {v1:^10s} │────│ {sw1:^10s} │────│ {l1:^10s} │─┬──│ {r1:^10s} │
  └─────┬──────┘    └─────┬──────┘    └────────────┘ │  └─────┬──────┘
        │                 │                          │        │
        │           ┌─────┴──────┐              ┌────┴─────┐  │
        │           │ {d1:^10s} │              │ {c1:^10s}│  │
        │           └─────┬──────┘              └────┬─────┘  │
        │                 │                          │        │
        └─────────────────┴──────────────────────────┴────────┘
                                 GND"""


def render_boost_ascii(components: list[dict]) -> str:
    """Render a Boost converter ASCII diagram."""
    labels = {c.get("id", ""): _comp_label(c) for c in components}
    v1 = labels.get("V1", "V1")
    l1 = labels.get("L1", "L1")
    sw1 = labels.get("SW1", "SW1")
    d1 = labels.get("D1", "D1")
    c1 = labels.get("C1", "C1")
    r1 = labels.get("R1", "R1")

    return f"""\
  ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
  │ {v1:^10s} │────│ {l1:^10s} │─┬──│ {d1:^10s} │─┬──│ {r1:^10s} │
  └─────┬──────┘    └────────────┘ │  └────────────┘ │  └─────┬──────┘
        │                          │                 │        │
        │                    ┌─────┴──────┐     ┌────┴─────┐  │
        │                    │ {sw1:^10s} │     │ {c1:^10s}│  │
        │                    └─────┬──────┘     └────┬─────┘  │
        │                          │                 │        │
        └──────────────────────────┴─────────────────┴────────┘
                                 GND"""


def render_half_bridge_ascii(components: list[dict]) -> str:
    """Render a Half-bridge inverter ASCII diagram."""
    labels = {c.get("id", ""): _comp_label(c) for c in components}
    v1 = labels.get("V1", "V1")
    sw1 = labels.get("SW1", "SW1")
    sw2 = labels.get("SW2", "SW2")
    l1 = labels.get("L1", "L1")
    r1 = labels.get("R1", "R1")

    return f"""\
  ┌────────────┐    ┌────────────┐
  │ {v1:^10s} │────│ {sw1:^10s} │
  └─────┬──────┘    └─────┬──────┘
        │                 ├────────┌────────────┐────┌────────────┐
        │                 │        │ {l1:^10s} │    │ {r1:^10s} │
        │           ┌─────┴──────┐ └────────────┘    └─────┬──────┘
        │           │ {sw2:^10s} │                         │
        │           └─────┬──────┘                         │
        └─────────────────┴────────────────────────────────┘
                                 GND"""


def render_full_bridge_ascii(components: list[dict]) -> str:
    """Render a Full-bridge inverter ASCII diagram."""
    labels = {c.get("id", ""): _comp_label(c) for c in components}
    v1 = labels.get("V1", "V1")
    sw1 = labels.get("SW1", "SW1")
    sw2 = labels.get("SW2", "SW2")
    sw3 = labels.get("SW3", "SW3")
    sw4 = labels.get("SW4", "SW4")
    l1 = labels.get("L1", "L1")
    r1 = labels.get("R1", "R1")

    return f"""\
              ┌────────────┐                     ┌────────────┐
     ┌────────│ {sw1:^10s} │             ┌───────│ {sw3:^10s} │
     │        └─────┬──────┘             │       └─────┬──────┘
     │              │                    │             │
  ┌──┴─────────┐    ├──┌────────────┐──┌─┴──────────┐──┤
  │ {v1:^10s} │    │  │ {l1:^10s} │  │ {r1:^10s} │  │
  └──┬─────────┘    │  └────────────┘  └────────────┘  │
     │              │                                  │
     │        ┌─────┴──────┐                     ┌─────┴──────┐
     └────────│ {sw2:^10s} │             ┌───────│ {sw4:^10s} │
              └─────┬──────┘             │       └─────┬──────┘
                    └────────────GND─────┴─────────────┘"""


def render_generic_ascii(components: list[dict], connections: list[dict]) -> str:
    """Render a generic component list as a simple text table."""
    lines = ["┌─ Components ──────────────────────────────────┐"]
    for comp in components:
        label = _comp_label(comp)
        ctype = comp.get("type", "Unknown")
        lines.append(f"│  {label:<20s}  ({ctype})")
    lines.append("└───────────────────────────────────────────────┘")
    lines.append(f"  Connections: {len(connections)}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_CIRCUIT_RENDERERS = {
    "buck": render_buck_ascii,
    "boost": render_boost_ascii,
    "half_bridge": render_half_bridge_ascii,
    "full_bridge": render_full_bridge_ascii,
}


def render_circuit_ascii(
    circuit_type: str,
    components: list[dict],
    connections: list[dict],
) -> str:
    """Render an ASCII circuit diagram.

    Uses a specialized renderer for known circuit types, falls back
    to a generic component list for custom circuits.
    """
    renderer = _CIRCUIT_RENDERERS.get(circuit_type.lower())
    if renderer:
        return renderer(components)
    return render_generic_ascii(components, connections)
