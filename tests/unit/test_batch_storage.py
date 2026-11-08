"""run_batch 저장 정책(rank_by·top_k·keep_smv) mock 테스트.

mock 워커: Vo1.ripple = 0.004 / Lx, I(L1).ripple = 2 × Vo1.ripple → Lx가 클수록 리플이 작다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.server import create_app


@pytest.fixture
def env(tmp_path: Path):
    cfg = AppConfig(
        psim_mode="mock",
        psim_output_dir=tmp_path / "output",
        log_dir=tmp_path / "logs",
        allowed_project_dirs=[str(tmp_path)],
        runs_dir=tmp_path / "runs",
        parallel_settings_path=tmp_path / "parallel.json",
        parallel_idle_timeout=0,
        vault_drive_root=tmp_path / "drive",
        vault_local_root=tmp_path / "local",
    )
    (tmp_path / "drive").mkdir()
    app = create_app(cfg)
    sch = tmp_path / "buck.psimsch"
    sch.write_bytes(b"<psim/>")
    return app, cfg, sch


async def _call(app, name: str, **kwargs) -> dict:
    result = await app.call_tool(name, kwargs)
    blocks = result[0] if isinstance(result, tuple) else result
    return json.loads(blocks[0].text)


async def _close(app):
    await app._services["pool"].shutdown()


def _lx(n: int) -> list[dict]:
    return [{"Lx": round(0.001 * (i + 1), 6)} for i in range(n)]


def _smv_runs(study: Path) -> list[int]:
    return sorted(int(p.parent.name[4:]) for p in study.glob("run_*/*.smv"))


def _study(data: dict) -> tuple[Path, dict]:
    study = Path(data["study_dir"])
    return study, json.loads((study / "study.json").read_text(encoding="utf-8"))


async def _run(app, sch, conditions, **kwargs) -> dict:
    res = await _call(
        app, "run_batch", schematic_path=str(sch), conditions=conditions, workers=2, **kwargs
    )
    await _close(app)
    return res


# ---------------------------------------------------------------------------
# 순위와 기본값
# ---------------------------------------------------------------------------


async def test_rank_by_ascending_keeps_top3_by_default(env):
    app, _, sch = env
    res = await _run(app, sch, _lx(6), rank_by="I(L1).ripple")
    assert res["success"], res
    data = res["data"]
    # 오름차순: Lx가 큰 run 5가 1위
    ranks = {r["run"]: r["rank"] for r in data["rows"]}
    assert ranks == {5: 1, 4: 2, 3: 3, 2: 4, 1: 5, 0: 6}
    assert "rank" in data["columns"]
    st = data["storage"]
    assert st["keep_smv"] == "top_k" and st["keep_smv_defaulted"] is True and st["top_k"] == 3
    assert st["applied_keep_smv"] == "top_k" and st["kept_runs"] == [3, 4, 5]
    assert st["deleted_count"] == 3 and st["delete_failed"] == []
    assert any('keep_smv="all"' in n and "상위 3개" in n for n in data["notes"])

    study, saved = _study(data)
    assert _smv_runs(study) == [3, 4, 5]
    assert saved["summary"]["storage"]["rank_by"] == "I(L1).ripple"
    assert len(saved["summary"]["storage"]["deleted"]) == 3
    by_run = {r["run"]: r for r in saved["runs"]}
    assert by_run[5]["rank"] == 1 and by_run[5]["smv_kept"] is True
    assert by_run[0]["smv_kept"] is False and by_run[0]["smv_path"] is None
    # run 폴더 summary.json에도 순위·보존 여부
    run0 = json.loads((study / "run_000" / "summary.json").read_text(encoding="utf-8"))
    assert run0["rank"] == 6 and run0["smv_kept"] is False
    # 요약 파일은 모두 남는다
    for i in range(6):
        assert (study / f"run_{i:03d}" / "summary.json").exists()
        assert (study / f"run_{i:03d}" / "config.json").exists()
    assert (study / "results.csv").exists()


async def test_rank_by_descending_with_explicit_top_k(env):
    app, _, sch = env
    res = await _run(app, sch, _lx(5), rank_by="-Vo1.ripple", top_k=2)
    data = res["data"]
    assert [r["rank"] for r in data["rows"]] == [1, 2, 3, 4, 5]
    assert data["storage"]["kept_runs"] == [0, 1]
    assert _smv_runs(Path(data["study_dir"])) == [0, 1]


async def test_ties_rank_lower_run_first(env):
    app, _, sch = env
    conds = [{"Lx": 0.001}, {"Lx": 0.004}, {"Lx": 0.002}, {"Lx": 0.004}, {"Lx": 0.004}]
    res = await _run(app, sch, conds, rank_by="Vo1.ripple", top_k=2)
    data = res["data"]
    ranks = {r["run"]: r["rank"] for r in data["rows"]}
    assert ranks == {1: 1, 3: 2, 4: 3, 2: 4, 0: 5}
    assert data["storage"]["kept_runs"] == [1, 3]


async def test_failed_and_invalid_rows_are_not_ranked(env, monkeypatch):
    app, _, sch = env
    batch = app._services["batch"]
    real_precheck = batch.precheck

    async def let_fail_through(schematic, parsed, strict=True):
        info = await real_precheck(schematic, parsed, strict=strict)
        for c in parsed:
            if "__fail__" in c["variables"]:
                c.pop("error", None)
        return info

    monkeypatch.setattr(batch, "precheck", let_fail_through)
    conds = [
        {"Lx": 0.001},
        {"Lx": 0.009, "__fail__": 1},  # 실행했지만 실패
        {"L1": 0.002},  # 형식 오류
        {"Lx": 0.003},
    ]
    res = await _run(app, sch, conds, rank_by="Vo1.ripple", top_k=3)
    data = res["data"]
    ranks = {r["run"]: r.get("rank") for r in data["rows"]}
    assert ranks == {0: 2, 1: None, 2: None, 3: 1}
    assert (data["succeeded"], data["failed"], data["invalid"]) == (2, 1, 1)
    assert data["storage"]["ranked"] == 2
    assert any("top_k=3이지만 순위 대상이 2개" in n for n in data["notes"])
    assert _smv_runs(Path(data["study_dir"])) == [0, 3]


async def test_missing_rank_column_falls_back_to_none(env):
    app, _, sch = env
    res = await _run(app, sch, _lx(3), rank_by="Vx.mean")
    assert res["success"], res
    data = res["data"]
    st = data["storage"]
    assert st["keep_smv"] == "top_k" and st["applied_keep_smv"] == "none"
    assert st["ranked"] == 0 and st["kept_runs"] == []
    assert all(r["rank"] is None for r in data["rows"])
    note = next(n for n in data["notes"] if "Vx.mean" in n)
    assert 'keep_smv="none"' in note and "Vo1" in note
    assert _smv_runs(Path(data["study_dir"])) == []


async def test_default_without_rank_by_keeps_no_smv(env):
    app, _, sch = env
    res = await _run(app, sch, _lx(3))
    data = res["data"]
    assert "rank" not in data["columns"]
    st = data["storage"]
    assert (st["keep_smv"], st["rank_by"], st["keep_smv_defaulted"]) == ("none", None, True)
    assert any("남기지 않았습니다" in n and 'keep_smv="all"' in n for n in data["notes"])
    study, saved = _study(data)
    assert _smv_runs(study) == []
    assert all(r["smv_kept"] is False and "rank" not in r for r in saved["runs"])


async def test_keep_all_keeps_every_smv_with_rank(env):
    app, _, sch = env
    res = await _run(app, sch, _lx(4), rank_by="Vo1.ripple", keep_smv="all")
    data = res["data"]
    assert data["storage"]["deleted_count"] == 0
    assert [r["rank"] for r in data["rows"]] == [4, 3, 2, 1]
    assert _smv_runs(Path(data["study_dir"])) == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# 삭제 실패·안전장치
# ---------------------------------------------------------------------------


async def test_delete_failure_does_not_fail_batch(env, monkeypatch):
    app, _, sch = env
    original = Path.unlink

    def locked(self, *args, **kwargs):
        if self.parent.name == "run_001" and self.suffix == ".smv":
            raise PermissionError("file is locked")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    res = await _run(app, sch, _lx(4), rank_by="Vo1.ripple", top_k=1)
    assert res["success"], res
    data = res["data"]
    failed = data["storage"]["delete_failed"]
    assert len(failed) == 1 and "run_001" in failed[0]["path"]
    assert "PermissionError" in failed[0]["error"]
    assert any("지우지 못했습니다" in n for n in data["notes"])
    study, saved = _study(data)
    assert _smv_runs(study) == [1, 3]  # run 3(1위) + 지우지 못한 run 1
    assert saved["summary"]["storage"]["delete_failed"] == failed
    by_run = {r["run"]: r for r in saved["runs"]}
    assert by_run[1]["smv_kept"] is True and by_run[1]["smv_path"]
    assert data["storage"]["kept_runs"] == [1, 3]


async def test_smv_path_outside_study_is_never_deleted(env, monkeypatch, tmp_path_factory):
    app, _, sch = env
    outside = tmp_path_factory.mktemp("outside") / "run_000" / "result.smv"
    outside.parent.mkdir()
    outside.write_text("keep me", encoding="utf-8")
    pool = app._services["pool"]
    original = pool.run_jobs

    async def tampered(jobs, *args, **kwargs):
        results, info = await original(jobs, *args, **kwargs)
        results[0]["data"]["smv_path"] = str(outside)  # 워커가 study 밖 경로를 보고한 경우
        return results, info

    monkeypatch.setattr(pool, "run_jobs", tampered)
    res = await _run(app, sch, _lx(2))  # 기본 keep_smv="none" → 전부 삭제 대상
    assert res["success"], res
    data = res["data"]
    assert outside.read_text(encoding="utf-8") == "keep me"
    assert data["storage"]["rejected"] == [str(outside)]
    assert any("지우지 않았습니다" in n for n in data["notes"])
    study, saved = _study(data)
    assert _smv_runs(study) == []  # study 안의 파일은 정책대로 삭제
    assert saved["summary"]["storage"]["rejected"] == [str(outside)]


# ---------------------------------------------------------------------------
# 입력 검증(실행 전 거부)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"keep_smv": "top_k"}, "INVALID_STORAGE_POLICY"),
        ({"rank_by": "Vo1.ripple", "top_k": 0}, "INVALID_STORAGE_POLICY"),
        ({"rank_by": "Vo1.ripple", "keep_smv": "best"}, "INVALID_STORAGE_POLICY"),
        ({"rank_by": "Vo1"}, "INVALID_RANK_BY"),
        ({"rank_by": "Vo1.rms"}, "INVALID_RANK_BY"),
        ({"rank_by": "--Vo1.mean"}, "INVALID_RANK_BY"),
    ],
)
async def test_bad_storage_input_rejected_before_run(env, kwargs, code):
    app, cfg, sch = env
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=_lx(2), **kwargs)
    assert res["success"] is False
    assert res["error"]["code"] == code and res["error"]["suggestion"]
    # 실행 전 거부: study 폴더도, 워커도 없다
    assert not cfg.runs_dir.exists() or not any(cfg.runs_dir.iterdir())
    assert app._services["pool"].status()["workers"] == 0
    await _close(app)


async def test_non_integer_top_k_rejected_by_service(env):
    app, _, sch = env
    batch = app._services["batch"]
    res = await batch.run_batch(_lx(2), schematic_path=str(sch), rank_by="Vo1.mean", top_k=1.5)
    assert res["success"] is False and res["error"]["code"] == "INVALID_STORAGE_POLICY"
    await _close(app)


# ---------------------------------------------------------------------------
# 병렬 스윕은 .smv를 모두 보존
# ---------------------------------------------------------------------------


async def test_parallel_sweep_keeps_all_smv(env):
    app, _, sch = env
    await _call(app, "open_project", path=str(sch))
    res = await _call(
        app,
        "sweep_parameter",
        component_id="L1",
        parameter_name="Inductance",
        start=0.001,
        end=0.004,
        step=0.001,
        parallel=True,
        workers=2,
    )
    await _close(app)
    assert res["success"], res
    study = Path(res["data"]["parallel"]["study_dir"])
    assert _smv_runs(study) == [0, 1, 2, 3]
    saved = json.loads((study / "study.json").read_text(encoding="utf-8"))
    assert saved["summary"]["storage"]["keep_smv"] == "all"
    assert saved["summary"]["storage"]["deleted"] == []
