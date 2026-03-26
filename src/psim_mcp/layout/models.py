"""Layout data models — SchematicLayout and supporting types."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


@dataclass
class LayoutComponent:
    """A component with determined position and orientation."""

    id: str
    x: int
    y: int
    direction: int
    symbol_variant: str | None = None
    region_id: str | None = None
    anchor_policy: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class LayoutRegion:
    """A logical area grouping related components."""

    id: str
    role: str
    x: int
    y: int
    width: int
    height: int
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class LayoutConstraint:
    """A placement constraint between components or regions."""

    kind: str  # same_row, same_column, left_of, right_of, inside_region, align_to_rail
    subject_ids: list[str]
    value: object = None
    priority: str = "normal"  # normal | high | low


@dataclass
class SchematicLayout:
    """Complete schematic layout — the output of LayoutEngine."""

    topology: str
    components: list[LayoutComponent]
    regions: list[LayoutRegion] = field(default_factory=list)
    constraints: list[LayoutConstraint] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    layout_version: str = "1.0"

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SchematicLayout:
        return cls(
            topology=data["topology"],
            components=[LayoutComponent(**c) for c in data.get("components", [])],
            regions=[LayoutRegion(**r) for r in data.get("regions", [])],
            constraints=[LayoutConstraint(**c) for c in data.get("constraints", [])],
            metadata=data.get("metadata", {}),
            layout_version=data.get("layout_version", "1.0"),
        )

    def get_component(self, component_id: str) -> LayoutComponent | None:
        return next((c for c in self.components if c.id == component_id), None)

    def get_region(self, region_id: str) -> LayoutRegion | None:
        return next((r for r in self.regions if r.id == region_id), None)
