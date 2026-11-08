"""상주 워커 프로세스 풀 (DEVELOPMENT_PLAN 2단계, 방식 B).

- 워커 1개 = ``bridge_script.py`` 프로세스 1개 = ``PSIM()`` 1개. 첫 병렬 요청 때 띄우고 재사용한다.
- ``PSIM()`` 생성(약 17초)은 워커를 띄울 때 ``get_status``로 미리 끝내 둔다(여러 워커 동시).
- 일정 시간 쓰지 않으면 모든 워커를 종료해 메모리와 라이선스를 돌려준다.
- 작업 중 워커가 죽으면 그 작업만 실패로 기록하고 워커를 다시 띄운 뒤 나머지를 계속한다.
- 정리할 때는 풀이 직접 띄운 프로세스만 종료한다(PSIM GUI·Simview 등 기존 프로세스는 건드리지 않음).
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from psim_mcp.bridge import STREAM_LIMIT

logger = logging.getLogger(__name__)

_BELOW_NORMAL_PRIORITY_CLASS = 0x00004000


class WorkerError(RuntimeError):
    """워커 프로세스 자체의 문제(죽음·시간 초과·프로토콜 오류)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PoolError(RuntimeError):
    """풀을 사용할 수 없음(워커를 하나도 띄우지 못함 등)."""

    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


class Worker(Protocol):
    wid: int

    @property
    def pid(self) -> int | None: ...

    @property
    def alive(self) -> bool: ...

    async def start(self) -> None: ...

    async def call(self, action: str, params: dict, timeout: float) -> dict: ...

    async def close(self) -> None: ...


# ---------------------------------------------------------------------------
# 실제 워커: bridge_script.py 서브프로세스
# ---------------------------------------------------------------------------


class BridgeWorker:
    """``bridge_script.py``를 하나 띄워 JSON 줄 단위로 통신한다."""

    def __init__(
        self,
        wid: int,
        python_exe: str,
        bridge_script: str,
        env: dict[str, str],
        low_priority: bool = True,
    ) -> None:
        self.wid = wid
        self._python_exe = python_exe
        self._bridge_script = bridge_script
        self._env = env
        self._low_priority = low_priority
        self._proc: asyncio.subprocess.Process | None = None
        self._stderr_task: asyncio.Task | None = None

    @property
    def pid(self) -> int | None:
        return self._proc.pid if self._proc else None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def start(self) -> None:
        kwargs: dict[str, Any] = {}
        if sys.platform == "win32" and self._low_priority:
            # PC 사용·원격 명령이 끊기지 않게 워커는 낮은 우선순위로 실행한다.
            kwargs["creationflags"] = _BELOW_NORMAL_PRIORITY_CLASS
        self._proc = await asyncio.create_subprocess_exec(
            self._python_exe,
            self._bridge_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env,
            limit=STREAM_LIMIT,
            **kwargs,
        )
        self._stderr_task = asyncio.create_task(self._drain_stderr(self._proc))
        logger.info("Parallel worker %d started (pid=%d)", self.wid, self._proc.pid)

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
        try:
            while True:
                line = await proc.stderr.readline()  # type: ignore[union-attr]
                if not line:
                    break
                msg = line.decode("utf-8", errors="replace").rstrip()
                if msg:
                    logger.warning("Worker %d stderr: %s", self.wid, msg)
        except Exception:
            pass

    async def call(self, action: str, params: dict, timeout: float) -> dict:
        if not self.alive:
            raise WorkerError("WORKER_CRASHED", f"워커 {self.wid} 프로세스가 종료되어 있습니다.")
        proc = self._proc
        assert proc is not None and proc.stdin is not None and proc.stdout is not None
        payload = json.dumps({"action": action, "params": params}, ensure_ascii=False)
        try:
            proc.stdin.write((payload + "\n").encode("utf-8"))
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError) as exc:
            raise WorkerError("WORKER_CRASHED", f"워커 {self.wid} 입력 실패: {exc}") from exc
        try:
            raw = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError:
            await self.close(force=True)
            raise WorkerError(
                "WORKER_TIMEOUT", f"워커 {self.wid}가 {timeout:.0f}초 안에 응답하지 않았습니다."
            ) from None
        except ValueError as exc:
            # 응답 한 줄이 STREAM_LIMIT을 넘음(LimitOverrunError). asyncio는 버퍼만 비우고 줄의
            # 나머지는 파이프에 남기므로, 이 워커의 다음 응답은 어긋난다 → 재사용하지 않고 닫는다.
            await self.close(force=True)
            raise WorkerError(
                "WORKER_PROTOCOL",
                f"워커 {self.wid} 응답이 한 줄 한도({STREAM_LIMIT} B)를 넘었습니다: {exc}",
            ) from exc
        if not raw:
            raise WorkerError(
                "WORKER_CRASHED",
                f"워커 {self.wid}(pid={self.pid})가 응답 없이 종료되었습니다.",
            )
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise WorkerError("WORKER_PROTOCOL", f"워커 {self.wid} 응답 형식 오류: {exc}") from exc

    async def close(self, force: bool = False) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.returncode is None:
            try:
                if force:
                    proc.kill()
                else:
                    proc.stdin.close()  # type: ignore[union-attr]
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except (asyncio.TimeoutError, ProcessLookupError, OSError):
                try:
                    proc.kill()
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except Exception:
                    logger.warning("Worker %d (pid=%s) did not exit", self.wid, proc.pid)
        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
        logger.info("Parallel worker %d stopped (pid=%s)", self.wid, proc.pid)


# ---------------------------------------------------------------------------
# mock 워커: 테스트·개발용 (PSIM 없음)
# ---------------------------------------------------------------------------

MOCK_ELEMENTS = {
    "L1": {"type": "L", "params": {"Name": "L1", "Inductance": "Lx", "Initial Current": "0"}},
    "C1": {"type": "C", "params": {"Name": "C1", "Capacitance": "100u"}},
    "R1": {"type": "R", "params": {"Name": "R1", "Resistance": "Rload"}},
    "VDC1": {"type": "VDC", "params": {"Name": "VDC1", "Amplitude": "100"}},
}


def _to_float(value: Any, default: float) -> float:
    suffix = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6}
    text = str(value).strip().lower()
    for s in sorted(suffix, key=len, reverse=True):
        if text.endswith(s):
            try:
                return float(text[: -len(s)]) * suffix[s]
            except ValueError:
                return default
    try:
        return float(text)
    except ValueError:
        return default


# MockWorker extract_signals 파형: MOCK_WAVE_POINTS점, 간격 MOCK_WAVE_DT초, 주기 MOCK_WAVE_PERIOD 샘플
# 삼각파(짝수). 테스트에서 바꿔 저해상도(주기 < 20 샘플)·주기 추정 실패(0 = 일정한 신호)를 만든다.
MOCK_WAVE_POINTS = 20000
MOCK_WAVE_DT = 1e-6
MOCK_WAVE_PERIOD = 40


class MockWorker:
    """PSIM 없이 결정적 요약값을 돌려주는 워커.

    시험용 장치: 변수 ``__crash__``가 있으면 워커가 죽은 것처럼, ``__fail__``이면
    시뮬레이션 실패처럼 동작한다.
    """

    _next_pid = 50000

    def __init__(self, wid: int, delay: float = 0.0, fail_init: bool = False) -> None:
        self.wid = wid
        self._delay = delay
        self._fail_init = fail_init
        self._pid: int | None = None

    @property
    def pid(self) -> int | None:
        return self._pid

    @property
    def alive(self) -> bool:
        return self._pid is not None

    async def start(self) -> None:
        MockWorker._next_pid += 1
        self._pid = MockWorker._next_pid

    async def close(self, force: bool = False) -> None:
        self._pid = None

    async def call(self, action: str, params: dict, timeout: float) -> dict:
        if not self.alive:
            raise WorkerError("WORKER_CRASHED", f"워커 {self.wid} 프로세스가 종료되어 있습니다.")
        if action == "get_status":
            if self._fail_init:
                return {"success": True, "data": {"psim_available": False, "error": "mock init"}}
            return {"success": True, "data": {"psim_available": True, "psim_version": "mock"}}
        if action == "inspect_schematic":
            return {
                "success": True,
                "data": {
                    "path": params.get("path"),
                    "elements": MOCK_ELEMENTS,
                    "referenced_identifiers": ["Lx", "Rload"],
                    "undefined_variables": [],  # mock 회로는 변수를 기본값으로 정의
                },
            }
        if action == "open_in_viewer":
            return {"success": True, "data": {"graph_file": params.get("graph_file")}}
        if action == "run_job":
            return await self._run_job(params)
        if action == "extract_signals":
            return self._extract_signals(params)
        return {"success": False, "error": {"code": "UNKNOWN_ACTION", "message": action}}

    @staticmethod
    def _extract_signals(params: dict) -> dict:
        """mock .smv(JSON 요약)에서 평균·리플에 맞춘 삼각파를 만든다. 브리지와 같은 응답 형식."""
        graph_file = params.get("graph_file") or ""
        path = Path(graph_file)
        if not graph_file or not path.is_file():
            return {
                "success": False,
                "error": {
                    "code": "NO_GRAPH_FILE",
                    "message": "결과 파일을 찾을 수 없습니다: %s" % graph_file,
                },
            }
        try:
            summary = json.loads(path.read_text(encoding="utf-8")).get("summary") or {}
        except (ValueError, AttributeError):
            return {"success": False, "error": {"code": "READ_FAILED", "message": "mock read"}}
        names = params.get("signals")
        skip = float(params.get("skip_ratio", 0.0))
        max_points = int(params.get("max_points", 2000))
        minmax = params.get("reduce") == "minmax"
        t_start, t_end = params.get("t_start"), params.get("t_end")
        total = MOCK_WAVE_POINTS
        period = MOCK_WAVE_PERIOD
        idx = [
            i
            for i in range(int(total * skip), total)
            if (t_start is None or i * MOCK_WAVE_DT >= t_start - 1e-15)
            and (t_end is None or i * MOCK_WAVE_DT <= t_end + 1e-15)
        ]
        full: dict[str, list[float]] = {"Time": [round(i * MOCK_WAVE_DT, 12) for i in idx]}
        half = period / 2.0
        for name, m in summary.items():
            mean, ripple = float(m["mean"]), float(m["ripple"])
            if period <= 0:  # 일정한 신호(주기 추정 실패 테스트용)
                full[name] = [round(mean, 9) for _ in idx]
                continue
            # 짝수 주기 삼각파: 정확히 mean ± ripple/2
            full[name] = [
                round(mean + ripple * (abs((i % period) / half - 1.0) - 0.5), 9) for i in idx
            ]
        wanted = [k for k in full if not names or k in names]
        # 브리지와 같게: Time을 요청하지 않았고 시간 범위도 없으면 times를 채우지 않는다.
        has_times = "Time" in wanted or t_start is not None or t_end is not None
        if params.get("reduce") == "bins":
            from psim_mcp.services.batch_report import bin_stats

            bins = int(params.get("bins", 1000))
            stats = {
                name: bin_stats(full[name], full["Time"], bins) for name in wanted if name != "Time"
            }
            data_bins: dict[str, Any] = {
                "bins": stats,
                "source_points": {name: len(full[name]) for name in stats},
                "time_span": [full["Time"][0], full["Time"][-1]] if full["Time"] else None,
                "reduce": "bins",
                "signal_names": list(stats),
                "point_count": len(next(iter(stats.values()), {}).get("mean", [])),
                "graph_file": graph_file,
            }
            return {"success": True, "data": data_bins}
        if minmax:
            from psim_mcp.services.batch_report import minmax_envelope

            out: dict[str, list[float]] = {}
            times: dict[str, list[float] | None] = {}
            reduced: dict[str, bool] = {}
            source_points: dict[str, int] = {}
            for name in wanted:
                if name == "Time":
                    continue
                out[name], t_env, reduced[name] = minmax_envelope(
                    full[name], full["Time"], max_points
                )
                if has_times:
                    times[name] = t_env
                source_points[name] = len(full[name])
            data: dict[str, Any] = {
                "signals": out,
                "times": times,
                "reduced": reduced,
                "source_points": source_points,
                "time_span": (
                    [full["Time"][0], full["Time"][-1]] if full["Time"] and has_times else None
                ),
                "reduce": "minmax",
            }
        else:
            step = max(1, len(idx) // max_points) if len(idx) > max_points else 1
            out = {k: full[k][::step] for k in wanted}
            data = {"signals": out}
        data.update(
            {
                "signal_names": list(out),
                "point_count": len(next(iter(out.values()), [])),
                "graph_file": graph_file,
            }
        )
        return {"success": True, "data": data}

    async def _run_job(self, params: dict) -> dict:
        variables = params.get("variables") or {}
        if "__crash__" in variables:
            self._pid = None
            raise WorkerError("WORKER_CRASHED", f"워커 {self.wid}가 응답 없이 종료되었습니다.")
        if self._delay:
            await asyncio.sleep(self._delay)
        if "__fail__" in variables:
            return {
                "success": False,
                "error": {"code": "SIMULATION_FAILED", "message": "mock simulation failure"},
            }
        values = {k.lower(): v for k, v in variables.items()}
        for ch in params.get("elements") or []:
            values[f"{ch['component_id']}.{ch['parameter_name']}".lower()] = ch["value"]
        inductance = _to_float(values.get("lx", values.get("l1.inductance", 1e-3)), 1e-3)
        load = _to_float(values.get("rload", values.get("r1.resistance", 10.0)), 10.0)
        vo = 50.0 - 0.1 * load
        ripple = 0.004 / max(inductance, 1e-9)
        run_dir = Path(params["run_dir"])
        run_dir.mkdir(parents=True, exist_ok=True)
        copy_path = None
        if params.get("elements") or params.get("total_time") or params.get("time_step"):
            copy_path = run_dir / "circuit.psimsch"
            copy_path.write_text("mock circuit copy", encoding="utf-8")
        smv = run_dir / "result.smv"
        keep = bool(params.get("keep_smv", True))
        summary = {
            "Vo1": {"mean": vo, "ripple": ripple, "max": vo + ripple / 2, "min": vo - ripple / 2},
            "I(L1)": {"mean": vo / load, "ripple": ripple * 2, "max": 0.0, "min": 0.0},
        }
        for s in summary.values():
            s["last"] = s["mean"]
        signals = params.get("signals")
        if signals:
            summary = {k: v for k, v in summary.items() if k in signals}
        if keep:
            # extract_signals(mock)가 읽을 수 있게 요약을 JSON으로 남긴다.
            smv.write_text(json.dumps({"mock": True, "summary": summary}), encoding="utf-8")
        return {
            "success": True,
            "data": {
                "duration_seconds": self._delay,
                "rows": 1000,
                "summary": summary,
                "smv_path": str(smv) if keep else None,
                "circuit_copy": str(copy_path) if copy_path else None,
                "pid": self._pid,
            },
        }


# ---------------------------------------------------------------------------
# 풀
# ---------------------------------------------------------------------------


class WorkerPool:
    """워커를 필요한 만큼 띄워 작업 목록을 나눠 실행한다. 한 번에 배치 하나."""

    def __init__(
        self,
        factory: Callable[[int], Worker],
        *,
        idle_timeout: float = 600.0,
        init_timeout: float = 120.0,
        job_timeout: float = 300.0,
        max_workers: int = 64,
    ) -> None:
        self._factory = factory
        self.idle_timeout = idle_timeout
        self.init_timeout = init_timeout
        self.job_timeout = job_timeout
        self.max_workers = max_workers
        self._workers: dict[int, Worker] = {}
        self._lock = asyncio.Lock()
        self._idle_task: asyncio.Task | None = None
        self._last_used: float | None = None
        self.restarts = 0

    # -- 상태 ---------------------------------------------------------

    @property
    def pids(self) -> list[int]:
        return [w.pid for w in self._workers.values() if w.alive and w.pid is not None]

    def status(self) -> dict:
        return {
            "workers": len(self.pids),
            "pids": self.pids,
            "idle_timeout_s": self.idle_timeout,
            "restarts": self.restarts,
            "busy": self._lock.locked(),
        }

    # -- 워커 시작/정리 ---------------------------------------------------

    async def _start_worker(self, wid: int) -> tuple[Worker | None, dict]:
        worker = self._factory(wid)
        t0 = time.monotonic()
        try:
            await worker.start()
            res = await worker.call("get_status", {}, self.init_timeout)
        except Exception as exc:  # 시작 실패·시간 초과
            await _safe_close(worker)
            return None, {"wid": wid, "error": str(exc)}
        data = res.get("data") or {}
        if not res.get("success") or not data.get("psim_available"):
            await _safe_close(worker)
            message = (
                data.get("error") or (res.get("error") or {}).get("message") or "PSIM 초기화 실패"
            )
            return None, {"wid": wid, "error": str(message)}
        return worker, {"wid": wid, "pid": worker.pid, "init_s": round(time.monotonic() - t0, 2)}

    async def _ensure(self, size: int, start_missing: bool = True) -> dict:
        for wid, w in list(self._workers.items()):
            if not w.alive:
                await _safe_close(w)
                del self._workers[wid]
        missing = [wid for wid in range(size) if wid not in self._workers] if start_missing else []
        started, errors = [], []
        if missing:
            results = await asyncio.gather(*(self._start_worker(wid) for wid in missing))
            for worker, info in results:
                if worker is not None:
                    self._workers[worker.wid] = worker
                    started.append(info)
                else:
                    errors.append(info)
        return {"started": started, "init_errors": errors}

    async def shutdown(self) -> None:
        """풀이 띄운 워커만 모두 종료한다."""
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        self._idle_task = None
        workers, self._workers = list(self._workers.values()), {}
        await asyncio.gather(*(_safe_close(w) for w in workers))

    async def warm(self, size: int) -> dict:
        """워커 ``size``개를 동시에 띄워 둔다(PSIM() 생성을 한 번에 병렬로)."""
        size = max(1, min(int(size), self.max_workers))
        async with self._lock:
            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()
            t0 = time.monotonic()
            try:
                info = await self._ensure(size)
            finally:
                self._schedule_idle_shutdown()
            info["start_s"] = round(time.monotonic() - t0, 2)
            return info

    async def trim(self, size: int) -> None:
        """워커 번호가 ``size`` 이상인 워커를 종료한다(벤치마크 후 라이선스 반환)."""
        async with self._lock:
            extra = [w for wid, w in self._workers.items() if wid >= size]
            for w in extra:
                self._workers.pop(w.wid, None)
            await asyncio.gather(*(_safe_close(w) for w in extra))

    def _schedule_idle_shutdown(self) -> None:
        self._last_used = time.monotonic()
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
        if self.idle_timeout and self.idle_timeout > 0:
            self._idle_task = asyncio.create_task(self._idle_watch())

    async def _idle_watch(self) -> None:
        try:
            await asyncio.sleep(self.idle_timeout)
            if self._lock.locked():
                return
            logger.info("Worker pool idle for %.0fs — shutting down", self.idle_timeout)
            workers, self._workers = list(self._workers.values()), {}
            await asyncio.gather(*(_safe_close(w) for w in workers))
        except asyncio.CancelledError:
            pass

    # -- 실행 -----------------------------------------------------------

    async def call_one(self, action: str, params: dict, timeout: float | None = None) -> dict:
        """워커 하나에서 단일 명령 실행(사전 검사 등). 필요하면 워커 1개를 띄운다."""
        async with self._lock:
            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()
            try:
                worker = next((w for w in self._workers.values() if w.alive), None)
                info: dict = {"init_errors": []}
                if worker is None:
                    info = await self._ensure(1)
                    worker = next((w for w in self._workers.values() if w.alive), None)
                if worker is None:
                    raise PoolError(
                        "WORKER_INIT_FAILED",
                        "병렬 워커를 시작하지 못했습니다.",
                        {"init_errors": info["init_errors"]},
                    )
                try:
                    return await worker.call(action, params, timeout or self.job_timeout)
                except WorkerError:
                    await _safe_close(worker)
                    self._workers.pop(worker.wid, None)
                    raise
            finally:
                self._schedule_idle_shutdown()

    async def run_jobs(
        self,
        jobs: list[dict],
        size: int,
        on_result: Callable[[int, dict], Any] | None = None,
        start_missing: bool = True,
    ) -> tuple[list[dict], dict]:
        """작업 목록을 ``size``개 워커로 나눠 실행한다.

        반환: (작업 순서대로의 결과 목록, 실행 정보). 결과는 브리지 응답 형식
        ``{"success": ..., "data"|"error": ...}``에 ``worker``, ``wall_s``가 붙는다.
        """
        size = max(1, min(int(size), self.max_workers))
        async with self._lock:
            if self._idle_task and not self._idle_task.done():
                self._idle_task.cancel()
            try:
                return await self._run_locked(jobs, size, on_result, start_missing)
            finally:
                self._schedule_idle_shutdown()

    async def _run_locked(self, jobs, size, on_result, start_missing=True):
        t_init = time.monotonic()
        # start_missing=False: warm()에서 시작에 실패한 워커를 다시 시도하지 않는다.
        init = await self._ensure(size, start_missing)
        init_s = round(time.monotonic() - t_init, 2)
        workers = [w for wid, w in sorted(self._workers.items()) if wid < size and w.alive]
        if not workers:
            raise PoolError(
                "WORKER_INIT_FAILED",
                "병렬 워커를 하나도 시작하지 못했습니다(PSIM 라이선스·설치 확인).",
                {"init_errors": init["init_errors"]},
            )

        queue: asyncio.Queue[tuple[int, dict]] = asyncio.Queue()
        for i, job in enumerate(jobs):
            queue.put_nowait((i, job))
        results: list[dict | None] = [None] * len(jobs)
        restarted: list[dict] = []

        async def consume(worker: Worker) -> None:
            while True:
                try:
                    i, job = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                t0 = time.monotonic()
                try:
                    res = await worker.call("run_job", job, self.job_timeout)
                except WorkerError as exc:
                    res = {"success": False, "error": {"code": exc.code, "message": str(exc)}}
                    crashed = True
                else:
                    crashed = False
                res["worker"] = worker.wid
                res["wall_s"] = round(time.monotonic() - t0, 4)
                results[i] = res
                if on_result is not None:
                    on_result(i, res)
                if crashed:
                    # 그 작업만 실패로 남기고 워커를 새로 띄워 나머지를 계속한다.
                    await _safe_close(worker)
                    self._workers.pop(worker.wid, None)
                    self.restarts += 1
                    new, info = await self._start_worker(worker.wid)
                    restarted.append(info)
                    if new is None:
                        return
                    self._workers[new.wid] = new
                    worker = new

        t0 = time.monotonic()
        await asyncio.gather(*(consume(w) for w in workers))
        total_s = round(time.monotonic() - t0, 3)

        for i, res in enumerate(results):
            if res is None:
                results[i] = {
                    "success": False,
                    "error": {
                        "code": "NO_WORKER",
                        "message": "사용 가능한 워커가 없어 실행하지 못했습니다.",
                    },
                    "worker": None,
                    "wall_s": 0.0,
                }
        info = {
            "workers": len(workers),
            "requested_workers": size,
            "pool_start_s": init_s,
            "started": init["started"],
            "init_errors": init["init_errors"],
            "restarted": restarted,
            "total_s": total_s,
        }
        return results, info  # type: ignore[return-value]


async def _safe_close(worker: Worker) -> None:
    try:
        await worker.close()
    except Exception:
        logger.exception("Failed to close worker %s", getattr(worker, "wid", "?"))
