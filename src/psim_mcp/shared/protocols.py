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


@runtime_checkable
class CircuitDesignServiceProtocol(Protocol):
    """Circuit design pipeline."""

    async def design_circuit(self, description: str) -> dict: ...

    async def continue_design(
        self,
        session_token: str,
        additional_specs: dict | None = None,
        additional_description: str | None = None,
    ) -> dict: ...

    async def preview_circuit(
        self,
        circuit_type: str,
        specs: dict | None = None,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> dict: ...

    async def confirm_circuit(
        self,
        save_path: str,
        preview_token: str | None = None,
        modifications: dict | None = None,
    ) -> dict: ...

    async def create_circuit_direct(
        self,
        circuit_type: str,
        save_path: str,
        components: list[dict] | None = None,
        connections: list[dict] | None = None,
        simulation_settings: dict | None = None,
    ) -> dict: ...

    def get_component_library(self, category: str | None = None) -> dict: ...

    def list_templates(self, category: str | None = None) -> dict: ...
