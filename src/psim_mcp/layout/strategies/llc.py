"""LLC resonant converter layout strategy.

Position mapping derived from generators/llc.py:
  V1   at (80,80) DIR=0     — DC source
  GND1 at (80,230) DIR=0    — primary ground
  GND2 at (490,230) DIR=0   — secondary ground
  SW1  at (200,80) DIR=0    — high-side MOSFET vertical
  SW2  at (200,160) DIR=0   — low-side MOSFET vertical
  G1   at (160,110) DIR=0   — high-side gate
  G2   at (160,190) DIR=0   — low-side gate
  Cr   at (260,130) DIR=0   — resonant cap horizontal
  Lr   at (330,130) DIR=0   — resonant inductor horizontal
  Lm   at (400,130) DIR=90  — magnetizing inductor vertical
  T1   at (420,130) DIR=0   — ideal transformer
  BD1  at (490,130) DIR=0   — diode bridge rectifier
  Cout at (600,130) DIR=90  — output capacitor
  R1   at (650,130) DIR=90  — load resistor
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
_LLC_ROLE_POSITIONS: dict[str, tuple[int, int, int, str]] = {
    "input_source": (80, 80, 0, "dc_source_vertical"),
    "ground_ref": (80, 230, 0, "ground"),
    "secondary_ground_ref": (490, 230, 0, "ground"),
    "high_side_switch": (200, 80, 0, "mosfet_vertical"),
    "low_side_switch": (200, 160, 0, "mosfet_vertical"),
    "high_side_gate": (160, 110, 0, "pwm_block"),
    "low_side_gate": (160, 190, 0, "pwm_block"),
    "resonant_capacitor": (260, 130, 0, "capacitor_horizontal"),
    "resonant_inductor": (330, 130, 0, "inductor_horizontal"),
    "magnetizing_inductor": (400, 130, 90, "inductor_vertical"),
    "isolation_transformer": (420, 130, 0, "ideal_transformer"),
    "output_rectifier": (490, 130, 0, "diode_bridge"),
    "output_capacitor": (600, 130, 90, "capacitor_vertical"),
    "load": (650, 130, 90, "resistor_vertical"),
}

_ROLE_TO_REGION: dict[str, str] = {
    "input_source": "input_region",
    "ground_ref": "input_region",
    "high_side_switch": "half_bridge_region",
    "low_side_switch": "half_bridge_region",
    "high_side_gate": "half_bridge_region",
    "low_side_gate": "half_bridge_region",
    "resonant_capacitor": "resonant_region",
    "resonant_inductor": "resonant_region",
    "magnetizing_inductor": "magnetizing_region",
    "isolation_transformer": "transformer_region",
    "output_rectifier": "secondary_region",
    "secondary_ground_ref": "secondary_region",
    "output_capacitor": "output_region",
    "load": "output_region",
}

_FALLBACK_X = 700
_FALLBACK_Y = 200


class LlcLayoutStrategy:
    """Layout strategy for LLC resonant converter topology."""

    def build_layout(
        self,
        graph: CircuitGraph,
        preferences: dict[str, object] | None = None,
    ) -> SchematicLayout:
        components: list[LayoutComponent] = []
        fallback_offset = 0

        for gc in graph.components:
            role = gc.role or ""
            pos_info = _LLC_ROLE_POSITIONS.get(role)
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
            LayoutRegion(id="input_region", role="input", x=60, y=60, width=80, height=200),
            LayoutRegion(id="half_bridge_region", role="half_bridge", x=140, y=60, width=100, height=200),
            LayoutRegion(id="resonant_region", role="resonant", x=250, y=110, width=140, height=80),
            LayoutRegion(id="magnetizing_region", role="magnetizing", x=390, y=110, width=40, height=80),
            LayoutRegion(id="transformer_region", role="transformer", x=410, y=110, width=80, height=80),
            LayoutRegion(id="secondary_region", role="secondary", x=480, y=60, width=110, height=200),
            LayoutRegion(id="output_region", role="output", x=590, y=110, width=100, height=80),
        ]

        constraints = [
            LayoutConstraint(kind="left_of", subject_ids=["input_region", "half_bridge_region"]),
            LayoutConstraint(kind="left_of", subject_ids=["half_bridge_region", "resonant_region"]),
            LayoutConstraint(kind="left_of", subject_ids=["resonant_region", "transformer_region"]),
            LayoutConstraint(kind="left_of", subject_ids=["transformer_region", "secondary_region"]),
            LayoutConstraint(kind="left_of", subject_ids=["secondary_region", "output_region"]),
            LayoutConstraint(kind="align_to_rail", subject_ids=["net_gnd_pri"], value={"y": 230}),
            LayoutConstraint(kind="align_to_rail", subject_ids=["net_gnd_sec"], value={"y": 230}),
        ]

        return SchematicLayout(
            topology="llc",
            components=components,
            regions=regions,
            constraints=constraints,
            metadata={
                "flow_direction": "left_to_right",
                "primary_ground_y": 230,
                "secondary_ground_y": 230,
            },
        )
