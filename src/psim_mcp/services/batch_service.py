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
    ) -> dict:
        try:
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
                (study_dir / f"run_{i:03d}" / "summary.json").write_text(
                    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8"
                )
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
            (study_dir / f"run_{i:03d}" / "summary.json").write_text(
                json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            records.append(rec)

        table = self._build_table(records, signals)
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
        }
        self._write_study_files(study_dir, summary, records, table)
        data = dict(summary)
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
        return ResponseBuilder.success(data, msg)

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

    def _build_table(self, records: list[dict], signals: list[str] | None) -> dict:
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
        columns = ["run", *input_keys, "status", "executed", "sim_s"] + [
            f"{s}.{m}" for s in shown for m in _METRICS
        ]
        rows = []
        messages: dict[int, str] = {}  # results.csv 전용 오류 메시지 열
        for r in records:
            row: dict[str, Any] = {"run": r["run"]}
            for k in input_keys:
                row[k] = r["inputs"].get(k)
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
