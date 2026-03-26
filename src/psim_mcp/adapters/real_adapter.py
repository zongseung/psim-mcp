"""Real PSIM adapter that delegates to a bridge script via subprocess."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import os
import time
from enum import Enum
from pathlib import Path
from typing import Any

from psim_mcp.adapters.base import BasePsimAdapter
from psim_mcp.config import AppConfig

# Bridge script lives inside this package
_BRIDGE_SCRIPT = str(Path(__file__).resolve().parent.parent / "bridge" / "bridge_script.py")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Circuit breaker & resilience constants
# ---------------------------------------------------------------------------
_MAX_CONSECUTIVE_FAILURES = 5
_CIRCUIT_BREAKER_COOLDOWN = 30.0  # seconds before HALF_OPEN probe
_LOCK_ACQUIRE_TIMEOUT = 10.0     # seconds to wait for asyncio.Lock
_MAX_RESTARTS = 10               # lifetime restart cap


class CircuitState(Enum):
    """Three-state circuit breaker model (Nygard, *Release It!*)."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclasses.dataclass
class BridgeMetrics:
    """Observable operational metrics for the bridge subprocess."""
    restart_count: int = 0
    total_calls: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    circuit_state: str = "closed"
    last_error: str | None = None
    last_error_time: float | None = None


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

        # Circuit breaker state
        self._circuit_state: CircuitState = CircuitState.CLOSED
        self._circuit_opened_at: float | None = None
        self._consecutive_failures: int = 0
        self._total_restarts: int = 0
        self._metrics = BridgeMetrics()

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
    # Circuit breaker
    # ------------------------------------------------------------------

    def _check_circuit_breaker(self) -> None:
        """Raise if the circuit breaker is open and cooldown has not elapsed."""
        if self._circuit_state is CircuitState.CLOSED:
            return
        if self._circuit_state is CircuitState.OPEN:
            elapsed = time.monotonic() - (self._circuit_opened_at or 0.0)
            if elapsed >= _CIRCUIT_BREAKER_COOLDOWN:
                logger.info("Circuit breaker cooldown elapsed, transitioning to HALF_OPEN")
                self._circuit_state = CircuitState.HALF_OPEN
                self._metrics.circuit_state = CircuitState.HALF_OPEN.value
                return
            raise RuntimeError(
                f"Circuit breaker is OPEN — bridge failed {self._consecutive_failures} "
                f"consecutive times. Retry after {_CIRCUIT_BREAKER_COOLDOWN - elapsed:.0f}s."
            )
        # HALF_OPEN: allow one probe call through

    def _record_success(self) -> None:
        """Reset failure counters on a successful bridge call."""
        self._consecutive_failures = 0
        self._metrics.consecutive_failures = 0
        if self._circuit_state is CircuitState.HALF_OPEN:
            logger.info("Probe call succeeded, circuit breaker → CLOSED")
            self._circuit_state = CircuitState.CLOSED
            self._circuit_opened_at = None
            self._metrics.circuit_state = CircuitState.CLOSED.value

    def _record_failure(self, error: str) -> None:
        """Increment failure counters; open circuit breaker if threshold reached."""
        self._consecutive_failures += 1
        self._metrics.consecutive_failures = self._consecutive_failures
        self._metrics.failure_count += 1
        self._metrics.last_error = error
        self._metrics.last_error_time = time.monotonic()

        if self._consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
            logger.error(
                "Bridge failed %d consecutive times — opening circuit breaker",
                self._consecutive_failures,
            )
            self._circuit_state = CircuitState.OPEN
            self._circuit_opened_at = time.monotonic()
            self._metrics.circuit_state = CircuitState.OPEN.value

    def get_metrics(self) -> dict:
        """Return a snapshot of operational metrics."""
        return dataclasses.asdict(self._metrics)

    async def health_check(self) -> dict:
        """Proactive health assessment of the bridge subprocess."""
        process_alive = self._process is not None and self._process.returncode is None
        return {
            "healthy": self._circuit_state is CircuitState.CLOSED and process_alive,
            "circuit_state": self._circuit_state.value,
            "process_alive": process_alive,
            "metrics": self.get_metrics(),
        }

    # ------------------------------------------------------------------
    # Internal bridge call
    # ------------------------------------------------------------------

    async def _ensure_bridge(self) -> asyncio.subprocess.Process:
        """Bridge 프로세스가 살아있으면 재사용, 아니면 새로 시작한다."""
        if self._process is not None and self._process.returncode is None:
            return self._process

        if self._total_restarts >= _MAX_RESTARTS:
            raise RuntimeError(
                f"Bridge exceeded max restart limit ({_MAX_RESTARTS}). "
                "Manual intervention required — check PSIM installation and bridge_script.py."
            )

        self._total_restarts += 1
        self._metrics.restart_count = self._total_restarts

        logger.info(
            "Starting bridge process (%d/%d): %s %s",
            self._total_restarts, _MAX_RESTARTS,
            self._python_exe, self._bridge_script,
        )
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
            RuntimeError: If the bridge process dies, returns invalid JSON,
                or the circuit breaker is open.
        """
        self._metrics.total_calls += 1
        self._check_circuit_breaker()

        payload = json.dumps({"action": action, "params": params or {}})
        logger.debug("Bridge call: action=%s params=%s", action, params)

        # Acquire lock with timeout to prevent deadlock
        try:
            await asyncio.wait_for(self._lock.acquire(), timeout=_LOCK_ACQUIRE_TIMEOUT)
        except asyncio.TimeoutError:
            error_msg = (
                f"Could not acquire bridge lock within {_LOCK_ACQUIRE_TIMEOUT}s "
                f"for action '{action}' — a previous call may be hung."
            )
            self._record_failure(error_msg)
            raise RuntimeError(error_msg) from None

        try:
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
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                self._process = None
                error_msg = f"PSIM bridge timed out after {self._timeout}s for action '{action}'"
                self._record_failure(error_msg)
                raise TimeoutError(error_msg) from None

            if not raw:
                logger.error("Bridge returned empty response (process may have crashed)")
                self._process = None
                error_msg = (
                    f"PSIM bridge returned empty response for action '{action}'. "
                    "The bridge process may have crashed."
                )
                self._record_failure(error_msg)
                raise RuntimeError(error_msg)

            try:
                result = json.loads(raw.decode())
            except json.JSONDecodeError as exc:
                logger.error("Bridge returned invalid JSON: %s", raw[:500])
                error_msg = f"PSIM bridge returned invalid JSON for action '{action}': {exc}"
                self._record_failure(error_msg)
                raise RuntimeError(error_msg) from exc

            self._record_success()
            return result

        except (RuntimeError, TimeoutError):
            # Already recorded by failure handlers above; re-raise
            raise
        except Exception as exc:
            self._record_failure(str(exc))
            raise
        finally:
            self._lock.release()

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
        if result.get("success", False):
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
        nets: list[dict] | None = None,
    ) -> dict:
        """Create a circuit schematic via the bridge (uses psimapipy)."""
        params: dict = {
            "circuit_type": circuit_type,
            "components": components,
            "connections": connections,
            "wire_segments": wire_segments,
            "save_path": save_path,
            "simulation_settings": simulation_settings,
            "nets": nets,
        }
        if psim_template:
            params["psim_template"] = psim_template
        result = await self._call_bridge("create_circuit", params)
        if result.get("success", False):
            self._project_open = True
        return result
