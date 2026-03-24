"""CircuitGraph — topology-independent circuit representation.

A CircuitGraph holds components, nets, and functional blocks with
roles and parameters, but NO positions, directions, or port coordinates.
Layout is determined separately by the Layout Engine (Phase 3).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


@dataclass
class GraphComponent:
    """A circuit component with role and parameters, but no position."""

    id: str
    type: str
    role: str | None = None
    parameters: dict[str, object] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    block_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class GraphNet:
    """A named net connecting component pins."""

    id: str
    pins: list[str]
    role: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class FunctionalBlock:
    """A logical grouping of components (e.g. input_stage, output_filter)."""

    id: str
    type: str
    role: str | None = None
    component_ids: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class DesignDecisionTrace:
    """Records a design decision for traceability."""

    source: str
    key: str
    value: object
    confidence: float | None = None
    rationale: str | None = None


@dataclass
class CircuitGraph:
    """Complete circuit representation without layout information."""

    topology: str
    components: list[GraphComponent]
    nets: list[GraphNet]
    blocks: list[FunctionalBlock] = field(default_factory=list)
    design: dict[str, object] = field(default_factory=dict)
    simulation: dict[str, object] = field(default_factory=dict)
    traces: list[DesignDecisionTrace] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> CircuitGraph:
        return cls(
            topology=data["topology"],
            components=[GraphComponent(**c) for c in data.get("components", [])],
            nets=[GraphNet(**n) for n in data.get("nets", [])],
            blocks=[FunctionalBlock(**b) for b in data.get("blocks", [])],
            design=data.get("design", {}),
            simulation=data.get("simulation", {}),
            traces=[DesignDecisionTrace(**t) for t in data.get("traces", [])],
            metadata=data.get("metadata", {}),
        )

    def get_component(self, component_id: str) -> GraphComponent | None:
        return next((c for c in self.components if c.id == component_id), None)

    def get_net(self, net_id: str) -> GraphNet | None:
        return next((n for n in self.nets if n.id == net_id), None)

    def get_block(self, block_id: str) -> FunctionalBlock | None:
        return next((b for b in self.blocks if b.id == block_id), None)

    def components_in_block(self, block_id: str) -> list[GraphComponent]:
        return [c for c in self.components if block_id in c.block_ids]
