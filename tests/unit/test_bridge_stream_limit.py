"""브리지 응답 한 줄 한도(STREAM_LIMIT) — 실제 서브프로세스(가짜 브리지)로 확인.

2026-11-08 실측: heavy 회로 FFT용 extract_signals 응답(수백 KB 한 줄)이 asyncio 기본 한도
64 KiB를 넘어 ``ValueError: Separator is not found, and chunk exceed the limit``가 났고,
워커는 닫히지 않아 줄의 나머지가 파이프에 남았다(다음 응답 어긋남).
"""

from __future__ import annotations

import sys
import textwrap
from unittest.mock import patch

import pytest

import psim_mcp.adapters.real_adapter as ra
import psim_mcp.parallel.pool as pool_mod
from psim_mcp.bridge import STREAM_LIMIT
from psim_mcp.config import AppConfig
from psim_mcp.parallel.pool import BridgeWorker, WorkerError, WorkerPool

_DEFAULT_ASYNCIO_LIMIT = 64 * 1024

_FAKE_BRIDGE = textwrap.dedent(
    """
    import json, sys
    for line in sys.stdin:
        cmd = json.loads(line)
        params = cmd.get("params") or {}
        if cmd["action"] == "big":
            out = {"success": True, "data": {"blob": "x" * int(params["size"])}}
        else:
            out = {"success": True, "data": {"echo": params.get("tag"), "psim_available": True}}
        print(json.dumps(out), flush=True)
    """
)

_BIG = 1_000_000  # 기본 한도(64 KiB)의 약 15배
_OVER_SMALL_LIMIT = 200_000


@pytest.fixture
def fake_bridge(tmp_path):
    script = tmp_path / "fake_bridge.py"
    script.write_text(_FAKE_BRIDGE, encoding="utf-8")
    return str(script)


def _pool(script: str) -> WorkerPool:
    import os

    env = dict(os.environ)
    return WorkerPool(
        lambda wid: BridgeWorker(wid, sys.executable, script, env, low_priority=False),
        idle_timeout=0,
        init_timeout=30.0,
        job_timeout=30.0,
    )


def test_stream_limit_covers_fft_response():
    # FFT 요청 상한: 2 * FFT_MAX_POINTS점 × (값 + times) × 약 25 B
    from psim_mcp.services import batch_report as br

    assert STREAM_LIMIT > _DEFAULT_ASYNCIO_LIMIT
    assert STREAM_LIMIT >= 2 * br.FFT_MAX_POINTS * 2 * 25 * 4


async def test_worker_receives_response_larger_than_default_limit(fake_bridge):
    pool = _pool(fake_bridge)
    try:
        res = await pool.call_one("big", {"size": _BIG})
        assert res["success"] and len(res["data"]["blob"]) == _BIG
        # 같은 워커가 다음 응답도 제대로 받는다(어긋나지 않음).
        res2 = await pool.call_one("echo", {"tag": "after"})
        assert res2["data"]["echo"] == "after"
    finally:
        await pool.shutdown()


async def test_worker_over_limit_is_closed_and_not_reused(fake_bridge, monkeypatch):
    monkeypatch.setattr(pool_mod, "STREAM_LIMIT", _DEFAULT_ASYNCIO_LIMIT)
    pool = _pool(fake_bridge)
    try:
        await pool.call_one("echo", {"tag": "warm"})
        old = list(pool.pids)
        assert len(old) == 1
        with pytest.raises(WorkerError) as exc:
            await pool.call_one("big", {"size": _OVER_SMALL_LIMIT})
        assert exc.value.code == "WORKER_PROTOCOL"
        assert pool.pids == []  # 어긋난 워커는 닫힘
        # 다음 호출은 새 워커가 받고, 이전 응답 꼬리가 아니라 제 응답을 받는다.
        res = await pool.call_one("echo", {"tag": "fresh"})
        assert res["data"]["echo"] == "fresh"
        assert pool.pids and pool.pids[0] not in old
    finally:
        await pool.shutdown()


@pytest.fixture
async def adapter(tmp_path, fake_bridge):
    config = AppConfig(
        psim_mode="real",
        psim_python_exe=sys.executable,
        psim_path=str(tmp_path),
        psim_output_dir=tmp_path / "output",
    )
    with patch("psim_mcp.adapters.real_adapter._BRIDGE_SCRIPT", fake_bridge):
        adapter = ra.RealPsimAdapter(config)
    yield adapter
    proc = adapter._process
    if proc is not None:
        await adapter._discard_bridge(proc)


async def test_main_bridge_receives_response_larger_than_default_limit(adapter):
    res = await adapter._call_bridge_transport("big", {"size": _BIG}, timeout=30)
    assert len(res["data"]["blob"]) == _BIG
    res2 = await adapter._call_bridge_transport("echo", {"tag": "after"}, timeout=30)
    assert res2["data"]["echo"] == "after"


async def test_main_bridge_over_limit_restarts_cleanly(adapter, monkeypatch):
    monkeypatch.setattr(ra, "STREAM_LIMIT", _DEFAULT_ASYNCIO_LIMIT)
    await adapter._call_bridge_transport("echo", {"tag": "warm"}, timeout=30)
    old_pid = adapter._process.pid
    with pytest.raises(RuntimeError, match="line limit"):
        await adapter._call_bridge_transport("big", {"size": _OVER_SMALL_LIMIT}, timeout=30)
    assert adapter._process is None
    res = await adapter._call_bridge_transport("echo", {"tag": "fresh"}, timeout=30)
    assert res["data"]["echo"] == "fresh"
    assert adapter._process.pid != old_pid
