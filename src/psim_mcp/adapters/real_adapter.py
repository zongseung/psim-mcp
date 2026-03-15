"""Real PSIM adapter that delegates to a bridge script via subprocess."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from psim_mcp.adapters.base import BasePsimAdapter
from psim_mcp.config import AppConfig

# Bridge script lives inside this package
_BRIDGE_SCRIPT = str(Path(__file__).resolve().parent.parent / "bridge" / "bridge_script.py")

logger = logging.getLogger(__name__)


class RealPsimAdapter(BasePsimAdapter):
    """Adapter that communicates with PSIM through a Python bridge script.

    The bridge script is executed as a subprocess using the PSIM-bundled
    Python interpreter.  Communication uses JSON over stdin/stdout.
    """

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._python_exe = str(config.psim_python_exe) if config.psim_python_exe else "python"
        self._bridge_script = _BRIDGE_SCRIPT
        self._timeout = config.simulation_timeout
        self._psim_path = config.psim_path
        self._project_open = False

        # Startup validation: bridge script must exist
        if not Path(self._bridge_script).is_file():
            raise FileNotFoundError(
                f"Bridge script not found: {self._bridge_script}. "
                "The psim-mcp package may be corrupted or improperly installed."
            )

    @property
    def is_project_open(self) -> bool:
        return self._project_open

    # ------------------------------------------------------------------
    # Environment sanitisation
    # ------------------------------------------------------------------

    def _get_sanitized_env(self) -> dict[str, str]:
        """Create a minimal, sanitized environment for the PSIM subprocess.

        Only passes the minimum required environment variables to prevent
        information leakage and reduce attack surface.
        """
        env: dict[str, str] = {}
        # Only pass essential variables
        essential_vars = [
            "PATH",           # Required for subprocess execution
            "SystemRoot",     # Required on Windows
            "TEMP", "TMP",    # Temp directories
            "HOME", "USERPROFILE",  # Home directory
            "PSIM_PATH",      # PSIM installation
        ]
        for var in essential_vars:
            val = os.environ.get(var)
            if val is not None:
                env[var] = val

        # Add PSIM-specific paths if configured
        if self._psim_path:
            env["PSIM_PATH"] = str(self._psim_path)

        return env

    # ------------------------------------------------------------------
    # Internal bridge call
    # ------------------------------------------------------------------

    async def _call_bridge(self, action: str, params: dict[str, Any] | None = None) -> dict:
        """Invoke the bridge script as a subprocess.

        Args:
            action: The action name (e.g. ``"open_project"``).
            params: Optional parameter dict passed as JSON via stdin.

        Returns:
            Parsed JSON response from the bridge script.

        Raises:
            TimeoutError: If the subprocess exceeds the configured timeout.
            RuntimeError: If the subprocess exits with a non-zero code or
                returns invalid JSON.
        """
        payload = json.dumps({"action": action, "params": params or {}})
        cmd = [self._python_exe, self._bridge_script]

        logger.debug("Bridge call: action=%s params=%s", action, params)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._get_sanitized_env(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=payload.encode()),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            logger.error("Bridge call timed out: action=%s", action)
            raise TimeoutError(
                f"PSIM bridge timed out after {self._timeout}s for action '{action}'"
            ) from None
        except FileNotFoundError as exc:
            logger.error("Bridge executable not found: %s", cmd)
            raise RuntimeError(
                f"PSIM Python executable not found: {self._python_exe}. "
                "Ensure psim_python_exe is set correctly in the configuration."
            ) from exc

        # Always log stderr (but never return it to the user)
        stderr_text = stderr.decode(errors="replace").strip()
        if stderr_text:
            logger.debug("Bridge stderr output: %s", stderr_text)

        if proc.returncode != 0:
            logger.error("Bridge returned non-zero exit code %d: %s", proc.returncode, stderr_text)
            raise RuntimeError(
                f"PSIM bridge exited with code {proc.returncode}"
            )

        try:
            result = json.loads(stdout.decode())
        except json.JSONDecodeError as exc:
            logger.error("Bridge returned invalid JSON: %s", stdout[:500])
            raise RuntimeError(
                f"PSIM bridge returned invalid JSON for action '{action}': {exc}"
            ) from exc

        return result

    # ------------------------------------------------------------------
    # BasePsimAdapter interface
    # ------------------------------------------------------------------

    async def open_project(self, path: str) -> dict:
        """Open a PSIM project via the bridge."""
        result = await self._call_bridge("open_project", {"path": path})
        self._project_open = True
        return result

    async def set_parameter(
        self,
        component_id: str,
        parameter_name: str,
        value: int | float | str,
    ) -> dict:
        """Set a component parameter via the bridge."""
        return await self._call_bridge(
            "set_parameter",
            {
                "component_id": component_id,
                "parameter_name": parameter_name,
                "value": value,
            },
        )

    async def run_simulation(self, options: dict | None = None) -> dict:
        """Run a simulation via the bridge."""
        return await self._call_bridge("run_simulation", {"options": options or {}})

    async def export_results(
        self,
        output_dir: str,
        format: str = "json",
        signals: list[str] | None = None,
    ) -> dict:
        """Export results via the bridge."""
        return await self._call_bridge(
            "export_results",
            {
                "output_dir": output_dir,
                "format": format,
                "signals": signals,
            },
        )

    async def get_status(self) -> dict:
        """Query PSIM status via the bridge."""
        return await self._call_bridge("get_status")

    async def get_project_info(self) -> dict:
        """Query project info via the bridge."""
        return await self._call_bridge("get_project_info")

    async def create_circuit(
        self,
        circuit_type: str,
        components: list[dict],
        connections: list[dict],
        save_path: str,
        simulation_settings: dict | None = None,
    ) -> dict:
        """Create a circuit schematic via the bridge (uses psimapipy)."""
        result = await self._call_bridge(
            "create_circuit",
            {
                "circuit_type": circuit_type,
                "components": components,
                "connections": connections,
                "save_path": save_path,
                "simulation_settings": simulation_settings,
            },
        )
        self._project_open = True
        return result
