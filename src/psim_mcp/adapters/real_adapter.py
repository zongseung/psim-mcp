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
        self._process: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()  # 동시 호출 방지
        self._stderr_task: asyncio.Task | None = None

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

        # Force UTF-8 encoding for the subprocess on Windows
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        return env

    # ------------------------------------------------------------------
    # Internal bridge call
    # ------------------------------------------------------------------

    async def _ensure_bridge(self) -> asyncio.subprocess.Process:
        """Bridge 프로세스가 살아있으면 재사용, 아니면 새로 시작한다."""
        if self._process is not None and self._process.returncode is None:
            return self._process

        logger.info("Starting new bridge process: %s %s", self._python_exe, self._bridge_script)
        cmd = [self._python_exe, self._bridge_script]

        try:
            self._process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._get_sanitized_env(),
            )
        except FileNotFoundError as exc:
            logger.error("Bridge executable not found: %s", cmd)
            raise RuntimeError(
                f"PSIM Python executable not found: {self._python_exe}. "
                "Ensure psim_python_exe is set correctly in the configuration."
            ) from exc

        # Drain stderr in the background to prevent pipe buffer deadlock
        self._stderr_task = asyncio.create_task(self._drain_stderr(self._process))

        return self._process

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
        """Continuously read stderr from the bridge process and log it."""
        try:
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                msg = line.decode("utf-8", errors="replace").rstrip()
                if msg:
                    logger.warning("Bridge stderr: %s", msg)
        except Exception:
            pass

    async def _call_bridge(self, action: str, params: dict[str, Any] | None = None) -> dict:
        """장기 실행 Bridge 프로세스에 명령을 보내고 응답을 받는다.

        Args:
            action: The action name (e.g. ``"open_project"``).
            params: Optional parameter dict passed as JSON via stdin.

        Returns:
            Parsed JSON response from the bridge script.

        Raises:
            TimeoutError: If the response exceeds the configured timeout.
            RuntimeError: If the bridge process dies or returns invalid JSON.
        """
        payload = json.dumps({"action": action, "params": params or {}})

        logger.debug("Bridge call: action=%s params=%s", action, params)

        async with self._lock:
            proc = await self._ensure_bridge()

            # Bridge 프로세스가 종료된 경우 자동 재시작
            if proc.returncode is not None:
                logger.warning("Bridge process died (rc=%d), restarting...", proc.returncode)
                if self._stderr_task and not self._stderr_task.done():
                    self._stderr_task.cancel()
                self._process = None
                proc = await self._ensure_bridge()

            try:
                proc.stdin.write((payload + "\n").encode())
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError) as exc:
                logger.warning("Bridge stdin write failed, restarting: %s", exc)
                self._process = None
                proc = await self._ensure_bridge()
                proc.stdin.write((payload + "\n").encode())
                await proc.stdin.drain()

            try:
                raw = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=self._timeout,
                )
            except asyncio.TimeoutError:
                logger.error("Bridge call timed out: action=%s", action)
                # 타임아웃 시 프로세스를 종료하고 다음 호출에서 재시작
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                self._process = None
                raise TimeoutError(
                    f"PSIM bridge timed out after {self._timeout}s for action '{action}'"
                ) from None

            if not raw:
                # 빈 응답 = 프로세스가 종료됨
                logger.error("Bridge returned empty response (process may have crashed)")
                self._process = None
                raise RuntimeError(
                    f"PSIM bridge returned empty response for action '{action}'. "
                    "The bridge process may have crashed."
                )

            try:
                result = json.loads(raw.decode())
            except json.JSONDecodeError as exc:
                logger.error("Bridge returned invalid JSON: %s", raw[:500])
                raise RuntimeError(
                    f"PSIM bridge returned invalid JSON for action '{action}': {exc}"
                ) from exc

            return result

    async def shutdown(self) -> None:
        """MCP 서버 종료 시 Bridge 프로세스를 정리한다."""
        if self._process is not None and self._process.returncode is None:
            logger.info("Shutting down bridge process (pid=%d)", self._process.pid)
            try:
                self._process.stdin.close()
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Bridge process did not exit gracefully, killing...")
                try:
                    self._process.kill()
                except ProcessLookupError:
                    pass
            except Exception:
                logger.exception("Error during bridge shutdown")
            finally:
                self._process = None

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
        graph_file: str = "",
    ) -> dict:
        """Export results via the bridge."""
        return await self._call_bridge(
            "export_results",
            {
                "output_dir": output_dir,
                "format": format,
                "signals": signals,
                "graph_file": graph_file,
            },
        )

    async def extract_signals(
        self,
        graph_file: str = "",
        signals: list[str] | None = None,
        skip_ratio: float = 0.0,
        max_points: int = 2000,
    ) -> dict:
        """Extract waveform samples via the bridge."""
        result = await self._call_bridge(
            "extract_signals",
            {
                "graph_file": graph_file,
                "signals": signals,
                "skip_ratio": skip_ratio,
                "max_points": max_points,
            },
        )
        return result.get("data", result)

    async def compute_metrics(
        self,
        metrics_spec: list[dict],
        graph_file: str = "",
        skip_ratio: float = 0.5,
        time_step: float = 1e-6,
    ) -> dict:
        """Compute simulation metrics via the bridge."""
        result = await self._call_bridge(
            "compute_metrics",
            {
                "graph_file": graph_file,
                "metrics": metrics_spec,
                "skip_ratio": skip_ratio,
                "time_step": time_step,
            },
        )
        return result.get("data", result)

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
        wire_segments: list[dict] | None = None,
        simulation_settings: dict | None = None,
        psim_template: dict | None = None,
    ) -> dict:
        """Create a circuit schematic via the bridge (uses psimapipy)."""
        params: dict = {
            "circuit_type": circuit_type,
            "components": components,
            "connections": connections,
            "wire_segments": wire_segments,
            "save_path": save_path,
            "simulation_settings": simulation_settings,
        }
        if psim_template:
            params["psim_template"] = psim_template
        result = await self._call_bridge("create_circuit", params)
        self._project_open = True
        return result
