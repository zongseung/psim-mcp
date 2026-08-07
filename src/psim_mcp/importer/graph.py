"""CircuitGraph — importer representation of an existing circuit.

Holds components and electrical nets reconstructed from PSIM conversion
output, with parameters and metadata but no layout information.
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
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class GraphNet:
    """A named net connecting component pins."""

    id: str
    pins: list[str]
    role: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class CircuitGraph:
    """Complete circuit representation without layout information."""

    topology: str
    components: list[GraphComponent]
    nets: list[GraphNet]
    simulation: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def get_net(self, net_id: str) -> GraphNet | None:
        return next((n for n in self.nets if n.id == net_id), None)
