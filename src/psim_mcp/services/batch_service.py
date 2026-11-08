"""병렬 배치 실행 서비스: run_batch, benchmark_parallel, open_in_viewer, 병렬 스윕.

조건 하나 = ``{"Lx": 0.002}`` 같은 회로 변수 덮어쓰기 + ``{"L1.Inductance": 0.002}`` 같은
소자 값 변경의 조합이다.

- 점이 없는 키(``Lx``)는 회로 변수다. 파일 복제 없이 ``PsimSimulate`` kwargs로 넘긴다.
  변수 덮어쓰기는 회로가 그 변수를 실제로 참조할 때만 효과가 있으므로, 참조하지 않는 이름은
  실행하지 않는다(숫자 값인 ``L1`` 인덕턴스 같은 것은 덮어쓰기가 조용히 무시된다).
- 형식이 틀린 조건은 기본적으로 그 행만 오류로 표시하고 나머지를 실행한다. 모든 조건이 틀렸거나
  ``strict=True``면 배치 전체를 실행 전에 거부한다.
- ``소자.파라미터`` 키나 ``total_time``/``time_step``은 run 폴더에 회로 사본을 만들어 수정한다.

작업 폴더: ``<runs_dir>/<study_id>/run_000/``마다 ``config.json``(넣은 값), ``summary.json``
(측정 요약), ``result.smv``(결과), 필요하면 ``circuit.psimsch``(회로 사본).
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from psim_mcp.parallel import settings as parallel_settings
from psim_mcp.parallel.cpu import logical_cores, physical_cores
from psim_mcp.parallel.pool import PoolError, WorkerError
from psim_mcp.services import batch_report as br
from psim_mcp.services import storage_policy as sp
from psim_mcp.services.validators import (
    normalize_parameter_name,
    validate_component_id,
    validate_parameter_name,
    validate_project_path,
    validate_simulation_options,
)
from psim_mcp.shared.response import ResponseBuilder

if TYPE_CHECKING:
    from psim_mcp.adapters.base import BasePsimAdapter
    from psim_mcp.config import AppConfig
    from psim_mcp.parallel.pool import WorkerPool

logger = logging.getLogger(__name__)

_VARIABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
_STUDY_NAME_RE = re.compile(r"[^A-Za-z0-9_-]+")
_METRICS = ("mean", "ripple", "max", "min")
_MAX_TABLE_SIGNALS = 8
_MAX_TABLE_ROWS = 100
# 실행당 시간이 이보다 짧으면 병렬 효과보다 오버헤드가 지배한다(실측 0.03 s 회로).
_SHORT_RUN_WARNING_S = 0.5


def _sig(value: float, digits: int = 6) -> float:
    """응답용 유효숫자 반올림."""
    return float(f"{value:.{digits}g}")


class BatchInputError(ValueError):
    def __init__(self, code: str, message: str, suggestion: str | None = None, details=None):
        super().__init__(message)
        self.code = code
        self.suggestion = suggestion
        self.details = details


def _error_doc(e: BatchInputError) -> dict:
    doc: dict[str, Any] = {"code": e.code, "message": str(e)}
    if e.suggestion:
        doc["suggestion"] = e.suggestion
    if e.details:
        doc["details"] = e.details
    return doc


def _round(value: Any) -> Any:
    if isinstance(value, float):
        return float(f"{value:.6g}")
    return value


class BatchService:
    def __init__(
        self,
        config: AppConfig,
        adapter: BasePsimAdapter,
        pool: WorkerPool,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._pool = pool

    @property
    def pool(self) -> WorkerPool:
        return self._pool

    # ------------------------------------------------------------------
    # 경로
    # ------------------------------------------------------------------

    def runs_root(self) -> Path:
        if self._config.runs_dir:
            return Path(self._config.runs_dir)
        if self._config.psim_output_dir:
            return Path(self._config.psim_output_dir) / "runs"
        return Path.home() / "psim-mcp-runs"

    def _new_study_dir(self, name: str | None, prefix: str) -> tuple[str, Path]:
        slug = _STUDY_NAME_RE.sub("_", name or prefix).strip("_")[:40] or prefix
        study_id = f"{time.strftime('%Y%m%d-%H%M%S')}_{slug}_{secrets.token_hex(2)}"
        path = self.runs_root() / study_id
        path.mkdir(parents=True, exist_ok=False)
        return study_id, path

    def _resolve_schematic(self, schematic_path: str | None) -> Path:
        path = schematic_path or self._adapter.current_project_path
        if not path:
            raise BatchInputError(
                "NO_PROJECT",
                "실행할 회로가 없습니다.",
                "schematic_path를 지정하거나 open_project로 회로를 먼저 여세요.",
            )
        vr = validate_project_path(path, self._config.allowed_project_dirs)
        if not vr.is_valid:
            raise BatchInputError(vr.error_code or "INVALID_PATH", vr.error_message or "")
        return Path(path).resolve()

    # ------------------------------------------------------------------
    # 조건 해석·검사
    # ------------------------------------------------------------------

    def parse_conditions(self, conditions: list[dict], strict: bool = True) -> list[dict]:
        """조건 목록을 해석한다.

        strict=True면 형식이 틀린 조건이 하나라도 있으면 BatchInputError를 낸다.
        strict=False면 틀린 조건은 ``error``를 붙인 항목으로 남기고 나머지를 계속 해석한다.
        목록 자체의 오류(비어 있음, 개수 초과)는 항상 거부한다.
        """
        if not isinstance(conditions, list) or not conditions:
            raise BatchInputError("INVALID_INPUT", "conditions는 비어 있지 않은 목록이어야 합니다.")
        limit = self._config.max_batch_conditions
        if len(conditions) > limit:
            raise BatchInputError(
                "BATCH_LIMIT_EXCEEDED",
                f"조건이 {len(conditions)}개입니다. 최대 {limit}개까지 실행할 수 있습니다.",
            )
        parsed = []
        for i, cond in enumerate(conditions):
            try:
                parsed.append(self._parse_one(i, cond))
            except BatchInputError as e:
                if strict:
                    raise
                inputs = dict(cond) if isinstance(cond, dict) else {}
                parsed.append(
                    {"inputs": inputs, "variables": {}, "elements": [], "error": _error_doc(e)}
                )
        return parsed

    @staticmethod
    def _parse_one(i: int, cond: Any) -> dict:
        if not isinstance(cond, dict) or not cond:
            raise BatchInputError(
                "INVALID_CONDITION",
                f'조건 {i}: 비어 있지 않은 객체여야 합니다. 예: {{"Lx": 0.002}}',
            )
        variables: dict[str, str] = {}
        elements: list[dict] = []
        for key, value in cond.items():
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                raise BatchInputError(
                    "INVALID_CONDITION",
                    f"조건 {i}: '{key}' 값은 숫자 또는 문자열이어야 합니다.",
                )
            text = str(value).strip()
            if not text or len(text) > 200:
                raise BatchInputError(
                    "INVALID_CONDITION", f"조건 {i}: '{key}' 값이 비어 있거나 너무 깁니다."
                )
            if "." in key:
                cid, pname = key.split(".", 1)
                if not validate_component_id(cid) or not validate_parameter_name(pname):
                    raise BatchInputError(
                        "INVALID_CONDITION",
                        f"조건 {i}: '{key}'는 '소자.파라미터' 형식이어야 합니다(예: L1.Inductance).",
                    )
                elements.append({"component_id": cid, "parameter_name": pname, "value": text})
            else:
                if not _VARIABLE_RE.match(key):
                    raise BatchInputError(
                        "INVALID_CONDITION", f"조건 {i}: 변수 이름 '{key}'가 올바르지 않습니다."
                    )
                variables[key] = text
        return {"inputs": dict(cond), "variables": variables, "elements": elements}

    async def precheck(self, schematic: Path, parsed: list[dict], strict: bool = True) -> dict:
        """워커 하나로 회로를 읽어 조건이 실제로 적용될 수 있는지 확인한다.

        strict=False면 적용할 수 없는 조건에 ``error``를 붙이고 계속 검사한다.
        이미 ``error``가 붙은 조건은 건너뛴다.
        """
        res = await self._pool.call_one("inspect_schematic", {"path": str(schematic)})
        if not res.get("success"):
            err = res.get("error") or {}
            raise BatchInputError(err.get("code", "INSPECT_FAILED"), str(err.get("message")))
        info = res.get("data") or {}
        for i, cond in enumerate(parsed):
            if "error" in cond:
                continue
            try:
                self._check_one(i, cond, info)
            except BatchInputError as e:
                if strict:
                    raise
                cond["error"] = _error_doc(e)
        return info

    @staticmethod
    def _check_one(i: int, cond: dict, info: dict) -> None:
        elements: dict = info.get("elements") or {}
        referenced = {str(n).lower(): str(n) for n in info.get("referenced_identifiers") or []}
        undefined = [str(n) for n in info.get("undefined_variables") or []]
        elem_lower = {name.lower(): name for name in elements}

        for var in cond["variables"]:
            if var.lower() not in referenced:
                elem = elem_lower.get(var.lower())
                hint = (
                    f" 소자 값을 바꾸려면 '{elem}.파라미터' 형식을 쓰세요."
                    if elem
                    else " 소자 값을 바꾸려면 'L1.Inductance'처럼 '소자.파라미터' 형식을 쓰세요."
                )
                refs = sorted(referenced.values())
                example = "L1.Inductance"
                if elem:
                    params = [p for p in (elements[elem].get("params") or {}) if p != "Name"]
                    if params:
                        example = f"{elem}.{params[0]}"
                var_example = f'{{"{refs[0]}": 값}}' if refs else '{"변수": 값}'
                suggestion = (
                    f"회로에서 참조하는 변수: {', '.join(refs) if refs else '없음'}. "
                    f"회로 변수는 {var_example}, 소자 값은 "
                    f'{{"{example}": 값}}처럼 "소자.파라미터" 형식으로 쓰세요.'
                )
                raise BatchInputError(
                    "VARIABLE_NOT_REFERENCED",
                    f"조건 {i}: '{var}'는 회로에서 참조하지 않는 변수라 덮어써도 효과가 없습니다.{hint}",
                    suggestion,
                    {"referenced_variables": refs, "example": example},
                )
        for ch in cond["elements"]:
            name = elem_lower.get(ch["component_id"].lower())
            if name is None:
                raise BatchInputError(
                    "COMPONENT_NOT_FOUND",
                    f"조건 {i}: 소자 '{ch['component_id']}'가 회로에 없습니다.",
                    details={"available_components": sorted(elements)},
                )
            ch["component_id"] = name
            actual = [p for p in (elements[name].get("params") or {}) if p != "Name"]
            key = normalize_parameter_name(ch["parameter_name"])
            matches = [p for p in actual if p == ch["parameter_name"]] or [
                p for p in actual if normalize_parameter_name(p) == key
            ]
            if len(matches) != 1:
                raise BatchInputError(
                    "AMBIGUOUS_PARAMETER" if matches else "PARAMETER_NOT_FOUND",
                    f"조건 {i}: {name}의 파라미터 '{ch['parameter_name']}'를 찾을 수 없습니다.",
                    "사용 가능한 파라미터: " + ", ".join(actual),
                    {"available_parameters": actual},
                )
            ch["parameter_name"] = matches[0]
        provided = {v.lower() for v in cond["variables"]}
        missing = [u for u in undefined if u.lower() not in provided]
        if missing:
            raise BatchInputError(
                "UNDEFINED_VARIABLE",
                f"조건 {i}: 회로의 정의되지 않은 변수 {missing}에 값을 주지 않았습니다.",
                "모든 조건에 이 변수 값을 넣으세요.",
            )

    @staticmethod
    def _reject_if_all_invalid(parsed: list[dict]) -> None:
        """모든 조건이 틀렸으면 첫 오류로 배치 전체를 거부한다."""
        if not parsed or any("error" not in c for c in parsed):
            return
        first = parsed[0]["error"]
        details = dict(first.get("details") or {})
        message = first["message"]
        if len(parsed) > 1:
            details["invalid_conditions"] = [
                {"run": i, "code": c["error"]["code"], "message": c["error"]["message"]}
                for i, c in enumerate(parsed)
            ]
            message = f"{len(parsed)}개 조건이 모두 실행할 수 없는 형식입니다. 첫 오류: {message}"
        raise BatchInputError(first["code"], message, first.get("suggestion"), details or None)

    # ------------------------------------------------------------------
    # 실행
    # ------------------------------------------------------------------

    async def run_batch(
        self,
        conditions: list[dict],
        schematic_path: str | None = None,
        signals: list[str] | None = None,
        total_time: float | None = None,
        time_step: float | None = None,
        workers: int | None = None,
        study_name: str | None = None,
        skip_ratio: float = 0.5,
        strict: bool = False,
        rank_by: str | None = None,
        top_k: int | None = sp.DEFAULT_TOP_K,
        keep_smv: str | None = None,
        plot: bool = False,
        max_images: int = br.DEFAULT_MAX_IMAGES,
        plot_window_s: float | None = None,
    ) -> dict:
        try:
            try:
                policy = sp.resolve_policy(rank_by, keep_smv, top_k)
            except sp.StoragePolicyError as e:
                raise BatchInputError(e.code, str(e), e.suggestion) from e
            # 그림 옵션도 워커 시작·study 폴더 생성 전에 검사한다.
            try:
                max_images = br.validate_max_images(max_images)
                plot_window_s = br.validate_plot_window_s(plot_window_s)
            except br.ReportInputError as e:
                raise BatchInputError(e.code, str(e), e.suggestion) from e
            return await self._run_batch(
                conditions,
                schematic_path,
                signals,
                total_time,
                time_step,
                workers,
                study_name,
                skip_ratio,
                strict,
                policy,
                bool(plot),
                max_images,
                plot_window_s,
            )
        except BatchInputError as e:
            return ResponseBuilder.error(e.code, str(e), e.suggestion, e.details)
        except PoolError as e:
            return ResponseBuilder.error(
                e.code,
                str(e),
                "PSIM 라이선스·설치 상태를 get_status로 확인하세요.",
                e.details,
            )
        except WorkerError as e:
            return ResponseBuilder.error(e.code, str(e))

    async def _run_batch(
        self,
        conditions,
        schematic_path,
        signals,
        total_time,
        time_step,
        workers,
        study_name,
        skip_ratio,
        strict,
        policy: sp.StoragePolicy,
        plot: bool = False,
        max_images: int = br.DEFAULT_MAX_IMAGES,
        plot_window_s: float | None = None,
    ) -> dict:
        schematic = self._resolve_schematic(schematic_path)
        # strict=False: 형식이 틀린 조건은 그 행만 오류로 남기고 나머지를 실행한다.
        parsed = self.parse_conditions(conditions, strict=strict)
        self._reject_if_all_invalid(parsed)
        sim_opts = {
            k: v for k, v in (("total_time", total_time), ("time_step", time_step)) if v is not None
        }
        vr = validate_simulation_options(sim_opts or None, self._config.simulation_timeout)
        if not vr.is_valid:
            raise BatchInputError(vr.error_code or "INVALID_INPUT", vr.error_message or "")
        if not 0.0 <= float(skip_ratio) < 1.0:
            raise BatchInputError("INVALID_INPUT", "skip_ratio는 0 이상 1 미만이어야 합니다.")
        if signals is not None and (
            not isinstance(signals, list) or not all(isinstance(s, str) for s in signals)
        ):
            raise BatchInputError("INVALID_INPUT", "signals는 문자열 목록이어야 합니다.")
        if workers is not None and (workers < 1 or workers > parallel_settings.max_workers()):
            raise BatchInputError(
                "INVALID_INPUT",
                f"workers는 1~{parallel_settings.max_workers()} 사이여야 합니다.",
            )

        n_workers, source = parallel_settings.resolve_workers(self._config, workers)
        n_workers = min(n_workers, sum(1 for c in parsed if "error" not in c))
        # 필요한 워커를 먼저 한꺼번에 띄운다(PSIM() 생성 ~17 s를 병렬로 한 번만).
        warm = await self._pool.warm(n_workers)
        await self.precheck(schematic, parsed, strict=strict)
        self._reject_if_all_invalid(parsed)
        n_workers = min(n_workers, sum(1 for c in parsed if "error" not in c))

        study_id, study_dir = self._new_study_dir(study_name, "batch")
        jobs = []
        job_index: dict[int, int] = {}  # 조건 번호 → jobs 위치(형식 오류 조건은 실행하지 않음)
        for i, cond in enumerate(parsed):
            run_dir = study_dir / f"run_{i:03d}"
            run_dir.mkdir()
            if "error" in cond:
                (run_dir / "config.json").write_text(
                    json.dumps(
                        {
                            "study_id": study_id,
                            "run": i,
                            "schematic": str(schematic),
                            "inputs": cond["inputs"],
                            "executed": False,
                            "error": cond["error"],
                        },
                        ensure_ascii=False,
                        indent=1,
                    ),
                    encoding="utf-8",
                )
                continue
            uses_copy = bool(cond["elements"] or sim_opts)
            config_doc = {
                "study_id": study_id,
                "run": i,
                "schematic": str(schematic),
                "inputs": cond["inputs"],
                "variables": cond["variables"],
                "elements": cond["elements"],
                "simulation": sim_opts,
                "method": "circuit_copy" if uses_copy else "variable_override",
                "simview": 0,
            }
            (run_dir / "config.json").write_text(
                json.dumps(config_doc, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            job_index[i] = len(jobs)
            jobs.append(
                {
                    "schematic": str(schematic),
                    "run_dir": str(run_dir),
                    "variables": cond["variables"],
                    "elements": cond["elements"],
                    "total_time": total_time,
                    "time_step": time_step,
                    "signals": signals,
                    "skip_ratio": float(skip_ratio),
                    # 실행 중에는 모두 저장하고, 전체 결과를 모은 뒤 저장 정책으로 정리한다.
                    "keep_smv": True,
                }
            )

        results, info = await self._pool.run_jobs(jobs, n_workers, start_missing=False)
        info["pool_start_s"] = round(warm["start_s"] + info["pool_start_s"], 2)
        info["init_errors"] = warm["init_errors"] + info["init_errors"]
        records = []
        for i, cond in enumerate(parsed):
            if i not in job_index:
                rec = {
                    "run": i,
                    "inputs": cond["inputs"],
                    "ok": False,
                    "executed": False,
                    "error": cond["error"],
                }
                records.append(rec)
                continue
            res = results[job_index[i]]
            rec = {
                "run": i,
                "inputs": cond["inputs"],
                "ok": bool(res.get("success")),
                "executed": True,
                "wall_s": res.get("wall_s"),
                "worker": res.get("worker"),
            }
            if rec["ok"]:
                data = res.get("data") or {}
                rec["sim_s"] = data.get("duration_seconds")
                rec["summary"] = data.get("summary") or {}
                rec["smv_path"] = data.get("smv_path")
                rec["circuit_copy"] = data.get("circuit_copy")
            else:
                err = res.get("error") or {}
                rec["error"] = {"code": err.get("code"), "message": err.get("message")}
            records.append(rec)

        # 모든 워커의 결과 수집이 끝난 뒤에 순위를 매기고 .smv를 정리한다.
        storage, storage_notes = self._apply_storage(policy, records, study_dir)
        for rec in records:
            (study_dir / f"run_{rec['run']:03d}" / "summary.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8"
            )

        table = self._build_table(records, signals, with_rank=policy.rank is not None)
        counts = self._count_records(records)
        ok, invalid = counts["succeeded"], counts["invalid"]
        sum_wall = sum(r.get("wall_s") or 0.0 for r in records)
        total_s = info["total_s"]
        summary = {
            "study_id": study_id,
            "study_dir": str(study_dir),
            "schematic": str(schematic),
            "conditions": len(records),
            # succeeded + failed + invalid == conditions
            **counts,
            "strict": bool(strict),
            "workers": info["workers"],
            "workers_source": source,
            "total_s": total_s,
            "sum_of_run_times_s": round(sum_wall, 3),
            "pool_start_s": info["pool_start_s"],
            "init_errors": info["init_errors"],
            "restarted_workers": info["restarted"],
            "simview": 0,
            "storage": storage,
        }
        self._write_study_files(study_dir, summary, records, table)
        data = dict(summary)
        # 응답에는 삭제 파일 목록 대신 개수만 싣는다(전체 목록은 study.json).
        data["storage"] = {
            **{k: v for k, v in storage.items() if k not in ("deleted", "rejected")},
            "deleted_count": len(storage["deleted"]),
            "rejected": storage["rejected"][:10],
        }
        data["columns"] = table["columns"]
        data["rows"] = table["rows"][:_MAX_TABLE_ROWS]
        if len(table["rows"]) > _MAX_TABLE_ROWS:
            data["rows_truncated"] = len(table["rows"])
        if table["omitted_signals"]:
            data["omitted_signals"] = table["omitted_signals"]
        data["results_csv"] = str(study_dir / "results.csv")
        if invalid:
            data.update(self._invalid_report(records))
        notes = []
        if invalid:
            notes.append(
                f"형식이 틀린 조건 {invalid}개는 실행하지 않았습니다(invalid_conditions·suggestions 참고). "
                "하나라도 틀리면 전체를 거부하려면 strict=true를 쓰세요."
            )
        notes.extend(storage_notes)
        if policy.rank is not None and storage["ranked"]:
            data["top"] = br.build_top(records, policy.rank, policy.top_k)
        else:
            notes.append(
                "top(상위 요약)은 생략했습니다: rank_by가 없거나 순위를 매긴 행이 없습니다. "
                'rank_by="신호.지표"를 주면 상위 행 요약이 붙습니다.'
            )
        images: list[dict] = []
        if plot:
            images, plots, plot_notes = await self._make_plots(
                records, table, policy, study_dir, float(skip_ratio), max_images, plot_window_s
            )
            data["plots"] = plots
            notes.extend(plot_notes)
        if info["workers"] < n_workers:
            notes.append(f"워커 {n_workers}개 중 {info['workers']}개만 시작됨(init_errors 참고).")
        if ok and sum_wall / max(ok, 1) < _SHORT_RUN_WARNING_S:
            notes.append("실행당 시간이 짧아 병렬 효과보다 오버헤드 비중이 큽니다.")
        if notes:
            data["notes"] = notes
        msg = (
            f"{len(records)}개 조건 중 성공 {ok}, 실행 실패 {counts['failed']}, "
            f"형식 오류(미실행) {invalid}. 워커 {info['workers']}개, {total_s:.1f}초."
        )
        response = ResponseBuilder.success(data, msg)
        if plot:
            # tool_handler가 [TextContent, ImageContent...]로 바꾼다(그림이 없으면 텍스트만).
            response["_images"] = images
        return response

    # ------------------------------------------------------------------
    # 결과 그림 (2차 10번)
    # ------------------------------------------------------------------

    async def _make_plots(
        self,
        records: list[dict],
        table: dict,
        policy: sp.StoragePolicy,
        study_dir: Path,
        skip_ratio: float,
        max_images: int,
        plot_window_s: float | None = None,
    ) -> tuple[list[dict], list[dict], list[str]]:
        """그림 1(조건-지표), 그림 2(상위 파형)를 그려 plots/에 저장하고 첨부 목록을 만든다.

        어떤 그림이 실패해도 예외를 밖으로 내지 않는다 — 배치 결과는 그대로 성공이고 note로 알린다.
        """
        images: list[dict] = []
        plots: list[dict] = []
        notes: list[str] = []
        try:
            ok_records = [r for r in records if r["executed"] and r["ok"]]
            if not ok_records:
                notes.append("성공한 조건이 없어 그림을 만들지 않았습니다.")
                return images, plots, notes
            signal = policy.rank.signal if policy.rank else self._first_signal(table)
            if signal is None:
                notes.append("결과 신호가 없어 그림을 만들지 않았습니다.")
                return images, plots, notes
            ranked = sorted((r for r in records if r.get("rank")), key=lambda r: r["rank"])
            highlight = [r["run"] for r in ranked][: policy.top_k] if policy.rank else []
        except Exception as e:  # noqa: BLE001 - 그림 실패는 배치 결과에 영향 없음
            logger.warning("run_batch plot setup failed", exc_info=True)
            notes.append(f"그림 생성 실패: {type(e).__name__}: {e}")
            return images, plots, notes
        plot_dir = study_dir / "plots"

        def save(name: str, kind: str, png: bytes, extra: dict | None = None) -> None:
            plot_dir.mkdir(exist_ok=True)
            path = plot_dir / name
            path.write_bytes(png)
            attached = len(images) < max_images
            entry = {"kind": kind, "path": str(path), "bytes": len(png), "attached": attached}
            if extra:
                entry.update(extra)
            plots.append(entry)
            if attached:
                images.append({"data": png, "mime_type": "image/png", "name": name})

        # 그림 1: 조건-지표
        try:
            x_key, xs = br.choose_x_axis(records)
            if policy.rank:
                series = [(policy.rank.signal, policy.rank.metric)]
                order = "higher is better" if policy.rank.descending else "lower is better"
                title = f"{policy.rank.column} vs {x_key} ({order}, top {len(highlight)} circled)"
            else:
                series = [(signal, "mean"), (signal, "ripple")]
                title = f"{signal} mean / ripple vs {x_key}"
            png = await asyncio.to_thread(
                br.render_metric_plot, records, series, x_key, xs, highlight, title
            )
            save("fig1_metrics.png", "metrics", png)
        except Exception as e:  # noqa: BLE001 - 그림 실패는 배치 결과에 영향 없음
            logger.warning("run_batch plot 1 failed", exc_info=True)
            notes.append(f"그림 1(조건-지표) 생성 실패: {type(e).__name__}: {e}")

        # 그림 2: 파형이 남아 있는 상위 run 겹쳐 그리기
        if max_images < 2:
            notes.append("max_images=1이라 그림 2(파형)는 만들지 않았습니다.")
            return images, plots, notes
        try:
            notes.extend(
                await self._waveform_plot(
                    records, policy, signal, highlight, skip_ratio, save, plot_window_s
                )
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("run_batch plot 2 failed", exc_info=True)
            notes.append(f"그림 2(파형) 생성 실패: {type(e).__name__}: {e}")
        return images, plots, notes

    @staticmethod
    def _first_signal(table: dict) -> str | None:
        for col in table["columns"]:
            if col.endswith(".mean"):
                return col[: -len(".mean")]
        return None

    async def _waveform_plot(
        self, records, policy, signal, highlight, skip_ratio, save, plot_window_s=None
    ):
        """상위 run의 .smv에서 파형을 읽어 그림 2(두 칸)를 그린다. 반환: notes.

        - 아래 칸: 측정 구간 전체 min/max envelope(반투명 띠 + 테두리선).
        - 위 칸: 측정 구간 끝 마지막 약 5 스위칭 주기를 원본 해상도로, 평균은 점선.
          주기는 plot_window_s(확대 길이, 초)가 있으면 그 길이를 쓰고, 없으면 1위 run의 측정 구간
          끝 원본 데이터 FFT로 추정한다. 추정 실패 시 측정 구간 마지막 1%.

        파형은 기존 분석 경로와 같은 브리지 ``extract_signals``로 읽되(확대 구간은 t_start로
        시간 범위 지정), 메인 브리지가 아니라 이미 PSIM을 띄운 상주 워커에서 실행한다
        (``pool.call_one``).
        """
        notes: list[str] = []
        by_run = {r["run"]: r for r in records}
        order = highlight or [r["run"] for r in records if r["executed"] and r["ok"]]
        candidates = [
            by_run[run]
            for run in order
            if by_run[run].get("smv_kept") and by_run[run].get("smv_path")
        ][: policy.top_k]
        if not candidates:
            notes.append(
                "남아 있는 파형(.smv)이 없어 그림 2(파형)는 건너뛰었습니다. "
                'keep_smv="top_k"(rank_by 필요) 또는 "all"이면 그려집니다.'
            )
            return notes
        traces = []
        x_label = "Time (s)"
        any_reduced = False
        for rec in candidates:
            res = await self._pool.call_one(
                "extract_signals",
                {
                    "graph_file": rec["smv_path"],
                    "signals": [signal, "Time"],
                    "skip_ratio": skip_ratio,  # 측정 구간(기본 마지막 50%)만
                    "max_points": br.WAVEFORM_MAX_POINTS,
                    # 등간격 추출은 고주파 리플을 에일리어싱하므로 구간별 min/max envelope
                    "reduce": "minmax",
                },
            )
            sigs = ((res.get("data") or {}).get("signals") or {}) if res.get("success") else {}
            y = sigs.get(signal)
            if not y:
                err = None if res.get("success") else (res.get("error") or {}).get("message")
                notes.append(
                    f"run {rec['run']}의 파형에서 '{signal}'을 읽지 못해 그림 2에서 뺐습니다"
                    + (f"({err})." if err else ".")
                )
                continue
            data = res.get("data") or {}
            t = (data.get("times") or {}).get(signal)
            bridge_reduced = bool((data.get("reduced") or {}).get(signal))
            # 브리지가 이미 줄였어야 하지만, 2000점을 넘으면 여기서도 같은 방식으로 줄인다.
            y, t, server_reduced = br.minmax_envelope(y, t)
            any_reduced = any_reduced or bridge_reduced or server_reduced
            t = t or []
            rank_text = f"#{rec['rank']} " if rec.get("rank") else ""
            label = f"{rank_text}run {rec['run']} ({br.describe_inputs(rec['inputs'])})"
            span = data.get("time_span")
            traces.append(
                {
                    "rec": rec,
                    "label": label,
                    "env_x": t[: len(y)],
                    "env_y": y,
                    "mean": br.metric_value(rec, signal, "mean"),
                    "span": span if isinstance(span, list) and len(span) == 2 else None,
                    "source_points": (data.get("source_points") or {}).get(signal),
                }
            )
        if not traces:
            notes.append("읽을 수 있는 파형이 없어 그림 2(파형)는 건너뛰었습니다.")
            return notes

        # 시간 축이 하나라도 없으면 모두 측정 구간 안 샘플 번호로 맞추고(축 섞임 방지) 확대는 생략.
        has_time = all(len(tr["env_x"]) == len(tr["env_y"]) and tr["span"] for tr in traces)
        zoom: dict = {}
        if has_time:
            zoom, zoom_notes = await self._zoom_window(traces[0], signal, skip_ratio, plot_window_s)
            notes.extend(zoom_notes)
            zoom_reduced = await self._read_zoom(traces, signal, skip_ratio, zoom, notes)
        else:
            x_label = "sample (measurement window)"
            for tr in traces:
                tr["env_x"] = list(range(len(tr["env_y"])))
            notes.append("결과에 Time 곡선이 없어 그림 2 위 칸(확대 파형)은 그리지 않았습니다.")
            zoom_reduced = False

        window = f"last {round((1 - skip_ratio) * 100)}%"
        method = "min/max envelope" if any_reduced else "full resolution"
        title = f"{signal} waveforms" + (
            f" (top {len(traces)} by {policy.rank.text})" if policy.rank else ""
        )
        if zoom.get("low_resolution"):
            title += f", low resolution: {zoom['samples_per_period']:g} samples/period"
        zoom_title = self._zoom_title(zoom, zoom_reduced)
        envelope_title = f"{window} of run, {method} (band = min..max)"
        plot_traces = [
            {k: tr.get(k) for k in ("label", "env_x", "env_y", "mean", "zoom_x", "zoom_y")}
            for tr in traces
        ]
        png = await asyncio.to_thread(
            br.render_waveform_plot,
            plot_traces,
            signal,
            title,
            zoom_title,
            envelope_title,
            x_label,
        )
        save("fig2_waveforms.png", "waveforms", png, {"zoom": zoom} if zoom else None)
        return notes

    async def _zoom_window(self, first: dict, signal: str, skip_ratio: float, plot_window_s):
        """확대 구간 길이와 주기 정보. 반환: (zoom 정보, notes).

        FFT 주기 추정·주기당 샘플 수·저해상도 경고는 plot_window_s 유무와 관계없이 항상 한다.
        plot_window_s는 확대 길이 결정에만 쓴다.

        zoom 정보: ``window_s``, ``window_source``(확대 길이: plot_window_s·fft·fallback),
        ``period_source``(fft, 추정 실패면 None), ``period_s``, ``samples_per_period``,
        ``low_resolution``.
        """
        notes: list[str] = []
        t0, t1 = float(first["span"][0]), float(first["span"][1])
        duration = t1 - t0
        info: dict = {
            "window_s": None,
            "window_source": None,
            "period_source": None,
            "period_s": None,
            "samples_per_period": None,
            "low_resolution": False,
        }
        if not duration > 0:
            notes.append("측정 구간 길이가 0이라 그림 2 위 칸(확대 파형)은 그리지 않았습니다.")
            return info, notes

        estimate = await self._estimate_period(first, signal, skip_ratio, t1, duration)
        if estimate:
            spp = estimate["samples_per_period"]
            info.update(
                period_source="fft",
                period_s=_sig(estimate["period_s"]),
                samples_per_period=spp,
                low_resolution=bool(spp < br.LOW_RESOLUTION_SAMPLES),
            )
            if info["low_resolution"]:
                notes.append(
                    f"스위칭 주기당 샘플이 {spp:g}개뿐이라(기준 {br.LOW_RESOLUTION_SAMPLES}개) "
                    "확대 파형이 거칠게 보입니다. 회로 Simulation Control의 PRINTSTEP을 줄이면"
                    "(1이면 모든 계산 점 저장) 해상도가 올라갑니다(.smv 크기는 커짐)."
                )

        if plot_window_s is not None:
            window = float(plot_window_s)
            if window > duration:
                notes.append(
                    f"plot_window_s({plot_window_s:g} s)가 측정 구간({duration:.6g} s)보다 길어 "
                    "측정 구간 전체를 확대 구간으로 썼습니다."
                )
                window = duration
            info.update(window_s=_sig(window), window_source="plot_window_s")
            if not estimate:
                notes.append(
                    "스위칭 주기를 FFT로 추정하지 못해 period_s·samples_per_period는 null입니다"
                    "(확대 길이는 plot_window_s 그대로)."
                )
        elif estimate:
            info.update(
                window_s=_sig(min(br.ZOOM_PERIODS * estimate["period_s"], duration)),
                window_source="fft",
            )
        else:
            info.update(
                window_s=_sig(duration * br.FALLBACK_WINDOW_FRACTION), window_source="fallback"
            )
            notes.append(
                "스위칭 주기를 FFT로 추정하지 못해 그림 2 위 칸은 측정 구간 마지막 1%를 "
                "확대했습니다. 원하는 길이는 plot_window_s(초)로 지정하세요."
            )
        return info, notes

    async def _estimate_period(self, first: dict, signal: str, skip_ratio, t1, duration):
        """1위 run 측정 구간 끝 최대 FFT_MAX_POINTS점(원본 해상도) FFT로 주기 추정. 실패면 None."""
        n_src = int(first.get("source_points") or 0)
        dt_est = duration / (n_src - 1) if n_src > 1 else None
        chunk = duration if dt_est is None else min(duration, dt_est * (br.FFT_MAX_POINTS - 1))
        estimate = None
        res = await self._pool.call_one(
            "extract_signals",
            {
                "graph_file": first["rec"]["smv_path"],
                "signals": [signal, "Time"],
                "skip_ratio": skip_ratio,
                "t_start": t1 - chunk,
                # dt 추정 오차 여유. 그래도 넘으면 envelope로 줄여 오므로 추정하지 않는다.
                "max_points": 2 * br.FFT_MAX_POINTS,
                "reduce": "minmax",
            },
        )
        if res.get("success"):
            data = res.get("data") or {}
            y = (data.get("signals") or {}).get(signal) or []
            t = (data.get("times") or {}).get(signal)
            if y and t and not (data.get("reduced") or {}).get(signal):
                y, t = y[-br.FFT_MAX_POINTS :], t[-br.FFT_MAX_POINTS :]
                estimate = await asyncio.to_thread(br.estimate_period, y, t)
        return estimate

    async def _read_zoom(self, traces, signal, skip_ratio, zoom: dict, notes: list[str]) -> bool:
        """traces마다 확대 구간 원본을 읽어 ``zoom_x``(run 끝 기준 상대 시간)·``zoom_y``를 채운다.

        반환: 점이 많아 envelope로 줄인 run이 있었는지.
        """
        window = zoom.get("window_s")
        if not window:
            return False
        any_reduced = False
        for i, tr in enumerate(traces):
            end = float(tr["span"][1])
            res = await self._pool.call_one(
                "extract_signals",
                {
                    "graph_file": tr["rec"]["smv_path"],
                    "signals": [signal, "Time"],
                    "skip_ratio": skip_ratio,
                    "t_start": end - window,
                    "max_points": br.ZOOM_MAX_POINTS,
                    "reduce": "minmax",
                },
            )
            data = (res.get("data") or {}) if res.get("success") else {}
            y = (data.get("signals") or {}).get(signal) or []
            t = (data.get("times") or {}).get(signal) or []
            if not y or len(t) != len(y):
                err = None if res.get("success") else (res.get("error") or {}).get("message")
                notes.append(
                    f"run {tr['rec']['run']}의 확대 구간을 읽지 못해 그림 2 위 칸에서 뺐습니다"
                    + (f"({err})." if err else ".")
                )
                continue
            if (data.get("reduced") or {}).get(signal):
                any_reduced = True
            if i == 0:
                zoom["window_samples"] = (data.get("source_points") or {}).get(signal, len(y))
            tr["zoom_x"] = [tt - end for tt in t]
            tr["zoom_y"] = y
        if any_reduced:
            notes.append(
                f"확대 구간 점이 {br.ZOOM_MAX_POINTS}개를 넘어 min/max envelope로 줄였습니다. "
                "원본 해상도로 보려면 plot_window_s를 줄이세요."
            )
        return any_reduced

    @staticmethod
    def _zoom_title(zoom: dict, reduced: bool) -> str:
        window = zoom.get("window_s")
        if not window:
            return "zoom: not available"
        res = "min/max envelope (too many points)" if reduced else "full resolution"
        if zoom.get("period_source") == "fft":
            period = (
                f"T = {br.eng(zoom['period_s'], 's')} by FFT, "
                f"{zoom['samples_per_period']:g} samples/period"
            )
        else:
            period = "period not found"
        source = zoom.get("window_source")
        if source == "fft":
            head = f"last {br.ZOOM_PERIODS} switching periods ({br.eng(window, 's')})"
        elif source == "plot_window_s":
            head = f"last {br.eng(window, 's')} (plot_window_s)"
        else:
            head = f"last 1% of measurement window ({br.eng(window, 's')})"
        return f"{head}, {period}, {res}"

    @staticmethod
    def _count_records(records: list[dict]) -> dict:
        """실행·성공 / 실행했지만 실패 / 형식 오류로 미실행. 세 값의 합 = 조건 수."""
        succeeded = sum(1 for r in records if r["executed"] and r["ok"])
        failed = sum(1 for r in records if r["executed"] and not r["ok"])
        invalid = sum(1 for r in records if not r["executed"])
        return {"succeeded": succeeded, "failed": failed, "invalid": invalid}

    @staticmethod
    def _invalid_report(records: list[dict]) -> dict:
        """형식 오류 조건 목록과 오류 코드별 suggestion(중복 제거).

        같은 코드의 suggestion이 대부분 같으므로 ``suggestions``에 코드당 한 번만 넣고,
        코드 대표 문장과 다른 경우에만 해당 조건 항목에 ``suggestion``을 붙인다(응답 크기 절약).
        """
        suggestions: dict[str, str] = {}
        items: list[dict] = []
        for r in records:
            if r["executed"]:
                continue
            err = r.get("error") or {}
            code = str(err.get("code"))
            item: dict[str, Any] = {"run": r["run"], "code": code, "message": err.get("message")}
            text = err.get("suggestion")
            if text:
                if code not in suggestions:
                    suggestions[code] = text
                elif suggestions[code] != text:
                    item["suggestion"] = text
            items.append(item)
        report: dict[str, Any] = {"invalid_conditions": items[:_MAX_TABLE_ROWS]}
        if len(items) > _MAX_TABLE_ROWS:
            report["invalid_conditions_truncated"] = len(items)
        if suggestions:
            report["suggestions"] = suggestions
        return report

    @staticmethod
    def _apply_storage(
        policy: sp.StoragePolicy, records: list[dict], study_dir: Path
    ) -> tuple[dict, list[str]]:
        """저장 정책 적용: 순위를 매기고 대상 외 .smv를 지운다. 행마다 rank·smv_kept를 기록."""
        notes: list[str] = []
        applied = policy.keep_smv
        ranked: list[tuple[int, float]] = []
        if policy.rank is not None:
            if sp.column_exists(records, policy.rank):
                ranked = sp.rank_records(records, policy.rank)
            else:
                signals = sorted(
                    {s for r in records if r.get("ok") for s in (r.get("summary") or {})}
                )
                note = (
                    f"rank_by 열 '{policy.rank.column}'가 결과에 없어 순위를 매기지 않았습니다"
                    f"(결과 신호: {', '.join(signals) or '없음'})."
                )
                if applied == "top_k":
                    applied = "none"
                    note += ' 그래서 keep_smv="none"으로 처리했습니다.'
                notes.append(note)
        if applied == "top_k" and policy.top_k > len(ranked):
            notes.append(
                f"top_k={policy.top_k}이지만 순위 대상이 {len(ranked)}개라 "
                f"{len(ranked)}개만 남겼습니다."
            )

        candidates: dict[int, list[str]] = {}
        for r in records:
            run_dir = study_dir / f"run_{r['run']:03d}"
            paths = [str(p) for p in sorted(run_dir.glob("*.smv"))] if run_dir.is_dir() else []
            if r.get("smv_path") and str(r["smv_path"]) not in paths:
                paths.append(str(r["smv_path"]))
            candidates[r["run"]] = paths
        plan = sp.plan_smv_deletion(candidates, ranked, applied, policy.top_k, study_dir)
        deleted, delete_failed = sp.delete_files(plan.delete)
        deleted_set = set(deleted)

        rank_of = {run: i + 1 for i, (run, _) in enumerate(ranked)}
        for r in records:
            remaining = [p for p in candidates[r["run"]] if p not in deleted_set]
            if policy.rank is not None:
                r["rank"] = rank_of.get(r["run"])
            r["smv_kept"] = bool(remaining)
            if r.get("smv_path") and str(r["smv_path"]) in deleted_set:
                r["smv_path"] = None

        kept_runs = [r["run"] for r in records if r["smv_kept"]]
        if applied == "top_k":
            runs_text = ", ".join(map(str, plan.keep_runs)) or "없음"
            notes.append(
                f"파형(.smv)은 rank_by({policy.rank.text}) 상위 {len(plan.keep_runs)}개"
                f"(run {runs_text})만 남겼습니다. "
                '전부 필요하면 keep_smv="all"로 다시 요청하세요.'
            )
        elif applied == "none" and any(candidates.values()):
            notes.append(
                "파형(.smv)은 남기지 않았습니다(config.json·summary.json·results.csv만 보존). "
                '전부 필요하면 keep_smv="all"로 다시 요청하세요.'
            )
        if delete_failed:
            notes.append(
                f".smv {len(delete_failed)}개를 지우지 못했습니다(파일 잠금 등). "
                "storage.delete_failed 참고 — 배치 결과에는 영향이 없습니다."
            )
        if plan.rejected:
            notes.append(
                f"study 폴더의 run_NNN/*.smv가 아닌 경로 {len(plan.rejected)}개는 "
                "지우지 않았습니다(storage.rejected 참고)."
            )
        storage = {
            **policy.as_dict(),
            "applied_keep_smv": applied,
            "ranked": len(ranked),
            "kept_runs": kept_runs,
            "deleted": deleted,
            "delete_failed": delete_failed,
            "rejected": plan.rejected,
        }
        return storage, notes

    def _build_table(
        self, records: list[dict], signals: list[str] | None, with_rank: bool = False
    ) -> dict:
        input_keys: list[str] = []
        all_signals: list[str] = []
        for r in records:
            for k in r["inputs"]:
                if k not in input_keys:
                    input_keys.append(k)
            for s in r.get("summary") or {}:
                if s not in all_signals:
                    all_signals.append(s)
        if signals:
            shown = [s for s in signals if s in all_signals]
            omitted: list[str] = []
        else:
            shown, omitted = all_signals[:_MAX_TABLE_SIGNALS], all_signals[_MAX_TABLE_SIGNALS:]
        columns = ["run", *input_keys, "status", "executed"]
        columns += (
            (["rank"] if with_rank else [])
            + ["sim_s"]
            + [f"{s}.{m}" for s in shown for m in _METRICS]
        )
        rows = []
        messages: dict[int, str] = {}  # results.csv 전용 오류 메시지 열
        for r in records:
            row: dict[str, Any] = {"run": r["run"]}
            for k in input_keys:
                row[k] = r["inputs"].get(k)
            if with_rank:
                row["rank"] = r.get("rank")
            if r["ok"]:
                row["status"] = "ok"
                row["executed"] = True
                row["sim_s"] = _round(r.get("sim_s"))
                for s in shown:
                    m = (r.get("summary") or {}).get(s) or {}
                    for metric in _METRICS:
                        row[f"{s}.{metric}"] = _round(m.get(metric))
            else:
                err = r.get("error") or {}
                message = str(err.get("message"))[:200]
                messages[r["run"]] = message
                if r["executed"]:
                    row["status"] = f"error: {err.get('code')}: {message}"
                else:
                    # 메시지·suggestion은 응답의 invalid_conditions·suggestions에 있다(크기 절약).
                    row["status"] = f"error: {err.get('code')}"
                row["executed"] = bool(r["executed"])
            rows.append(row)
        return {
            "columns": columns,
            "rows": rows,
            "omitted_signals": omitted,
            "messages": messages,
        }

    @staticmethod
    def _write_study_files(
        study_dir: Path, summary: dict, records: list[dict], table: dict
    ) -> None:
        (study_dir / "study.json").write_text(
            json.dumps({"summary": summary, "runs": records}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
        columns = [*table["columns"], "message"]
        with (study_dir / "results.csv").open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for row in table["rows"]:
                writer.writerow({**row, "message": table["messages"].get(row["run"], "")})

    # ------------------------------------------------------------------
    # 병렬 스윕 (sweep_parameter parallel=True)
    # ------------------------------------------------------------------

    async def sweep(
        self,
        component_id: str,
        parameter_name: str,
        values: list[float],
        metrics: list[str] | None = None,
        workers: int | None = None,
    ) -> dict:
        key = f"{component_id}.{parameter_name}"
        res = await self.run_batch(
            [{key: v} for v in values],
            workers=workers,
            study_name=f"sweep_{component_id}_{parameter_name}",
            strict=True,  # 스윕은 모든 단계가 같은 키라 기존처럼 전체 거부
            keep_smv="all",  # 병렬 스윕은 저장 정책과 무관하게 .smv를 모두 보존
        )
        if not res.get("success"):
            return res
        data = res["data"]
        study = json.loads((Path(data["study_dir"]) / "study.json").read_text(encoding="utf-8"))
        steps = []
        for rec, value in zip(study["runs"], values):
            step: dict[str, Any] = {"value": round(value, 10)}
            if rec["ok"]:
                flat = {
                    f"{s}.{m}": _round(v)
                    for s, ms in (rec.get("summary") or {}).items()
                    for m, v in ms.items()
                    if m in _METRICS
                }
                step["summary"] = flat
                if metrics:
                    step["metrics"] = {m: flat.get(m) for m in metrics}
            else:
                step["error"] = rec.get("error")
            steps.append(step)
        failed = sum(1 for s in steps if "error" in s)
        result = {
            "component_id": component_id,
            "parameter_name": parameter_name,
            "total_steps": len(steps),
            "failed_steps": failed,
            "results": steps,
            "parallel": {
                "workers": data["workers"],
                "total_s": data["total_s"],
                "study_dir": data["study_dir"],
                "modifies_open_project": False,
            },
        }
        msg = f"병렬 파라미터 스윕 완료: {len(steps)}단계, 워커 {data['workers']}개, {data['total_s']:.1f}초"
        if failed:
            msg += f" (실패 {failed}건)"
        return ResponseBuilder.success(result, msg + ". 열린 회로 파일은 바뀌지 않았습니다.")

    # ------------------------------------------------------------------
    # 벤치마크
    # ------------------------------------------------------------------

    async def benchmark(
        self,
        schematic_path: str | None = None,
        levels: list[int] | None = None,
        runs: int | None = None,
        conditions: list[dict] | None = None,
        save: bool = True,
    ) -> dict:
        try:
            return await self._benchmark(schematic_path, levels, runs, conditions, save)
        except BatchInputError as e:
            return ResponseBuilder.error(e.code, str(e), e.suggestion, e.details)
        except PoolError as e:
            return ResponseBuilder.error(e.code, str(e), None, e.details)

    async def _benchmark(self, schematic_path, levels, runs, conditions, save) -> dict:
        source = self._resolve_schematic(schematic_path)
        phys, logi = physical_cores(), logical_cores()
        if levels:
            if any((not isinstance(n, int)) or n < 1 or n > logi for n in levels):
                raise BatchInputError(
                    "INVALID_INPUT", f"levels 값은 1~{logi} 사이 정수여야 합니다."
                )
            levels = sorted(set(levels))
        else:
            levels = sorted({1, 2, 4, phys, logi} & set(range(1, logi + 1)))
        n_runs = runs or 2 * max(levels)
        if n_runs < 2 * max(levels) or n_runs > self._config.max_batch_conditions:
            raise BatchInputError(
                "INVALID_INPUT",
                f"runs는 최대 동시 실행 수의 2배({2 * max(levels)}) 이상, "
                f"{self._config.max_batch_conditions} 이하여야 합니다.",
            )

        bench_id, bench_dir = self._new_study_dir("bench", "bench")
        # 측정용 사본만 사용한다: 원본은 읽어서 복사만 하고 이후 사본으로만 실행한다.
        copy = bench_dir / f"bench_{source.name}"
        await asyncio.to_thread(shutil.copy2, source, copy)
        parsed = None
        if conditions:
            base = self.parse_conditions(conditions)
            parsed = [base[i % len(base)] for i in range(n_runs)]
            await self.precheck(copy, base)

        table, reference, stop_reason = [], None, None
        for level in levels:
            jobs = []
            for i in range(n_runs):
                cond = parsed[i] if parsed else {"variables": {}, "elements": []}
                jobs.append(
                    {
                        "schematic": str(copy),
                        "run_dir": str(bench_dir / f"c{level:02d}" / f"run_{i:03d}"),
                        "variables": cond["variables"],
                        "elements": cond["elements"],
                        "keep_smv": False,
                    }
                )
            results, info = await self._pool.run_jobs(jobs, level)
            ok = [r for r in results if r.get("success")]
            row = {
                "workers": level,
                "started_workers": info["workers"],
                "runs": n_runs,
                "ok": len(ok),
                "total_s": info["total_s"],
                "avg_interval_s": round(info["total_s"] / n_runs, 4),
                "per_run_wall_s": round(sum(r["wall_s"] for r in ok) / len(ok), 4) if ok else None,
                "runs_per_min": round(60.0 * len(ok) / max(info["total_s"], 1e-3), 1),
                "pool_start_s": info["pool_start_s"],
            }
            summaries = [(r.get("data") or {}).get("summary") for r in results]
            if reference is None:
                reference = summaries
            row["matches_sequential"] = self._max_rel_diff(reference, summaries)
            if info["init_errors"]:
                row["init_errors"] = info["init_errors"]
            failed = [r for r in results if not r.get("success")]
            if failed:
                row["errors"] = [(r.get("error") or {}) for r in failed[:3]]
            table.append(row)
            if info["init_errors"] or info["workers"] < level:
                stop_reason = f"동시 {level}: 워커 시작 실패(라이선스 가능성) — 더 올리지 않고 멈춤"
                break
            if failed:
                stop_reason = f"동시 {level}: 실행 실패 {len(failed)}건 — 더 올리지 않고 멈춤"
                break

        base_row = next((r for r in table if r["workers"] == 1 and r["ok"] == r["runs"]), None)
        for r in table:
            if base_row and r["total_s"]:
                r["speedup_vs_sequential"] = round(base_row["total_s"] / r["total_s"], 2)

        # 기본값 후보는 물리 코어 수 이하에서만 고른다(논리 스레드 수를 기본값으로 쓰지 않음).
        candidates = [
            r for r in table if r["ok"] == r["runs"] and r["workers"] <= phys and r["runs_per_min"]
        ]
        best = None
        if candidates:
            top = max(c["runs_per_min"] for c in candidates)
            # 3% 이내면 더 작은 동시 실행 수를 고른다(자원·라이선스 절약).
            best = min(c["workers"] for c in candidates if c["runs_per_min"] >= top * 0.97)

        # 측정 후 기본값보다 많이 띄운 워커는 정리해 라이선스를 돌려준다.
        await self._pool.trim(best or 1)

        notes = []
        mean_run = [r["per_run_wall_s"] for r in table if r["workers"] == 1 and r["per_run_wall_s"]]
        if mean_run and mean_run[0] < _SHORT_RUN_WARNING_S:
            notes.append(
                f"실행당 {mean_run[0]:.3f}초로 짧아 오버헤드 비중이 큽니다. 실제 작업과 비슷한 길이의 회로로 측정하세요."
            )
        saved_path = None
        if save and best:
            record = {
                "schematic": str(source),
                "bench_dir": str(bench_dir),
                "levels": table,
                "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            saved_path = str(parallel_settings.save_benchmark(self._config, best, record))
        data = {
            "bench_id": bench_id,
            "bench_dir": str(bench_dir),
            "bench_copy": str(copy),
            "physical_cores": phys,
            "logical_cores": logi,
            "levels": table,
            "best_workers": best,
            "saved_to": saved_path,
            "stopped": stop_reason,
            "notes": notes,
        }
        msg = (
            f"벤치마크 완료: 최적 동시 실행 수 {best}"
            + (f" (저장: {saved_path})" if saved_path else " (저장 안 함)")
            if best
            else "벤치마크에서 기본값을 정하지 못했습니다."
        )
        return ResponseBuilder.success(data, msg)

    @staticmethod
    def _max_rel_diff(ref: list, cur: list) -> float | None:
        worst, compared = 0.0, 0
        for a, b in zip(ref, cur):
            if not a or not b:
                continue
            for sig, ma in a.items():
                mb = b.get(sig) or {}
                for k in _METRICS:
                    if k in ma and k in mb:
                        compared += 1
                        denom = abs(ma[k]) if abs(ma[k]) > 1e-12 else 1.0
                        worst = max(worst, abs(ma[k] - mb[k]) / denom)
        return worst if compared else None

    # ------------------------------------------------------------------
    # 뷰어
    # ------------------------------------------------------------------

    async def open_in_viewer(self, graph_file: str) -> dict:
        if not graph_file:
            return ResponseBuilder.error("INVALID_INPUT", "graph_file이 필요합니다.")
        path = Path(graph_file)
        if path.suffix.lower() != ".smv":
            return ResponseBuilder.error("INVALID_EXTENSION", "결과 파일(.smv)만 열 수 있습니다.")
        if not path.is_file():
            return ResponseBuilder.error(
                "FILE_NOT_FOUND", f"결과 파일을 찾을 수 없습니다: {graph_file}"
            )
        resolved = path.resolve()
        allowed = [Path(d).resolve() for d in self._config.allowed_project_dirs]
        if allowed:
            allowed.append(self.runs_root().resolve())
            if not any(resolved.is_relative_to(d) for d in allowed):
                return ResponseBuilder.error(
                    "PATH_NOT_ALLOWED", "지정된 경로가 허용된 디렉터리 범위를 벗어났습니다."
                )
        try:
            data = await self._adapter.open_in_viewer(str(resolved))
        except NotImplementedError:
            return ResponseBuilder.error("NOT_SUPPORTED", "현재 모드에서는 뷰어를 열 수 없습니다.")
        except Exception as e:
            return ResponseBuilder.error("VIEWER_FAILED", f"Simview 실행 실패: {e}")
        return ResponseBuilder.success(data, f"Simview로 열었습니다: {resolved.name}")
