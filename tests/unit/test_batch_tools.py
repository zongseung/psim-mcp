"""run_batch / benchmark_parallel / open_in_viewer / sweep_parameter(parallel) / vault simview (mock)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from psim_mcp.config import AppConfig
from psim_mcp.parallel import settings as parallel_settings
from psim_mcp.parallel.cpu import physical_cores
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


# ---------------------------------------------------------------------------
# run_batch
# ---------------------------------------------------------------------------


async def test_run_batch_writes_run_folders_and_returns_table(env):
    app, cfg, sch = env
    res = await _call(
        app,
        "run_batch",
        schematic_path=str(sch),
        conditions=[{"Lx": 0.001}, {"Lx": "2m"}, {"L1.Inductance": 0.004, "Rload": 5}],
        workers=2,
    )
    await _close(app)
    assert res["success"], res
    data = res["data"]
    assert data["ok"] == 3 and data["failed"] == 0 and data["workers"] == 2
    assert data["simview"] == 0
    assert data["columns"][:5] == ["run", "Lx", "L1.Inductance", "Rload", "status"]
    assert "Vo1.mean" in data["columns"] and "Vo1.ripple" in data["columns"]
    # 파형 원본은 반환하지 않는다
    assert "signals" not in json.dumps(data["rows"])

    study = Path(data["study_dir"])
    assert study.parent == cfg.runs_dir
    run0 = json.loads((study / "run_000" / "config.json").read_text(encoding="utf-8"))
    assert run0["method"] == "variable_override" and run0["variables"] == {"Lx": "0.001"}
    assert not (study / "run_000" / "circuit.psimsch").exists()  # 변수는 파일 복제 없음
    run2 = json.loads((study / "run_002" / "config.json").read_text(encoding="utf-8"))
    assert run2["method"] == "circuit_copy"
    assert run2["elements"] == [
        {"component_id": "L1", "parameter_name": "Inductance", "value": "0.004"}
    ]
    assert (study / "run_002" / "circuit.psimsch").exists()
    for i in range(3):
        assert (study / f"run_{i:03d}" / "summary.json").exists()
        assert (study / f"run_{i:03d}" / "result.smv").exists()
    assert (study / "results.csv").exists() and (study / "study.json").exists()
    # 원본 회로는 그대로
    assert sch.read_bytes() == b"<psim/>"
    # 인덕턴스가 클수록 리플이 작다(조건이 실제로 반영됨)
    ripples = [r["Vo1.ripple"] for r in data["rows"]]
    assert ripples[0] > ripples[1] > ripples[2]


async def test_run_batch_marks_failed_conditions_in_table(env):
    app, _, sch = env
    res = await _call(
        app,
        "run_batch",
        schematic_path=str(sch),
        conditions=[{"Lx": 0.001}, {"Lx": 0.001, "__fail__": 1}, {"Lx": 0.002, "__crash__": 1}],
        workers=2,
    )
    await _close(app)
    # 시험용 변수(__fail__, __crash__)는 회로가 참조하지 않으므로 사전 검사에서 걸러져
    # 실행되지 않고(워커 크래시 없음) 그 행만 오류로 표시된다
    assert res["success"], res
    data = res["data"]
    assert data["ok"] == 1 and data["failed"] == 2 and data["invalid"] == 2
    rows = data["rows"]
    assert rows[0]["status"] == "ok"
    assert rows[1]["status"].startswith("error: VARIABLE_NOT_REFERENCED")
    assert rows[2]["status"].startswith("error: VARIABLE_NOT_REFERENCED")
    assert data["restarted_workers"] == []


def _bad_mix() -> list[dict]:
    conds = [{"Lx": round(0.0005 + i * 0.0005, 6)} for i in range(6)]
    conds.insert(3, {"L1": 0.002})
    return conds


async def test_invalid_condition_only_marks_its_row(env):
    app, _, sch = env
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=_bad_mix(), workers=2)
    await _close(app)
    assert res["success"], res
    data = res["data"]
    assert data["conditions"] == 7 and data["ok"] == 6
    assert data["failed"] == 1 and data["invalid"] == 1 and data["strict"] is False
    rows = data["rows"]
    assert [r["run"] for r in rows] == list(range(7))
    assert rows[3]["L1"] == 0.002
    assert rows[3]["status"].startswith("error: VARIABLE_NOT_REFERENCED")
    assert all(r["status"] == "ok" for i, r in enumerate(rows) if i != 3)
    # 실행된 조건은 순서·값이 그대로(Lx가 클수록 리플 감소)
    ripples = [r["Vo1.ripple"] for i, r in enumerate(rows) if i != 3]
    assert ripples == sorted(ripples, reverse=True)
    assert any("strict=true" in n for n in data["notes"])
    assert "형식 오류 1" in res["message"]

    study = Path(data["study_dir"])
    bad = json.loads((study / "run_003" / "config.json").read_text(encoding="utf-8"))
    assert bad["executed"] is False and bad["error"]["code"] == "VARIABLE_NOT_REFERENCED"
    assert bad["error"]["suggestion"]
    assert not (study / "run_003" / "result.smv").exists()
    summary = json.loads((study / "run_003" / "summary.json").read_text(encoding="utf-8"))
    assert summary["ok"] is False and summary["executed"] is False
    assert (study / "run_004" / "result.smv").exists()


async def test_invalid_format_condition_only_marks_its_row(env):
    app, _, sch = env
    res = await _call(
        app,
        "run_batch",
        schematic_path=str(sch),
        conditions=[{"Lx": 0.001}, {"Lx": None}, {"bad name": 1}, {"Q9.Inductance": 1}],
    )
    await _close(app)
    assert res["success"], res
    rows = res["data"]["rows"]
    assert rows[0]["status"] == "ok"
    assert rows[1]["status"].startswith("error: INVALID_CONDITION")
    assert rows[2]["status"].startswith("error: INVALID_CONDITION")
    assert rows[3]["status"].startswith("error: COMPONENT_NOT_FOUND")
    assert res["data"]["invalid"] == 3


async def test_strict_rejects_whole_batch(env):
    app, cfg, sch = env
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=_bad_mix(), strict=True)
    await _close(app)
    assert res["success"] is False
    assert res["error"]["code"] == "VARIABLE_NOT_REFERENCED"
    assert res["error"]["message"].startswith("조건 3:")
    assert res["error"]["suggestion"]
    # 실행 전에 거부되므로 study 폴더도 만들지 않는다
    assert not cfg.runs_dir.exists() or not any(cfg.runs_dir.iterdir())


async def test_all_invalid_conditions_reject_batch(env):
    app, cfg, sch = env
    res = await _call(
        app,
        "run_batch",
        schematic_path=str(sch),
        conditions=[{"L1": 0.002}, {"Q9.Inductance": 1}, {"Lx": None}],
    )
    await _close(app)
    assert res["success"] is False
    err = res["error"]
    assert err["code"] == "VARIABLE_NOT_REFERENCED"
    assert "3개 조건이 모두" in err["message"]
    codes = [c["code"] for c in err["details"]["invalid_conditions"]]
    assert codes == ["VARIABLE_NOT_REFERENCED", "COMPONENT_NOT_FOUND", "INVALID_CONDITION"]
    assert not cfg.runs_dir.exists() or not any(cfg.runs_dir.iterdir())


async def test_variable_not_referenced_has_suggestion(env):
    app, _, sch = env
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=[{"Lout": 1e-3}])
    await _close(app)
    err = res["error"]
    assert err["code"] == "VARIABLE_NOT_REFERENCED"
    # 회로가 참조하는 변수 목록과 '소자.파라미터' 형식 예시
    assert "Lx" in err["suggestion"] and "Rload" in err["suggestion"]
    assert "L1.Inductance" in err["suggestion"]
    assert err["details"]["referenced_variables"] == ["Lx", "Rload"]


async def test_run_batch_failed_rows_show_error(env, monkeypatch):
    app, _, sch = env
    batch = app._services["batch"]

    async def no_precheck(schematic, parsed, strict=True):
        return {}

    monkeypatch.setattr(batch, "precheck", no_precheck)
    res = await _call(
        app,
        "run_batch",
        schematic_path=str(sch),
        conditions=[{"Lx": 0.001}, {"__fail__": 1}, {"__crash__": 1}, {"Lx": 0.003}],
        workers=2,
    )
    await _close(app)
    assert res["success"]
    rows = res["data"]["rows"]
    assert rows[0]["status"] == "ok" and rows[3]["status"] == "ok"
    assert rows[1]["status"].startswith("error: SIMULATION_FAILED")
    assert rows[2]["status"].startswith("error: WORKER_CRASHED")
    assert res["data"]["failed"] == 2
    assert len(res["data"]["restarted_workers"]) == 1


async def test_numeric_element_value_is_not_treated_as_variable(env):
    app, _, sch = env
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=[{"L1": 0.002}])
    await _close(app)
    assert res["success"] is False
    assert res["error"]["code"] == "VARIABLE_NOT_REFERENCED"
    assert "L1.파라미터" in res["error"]["message"]
    # 소자 이름과 같은 키면 그 소자의 실제 파라미터로 예시를 든다
    assert '"L1.Inductance"' in res["error"]["suggestion"]
    assert "Lx" in res["error"]["suggestion"]


@pytest.mark.parametrize(
    ("conditions", "code"),
    [
        ([], "INVALID_INPUT"),
        ([{"Q9.Inductance": 1}], "COMPONENT_NOT_FOUND"),
        ([{"L1.Ind": 1}], "PARAMETER_NOT_FOUND"),
        ([{"L1.Inductance": None}], "INVALID_CONDITION"),
        ([{"bad name": 1}], "INVALID_CONDITION"),
    ],
)
async def test_run_batch_rejects_bad_conditions(env, conditions, code):
    app, _, sch = env
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=conditions)
    await _close(app)
    assert res["success"] is False and res["error"]["code"] == code


async def test_parameter_name_is_resolved_like_set_parameter(env):
    app, _, sch = env
    res = await _call(
        app, "run_batch", schematic_path=str(sch), conditions=[{"l1.initial_current": 0.5}]
    )
    await _close(app)
    assert res["success"], res
    cfg = json.loads(
        (Path(res["data"]["study_dir"]) / "run_000" / "config.json").read_text(encoding="utf-8")
    )
    assert cfg["elements"][0]["component_id"] == "L1"
    assert cfg["elements"][0]["parameter_name"] == "Initial Current"


async def test_run_batch_uses_open_project_when_path_omitted(env):
    app, _, sch = env
    await _call(app, "open_project", path=str(sch))
    res = await _call(app, "run_batch", conditions=[{"Lx": 0.001}])
    await _close(app)
    assert res["success"], res
    assert Path(res["data"]["schematic"]) == sch.resolve()


async def test_run_batch_limit(env):
    app, cfg, sch = env
    conds = [{"Lx": 0.001}] * (cfg.max_batch_conditions + 1)
    res = await _call(app, "run_batch", schematic_path=str(sch), conditions=conds)
    await _close(app)
    assert res["error"]["code"] == "BATCH_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# 동시 실행 수 결정
# ---------------------------------------------------------------------------


def test_default_workers_is_physical_cores(tmp_path):
    cfg = AppConfig(psim_mode="mock", parallel_settings_path=tmp_path / "none.json")
    assert parallel_settings.resolve_workers(cfg) == (physical_cores(), "physical_cores")


def test_workers_priority(tmp_path):
    path = tmp_path / "p.json"
    cfg = AppConfig(psim_mode="mock", parallel_settings_path=path)
    parallel_settings.save_benchmark(cfg, 1, {"x": 1})
    assert parallel_settings.resolve_workers(cfg) == (1, "benchmark")
    cfg_env = AppConfig(psim_mode="mock", parallel_settings_path=path, parallel_workers=2)
    assert parallel_settings.resolve_workers(cfg_env) == (
        min(2, parallel_settings.max_workers()),
        "PARALLEL_WORKERS",
    )
    assert parallel_settings.resolve_workers(cfg_env, 1) == (1, "request")


async def test_run_batch_rejects_too_many_workers(env):
    app, _, sch = env
    res = await _call(
        app,
        "run_batch",
        schematic_path=str(sch),
        conditions=[{"Lx": 1}],
        workers=parallel_settings.max_workers() + 1,
    )
    assert res["error"]["code"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# benchmark_parallel
# ---------------------------------------------------------------------------


async def test_benchmark_uses_copy_and_saves_best(env):
    app, cfg, sch = env
    res = await _call(app, "benchmark_parallel", schematic_path=str(sch), levels=[1, 2], runs=4)
    assert res["success"], res
    data = res["data"]
    assert [r["workers"] for r in data["levels"]] == [1, 2]
    assert all(r["ok"] == 4 for r in data["levels"])
    assert all(r["matches_sequential"] == 0.0 for r in data["levels"])
    assert data["best_workers"] in (1, 2)
    assert data["best_workers"] <= physical_cores()
    assert Path(data["bench_copy"]).exists() and Path(data["bench_copy"]) != sch
    saved = json.loads(Path(cfg.parallel_settings_path).read_text(encoding="utf-8"))
    assert saved["workers"] == data["best_workers"]
    # 측정 후 기본값보다 많이 띄운 워커는 정리된다
    assert app._services["pool"].status()["workers"] <= data["best_workers"]
    # 측정 결과 .smv는 남기지 않는다
    assert not list(Path(data["bench_dir"]).rglob("*.smv"))
    await _close(app)


async def test_benchmark_validates_runs(env):
    app, _, sch = env
    res = await _call(app, "benchmark_parallel", schematic_path=str(sch), levels=[1, 2], runs=3)
    assert res["error"]["code"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# sweep_parameter parallel
# ---------------------------------------------------------------------------


async def test_sweep_parameter_parallel(env):
    app, _, sch = env
    await _call(app, "open_project", path=str(sch))
    res = await _call(
        app,
        "sweep_parameter",
        component_id="L1",
        parameter_name="Inductance",
        start=0.001,
        end=0.003,
        step=0.001,
        metrics=["Vo1.ripple"],
        parallel=True,
        workers=3,
    )
    await _close(app)
    assert res["success"], res
    data = res["data"]
    assert [s["value"] for s in data["results"]] == [0.001, 0.002, 0.003]
    assert all("Vo1.ripple" in s["metrics"] for s in data["results"])
    assert data["parallel"]["workers"] == 3
    assert data["parallel"]["modifies_open_project"] is False
    assert sch.read_bytes() == b"<psim/>"


async def test_sweep_parameter_default_is_sequential(env):
    app, _, sch = env
    await _call(app, "open_project", path=str(sch))
    res = await _call(
        app,
        "sweep_parameter",
        component_id="L1",
        parameter_name="inductance",
        start=1e-3,
        end=2e-3,
        step=1e-3,
    )
    assert res["success"]
    assert "parallel" not in res["data"]
    assert app._services["pool"].status()["workers"] == 0  # 풀을 띄우지 않음


# ---------------------------------------------------------------------------
# 뷰어 정책
# ---------------------------------------------------------------------------


async def test_open_in_viewer(env, tmp_path):
    app, _, _ = env
    smv = tmp_path / "result.smv"
    smv.write_text("x", encoding="utf-8")
    res = await _call(app, "open_in_viewer", graph_file=str(smv))
    assert res["success"], res
    assert app._services["_adapter"].viewer_requests == [str(smv.resolve())]

    bad = await _call(app, "open_in_viewer", graph_file=str(tmp_path / "buck.psimsch"))
    assert bad["error"]["code"] == "INVALID_EXTENSION"
    missing = await _call(app, "open_in_viewer", graph_file=str(tmp_path / "none.smv"))
    assert missing["error"]["code"] == "FILE_NOT_FOUND"


async def test_open_in_viewer_respects_allowed_dirs(env, tmp_path_factory):
    app, _, _ = env
    outside = tmp_path_factory.mktemp("outside") / "r.smv"
    outside.write_text("x", encoding="utf-8")
    res = await _call(app, "open_in_viewer", graph_file=str(outside))
    assert res["error"]["code"] == "PATH_NOT_ALLOWED"


async def test_vault_edit_and_run_runs_without_viewer(env):
    app, _, sch = env
    reg = await _call(app, "vault_register", source_path=str(sch), project="buck")
    assert reg["success"], reg
    res = await _call(
        app,
        "vault_edit_and_run",
        project="buck",
        changes=[{"component_id": "L1", "parameter_name": "inductance", "value": 2e-5}],
    )
    assert res["success"], res
    assert app._services["_adapter"].last_run_options.get("simview") == 0


async def test_run_simulation_default_unchanged(env):
    app, _, sch = env
    await _call(app, "open_project", path=str(sch))
    await _call(app, "run_simulation")
    # 기존 run_simulation 기본값(simview=1)은 바꾸지 않는다 — 별도 과제
    assert app._services["_adapter"].last_run_options.get("simview") == 1
