"""Abstract base class for PSIM adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BasePsimAdapter(ABC):
    """Contract that every PSIM adapter must satisfy.

    The service layer programs against this interface so that the concrete
    backend (mock on macOS, real on Windows) can be swapped via configuration.
    """

    @abstractmethod
    async def open_project(self, path: str) -> dict:
        """Open a PSIM project file.

        Args:
            path: Absolute filesystem path to the ``.psimsch`` file.

        Returns:
            Dict with project metadata (name, path, components, counts).
        """

    @abstractmethod
    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Set a single parameter on a component.

        Args:
            component_id: Identifier of the target component.
            parameter_name: Name of the parameter to update.
            value: New value (numeric or string).

        Returns:
            Dict with previous_value, new_value, and unit.

        Raises:
            ValueError: If the component or parameter is not found.
        """

    @abstractmethod
    async def run_simulation(self, options: dict | None = None) -> dict:
        """Execute the simulation for the currently open project.

        Args:
            options: Optional overrides (time_step, total_time, etc.).

        Returns:
            Dict with status, duration, result_file, and summary.
        """

    @abstractmethod
    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
        graph_file: str = "",
    ) -> dict:
        """Export simulation results to disk.

        Args:
            output_dir: Directory where files will be written.
            format: ``"json"`` or ``"csv"``.
            signals: Specific signal names to export; *None* means all.
            graph_file: Optional path to the simulation result file (.smv).

        Returns:
            Dict with list of exported files and metadata.
        """

    @abstractmethod
    async def extract_signals(
        self,
        graph_file: str = "",
        signals: list[str] | None = None,
        skip_ratio: float = 0.0,
        max_points: int = 2000,
    ) -> dict:
        """Extract signal waveforms from the latest simulation result.

        Args:
            graph_file: Optional path to the simulation result file (``.smv``).
            signals: Specific signal names to return; *None* means all.
            skip_ratio: Fraction of the waveform to skip from the start.
            max_points: Maximum number of samples per signal.

        Returns:
            Dict with ``signals``, ``signal_names``, and metadata.
        """

    @abstractmethod
    async def compute_metrics(
        self,
        metrics_spec: list[dict],
        graph_file: str = "",
        skip_ratio: float = 0.5,
        time_step: float = 1e-6,
    ) -> dict:
        """Compute simulation metrics from the latest simulation result.

        Args:
            metrics_spec: Metric definitions containing ``name``, ``signal``,
                and ``function`` fields.
            graph_file: Optional path to the simulation result file (``.smv``).
            skip_ratio: Fraction of initial samples to ignore.
            time_step: Simulation time step used for time-domain metrics.

        Returns:
            Dict with computed metric values and available signals.
        """

    @abstractmethod
    async def get_status(self) -> dict:
        """Return the current adapter / PSIM status."""

    @property
    @abstractmethod
    def is_project_open(self) -> bool:
        """Return True if a project is currently loaded."""

    @abstractmethod
    async def get_project_info(self) -> dict:
        """Return detailed information about the currently open project.

        Raises:
            RuntimeError: If no project is open.
        """

    async def shutdown(self) -> None:
        """Gracefully shut down the adapter and release resources.

        기본 구현은 아무 작업도 하지 않는다. 서브클래스에서 필요 시 오버라이드.
        """

    @abstractmethod
    async def create_circuit(
        self,
        circuit_type: str,
        components: list[dict],
        connections: list[dict],
        save_path: str,
        wire_segments: list[dict] | None = None,
        simulation_settings: dict | None = None,
        psim_template: dict | None = None,
    ) -> dict:
        """Create a new PSIM circuit schematic programmatically.

        Args:
            circuit_type: Type of circuit (e.g. ``"buck"``, ``"boost"``, ``"custom"``).
            components: List of component dicts with id, type, parameters, and position.
            connections: List of connection dicts specifying wiring between components.
            save_path: Filesystem path where the ``.psimsch`` file will be saved.
            simulation_settings: Optional dict with time_step, total_time, etc.

        Returns:
            Dict with created file path, component count, and connection count.
        """
