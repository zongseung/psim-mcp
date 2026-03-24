"""Layout Engine — converts CircuitGraph to SchematicLayout.

Determines component positions, orientations, and symbol variants
based on the algorithmic auto-layout engine.  Topology-specific
hardcoded strategies are kept as reference but no longer registered
as the primary path.  All topologies (including buck/flyback/llc)
now use the generic auto_place() engine by default.

Does NOT handle wire routing (that's Phase 4).
"""

from .engine import generate_layout, register_strategy
from .models import (
    LayoutComponent,
    LayoutConstraint,
    LayoutRegion,
    SchematicLayout,
)

# NOTE: Hardcoded strategies are intentionally NOT registered.
# All topologies now use the algorithmic auto_place() fallback in engine.py.
# The strategy files are kept as reference/comparison baselines.
#
# To re-enable a dedicated strategy for testing:
#   from .strategies.buck import BuckLayoutStrategy
#   register_strategy("buck", BuckLayoutStrategy())

__all__ = [
    "generate_layout",
    "register_strategy",
    "LayoutComponent",
    "LayoutConstraint",
    "LayoutRegion",
    "SchematicLayout",
]
