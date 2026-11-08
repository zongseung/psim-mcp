"""저장 정책 순수 함수(storage_policy) 단위 테스트."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from psim_mcp.services import storage_policy as sp

# ---------------------------------------------------------------------------
# rank_by 파싱
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "signal", "metric", "descending"),
    [
        ("I(L1).ripple", "I(L1)", "ripple", False),
        ("-Vo1.mean", "Vo1", "mean", True),
        ("V.out.max", "V.out", "max", False),  # 신호 이름의 점: 마지막 '.'에서 분리
        ("-I(Q1.D).min", "I(Q1.D)", "min", True),
        ("  Vo1.ripple  ", "Vo1", "ripple", False),
    ],
)
def test_parse_rank_by(text, signal, metric, descending):
    spec = sp.parse_rank_by(text)
    assert (spec.signal, spec.metric, spec.descending) == (signal, metric, descending)
    assert spec.column == f"{signal}.{metric}"


@pytest.mark.parametrize("text", ["", "   ", "Vo1", "Vo1.", ".mean", "Vo1.rms", "--Vo1.mean", "-"])
def test_parse_rank_by_rejects(text):
    with pytest.raises(sp.StoragePolicyError) as ei:
        sp.parse_rank_by(text)
    assert ei.value.code == "INVALID_RANK_BY"
    assert "I(L1).ripple" in ei.value.suggestion


# ---------------------------------------------------------------------------
# 정책 기본값·입력 검증
# ---------------------------------------------------------------------------


def test_default_keep_smv_depends_on_rank_by():
    with_rank = sp.resolve_policy("I(L1).ripple", None)
    assert (with_rank.keep_smv, with_rank.top_k, with_rank.defaulted) == ("top_k", 3, True)
    without = sp.resolve_policy(None, None)
    assert (without.keep_smv, without.rank) == ("none", None)
    explicit = sp.resolve_policy("Vo1.mean", "all", 5)
    assert (explicit.keep_smv, explicit.top_k, explicit.defaulted) == ("all", 5, False)


def test_top_k_without_rank_by_is_rejected():
    with pytest.raises(sp.StoragePolicyError) as ei:
        sp.resolve_policy(None, "top_k")
    assert ei.value.code == "INVALID_STORAGE_POLICY"
    assert "rank_by" in ei.value.suggestion


@pytest.mark.parametrize("top_k", [0, -1, 1.5, True, "3"])
def test_top_k_must_be_positive_int(top_k):
    with pytest.raises(sp.StoragePolicyError) as ei:
        sp.resolve_policy("Vo1.mean", None, top_k)
    assert ei.value.code == "INVALID_STORAGE_POLICY" and ei.value.suggestion


def test_unknown_keep_smv_is_rejected():
    with pytest.raises(sp.StoragePolicyError) as ei:
        sp.resolve_policy("Vo1.mean", "some")
    assert ei.value.code == "INVALID_STORAGE_POLICY"


# ---------------------------------------------------------------------------
# 순위
# ---------------------------------------------------------------------------


def _rec(run, value=None, ok=True, executed=True, signal="Vo1", metric="ripple"):
    r = {"run": run, "ok": ok, "executed": executed}
    if ok and executed:
        r["summary"] = {signal: {metric: value}} if value is not None else {signal: {}}
    return r


def test_rank_ascending_descending_and_ties():
    records = [_rec(0, 3.0), _rec(1, 1.0), _rec(2, 2.0), _rec(3, 1.0), _rec(4, 2.0)]
    asc = sp.rank_records(records, sp.parse_rank_by("Vo1.ripple"))
    assert [r for r, _ in asc] == [1, 3, 2, 4, 0]  # 동점은 run 번호가 작은 쪽이 앞
    desc = sp.rank_records(records, sp.parse_rank_by("-Vo1.ripple"))
    assert [r for r, _ in desc] == [0, 2, 4, 1, 3]  # 내림차순 동점도 run 오름차순


def test_rank_excludes_failed_invalid_nan_inf_missing():
    records = [
        _rec(0, 5.0),
        _rec(1, ok=False),  # 실행했지만 실패
        _rec(2, ok=False, executed=False),  # 형식 오류
        _rec(3, math.nan),
        _rec(4, math.inf),
        _rec(5, -math.inf),
        _rec(6),  # 값 없음
        _rec(7, 1.0),
        {"run": 8, "ok": True, "executed": True, "summary": {"Vo1": {"ripple": "1.0"}}},
        {"run": 9, "ok": True, "executed": True, "summary": {"Vo1": {"ripple": True}}},
    ]
    ranked = sp.rank_records(records, sp.parse_rank_by("Vo1.ripple"))
    assert ranked == [(7, 1.0), (0, 5.0)]


def test_column_exists_only_counts_succeeded_rows():
    spec = sp.parse_rank_by("Vx.mean")
    assert not sp.column_exists([_rec(0, 1.0)], spec)
    assert sp.column_exists([_rec(0, 1.0, signal="Vx", metric="mean")], spec)
    # 값이 NaN이어도 열은 있다(순위에서만 빠짐)
    assert sp.column_exists([_rec(0, math.nan, signal="Vx", metric="mean")], spec)


# ---------------------------------------------------------------------------
# 삭제 대상 선정·안전장치
# ---------------------------------------------------------------------------


def _candidates(study: Path, runs: list[int]) -> dict[int, list[str]]:
    return {r: [str(study / f"run_{r:03d}" / "result.smv")] for r in runs}


def test_plan_top_k_none_all(tmp_path):
    study = tmp_path / "study"
    cands = _candidates(study, [0, 1, 2, 3])
    ranked = [(2, 0.1), (0, 0.2), (3, 0.3), (1, 0.4)]
    top = sp.plan_smv_deletion(cands, ranked, "top_k", 2, study)
    assert top.keep_runs == [2, 0]
    assert top.delete == cands[1] + cands[3] and top.rejected == []
    none = sp.plan_smv_deletion(cands, ranked, "none", 2, study)
    assert none.keep_runs == [] and len(none.delete) == 4
    keep_all = sp.plan_smv_deletion(cands, ranked, "all", 2, study)
    assert keep_all.delete == [] and keep_all.keep_runs == [0, 1, 2, 3]


def test_plan_top_k_larger_than_ranked_keeps_what_exists(tmp_path):
    study = tmp_path / "study"
    cands = _candidates(study, [0, 1, 2])
    plan = sp.plan_smv_deletion(cands, [(1, 0.5)], "top_k", 3, study)
    assert plan.keep_runs == [1]
    assert plan.delete == cands[0] + cands[2]


@pytest.mark.parametrize(
    "relative",
    [
        "../other/run_000/result.smv",  # study 폴더 밖
        "run_000/../../outside.smv",  # 경로 이동으로 밖으로 나감
        "run_000/sub/result.smv",  # run 폴더 안 더 깊은 곳
        "plots/result.smv",  # run_NNN 폴더가 아님
        "run_00/result.smv",  # 번호 형식 틀림
        "run_000/result.csv",  # .smv가 아님
        "result.smv",  # study 폴더 바로 아래
    ],
)
def test_unsafe_paths_are_rejected_not_deleted(tmp_path, relative):
    study = tmp_path / "study"
    bad = str(study / relative)
    assert not sp.is_safe_smv_path(bad, study)
    plan = sp.plan_smv_deletion({0: [bad]}, [], "none", 3, study)
    assert plan.delete == [] and plan.rejected == [bad]


def test_safe_path_accepts_run_dir_smv(tmp_path):
    study = tmp_path / "study"
    assert sp.is_safe_smv_path(study / "run_000" / "result.smv", study)
    assert sp.is_safe_smv_path(study / "run_1234" / "circuit.SMV", study)


def test_delete_files_reports_failures(tmp_path, monkeypatch):
    a, b = tmp_path / "a.smv", tmp_path / "b.smv"
    a.write_text("x")
    b.write_text("x")
    original = Path.unlink

    def locked(self, *args, **kwargs):
        if self.name == "b.smv":
            raise PermissionError("locked")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", locked)
    deleted, failed = sp.delete_files([str(a), str(b)])
    assert deleted == [str(a)] and not a.exists()
    assert failed[0]["path"] == str(b) and "PermissionError" in failed[0]["error"]
    assert b.exists()
