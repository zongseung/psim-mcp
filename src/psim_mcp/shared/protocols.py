"""Service interface definitions.

All inter-service dependencies are expressed through the Protocols defined
here.  Depending on interfaces (not concrete classes) ensures testability
and allows implementations to be swapped freely.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProjectServiceProtocol(Protocol):
    """Project lifecycle management."""

    async def open_project(self, path: str) -> dict: ...

    async def get_project_info(self) -> dict: ...

    async def get_status(self) -> dict: ...

    @property
    def is_project_open(self) -> bool: ...


@runtime_checkable
class ParameterServiceProtocol(Protocol):
    """Component parameter management."""

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict: ...

    async def sweep_parameter(
        self,
        component_id: str,
        parameter_name: str,
        start: float,
        end: float,
        steps: int,
    ) -> dict: ...


@runtime_checkable
class SimulationServiceProtocol(Protocol):
    """Simulation execution and result management."""

    async def run_simulation(self, options: dict | None = None) -> dict: ...

    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> dict: ...

    @property
    def last_simulation(self) -> dict | None: ...
