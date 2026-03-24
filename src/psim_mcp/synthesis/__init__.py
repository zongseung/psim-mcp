"""Synthesis layer -- canonical circuit synthesis pipeline.

Provides:
- Data models (SizedComponentSpec, NetSpec, TopologySynthesisResult, etc.)
- Sizing formulas (size_buck, size_flyback, size_llc)
- CircuitGraph representation
- Graph builder helpers
- Topology-specific synthesizers
"""

from .graph import (
    CircuitGraph,
    DesignDecisionTrace,
    FunctionalBlock,
    GraphComponent,
    GraphNet,
)
from .graph_builders import make_block, make_component, make_net, make_trace
from .models import (
    DesignSessionV1,
    LegacyRenderableCircuit,
    NetSpec,
    PreviewPayloadV1,
    SizedComponentSpec,
    TopologySynthesisResult,
)
from .sizing import size_buck, size_flyback, size_llc
from .topologies.buck import synthesize_buck
from .topologies.flyback import synthesize_flyback
from .topologies.llc import synthesize_llc

__all__ = [
    # Graph
    "CircuitGraph",
    "DesignDecisionTrace",
    "FunctionalBlock",
    "GraphComponent",
    "GraphNet",
    # Graph builders
    "make_block",
    "make_component",
    "make_net",
    "make_trace",
    # Models
    "DesignSessionV1",
    "LegacyRenderableCircuit",
    "NetSpec",
    "PreviewPayloadV1",
    "SizedComponentSpec",
    "TopologySynthesisResult",
    # Sizing
    "size_buck",
    "size_flyback",
    "size_llc",
    # Topology synthesizers
    "synthesize_buck",
    "synthesize_flyback",
    "synthesize_llc",
]
