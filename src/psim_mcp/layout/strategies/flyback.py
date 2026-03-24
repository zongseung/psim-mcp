"""Flyback converter layout strategy.

Position mapping derived from generators/flyback.py:
  V1   at (80,80) DIR=0      — DC source
  GND1 at (80,230) DIR=0     — ground
  T1   at (200,80) DIR=0     — transformer (primary1 at 200,80)
  SW1  at (200,130) DIR=0    — vertical MOSFET (drain at T1.primary2)
  G1   at (160,160) DIR=0    — PWM gating
  D1   at (270,80) DIR=0     — horizontal diode (from sec2)
  C1   at (320,80) DIR=90    — output capacitor
  R1   at (370,80) DIR=90    — load resistor
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
_FLYBACK_ROLE_POSITIONS: dict[str, tuple[int, int, int, str]] = {
    "input_source": (80, 80, 0, "dc_source_vertical"),
    "ground_ref": (80, 230, 0, "ground"),
    "isolation_transformer": (200, 80, 0, "transformer_vertical"),
    "primary_switch": (200, 130, 0, "mosfet_vertical"),
    "gate_drive": (160, 160, 0, "pwm_block"),
    "secondary_rectifier": (270, 80, 0, "diode_horizontal"),
    "output_capacitor": (320, 80, 90, "capacitor_vertical"),
    "load": (370, 80, 90, "resistor_vertical"),
}

_ROLE_TO_REGION: dict[str, str] = {
    "input_source": "primary_region",
    "ground_ref": "primary_region",
    "isolation_transformer": "primary_region",
    "primary_switch": "primary_region",
    "gate_drive": "primary_region",
    "secondary_rectifier": "secondary_region",
    "output_capacitor": "secondary_region",
    "load": "secondary_region",
}

_FALLBACK_X = 450
_FALLBACK_Y = 200


class FlybackLayoutStrategy:
    """Layout strategy for flyback converter topology."""

    def build_layout(
        self,
        graph: CircuitGraph,
        preferences: dict[str, object] | None = None,
    ) -> SchematicLayout:
        components: list[LayoutComponent] = []
        fallback_offset = 0

        for gc in graph.components:
            role = gc.role or ""
            pos_info = _FLYBACK_ROLE_POSITIONS.get(role)
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
                    region_id=_ROLE_TO_REGION.get(role, "secondary_region"),
                )
            )

        regions = [
            LayoutRegion(
                id="primary_region", role="primary",
                x=60, y=60, width=200, height=200,
            ),
            LayoutRegion(
                id="secondary_region", role="secondary",
                x=260, y=60, width=160, height=120,
            ),
        ]

        constraints = [
            LayoutConstraint(kind="left_of", subject_ids=["primary_region", "secondary_region"]),
            LayoutConstraint(kind="align_to_rail", subject_ids=["net_sw_gnd"], value={"y": 230}),
        ]

        return SchematicLayout(
            topology="flyback",
            components=components,
            regions=regions,
            constraints=constraints,
            metadata={
                "flow_direction": "left_to_right",
                "primary_ground_y": 230,
                "isolation_boundary_x": 250,
            },
        )
