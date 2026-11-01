"""배치 결과 순위와 파형(.smv) 저장 정책 — 파일 시스템을 건드리지 않는 순수 함수 모음.

run_batch(11번 저장 정책)뿐 아니라 결과 요약·PNG(10번), 병렬 최적화(8번), promote_run에서
같은 순위 기준을 쓰도록 분리했다. 실제 삭제는 :func:`delete_files` 하나만 파일을 지운다.

rank_by 형식: ``"신호.지표"``(오름차순) 또는 ``"-신호.지표"``(내림차순).
신호 이름에 괄호·점이 들어갈 수 있으므로(``I(L1)``, ``V.out``) **마지막** ``.``에서 나눈다.
맨 앞 ``-`` 하나만 내림차순 표시로 본다.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

KEEP_SMV_VALUES = ("all", "top_k", "none")
RANK_METRICS = ("mean", "ripple", "max", "min")
DEFAULT_TOP_K = 3
_RUN_DIR_RE = re.compile(r"^run_\d{3,}$")


class StoragePolicyError(ValueError):
    def __init__(self, code: str, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.code = code
        self.suggestion = suggestion


@dataclass(frozen=True)
class RankSpec:
    signal: str
    metric: str
    descending: bool

    @property
    def column(self) -> str:
        return f"{self.signal}.{self.metric}"

    @property
    def text(self) -> str:
        return ("-" if self.descending else "") + self.column


@dataclass(frozen=True)
class StoragePolicy:
    keep_smv: str  # 요청(또는 기본값으로 정한) 정책: all | top_k | none
    top_k: int
    rank: RankSpec | None
    defaulted: bool  # keep_smv를 생략해 기본값으로 정했는지

    def as_dict(self) -> dict:
        return {
            "keep_smv": self.keep_smv,
            "top_k": self.top_k,
            "rank_by": self.rank.text if self.rank else None,
            "keep_smv_defaulted": self.defaulted,
        }


_RANK_BY_SUGGESTION = (
    '"신호.지표" 형식으로 쓰세요(예: "I(L1).ripple" 오름차순, "-Vo1.mean" 내림차순). '
    f"지표: {', '.join(RANK_METRICS)}. 신호 이름은 결과 표의 열 이름(신호.지표)과 같습니다."
)


def parse_rank_by(rank_by: str) -> RankSpec:
    """``"I(L1).ripple"`` / ``"-Vo1.mean"``을 해석한다. 형식이 틀리면 INVALID_RANK_BY."""
    if not isinstance(rank_by, str) or not rank_by.strip():
        raise StoragePolicyError(
            "INVALID_RANK_BY", "rank_by는 비어 있지 않은 문자열이어야 합니다.", _RANK_BY_SUGGESTION
        )
    text = rank_by.strip()
    descending = text.startswith("-")
    body = text[1:] if descending else text
    signal, dot, metric = body.rpartition(".")
    signal, metric = signal.strip(), metric.strip()
    if not dot or not signal or not metric:
        raise StoragePolicyError(
            "INVALID_RANK_BY",
            f"rank_by '{rank_by}'는 '신호.지표' 형식이 아닙니다.",
            _RANK_BY_SUGGESTION,
        )
    if metric not in RANK_METRICS:
        raise StoragePolicyError(
            "INVALID_RANK_BY",
            f"rank_by '{rank_by}'의 지표 '{metric}'는 지원하지 않습니다.",
            _RANK_BY_SUGGESTION,
        )
    if signal.startswith("-"):
        raise StoragePolicyError(
            "INVALID_RANK_BY",
            f"rank_by '{rank_by}': 내림차순 표시 '-'는 맨 앞에 하나만 씁니다.",
            _RANK_BY_SUGGESTION,
        )
    return RankSpec(signal=signal, metric=metric, descending=descending)


def resolve_policy(
    rank_by: str | None, keep_smv: str | None, top_k: Any = DEFAULT_TOP_K
) -> StoragePolicy:
    """입력을 검사하고 기본값을 정한다(실행 전에 호출).

    - rank_by가 있으면 기본 keep_smv="top_k", 없으면 "none".
    - rank_by 없이 keep_smv="top_k"를 명시하면 INVALID_STORAGE_POLICY.
    - top_k는 1 이상 정수.
    """
    if top_k is None:
        top_k = DEFAULT_TOP_K
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise StoragePolicyError(
            "INVALID_STORAGE_POLICY",
            f"top_k는 1 이상 정수여야 합니다(받은 값: {top_k!r}).",
            f"예: top_k={DEFAULT_TOP_K}",
        )
    if keep_smv is not None and keep_smv not in KEEP_SMV_VALUES:
        raise StoragePolicyError(
            "INVALID_STORAGE_POLICY",
            f"keep_smv '{keep_smv}'는 지원하지 않습니다.",
            'keep_smv는 "all"(전부 보존), "top_k"(rank_by 상위 top_k개만), "none"(보존 안 함) 중 하나입니다.',
        )
    rank = parse_rank_by(rank_by) if rank_by is not None else None
    if keep_smv == "top_k" and rank is None:
        raise StoragePolicyError(
            "INVALID_STORAGE_POLICY",
            'keep_smv="top_k"는 순위 기준(rank_by)이 있어야 합니다.',
            'rank_by="I(L1).ripple"처럼 순위 기준을 함께 주거나, keep_smv="all" 또는 "none"을 쓰세요.',
        )
    defaulted = keep_smv is None
    if defaulted:
        keep_smv = "top_k" if rank else "none"
    return StoragePolicy(keep_smv=keep_smv, top_k=top_k, rank=rank, defaulted=defaulted)


def _rank_value(record: dict, spec: RankSpec) -> float | None:
    summary = record.get("summary") or {}
    value = (summary.get(spec.signal) or {}).get(spec.metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def column_exists(records: Iterable[dict], spec: RankSpec) -> bool:
    """실행·성공한 행 중 하나라도 rank_by 열(신호·지표)을 갖고 있는지."""
    return any(
        spec.metric in ((r.get("summary") or {}).get(spec.signal) or {})
        for r in records
        if r.get("executed") and r.get("ok")
    )


def rank_records(records: Iterable[dict], spec: RankSpec) -> list[tuple[int, float]]:
    """순위 순서의 ``(run, 값)`` 목록.

    실행·성공한 행만, 값이 유한한 숫자인 행만 대상이다(invalid·failed·NaN·inf 제외).
    동점은 run 번호가 작은 쪽이 앞이다.
    """
    ranked = []
    for r in records:
        if not (r.get("executed") and r.get("ok")):
            continue
        value = _rank_value(r, spec)
        if value is not None:
            ranked.append((int(r["run"]), value))
    sign = -1.0 if spec.descending else 1.0
    ranked.sort(key=lambda rv: (sign * rv[1], rv[0]))
    return ranked


def is_safe_smv_path(path: str | Path, study_dir: str | Path) -> bool:
    """삭제해도 되는 경로인지: ``<study_dir>/run_NNN/*.smv``만 허용한다."""
    try:
        p = Path(path).resolve()
        root = Path(study_dir).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    return (
        p.suffix.lower() == ".smv"
        and p.parent.parent == root
        and bool(_RUN_DIR_RE.match(p.parent.name))
    )


@dataclass
class DeletionPlan:
    keep_runs: list[int]  # .smv를 남길 run(순위 순서)
    delete: list[str]  # 지울 파일(안전 검사 통과)
    rejected: list[str]  # study 폴더 밖 등 안전 검사에 걸려 지우지 않는 경로


def plan_smv_deletion(
    candidates: dict[int, list[str]],
    ranked: list[tuple[int, float]],
    keep_smv: str,
    top_k: int,
    study_dir: str | Path,
) -> DeletionPlan:
    """run별 .smv 후보 중 지울 파일을 고른다(파일은 지우지 않음).

    - all: 아무것도 지우지 않는다.
    - top_k: 순위 상위 top_k개 run의 파일만 남긴다.
    - none: 전부 지운다.
    """
    if keep_smv not in KEEP_SMV_VALUES:
        raise ValueError(f"unknown keep_smv: {keep_smv}")
    if keep_smv == "all":
        return DeletionPlan(keep_runs=sorted(candidates), delete=[], rejected=[])
    keep_runs = [run for run, _ in ranked[:top_k]] if keep_smv == "top_k" else []
    keep = set(keep_runs)
    delete: list[str] = []
    rejected: list[str] = []
    seen: set[str] = set()
    for run in sorted(candidates):
        if run in keep:
            continue
        for path in candidates[run]:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            (delete if is_safe_smv_path(path, study_dir) else rejected).append(key)
    return DeletionPlan(keep_runs=keep_runs, delete=delete, rejected=rejected)


def delete_files(paths: Iterable[str]) -> tuple[list[str], list[dict]]:
    """파일을 지운다. 실패(잠금 등)는 예외 대신 목록으로 돌려준다."""
    deleted: list[str] = []
    failed: list[dict] = []
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
            deleted.append(str(path))
        except OSError as e:
            failed.append({"path": str(path), "error": f"{type(e).__name__}: {e}"})
    return deleted, failed
