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

    def test_opens_after_max_failures(self, adapter: RealPsimAdapter):
        for i in range(_MAX_CONSECUTIVE_FAILURES):
            adapter._record_failure(f"error-{i}")

        assert adapter._circuit_state is CircuitState.OPEN
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


class TestLockTimeout:
    async def test_lock_acquisition_timeout(self, adapter: RealPsimAdapter):
        """When the lock is held by another coroutine, _call_bridge should time out."""
        # Hold the lock
        await adapter._lock.acquire()

        try:
            with (
                patch.object(
                    adapter,
                    "_check_circuit_breaker",
                    return_value=None,
                ),
                pytest.raises(RuntimeError, match="Could not acquire bridge lock"),
            ):
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

    async def test_non_owner_call_is_busy_during_session_lease(
        self,
        adapter: RealPsimAdapter,
        tmp_path,
    ) -> None:
        # Given / When
        async with adapter.session_lease(str(tmp_path)):
            # Then
            with pytest.raises(RuntimeError, match="SESSION_BUSY"):
                await adapter._call_bridge("get_status")


class TestMetrics:
    def test_failure_tracking(self, adapter: RealPsimAdapter):
        adapter._record_failure("timeout")
        adapter._record_failure("crash")

        assert adapter._consecutive_failures == 2


async def test_shutdown_clears_project_state_without_live_bridge(
    adapter: RealPsimAdapter,
) -> None:
    # Given
    adapter._project_open = True
    adapter._current_project_path = "stale.psimsch"
    adapter._last_output_path = "stale.smv"
    adapter._process = None

    # When
    await adapter.shutdown()

    # Then
    assert adapter.is_project_open is False
    assert adapter.current_project_path is None
    assert adapter._last_output_path == ""
