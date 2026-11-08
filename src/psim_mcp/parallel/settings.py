"""병렬 실행 설정: 기본 동시 실행 수 결정과 벤치마크 결과 저장.

우선순위: 도구 인자 > 환경변수 ``PARALLEL_WORKERS`` > 벤치마크 저장값 > 물리 코어 수.
논리 스레드 수는 기본값으로 쓰지 않는다(실측: SMT로 실행 1건이 2배 이상 느려져 처리량이 오히려 낮음).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

from psim_mcp.parallel.cpu import logical_cores, physical_cores

if TYPE_CHECKING:
    from psim_mcp.config import AppConfig


def settings_path(config: AppConfig) -> Path:
    if config.parallel_settings_path:
        return Path(config.parallel_settings_path)
    return Path.home() / ".psim-mcp" / "parallel.json"


def load_saved(config: AppConfig) -> dict | None:
    path = settings_path(config)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def save_benchmark(config: AppConfig, workers: int, record: dict) -> Path:
    path = settings_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "workers": int(workers),
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "physical_cores": physical_cores(),
        "logical_cores": logical_cores(),
        "benchmark": record,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def max_workers() -> int:
    """요청할 수 있는 최대 동시 실행 수(논리 스레드 수)."""
    return logical_cores()


def resolve_workers(config: AppConfig, requested: int | None = None) -> tuple[int, str]:
    """(동시 실행 수, 출처)."""
    if requested is not None:
        return _clamp(requested), "request"
    if config.parallel_workers:
        return _clamp(config.parallel_workers), "PARALLEL_WORKERS"
    saved = load_saved(config)
    if saved and isinstance(saved.get("workers"), int) and saved["workers"] > 0:
        return _clamp(saved["workers"]), "benchmark"
    return physical_cores(), "physical_cores"


def _clamp(n: int) -> int:
    return max(1, min(int(n), max_workers()))
