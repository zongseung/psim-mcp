"""WorkerPool: 지연 시작, 재사용, 병렬성, 크래시 복구, 유휴 종료, 자기 프로세스만 정리."""

from __future__ import annotations

import asyncio
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from psim_mcp.parallel.pool import BridgeWorker, MockWorker, PoolError, WorkerPool


def _jobs(tmp_path: Path, n: int, **variables) -> list[dict]:
    return [
        {"schematic": "x", "run_dir": str(tmp_path / f"run_{i:03d}"), "variables": dict(variables)}
        for i in range(n)
    ]


def _mock_pool(delay: float = 0.0, **kwargs) -> WorkerPool:
    return WorkerPool(lambda wid: MockWorker(wid, delay=delay), **kwargs)


async def test_pool_starts_lazily_and_reuses_workers(tmp_path):
    pool = _mock_pool(idle_timeout=0)
    assert pool.status()["workers"] == 0  # 생성만으로는 워커를 띄우지 않는다

    results, info = await pool.run_jobs(_jobs(tmp_path, 4), size=2)
    assert all(r["success"] for r in results)
    assert info["workers"] == 2 and len(info["started"]) == 2
    first_pids = sorted(pool.pids)

    _, info2 = await pool.run_jobs(_jobs(tmp_path, 4), size=2)
    assert info2["started"] == []  # 재사용: 새로 띄운 워커 없음
    assert sorted(pool.pids) == first_pids
    await pool.shutdown()
    assert pool.pids == []


async def test_jobs_run_concurrently(tmp_path):
    pool = _mock_pool(delay=0.2, idle_timeout=0)
    t0 = time.monotonic()
    results, info = await pool.run_jobs(_jobs(tmp_path, 8), size=4)
    elapsed = time.monotonic() - t0
    assert all(r["success"] for r in results)
    assert elapsed < 0.2 * 8 * 0.6  # 순차(1.6 s)보다 확실히 빠름
    assert {r["worker"] for r in results} == {0, 1, 2, 3}
    await pool.shutdown()


async def test_crashed_worker_fails_only_its_job_and_is_restarted(tmp_path):
    pool = _mock_pool(idle_timeout=0)
    jobs = _jobs(tmp_path, 6)
    jobs[2]["variables"] = {"__crash__": "1"}
    results, info = await pool.run_jobs(jobs, size=2)
    assert results[2]["success"] is False
    assert results[2]["error"]["code"] == "WORKER_CRASHED"
    assert all(r["success"] for i, r in enumerate(results) if i != 2)
    assert pool.restarts == 1 and len(info["restarted"]) == 1
    assert pool.status()["workers"] == 2
    await pool.shutdown()


async def test_simulation_failure_is_reported_per_job(tmp_path):
    pool = _mock_pool(idle_timeout=0)
    jobs = _jobs(tmp_path, 3)
    jobs[1]["variables"] = {"__fail__": "1"}
    results, _ = await pool.run_jobs(jobs, size=3)
    assert [r["success"] for r in results] == [True, False, True]
    assert results[1]["error"]["code"] == "SIMULATION_FAILED"
    assert pool.restarts == 0
    await pool.shutdown()


async def test_partial_init_failure_uses_remaining_workers(tmp_path):
    pool = WorkerPool(lambda wid: MockWorker(wid, fail_init=(wid == 1)), idle_timeout=0)
    results, info = await pool.run_jobs(_jobs(tmp_path, 4), size=3)
    assert all(r["success"] for r in results)
    assert info["workers"] == 2
    assert [e["wid"] for e in info["init_errors"]] == [1]
    await pool.shutdown()


async def test_all_init_failure_raises_pool_error(tmp_path):
    pool = WorkerPool(lambda wid: MockWorker(wid, fail_init=True), idle_timeout=0)
    with pytest.raises(PoolError) as exc:
        await pool.run_jobs(_jobs(tmp_path, 2), size=2)
    assert exc.value.code == "WORKER_INIT_FAILED"
    assert pool.pids == []


async def test_idle_timeout_stops_workers(tmp_path):
    pool = _mock_pool(idle_timeout=0.05)
    await pool.run_jobs(_jobs(tmp_path, 2), size=2)
    assert len(pool.pids) == 2
    await asyncio.sleep(0.2)
    assert pool.pids == []


async def test_trim_stops_extra_workers(tmp_path):
    pool = _mock_pool(idle_timeout=0)
    await pool.run_jobs(_jobs(tmp_path, 4), size=4)
    await pool.trim(2)
    assert pool.status()["workers"] == 2
    await pool.shutdown()


# ---------------------------------------------------------------------------
# BridgeWorker: 실제 서브프로세스(가짜 브리지)로 크래시·시간 초과·정리 확인
# ---------------------------------------------------------------------------

_FAKE_BRIDGE = textwrap.dedent(
    """
    import json, os, sys, time
    for line in sys.stdin:
        cmd = json.loads(line)
        params = cmd.get("params") or {}
        v = params.get("variables") or {}
        if "__exit__" in v:
            sys.exit(3)
        if "__hang__" in v:
            time.sleep(60)
        if cmd["action"] == "get_status":
            out = {"success": True, "data": {"psim_available": True}}
        else:
            out = {"success": True, "data": {"summary": {}, "pid": os.getpid()}}
        print(json.dumps(out), flush=True)
    """
)


@pytest.fixture
def fake_bridge(tmp_path):
    script = tmp_path / "fake_bridge.py"
    script.write_text(_FAKE_BRIDGE, encoding="utf-8")
    return str(script)


def _bridge_pool(script: str, **kwargs) -> WorkerPool:
    import os

    env = dict(os.environ)
    return WorkerPool(
        lambda wid: BridgeWorker(wid, sys.executable, script, env, low_priority=False),
        idle_timeout=0,
        **kwargs,
    )


async def test_bridge_worker_crash_and_timeout_are_isolated(tmp_path, fake_bridge):
    pool = _bridge_pool(fake_bridge, job_timeout=2.0, init_timeout=30.0)
    jobs = _jobs(tmp_path, 5)
    jobs[1]["variables"] = {"__exit__": "1"}
    jobs[3]["variables"] = {"__hang__": "1"}
    results, info = await pool.run_jobs(jobs, size=2)
    codes = [None if r["success"] else r["error"]["code"] for r in results]
    assert codes[1] == "WORKER_CRASHED"
    assert codes[3] == "WORKER_TIMEOUT"
    assert [c for i, c in enumerate(codes) if i not in (1, 3)] == [None, None, None]
    assert pool.restarts == 2
    assert len(pool.pids) == 2
    await pool.shutdown()
    assert pool.pids == []


async def test_shutdown_only_stops_pool_processes(tmp_path, fake_bridge):
    # 풀과 무관한 프로세스(PSIM GUI·Simview 대역)는 정리 후에도 살아 있어야 한다.
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        pool = _bridge_pool(fake_bridge, init_timeout=30.0)
        await pool.run_jobs(_jobs(tmp_path, 2), size=2)
        pids = pool.pids
        assert len(pids) == 2 and bystander.pid not in pids
        await pool.shutdown()
        assert pool.pids == []
        assert bystander.poll() is None
    finally:
        bystander.kill()
        bystander.wait()


async def test_warm_starts_workers_once_and_run_does_not_retry_failed(tmp_path):
    created: list[int] = []

    def factory(wid):
        created.append(wid)
        return MockWorker(wid, fail_init=(wid == 1))

    pool = WorkerPool(factory, idle_timeout=0)
    warm = await pool.warm(3)
    assert [e["wid"] for e in warm["init_errors"]] == [1]
    await pool.call_one("inspect_schematic", {"path": "x"})
    results, info = await pool.run_jobs(_jobs(tmp_path, 4), size=3, start_missing=False)
    assert all(r["success"] for r in results)
    assert info["workers"] == 2
    assert sorted(created) == [0, 1, 2]  # 실패한 1번을 다시 띄우지 않음
    await pool.shutdown()
