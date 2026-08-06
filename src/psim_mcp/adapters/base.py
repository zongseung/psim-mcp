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

    async def convert_to_python(self, path: str, output_path: str = "") -> dict:
        """Convert a ``.psimsch`` schematic into a PSIM Python script.

        The generated script (PsimCreateNewElement calls) is the only complete
        text representation of an existing schematic — element listing omits
        wires, positions, and node indices. Used by the importer pipeline.

        Args:
            path: Absolute path to the ``.psimsch`` file.
            output_path: Where to write the generated script; adapter picks a
                temp location when empty.

        Returns:
            Dict with ``script_path`` and ``script_text``.
        """
        raise NotImplementedError(f"{type(self).__name__} does not support convert_to_python.")
