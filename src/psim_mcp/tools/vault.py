"""Vault tools: Drive original + local copy routine for PSIM projects.

Routine
-------
신규:  vault_register(파일, 이름)       → 드라이브 원본 v001 + 로컬 사본 v001
수정:  vault_edit_and_run(이름, 변경목록) → 드라이브 원본 받기 → 수정 → 시뮬레이션
                                         → 드라이브 원본 v00N 갱신 + 로컬 사본 v00N
수동:  vault_checkout → (open_project/set_parameter/run_simulation …) → vault_commit
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

from psim_mcp.services.vault_service import VaultError, VaultService, vfmt
from psim_mcp.shared.response import ResponseBuilder
from psim_mcp.tools import tool_handler


def _err(e: VaultError) -> dict:
    return ResponseBuilder.error(e.code, e.message, e.suggestion)


def _compact(obj: Any, max_list: int = 50, max_str: int = 2000) -> Any:
    """Drop bulky waveform arrays before storing/returning a summary."""
    if isinstance(obj, dict):
        return {k: _compact(v, max_list, max_str) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) > max_list:
            return f"<list of {len(obj)} items omitted>"
        return [_compact(v, max_list, max_str) for v in obj]
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + f"... ({len(obj)} chars)"
    return obj


_SI = {
    "T": 1e12,
    "G": 1e9,
    "MEG": 1e6,
    "meg": 1e6,
    "M": 1e6,
    "k": 1e3,
    "K": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "µ": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}


def _to_number(v: Any) -> float | None:
    """Parse numbers incl. PSIM-style SI suffixes (22u, 4.7m, 100k, 1meg)."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    t = str(v).strip()
    try:
        return float(t)
    except ValueError:
        pass
    for suf in sorted(_SI, key=len, reverse=True):
        if t.endswith(suf):
            try:
                return float(t[: -len(suf)]) * _SI[suf]
            except ValueError:
                return None
    return None


def _compare(actual: Any, requested: Any) -> str:
    """'same' | 'different' | 'unknown' (e.g. expression/variable values)."""
    a, r = _to_number(actual), _to_number(requested)
    if a is not None and r is not None:
        return "same" if abs(a - r) <= 1e-9 * max(1.0, abs(a), abs(r)) else "different"
    if str(actual).strip() == str(requested).strip():
        return "same"
    return "unknown"


def _find_components(info: Any) -> list[dict]:
    """Locate the component list in a (possibly nested) project-info response."""
    if isinstance(info, dict):
        comps = info.get("components")
        if isinstance(comps, list):
            return comps
        for v in info.values():
            found = _find_components(v)
            if found:
                return found
    return []


async def _verify(project_svc, component_id: str, parameter_name: str, value: Any) -> dict:
    """Read the parameter back to catch PSIM's silent no-op on wrong names."""
    try:
        info = await project_svc.get_project_info()
    except Exception:  # noqa: BLE001
        return {"status": "unverified", "reason": "프로젝트 정보 조회 실패"}
    for comp in _find_components(info):
        if str(comp.get("name", comp.get("id", ""))) != component_id:
            continue
        params = comp.get("parameters") or {}
        if parameter_name not in params:
            return {
                "status": "not_applied",
                "reason": f"'{component_id}'에 '{parameter_name}' 파라미터가 없습니다(이름 오류 가능).",
                "available": sorted(params.keys())[:40],
            }
        actual = params[parameter_name]
        cmp = _compare(actual, value)
        if cmp == "same":
            return {"status": "verified", "actual": actual}
        if cmp == "unknown":
            return {
                "status": "unverified",
                "reason": "값 형식(수식·변수)이라 비교하지 못했습니다.",
                "actual": actual,
            }
        return {
            "status": "not_applied",
            "reason": "다시 읽은 값이 요청 값과 다릅니다.",
            "actual": actual,
        }
    return {
        "status": "unverified",
        "reason": f"'{component_id}' 소자를 정보 목록에서 찾지 못했습니다.",
    }


def register_tools(mcp, services: dict, vault: VaultService | None = None) -> VaultService:
    vault = vault or VaultService()
    project_svc = services["project"]
    sim_svc = services["simulation"]
    lock = asyncio.Lock()

    @mcp.tool(
        description=(
            "드라이브 원본/로컬 사본 저장소 상태를 보여줍니다: 드라이브·로컬 경로가 살아 있는지, "
            "등록된 프로젝트와 현재 버전 목록."
        ),
    )
    @tool_handler("vault_status")
    async def vault_status() -> dict:
        data = await asyncio.to_thread(vault.status)
        msg = (
            "저장소 상태를 조회했습니다."
            if data["drive_root_exists"]
            else "드라이브 원본 폴더가 보이지 않습니다."
        )
        return ResponseBuilder.success(data, msg)

    @mcp.tool(
        description=("프로젝트의 버전 이력(manifest)을 보여줍니다: 버전, 저장 시각, 메시지, 해시."),
    )
    @tool_handler("vault_history")
    async def vault_history(project: str) -> dict:
        try:
            p = vault.paths(project)
            man = await asyncio.to_thread(vault._read_manifest, p)
        except VaultError as e:
            return _err(e)
        return ResponseBuilder.success(man, f"'{project}' 이력 {len(man['versions'])}개 버전.")

    @mcp.tool(
        description=(
            "새 프로젝트 최초 저장: 기존/새로 만든 .psimsch 파일을 드라이브 원본 v001로 등록하고 "
            "로컬에 사본 v001을 저장합니다. project는 영문·숫자·_·- (예: buck_48v)."
        ),
    )
    @tool_handler("vault_register")
    async def vault_register(source_path: str, project: str, message: str = "") -> dict:
        async with lock:
            try:
                data = await asyncio.to_thread(vault.register, source_path, project, message)
            except VaultError as e:
                return _err(e)
        return ResponseBuilder.success(
            data, f"'{project}' 원본 v001을 드라이브에 저장하고 로컬 사본을 만들었습니다."
        )

    @mcp.tool(
        description=(
            "드라이브 원본을 로컬 작업 폴더로 가져와(체크아웃) PSIM 프로젝트로 엽니다. 이후 "
            "set_parameter / run_simulation으로 작업하고 vault_commit으로 저장하세요. "
            "커밋하지 않은 작업이 있으면 거부되며, 버리려면 force=true."
        ),
    )
    @tool_handler("vault_checkout")
    async def vault_checkout(project: str, force: bool = False, open_project: bool = True) -> dict:
        async with lock:
            try:
                data = await asyncio.to_thread(vault.checkout, project, force)
            except VaultError as e:
                return _err(e)
            if open_project:
                opened = await project_svc.open_project(data["work_file"])
                data["opened"] = bool(opened.get("success"))
                if not opened.get("success"):
                    data["open_error"] = opened.get("error")
        return ResponseBuilder.success(
            data, f"'{project}' {data['base_version']} 원본을 작업 폴더로 가져왔습니다."
        )

    @mcp.tool(
        description=(
            "작업 파일을 다음 버전으로 저장합니다: 드라이브 원본 갱신(이전 버전은 history에 보존) + "
            "로컬 사본 저장. 체크아웃 이후 드라이브 원본이 다른 곳에서 바뀌었으면 충돌로 거부(force=true로 덮어쓰기)."
        ),
    )
    @tool_handler("vault_commit")
    async def vault_commit(project: str, message: str = "", force: bool = False) -> dict:
        async with lock:
            try:
                data = await asyncio.to_thread(vault.commit, project, message, force)
            except VaultError as e:
                return _err(e)
        msg = (
            f"'{project}' {data['version']}로 드라이브 원본과 로컬 사본을 저장했습니다."
            if data.get("committed")
            else data.get("reason", "커밋하지 않았습니다.")
        )
        return ResponseBuilder.success(data, msg)

    @mcp.tool(
        description=(
            "한 번에 처리하는 수정 루틴(핸드폰 명령용): 드라이브 원본 가져오기 → 파라미터 변경(각각 다시 읽어 "
            "적용 여부 검증) → 시뮬레이션 → 드라이브 원본 새 버전 저장 + 로컬 사본 저장 → 결과 요약을 "
            "드라이브 results/vNNN에 저장. 변경 적용 실패나 시뮬레이션 실패 시 드라이브 원본은 그대로 둡니다.\n"
            'changes 예: [{"component_id": "L1", "parameter_name": "Inductance", "value": 2.2e-5}]'
        ),
    )
    @tool_handler("vault_edit_and_run")
    async def vault_edit_and_run(
        project: str,
        changes: list[dict],
        message: str = "",
        run: bool = True,
        total_time: float | None = None,
        time_step: float | None = None,
        copy_smv_to_drive: bool = False,
        commit_on_sim_failure: bool = False,
    ) -> dict:
        async with lock:
            # 1) 드라이브 원본 → 작업 폴더 (항상 최신 원본 기준)
            try:
                co = await asyncio.to_thread(vault.checkout, project, True)
            except VaultError as e:
                return _err(e)
            opened = await project_svc.open_project(co["work_file"])
            if not opened.get("success"):
                return ResponseBuilder.error(
                    "OPEN_FAILED",
                    "작업 파일을 PSIM에서 열지 못했습니다. 드라이브 원본은 변경되지 않았습니다.",
                )

            # 2) 파라미터 변경 + 검증
            applied = []
            for ch in changes or []:
                cid, pname = ch.get("component_id"), ch.get("parameter_name")
                if not cid or not pname or "value" not in ch:
                    return ResponseBuilder.error(
                        "INVALID_CHANGE",
                        f"변경 항목 형식 오류: {ch}",
                        "component_id, parameter_name, value 세 키가 필요합니다.",
                    )
                res = await sim_svc.set_parameter(cid, pname, ch["value"])
                if not res.get("success"):
                    return ResponseBuilder.error(
                        "SET_PARAMETER_FAILED",
                        f"{cid}.{pname} 변경 실패: {str(res.get('error', {}).get('message')).rstrip('.')}. 드라이브 원본은 변경되지 않았습니다.",
                    )
                check = await _verify(project_svc, cid, pname, ch["value"])
                applied.append(
                    {
                        "component_id": cid,
                        "parameter_name": pname,
                        "value": ch["value"],
                        "check": check,
                    }
                )
                if check["status"] == "not_applied":
                    return ResponseBuilder.error(
                        "PARAM_NOT_APPLIED",
                        f"{cid}.{pname} 값이 실제로 적용되지 않았습니다: {check['reason']} 드라이브 원본은 변경되지 않았습니다.",
                        f"사용 가능한 파라미터: {check.get('available', [])}",
                    )

            # 3) 시뮬레이션
            sim_summary, sim_ok, smv = None, True, None
            if run:
                opts = {
                    k: v
                    for k, v in {"total_time": total_time, "time_step": time_step}.items()
                    if v is not None
                }
                sim = await sim_svc.run_simulation(opts or None)
                sim_ok = bool(sim.get("success"))
                sim_summary = _compact(sim)
                smv = ((sim.get("data") or {}).get("output_path")) if sim_ok else None
                if not sim_ok and not commit_on_sim_failure:
                    return ResponseBuilder.error(
                        "SIMULATION_FAILED",
                        f"시뮬레이션 실패: {str((sim.get('error') or {}).get('message')).rstrip('.')}. 드라이브 원본은 변경되지 않았습니다.",
                    )

            # 4) 드라이브 원본 새 버전 + 로컬 사본
            auto_msg = ", ".join(
                f"{a['component_id']}.{a['parameter_name']}={a['value']}" for a in applied
            )
            try:
                cm = await asyncio.to_thread(
                    vault.commit, project, message or auto_msg or "edit_and_run", False
                )
            except VaultError as e:
                return _err(e)

            # 5) 결과 저장 (드라이브: 요약[+smv], 로컬: smv 보관)
            results = {}
            if run and sim_ok:
                # 새 버전이 생겼으면 그 버전, 변경이 없었으면 기존 원본 버전에 결과를 붙인다
                version = int(cm["version"][1:])
                summary = {
                    "project": project,
                    "version": cm["version"],
                    "changes": applied,
                    "simulation": sim_summary,
                }
                results["drive"] = await asyncio.to_thread(
                    vault.save_results,
                    project,
                    version,
                    summary,
                    smv if copy_smv_to_drive else None,
                )
                if smv and Path(smv).is_file():
                    p = vault.paths(project)
                    local_dst = p.local_dir / "results" / vfmt(version) / Path(smv).name
                    local_dst.parent.mkdir(parents=True, exist_ok=True)
                    await asyncio.to_thread(shutil.copy2, smv, local_dst)
                    results["local_smv"] = str(local_dst)

        data = {
            "project": project,
            "from_version": co["base_version"],
            "commit": cm,
            "changes": applied,
            "simulation_ok": sim_ok if run else None,
            "simulation": sim_summary,
            "results": results,
        }
        if cm.get("committed"):
            msg = f"'{project}' {co['base_version']} → {cm['version']}: 드라이브 원본과 로컬 사본을 저장했습니다."
        else:
            msg = f"'{project}': 변경 사항이 없어 새 버전을 만들지 않았습니다."
        return ResponseBuilder.success(data, msg)

    return vault
