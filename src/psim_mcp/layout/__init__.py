"""Layout Engine — converts CircuitGraph to SchematicLayout.

Determines component positions, orientations, and symbol variants
based on topology-specific placement strategies.
Does NOT handle wire routing (that's Phase 4).
"""

from .engine import generate_layout, register_strategy
from .models import (
    LayoutComponent,
    LayoutConstraint,
    LayoutRegion,
    SchematicLayout,
)

# Auto-register built-in strategies
from .strategies.buck import BuckLayoutStrategy
from .strategies.flyback import FlybackLayoutStrategy
from .strategies.llc import LlcLayoutStrategy

register_strategy("buck", BuckLayoutStrategy())
register_strategy("flyback", FlybackLayoutStrategy())
register_strategy("llc", LlcLayoutStrategy())

__all__ = [
    "generate_layout",
    "register_strategy",
    "LayoutComponent",
    "LayoutConstraint",
    "LayoutRegion",
    "SchematicLayout",
    "BuckLayoutStrategy",
    "FlybackLayoutStrategy",
    "LlcLayoutStrategy",
]
