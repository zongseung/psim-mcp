"""Synthesis layer data models.

Contains the canonical data types for the synthesis pipeline:
- SizedComponentSpec: component with parameters but no position
- NetSpec: net with role and pins
- TopologySynthesisResult: complete synthesis output
- LegacyRenderableCircuit: backward-compatible format
- PreviewPayloadV1: unified preview payload
- DesignSessionV1: design session state
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field


@dataclass
class SizedComponentSpec:
    """A component with sizing parameters but NO position or direction."""

    id: str
    type: str
    role: str | None = None
    parameters: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class NetSpec:
    """A named net connecting component pins."""

    name: str
    pins: list[str]
    role: str | None = None


@dataclass
class TopologySynthesisResult:
    """Complete synthesis output -- components, nets, design parameters."""

    topology: str
    components: list[SizedComponentSpec]
    nets: list[NetSpec]
    metadata: dict[str, object] = field(default_factory=dict)
    simulation: dict[str, object] = field(default_factory=dict)
    design: dict[str, object] = field(default_factory=dict)
    schema_version: str = "1.0"


@dataclass
class LegacyRenderableCircuit:
    """Backward-compatible circuit format for SVG/bridge pipeline.

    Components and nets are plain dicts matching the generator output format.
    """

    topology: str
    components: list[dict]
    nets: list[dict]
    metadata: dict[str, object] = field(default_factory=dict)
    simulation: dict[str, object] = field(default_factory=dict)


@dataclass
class PreviewPayloadV1:
    """Unified preview payload carrying all pipeline artifacts.

    All fields beyond payload_kind and payload_version are optional,
    populated progressively as the pipeline advances.
    """

    payload_kind: str = "preview_payload"
    payload_version: str = "v1"
    circuit_type: str | None = None
    components: list[dict] | None = None
    connections: list[dict] | None = None
    nets: list[dict] | None = None
    wire_segments: list[dict] | None = None
    synthesis_result: dict | None = None
    graph: dict | None = None
    layout: dict | None = None
    routing: dict | None = None
    psim_template: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> PreviewPayloadV1:
        return cls(**{
            k: v for k, v in data.items()
            if k in {f.name for f in dataclasses.fields(cls)}
        })


@dataclass
class DesignSessionV1:
    """Design session state for multi-turn circuit design."""

    payload_kind: str = "design_session"
    payload_version: str = "v1"
    topology: str | None = None
    specs: dict[str, object] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> DesignSessionV1:
        return cls(**{
            k: v for k, v in data.items()
            if k in {f.name for f in dataclasses.fields(cls)}
        })
