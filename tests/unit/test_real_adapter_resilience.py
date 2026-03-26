"""Unit tests for RealPsimAdapter circuit breaker, lock timeout, and metrics."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from psim_mcp.adapters.real_adapter import (
    CircuitState,
    RealPsimAdapter,
    _CIRCUIT_BREAKER_COOLDOWN,
    _MAX_CONSECUTIVE_FAILURES,
    _MAX_RESTARTS,
)
from psim_mcp.config import AppConfig


@pytest.fixture
def adapter(tmp_path) -> RealPsimAdapter:
    """Create a RealPsimAdapter with bridge_script validation bypassed."""
    # Write a dummy bridge script so the FileNotFoundError check passes
    fake_bridge = tmp_path / "bridge_script.py"
    fake_bridge.write_text("# dummy")

    config = AppConfig(
        psim_mode="real",
        psim_python_exe="python",
        psim_path=str(tmp_path),
        psim_project_dir=tmp_path / "projects",
        psim_output_dir=tmp_path / "output",
    )
    with patch(
        "psim_mcp.adapters.real_adapter._BRIDGE_SCRIPT",
        str(fake_bridge),
    ):
        return RealPsimAdapter(config)


class TestCircuitBreaker:
    def test_initial_state_is_closed(self, adapter: RealPsimAdapter):
        assert adapter._circuit_state is CircuitState.CLOSED
        assert adapter._consecutive_failures == 0
        assert adapter._metrics.circuit_state == "closed"

    def test_opens_after_max_failures(self, adapter: RealPsimAdapter):
        for i in range(_MAX_CONSECUTIVE_FAILURES):
            adapter._record_failure(f"error-{i}")

        assert adapter._circuit_state is CircuitState.OPEN
        assert adapter._metrics.circuit_state == "open"
        assert adapter._metrics.failure_count == _MAX_CONSECUTIVE_FAILURES
        assert adapter._circuit_opened_at is not None

    def test_rejects_calls_when_open(self, adapter: RealPsimAdapter):
        for i in range(_MAX_CONSECUTIVE_FAILURES):
            adapter._record_failure(f"error-{i}")

        with pytest.raises(RuntimeError, match="Circuit breaker is OPEN"):
            adapter._check_circuit_breaker()

    def test_transitions_to_half_open_after_cooldown(self, adapter: RealPsimAdapter):
        for i in range(_MAX_CONSECUTIVE_FAILURES):
            adapter._record_failure(f"error-{i}")

        # Simulate cooldown elapsed
        adapter._circuit_opened_at = time.monotonic() - _CIRCUIT_BREAKER_COOLDOWN - 1.0

        # Should NOT raise — transitions to HALF_OPEN
        adapter._check_circuit_breaker()
        assert adapter._circuit_state is CircuitState.HALF_OPEN

    def test_closes_on_success_from_half_open(self, adapter: RealPsimAdapter):
        adapter._circuit_state = CircuitState.HALF_OPEN
        adapter._consecutive_failures = _MAX_CONSECUTIVE_FAILURES

        adapter._record_success()

        assert adapter._circuit_state is CircuitState.CLOSED
        assert adapter._consecutive_failures == 0
        assert adapter._circuit_opened_at is None

    def test_success_resets_consecutive_failures(self, adapter: RealPsimAdapter):
        adapter._record_failure("err-1")
        adapter._record_failure("err-2")
        assert adapter._consecutive_failures == 2

        adapter._record_success()
        assert adapter._consecutive_failures == 0
        # Total failure count is cumulative, NOT reset
        assert adapter._metrics.failure_count == 2


class TestMaxRestarts:
    async def test_raises_after_max_restarts(self, adapter: RealPsimAdapter):
        adapter._total_restarts = _MAX_RESTARTS

        with pytest.raises(RuntimeError, match="max restart limit"):
            await adapter._ensure_bridge()

    async def test_restart_counter_increments(self, adapter: RealPsimAdapter):
        adapter._process = None

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = None
            mock_proc.stderr = AsyncMock()
            mock_proc.stderr.readline = AsyncMock(return_value=b"")
            mock_exec.return_value = mock_proc

            await adapter._ensure_bridge()
            assert adapter._total_restarts == 1
            assert adapter._metrics.restart_count == 1


class TestLockTimeout:
    async def test_lock_acquisition_timeout(self, adapter: RealPsimAdapter):
        """When the lock is held by another coroutine, _call_bridge should time out."""
        # Hold the lock
        await adapter._lock.acquire()

        try:
            with patch.object(
                adapter, "_check_circuit_breaker", return_value=None,
            ), pytest.raises(RuntimeError, match="Could not acquire bridge lock"):
                # Use a very short timeout for the test
                import psim_mcp.adapters.real_adapter as mod
                original = mod._LOCK_ACQUIRE_TIMEOUT
                mod._LOCK_ACQUIRE_TIMEOUT = 0.1
                try:
                    await adapter._call_bridge("test_action")
                finally:
                    mod._LOCK_ACQUIRE_TIMEOUT = original
        finally:
            adapter._lock.release()


class TestMetrics:
    def test_initial_metrics(self, adapter: RealPsimAdapter):
        m = adapter.get_metrics()
        assert m["restart_count"] == 0
        assert m["total_calls"] == 0
        assert m["failure_count"] == 0
        assert m["consecutive_failures"] == 0
        assert m["circuit_state"] == "closed"
        assert m["last_error"] is None

    def test_failure_tracking(self, adapter: RealPsimAdapter):
        adapter._record_failure("timeout")
        adapter._record_failure("crash")

        m = adapter.get_metrics()
        assert m["failure_count"] == 2
        assert m["consecutive_failures"] == 2
        assert m["last_error"] == "crash"
        assert m["last_error_time"] is not None

    async def test_health_check_healthy(self, adapter: RealPsimAdapter):
        # Simulate a live process
        mock_proc = AsyncMock()
        mock_proc.returncode = None
        adapter._process = mock_proc

        result = await adapter.health_check()
        assert result["healthy"] is True
        assert result["circuit_state"] == "closed"
        assert result["process_alive"] is True

    async def test_health_check_unhealthy_open_breaker(self, adapter: RealPsimAdapter):
        adapter._circuit_state = CircuitState.OPEN

        result = await adapter.health_check()
        assert result["healthy"] is False
        assert result["circuit_state"] == "open"

    async def test_health_check_unhealthy_no_process(self, adapter: RealPsimAdapter):
        adapter._process = None

        result = await adapter.health_check()
        assert result["healthy"] is False
        assert result["process_alive"] is False
