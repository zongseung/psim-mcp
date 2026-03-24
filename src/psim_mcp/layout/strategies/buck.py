"""Buck converter layout strategy.

Position mapping derived from generators/buck.py:
  V1  at (120,100) DIR=0    — DC source vertical
  GND1 at (120,150) DIR=0   — ground
  SW1 at (150,100) DIR=270  — horizontal MOSFET
  G1  at (180,170) DIR=0    — PWM block
  D1  at (220,150) DIR=270  — diode vertical cathode up
  L1  at (250,100) DIR=0    — inductor horizontal
  C1  at (300,100) DIR=90   — capacitor vertical
  R1  at (350,100) DIR=90   — resistor vertical
"""

from __future__ import annotations

from psim_mcp.synthesis.graph import CircuitGraph

from ..models import (
    LayoutComponent,
    LayoutConstraint,
    LayoutRegion,
    SchematicLayout,
)

# Role -> (x, y, direction, symbol_variant)
_BUCK_ROLE_POSITIONS: dict[str, tuple[int, int, int, str]] = {
    "input_source": (120, 100, 0, "dc_source_vertical"),
    "ground_ref": (120, 150, 0, "ground"),
    "main_switch": (150, 100, 270, "mosfet_horizontal"),
    "gate_drive": (180, 170, 0, "pwm_block"),
    "freewheel_diode": (220, 150, 270, "diode_vertical_cathode_up"),
    "output_inductor": (250, 100, 0, "inductor_horizontal"),
    "output_capacitor": (300, 100, 90, "capacitor_vertical"),
    "load": (350, 100, 90, "resistor_vertical"),
}

_ROLE_TO_REGION: dict[str, str] = {
    "input_source": "input_region",
    "ground_ref": "input_region",
    "main_switch": "switch_region",
    "freewheel_diode": "switch_region",
    "gate_drive": "switch_region",
    "output_inductor": "output_region",
    "output_capacitor": "output_region",
    "load": "output_region",
}

# Fallback position for unknown roles
_FALLBACK_X = 400
_FALLBACK_Y = 200


class BuckLayoutStrategy:
    """Layout strategy for buck converter topology."""

    def build_layout(
        self,
        graph: CircuitGraph,
        preferences: dict[str, object] | None = None,
    ) -> SchematicLayout:
        prefs = preferences or {}
        ground_rail_y = int(prefs.get("ground_rail_y", 150))
        flow_direction = str(prefs.get("flow_direction", "left_to_right"))
        components: list[LayoutComponent] = []
        fallback_offset = 0

        for gc in graph.components:
            role = gc.role or ""
            pos_info = _BUCK_ROLE_POSITIONS.get(role)
            if pos_info:
                x, y, direction, symbol_variant = pos_info
            else:
                x = _FALLBACK_X + fallback_offset
                y = _FALLBACK_Y
                direction = 0
                symbol_variant = None
                fallback_offset += 50

            components.append(
                LayoutComponent(
                    id=gc.id,
                    x=x,
                    y=y,
                    direction=direction,
                    symbol_variant=symbol_variant,
                    region_id=_ROLE_TO_REGION.get(role, "output_region"),
                )
            )

        regions = [
            LayoutRegion(id="input_region", role="input", x=100, y=80, width=80, height=100),
            LayoutRegion(id="switch_region", role="switch", x=140, y=80, width=110, height=120),
            LayoutRegion(id="output_region", role="output", x=240, y=80, width=150, height=100),
        ]

        constraints = [
            LayoutConstraint(kind="left_of", subject_ids=["input_region", "switch_region"]),
            LayoutConstraint(kind="left_of", subject_ids=["switch_region", "output_region"]),
            LayoutConstraint(kind="align_to_rail", subject_ids=["net_gnd"], value={"y": ground_rail_y}),
        ]

        return SchematicLayout(
            topology="buck",
            components=components,
            regions=regions,
            constraints=constraints,
            metadata={
                "flow_direction": flow_direction,
                "ground_rail_y": ground_rail_y,
                **prefs,
            },
        )
