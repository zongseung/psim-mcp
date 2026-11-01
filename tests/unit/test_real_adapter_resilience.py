"""Unit tests for RealPsimAdapter circuit breaker, lock timeout, and metrics."""

from __future__ import annotations

import sys
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


class TestSanitizedEnv:
    def test_passes_appdata_for_user_site_packages(self, adapter: RealPsimAdapter, monkeypatch):
        # APPDATA가 빠지면 브리지 Python이 사용자 site-packages의 psimapipy를 못 찾는다.
        monkeypatch.setenv("APPDATA", r"C:\Users\u\AppData\Roaming")
        monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\u\AppData\Local")

        env = adapter._get_sanitized_env()

        assert env["APPDATA"] == r"C:\Users\u\AppData\Roaming"
        assert env["LOCALAPPDATA"] == r"C:\Users\u\AppData\Local"

    def test_does_not_leak_unrelated_vars(self, adapter: RealPsimAdapter, monkeypatch):
        monkeypatch.setenv("SOME_SECRET_TOKEN", "x")

        env = adapter._get_sanitized_env()

        assert "SOME_SECRET_TOKEN" not in env

    @pytest.mark.parametrize(
        "name",
        [
            "ALM_HHWU",
            "ALTAIR_LICENSE_PATH",
            "LM_LICENSE_FILE",
            "COMPUTERNAME",
            "USERNAME",
            "USERDOMAIN",
            "ProgramData",
            "ProgramFiles",
            "ProgramFiles(x86)",
            "windir",
            "SystemDrive",
            "NUMBER_OF_PROCESSORS",
            "PROCESSOR_ARCHITECTURE",
        ],
    )
    def test_passes_license_and_windows_vars(self, adapter: RealPsimAdapter, monkeypatch, name):
        # ALM_HHWU가 빠지면 PSIM() 생성이 라이선스 확인에서 응답 없이 멈춘다.
        monkeypatch.setenv(name, "value-" + name)

        env = adapter._get_sanitized_env()

        assert {k.upper(): v for k, v in env.items()}[name.upper()] == "value-" + name

    @pytest.mark.parametrize("name", ["GITHUB_TOKEN", "ALMANAC_PASSWORD", "MY_ALTAIR_SECRET"])
    def test_does_not_pass_lookalike_secrets(self, adapter: RealPsimAdapter, monkeypatch, name):
        monkeypatch.setenv(name, "x")

        env = adapter._get_sanitized_env()

        assert name.upper() not in {k.upper() for k in env}


def _fake_bridge(tmp_path, body: str) -> str:
    script = tmp_path / "fake_bridge.py"
    script.write_text("import sys, time\nline = sys.stdin.readline()\n" + body)
    return str(script)


class TestGetStatusInitTimeout:
    async def test_returns_clear_error_when_psim_init_hangs(
        self, adapter: RealPsimAdapter, tmp_path, monkeypatch
    ):
        # Given: 라이선스 확인에서 멈춘 브리지(응답 없음)
        import psim_mcp.adapters.real_adapter as mod

        monkeypatch.setattr(mod, "_PSIM_INIT_TIMEOUT", 0.5)
        adapter._python_exe = sys.executable
        adapter._bridge_script = _fake_bridge(tmp_path, "time.sleep(30)\n")

        # When
        result = await adapter.get_status()

        # Then
        assert result["success"] is True
        assert result["data"]["psim_available"] is False
        assert result["data"]["error_code"] == "PSIM_INIT_TIMEOUT"
        assert "라이선스 확인 중 응답 없음" in result["data"]["error"]
        assert adapter._process is None  # 멈춘 브리지는 정리된다

    async def test_passes_through_normal_bridge_response(self, adapter: RealPsimAdapter, tmp_path):
        adapter._python_exe = sys.executable
        adapter._bridge_script = _fake_bridge(
            tmp_path,
            'print(\'{"success": true, "data": {"psim_available": true}}\', flush=True)\n'
            "sys.stdin.read()\n",  # shutdown()이 stdin을 닫으면 종료
        )

        try:
            result = await adapter.get_status()
        finally:
            await adapter.shutdown()

        assert result == {"success": True, "data": {"psim_available": True}}

    async def test_other_actions_keep_simulation_timeout(self, adapter: RealPsimAdapter):
        seen = {}

        async def fake_transport(action, params=None, timeout=None):
            seen["timeout"] = timeout
            return {"success": True, "data": {}}

        with patch.object(adapter, "_call_bridge_transport", side_effect=fake_transport):
            await adapter._call_bridge("open_project", {"path": "x"})

        assert seen["timeout"] is None  # None → simulation_timeout 사용
