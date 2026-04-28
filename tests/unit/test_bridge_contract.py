"""Bridge IPC contract tests.

These tests pin the JSON wire contract between RealPsimAdapter (Python 3.12)
and bridge_script.py (PSIM Python 3.8) WITHOUT requiring an actual PSIM
installation. They cover:

1. The action registry (`_ACTION_HANDLERS`) — shape and dispatch routing.
2. Response envelope helpers `_success` / `_error` — JSON-serialisable shape.
3. Handler validation paths that return errors *before* touching `psimapipy`
   (missing/invalid params, missing project state).
4. End-to-end dispatch via subprocess for `INVALID_JSON` and `UNKNOWN_ACTION`
   — these never reach a handler, so they run cleanly under any Python.
5. Adapter payload shape — what RealPsimAdapter actually writes to stdin.

If any of these assertions fail, the bridge IPC contract has drifted and
RealPsimAdapter ↔ bridge_script will desync at runtime.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import psim_mcp.bridge.bridge_script as bridge_script
from psim_mcp.bridge.bridge_script import (
    _ACTION_HANDLERS,
    _error,
    _success,
    handle_open_project,
    handle_set_parameter,
)


_BRIDGE_PATH = Path(bridge_script.__file__).resolve()


# ---------------------------------------------------------------------------
# 1) Action registry
# ---------------------------------------------------------------------------

EXPECTED_ACTIONS = {
    "open_project",
    "set_parameter",
    "run_simulation",
    "export_results",
    "get_status",
    "get_project_info",
    "create_circuit",
    "extract_signals",
    "compute_metrics",
}


class TestActionRegistry:
    def test_all_expected_actions_registered(self):
        assert set(_ACTION_HANDLERS.keys()) == EXPECTED_ACTIONS

    def test_every_handler_is_callable(self):
        for action, handler in _ACTION_HANDLERS.items():
            assert callable(handler), f"Handler for '{action}' is not callable"

    def test_no_duplicate_handlers(self):
        # Each action must map to a distinct callable
        assert len(set(id(h) for h in _ACTION_HANDLERS.values())) == len(_ACTION_HANDLERS)


# ---------------------------------------------------------------------------
# 2) Response envelope contract
# ---------------------------------------------------------------------------


class TestResponseEnvelope:
    def test_success_envelope_shape(self):
        env = _success({"x": 1})
        assert env == {"success": True, "data": {"x": 1}}

    def test_success_is_json_serialisable(self):
        env = _success({"path": "C:/tmp/buck.psimsch", "count": 5})
        roundtrip = json.loads(json.dumps(env))
        assert roundtrip == env

    def test_error_envelope_shape(self):
        env = _error("INVALID_INPUT", "missing path")
        assert env == {
            "success": False,
            "error": {"code": "INVALID_INPUT", "message": "missing path"},
        }

    def test_error_is_json_serialisable(self):
        env = _error("PSIM_ERROR", "exit code 1")
        roundtrip = json.loads(json.dumps(env))
        assert roundtrip == env

    def test_success_and_error_are_disjoint(self):
        # 'success' field must be the discriminator — never both data and error
        s = _success({})
        e = _error("X", "y")
        assert s["success"] is True and "error" not in s
        assert e["success"] is False and "data" not in e


# ---------------------------------------------------------------------------
# 3) Handler validation (no PSIM required)
# ---------------------------------------------------------------------------


class TestOpenProjectValidation:
    def test_missing_path_returns_invalid_input(self):
        result = handle_open_project({})
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_empty_path_returns_invalid_input(self):
        result = handle_open_project({"path": ""})
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_nonexistent_path_returns_file_not_found(self, tmp_path):
        ghost = tmp_path / "does_not_exist.psimsch"
        result = handle_open_project({"path": str(ghost)})
        assert result["success"] is False
        assert result["error"]["code"] == "FILE_NOT_FOUND"
        assert str(ghost) in result["error"]["message"]


class TestSetParameterValidation:
    def test_missing_component_id_returns_invalid_input(self, monkeypatch):
        monkeypatch.setattr(bridge_script, "_current_sch", None)
        result = handle_set_parameter({"parameter_name": "Resistance"})
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_missing_parameter_name_returns_invalid_input(self, monkeypatch):
        monkeypatch.setattr(bridge_script, "_current_sch", None)
        result = handle_set_parameter({"component_id": "R1"})
        assert result["success"] is False
        assert result["error"]["code"] == "INVALID_INPUT"

    def test_no_project_open_returns_no_project(self, monkeypatch):
        monkeypatch.setattr(bridge_script, "_current_sch", None)
        result = handle_set_parameter({
            "component_id": "R1",
            "parameter_name": "Resistance",
            "value": "10",
        })
        assert result["success"] is False
        assert result["error"]["code"] == "NO_PROJECT"


# ---------------------------------------------------------------------------
# 4) End-to-end dispatch via subprocess (no psimapipy needed)
# ---------------------------------------------------------------------------


def _run_bridge_with_stdin(line: str, timeout: float = 10.0) -> dict:
    """Spawn bridge_script.py, write one JSON line, capture one response.

    Mirrors RealPsimAdapter._get_sanitized_env() for encoding so that Korean
    error messages from the bridge round-trip cleanly on Windows (cp949 default).
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    proc = subprocess.run(
        [sys.executable, str(_BRIDGE_PATH)],
        input=(line + "\n").encode("utf-8"),
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    for raw in stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            continue
    raise AssertionError(
        f"Bridge produced no JSON line. stdout={stdout!r} stderr={stderr!r}"
    )


class TestDispatchSubprocess:
    """These cases never reach a handler that needs psimapipy."""

    def test_unknown_action_returns_unknown_action(self):
        response = _run_bridge_with_stdin(
            json.dumps({"action": "definitely_not_a_real_action", "params": {}})
        )
        assert response["success"] is False
        assert response["error"]["code"] == "UNKNOWN_ACTION"

    def test_invalid_json_returns_invalid_json(self):
        response = _run_bridge_with_stdin("this-is-not-json{")
        assert response["success"] is False
        assert response["error"]["code"] == "INVALID_JSON"

    def test_missing_action_field_returns_unknown_action(self):
        # action=None is not in handler map → treated as UNKNOWN_ACTION
        response = _run_bridge_with_stdin(json.dumps({"params": {}}))
        assert response["success"] is False
        assert response["error"]["code"] == "UNKNOWN_ACTION"


# ---------------------------------------------------------------------------
# 5) Adapter payload shape (RealPsimAdapter → bridge stdin)
# ---------------------------------------------------------------------------


class _FakeStdin:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None


class _FakeStdout:
    def __init__(self, response: bytes) -> None:
        self._response = response

    async def readline(self) -> bytes:
        return self._response


class _FakeProc:
    def __init__(self, response: bytes) -> None:
        self.returncode = None
        self.stdin = _FakeStdin()
        self.stdout = _FakeStdout(response)
        self.pid = 12345

    def kill(self) -> None:  # pragma: no cover - timeout path only
        self.returncode = -9


@pytest.fixture
def real_adapter(tmp_path):
    """A RealPsimAdapter with bridge-script existence check bypassed."""
    from psim_mcp.adapters.real_adapter import RealPsimAdapter
    from psim_mcp.config import AppConfig

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


class TestAdapterPayloadShape:
    """Tests are async to cooperate with pytest-asyncio's auto mode — calling
    ``asyncio.run()`` inside an auto-managed test would close the loop the
    surrounding suite relies on (see test_pipeline_invariants.py).
    """

    async def test_payload_is_action_plus_params_and_newline_terminated(self, real_adapter):
        response_bytes = (json.dumps({"success": True, "data": {"ok": 1}}) + "\n").encode()
        fake_proc = _FakeProc(response_bytes)

        with patch.object(real_adapter, "_ensure_bridge", AsyncMock(return_value=fake_proc)):
            result = await real_adapter._call_bridge(
                "open_project", {"path": "C:/tmp/x.psimsch"}
            )

        # Response parses cleanly
        assert result == {"success": True, "data": {"ok": 1}}

        # Exactly one payload was written to stdin
        assert len(fake_proc.stdin.writes) == 1
        wire = fake_proc.stdin.writes[0]

        # Must end with newline (line-delimited JSON)
        assert wire.endswith(b"\n")

        # Body must be a single JSON object with the contract shape
        sent = json.loads(wire.rstrip(b"\n").decode())
        assert set(sent.keys()) == {"action", "params"}
        assert sent["action"] == "open_project"
        assert sent["params"] == {"path": "C:/tmp/x.psimsch"}

    async def test_empty_params_serialises_as_empty_dict_not_null(self, real_adapter):
        # Bridge does `params = command.get("params", {})` — so None and missing
        # both work, but the contract is "always send {}" to keep it explicit.
        response_bytes = (json.dumps({"success": True, "data": {}}) + "\n").encode()
        fake_proc = _FakeProc(response_bytes)

        with patch.object(real_adapter, "_ensure_bridge", AsyncMock(return_value=fake_proc)):
            await real_adapter._call_bridge("get_status")

        sent = json.loads(fake_proc.stdin.writes[0].rstrip(b"\n").decode())
        assert sent["params"] == {}
        assert sent["params"] is not None
