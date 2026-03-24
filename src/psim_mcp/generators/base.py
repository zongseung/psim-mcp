"""Abstract base class for topology generators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from psim_mcp.synthesis.graph import CircuitGraph


class TopologyGenerator(ABC):
    """Base class that every topology generator must implement."""

    @abstractmethod
    def generate(self, requirements: dict) -> dict:
        """Generate circuit components, nets, and positions from requirements.

        Returns a dict with keys:
            topology, metadata, components, nets, simulation
        """

    def synthesize(self, requirements: dict) -> CircuitGraph:
        """Synthesize a CircuitGraph from requirements.

        The default implementation raises NotImplementedError.
        Generators with synthesis support override this to delegate
        to their topology-specific synthesizer.
        """
        raise NotImplementedError(
            f"Generator '{self.topology_name}' does not support synthesis. "
            "Override synthesize() or use the topology synthesizer directly."
        )

    @property
    @abstractmethod
    def topology_name(self) -> str:
        """Short identifier for the topology (e.g. 'buck')."""

    @property
    @abstractmethod
    def required_fields(self) -> list[str]:
        """List of required fields in *requirements* (e.g. ['vin', 'vout_target'])."""

    @property
    def optional_fields(self) -> list[str]:
        """List of optional fields in *requirements*."""
        return []

    def missing_fields(self, requirements: dict) -> list[str]:
        """Return list of required fields not present in *requirements*."""
        return [f for f in self.required_fields if not requirements.get(f)]
