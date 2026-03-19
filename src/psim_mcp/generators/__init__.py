"""Topology generator registry.

Usage::

    from psim_mcp.generators import get_generator, list_generators

    gen = get_generator("buck")
    spec = gen.generate({"vin": 48, "vout_target": 12, "iout": 5})
"""

from __future__ import annotations

from .base import TopologyGenerator
from .buck import BuckGenerator
from .boost import BoostGenerator
from .buck_boost import BuckBoostGenerator
from .flyback import FlybackGenerator
from .forward import ForwardGenerator
from .cuk import CukGenerator
from .sepic import SepicGenerator
from .full_bridge import FullBridgeInverterGenerator
from .half_bridge import HalfBridgeInverterGenerator
from .llc import LLCGenerator
from .boost_pfc import BoostPFCGenerator
from .bidirectional_buck_boost import BidirectionalBuckBoostGenerator
from .constraints import validate_design_constraints, ConstraintResult

_REGISTRY: dict[str, TopologyGenerator] = {}


def register(generator: TopologyGenerator) -> None:
    """Register a generator instance under its topology name."""
    _REGISTRY[generator.topology_name] = generator


def get_generator(name: str) -> TopologyGenerator:
    """Return the generator registered for *name*, or raise ``KeyError``."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown topology '{name}'. Available: {available}")
    return _REGISTRY[name]


def list_generators() -> list[str]:
    """Return sorted list of registered topology names."""
    return sorted(_REGISTRY)


# Auto-register built-in generators
register(BuckGenerator())
register(BoostGenerator())
register(BuckBoostGenerator())
register(FlybackGenerator())
register(ForwardGenerator())
register(CukGenerator())
register(SepicGenerator())
register(FullBridgeInverterGenerator())
register(HalfBridgeInverterGenerator())
register(LLCGenerator())
register(BoostPFCGenerator())
register(BidirectionalBuckBoostGenerator())

__all__ = [
    "TopologyGenerator",
    "register",
    "get_generator",
    "list_generators",
    "validate_design_constraints",
    "ConstraintResult",
    "BuckGenerator",
    "BoostGenerator",
    "BuckBoostGenerator",
    "FlybackGenerator",
    "ForwardGenerator",
    "CukGenerator",
    "SepicGenerator",
    "FullBridgeInverterGenerator",
    "HalfBridgeInverterGenerator",
    "LLCGenerator",
    "BoostPFCGenerator",
    "BidirectionalBuckBoostGenerator",
]
