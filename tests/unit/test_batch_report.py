"""run_batch 결과 요약(top)·PNG 그림(2차 10번) — mock."""

from __future__ import annotations

import base64
import io
import json
import math
import random
from pathlib import Path

import pytest
from mcp.types import ImageContent, TextContent
from PIL import Image

import psim_mcp.bridge.bridge_script as bridge_script
from psim_mcp.config import AppConfig
from psim_mcp.parallel import pool as pool_mod
from psim_mcp.server import create_app
from psim_mcp.services import batch_report as br
from psim_mcp.services.storage_policy import parse_rank_by
from psim_mcp.tools import MAX_IMAGE_TOTAL_BYTES
from psim_mcp.utils.sanitize import MAX_RESPONSE_SIZE

# ---------------------------------------------------------------------------
# 순수 함수
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [1, 2, 3, 4])
def test_validate_max_images_accepts_1_to_4(value):
    assert br.validate_max_images(value) == value


@pytest.mark.parametrize("value", [0, 5, -1, "2", 2.0, True, None])
def test_validate_max_images_rejects(value):
    with pytest.raises(br.ReportInputError) as e:
        br.validate_max_images(value)
    assert e.value.code == "INVALID_INPUT" and e.value.suggestion


@pytest.mark.parametrize(
    "value,expected",
    [(0.001, 0.001), ("2m", 0.002), ("220u", 220e-6), ("1.5k", 1500.0), ("3", 3.0)],
)
def test_parse_number(value, expected):
    assert br.parse_number(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["abc", None, True, float("nan"), "2x"])
def test_parse_number_rejects(value):
    assert br.parse_number(value) is None


def _rec(run, inputs, ripple=None, ok=True, executed=True, rank=None, smv=None):
    r = {"run": run, "inputs": inputs, "ok": ok, "executed": executed}
    if ok:
        r["summary"] = {"I(L1)": {"mean": 5.0, "ripple": ripple, "max": 6.0, "min": 4.0}}
    if rank is not None:
        r["rank"] = rank
    r["smv_kept"] = bool(smv)
    r["smv_path"] = smv
    return r


def test_choose_x_axis_single_numeric_input():
    recs = [_rec(0, {"Lx": "1m"}, 2.0), _rec(1, {"Lx": 0.002}, 1.0)]
    recs.append(_rec(2, {"L1": 0.002}, ok=False, executed=False))  # 형식 오류 행은 무시
    key, xs = br.choose_x_axis(recs)
    assert key == "Lx" and xs == {0: pytest.approx(0.001), 1: pytest.approx(0.002)}


def test_choose_x_axis_falls_back_to_run():
    two = [_rec(0, {"Lx": 1, "R": 1}, 1.0), _rec(1, {"Lx": 2, "R": 2}, 1.0)]
    assert br.choose_x_axis(two)[0] == "run"
    text = [_rec(0, {"Lx": "a"}, 1.0), _rec(1, {"Lx": "b"}, 1.0)]
    assert br.choose_x_axis(text) == ("run", {0: 0.0, 1: 1.0})


def test_build_top_orders_by_rank():
    recs = [
        _rec(0, {"Lx": 1}, 3.0, rank=3),
        _rec(1, {"Lx": 2}, 1.0, rank=1, smv="a.smv"),
        _rec(2, {"Lx": 3}, ok=False, executed=False),
        _rec(3, {"Lx": 4}, 2.0, rank=2),
    ]
    top = br.build_top(recs, parse_rank_by("I(L1).ripple"), 2)
    assert [t["run"] for t in top] == [1, 3]
    assert top[0] == {
        "rank": 1,
        "run": 1,
        "inputs": {"Lx": 2},
        "I(L1).ripple": 1.0,
        "smv_kept": True,
    }


def _hf_triangle(n: int, period: int = 10) -> list[float]:
    """고주파 삼각파(주기 10 샘플 — envelope 구간 ~n/1000보다 훨씬 짧음) + 느린 변화."""
    return [
        5.0 + 0.3 * math.sin(i / n * 6.0) + (abs((i % period) / (period / 2) - 1.0) - 0.5)
        for i in range(n)
    ]


def test_minmax_envelope_preserves_peak_to_peak():
    n = 200_000
    y = _hf_triangle(n)
    t = [i * 1e-6 for i in range(n)]
    ey, et, reduced = br.minmax_envelope(y, t)
    assert reduced
    # 약 1000구간 × (최소, 최대) = 약 2000점
    assert 1900 <= len(ey) <= br.WAVEFORM_MAX_POINTS
    assert max(ey) == max(y) and min(ey) == min(y)  # peak-to-peak 보존
    # 시간 순서이고, 각 점은 원본의 같은 시점 값
    assert all(a < b for a, b in zip(et, et[1:]))
    assert all(y[round(tt / 1e-6)] == v for tt, v in zip(et, ey))
    # 대조: 등간격 추출(간격 100 = 주기 10의 배수)은 에일리어싱으로 리플을 잃는다
    stride = y[:: n // br.WAVEFORM_MAX_POINTS]
    assert max(stride) - min(stride) < 0.7 * (max(y) - min(y))


def test_minmax_envelope_bucket_ripple_matches_local_peak_to_peak():
    """구간마다 최소·최대가 다 들어가므로 어느 구간에서나 띠 두께 = 그 구간의 실제 리플."""
    n = 100_000
    y = _hf_triangle(n)
    idx = br.minmax_envelope_indices(y)
    buckets = br.WAVEFORM_MAX_POINTS // 2
    for k in (0, 123, buckets - 1):
        lo, hi = k * n // buckets, (k + 1) * n // buckets
        vals = [y[i] for i in idx if lo <= i < hi]
        assert max(vals) == max(y[lo:hi]) and min(vals) == min(y[lo:hi])


def test_minmax_envelope_short_input_unchanged():
    y = _hf_triangle(1500)
    t = [i * 1e-6 for i in range(1500)]
    ey, et, reduced = br.minmax_envelope(y, t)
    assert ey == y and et == t and not reduced
    assert br.minmax_envelope_indices(_hf_triangle(2500), 2500) == list(range(2500))


def test_minmax_envelope_without_times():
    ey, et, reduced = br.minmax_envelope(_hf_triangle(10_000), None)
    assert et is None and reduced and len(ey) <= br.WAVEFORM_MAX_POINTS


@pytest.mark.parametrize("n,max_points", [(10, 2000), (2001, 2000), (50_000, 2000), (7777, 500)])
def test_bridge_envelope_matches_server(n, max_points):
    y = _hf_triangle(n, period=7)
    assert bridge_script._minmax_envelope_indices(y, max_points) == br.minmax_envelope_indices(
        y, max_points
    )


class _Curve:
    def __init__(self, name, values):
        self.Name, self.Values, self.Rows = name, values, len(values)


def _fake_psim(monkeypatch, curves):
    class _Psim:
        def PsimReadGraphFile(self, path):  # noqa: N802 - psimapipy 이름
            return type("R", (), {"Result": 1, "Graph": curves})()

    monkeypatch.setattr(bridge_script, "_get_psim", lambda: _Psim())


def test_bridge_extract_minmax_keeps_peaks_and_times(monkeypatch, tmp_path):
    n = 120_000
    y = _hf_triangle(n)
    t = [i * 1e-6 for i in range(n)]
    _fake_psim(monkeypatch, [_Curve("Time", t), _Curve("I(L1)", y), _Curve("Vo1", y)])
    smv = tmp_path / "result.smv"
    smv.write_bytes(b"x")
    res = bridge_script.handle_extract_signals(
        {
            "graph_file": str(smv),
            "signals": ["I(L1)", "Time"],
            "skip_ratio": 0.5,
            "max_points": 2000,
            "reduce": "minmax",
        }
    )
    assert res["success"], res
    data = res["data"]
    assert list(data["signals"]) == ["I(L1)"] and data["reduced"] == {"I(L1)": True}
    window = y[n // 2 :]
    ey, et = data["signals"]["I(L1)"], data["times"]["I(L1)"]
    assert round(max(window), 9) == max(ey) and round(min(window), 9) == min(ey)
    assert len(ey) == len(et) <= 2000
    assert et[0] >= t[n // 2] and all(a < b for a, b in zip(et, et[1:]))


def test_bridge_extract_default_stride_unchanged(monkeypatch, tmp_path):
    n = 9000
    y = _hf_triangle(n)
    t = [i * 1e-6 for i in range(n)]
    _fake_psim(monkeypatch, [_Curve("Time", t), _Curve("I(L1)", y)])
    smv = tmp_path / "result.smv"
    smv.write_bytes(b"x")
    res = bridge_script.handle_extract_signals({"graph_file": str(smv), "max_points": 2000})
    data = res["data"]
    assert "times" not in data and "reduce" not in data
    assert data["signals"]["I(L1)"] == [round(v, 9) for v in y[::4]]  # 9000 // 2000 = 4
    assert data["signals"]["Time"] == [round(v, 9) for v in t[::4]]


def test_bridge_extract_rejects_unknown_reduce(monkeypatch, tmp_path):
    _fake_psim(monkeypatch, [])
    res = bridge_script.handle_extract_signals({"graph_file": "x", "reduce": "avg"})
    assert not res["success"] and res["error"]["code"] == "INVALID_INPUT"


def test_report_module_uses_figure_api_not_pyplot():
    src = Path(br.__file__).read_text(encoding="utf-8")
    assert "pyplot" not in src.replace("pyplot 전역", "")
    assert "FigureCanvasAgg" in src


def _png_info(png: bytes) -> tuple[int, int]:
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    with Image.open(io.BytesIO(png)) as im:
        return im.size


def test_metric_plot_size_and_width():
    recs = [_rec(i, {"Lx": 0.0005 + i * 1e-5}, 10.0 / (i + 1), rank=i + 1) for i in range(200)]
    key, xs = br.choose_x_axis(recs)
    png = br.render_metric_plot(recs, [("I(L1)", "ripple")], key, xs, [0, 1, 2], "title")
    w, _ = _png_info(png)
    assert 850 <= w <= 950
    assert len(png) <= br.IMAGE_MAX_BYTES


def test_waveform_plot_size_worst_case_noise():
    rnd = random.Random(1)
    traces = [
        {
            "label": f"#{k + 1} run {k}",
            "x": [i * 1e-6 for i in range(2000)],
            "y": [math.sin(i / 7.0) + rnd.uniform(-1, 1) for i in range(2000)],
        }
        for k in range(4)
    ]
    png = br.render_waveform_plot(traces, "I(L1)", "Time (s)", "t")
    _png_info(png)
    assert len(png) <= br.IMAGE_MAX_BYTES
    assert 2 * len(png) <= MAX_IMAGE_TOTAL_BYTES


# ---------------------------------------------------------------------------
# run_batch(plot) — mock 앱
# ---------------------------------------------------------------------------


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
    )
    app = create_app(cfg)
    sch = tmp_path / "buck.psimsch"
    sch.write_bytes(b"<psim/>")
    return app, cfg, sch


async def _call_raw(app, **kwargs):
    """run_batch 호출 후 풀을 닫고 (JSON, 블록 목록)을 돌려준다."""
    try:
        out = await app.call_tool("run_batch", kwargs)
    finally:
        await app._services["pool"].shutdown()
    blocks = out[0] if isinstance(out, tuple) else out
    assert isinstance(blocks[0], TextContent)
    return json.loads(blocks[0].text), blocks


_LX = [0.0005 + i * 0.0045 / 11 for i in range(12)]


def _conds13():
    conds = [{"Lx": v} for v in _LX]
    conds.insert(6, {"L1": 0.002})
    return conds


async def test_plot_scenario_a_attaches_two_images(env):
    app, cfg, sch = env
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=_conds13(),
        workers=3,
        rank_by="I(L1).ripple",
        plot=True,
    )
    assert res["success"], res
    data = res["data"]
    assert data["succeeded"] == 12 and data["invalid"] == 1
    # top: 상위 3행, I(L1).ripple 오름차순 = Lx 큰 순서
    assert [t["run"] for t in data["top"]] == [12, 11, 10]
    assert [t["rank"] for t in data["top"]] == [1, 2, 3]
    assert all("I(L1).ripple" in t and t["smv_kept"] for t in data["top"])
    # 그림 2장이 응답에 이미지로 첨부되고 plots/에도 저장
    images = [b for b in blocks if isinstance(b, ImageContent)]
    assert len(images) == 2
    assert [p["kind"] for p in data["plots"]] == ["metrics", "waveforms"]
    total = 0
    for p, img in zip(data["plots"], images):
        path = Path(p["path"])
        assert path.parent == Path(data["study_dir"]) / "plots" and path.is_file()
        raw = base64.b64decode(img.data)
        assert raw == path.read_bytes() and len(raw) == p["bytes"]
        assert len(raw) <= br.IMAGE_MAX_BYTES and p["attached"] is True
        total += len(raw)
    assert total <= MAX_IMAGE_TOTAL_BYTES
    assert not any("실패" in n for n in data.get("notes", []))
    # 파형 원본은 텍스트 응답에 없다(원칙 4)
    assert '"signals"' not in blocks[0].text
    assert len(blocks[0].text.encode("utf-8")) <= MAX_RESPONSE_SIZE


async def test_plot_max_images_one_skips_waveform(env):
    app, cfg, sch = env
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
        max_images=1,
    )
    data = res["data"]
    assert sum(isinstance(b, ImageContent) for b in blocks) == 1
    assert [p["kind"] for p in data["plots"]] == ["metrics"]
    assert any("max_images=1" in n for n in data["notes"])


async def test_plot_without_rank_by_omits_top_and_waveform(env):
    app, cfg, sch = env
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        plot=True,
    )
    data = res["data"]
    assert res["success"] and "top" not in data
    notes = data["notes"]
    assert any("top(상위 요약)은 생략" in n for n in notes)
    assert any("남아 있는 파형(.smv)이 없어 그림 2" in n for n in notes)
    assert [p["kind"] for p in data["plots"]] == ["metrics"]
    assert sum(isinstance(b, ImageContent) for b in blocks) == 1


async def test_plot_keep_all_without_rank_uses_first_runs(env):
    app, cfg, sch = env
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:5]],
        workers=2,
        keep_smv="all",
        plot=True,
    )
    data = res["data"]
    assert [p["kind"] for p in data["plots"]] == ["metrics", "waveforms"]
    assert sum(isinstance(b, ImageContent) for b in blocks) == 2


async def test_no_plot_keeps_text_only_and_adds_top(env):
    app, cfg, sch = env
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="-Vo1.mean",
    )
    assert len(blocks) == 1
    data = res["data"]
    assert "plots" not in data and "_images" not in res
    assert len(data["top"]) == 3 and data["top"][0]["rank"] == 1
    assert not (Path(data["study_dir"]) / "plots").exists()


@pytest.mark.parametrize("bad", [0, 5, -1])
async def test_invalid_max_images_rejected_before_run(env, bad):
    app, cfg, sch = env
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": 0.001}],
        plot=True,
        max_images=bad,
    )
    assert not res["success"]
    assert res["error"]["code"] == "INVALID_INPUT" and res["error"]["suggestion"]
    assert not cfg.runs_dir.exists() or not any(cfg.runs_dir.iterdir())
    assert app._services["pool"].pids == []


async def test_plot_failure_keeps_batch_success(env, monkeypatch):
    app, cfg, sch = env

    def boom(*a, **k):
        raise RuntimeError("render broke")

    monkeypatch.setattr(br, "render_metric_plot", boom)
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
    )
    assert res["success"]
    data = res["data"]
    assert len(data["rows"]) == 4 and data["succeeded"] == 4
    assert any("그림 1(조건-지표) 생성 실패" in n and "render broke" in n for n in data["notes"])
    # 그림 2는 따로 만들어진다
    assert [p["kind"] for p in data["plots"]] == ["waveforms"]
    assert sum(isinstance(b, ImageContent) for b in blocks) == 1


async def test_all_plots_fail_returns_text_only(env, monkeypatch):
    app, cfg, sch = env

    def boom(*a, **k):
        raise RuntimeError("no render")

    monkeypatch.setattr(br, "render_metric_plot", boom)
    monkeypatch.setattr(br, "render_waveform_plot", boom)
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:3]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
    )
    assert res["success"] and len(blocks) == 1
    assert res["data"]["plots"] == []
    assert sum("생성 실패" in n for n in res["data"]["notes"]) == 2


async def test_waveform_read_failure_skips_figure_with_note(env, monkeypatch):
    app, cfg, sch = env

    def fail(params):
        return {"success": False, "error": {"code": "READ_FAILED", "message": "locked"}}

    monkeypatch.setattr(pool_mod.MockWorker, "_extract_signals", staticmethod(fail))
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
    )
    notes = res["data"]["notes"]
    assert any("읽지 못해" in n and "locked" in n for n in notes)
    assert any("읽을 수 있는 파형이 없어" in n for n in notes)
    assert [p["kind"] for p in res["data"]["plots"]] == ["metrics"]


async def test_waveform_uses_measurement_window_and_point_cap(env, monkeypatch):
    app, cfg, sch = env
    seen: list[dict] = []
    original = pool_mod.MockWorker._extract_signals

    def spy(params):
        seen.append(params)
        return original(params)

    monkeypatch.setattr(pool_mod.MockWorker, "_extract_signals", staticmethod(spy))
    res, _ = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
    )
    assert len(seen) == 3  # 상위 3개 .smv만
    for p in seen:
        assert p["skip_ratio"] == 0.5 and p["max_points"] == br.WAVEFORM_MAX_POINTS
        assert p["signals"] == ["I(L1)", "Time"]
        assert p["reduce"] == "minmax"
        assert Path(p["graph_file"]).name == "result.smv"


async def test_waveform_caption_says_min_max_envelope(env, monkeypatch):
    app, cfg, sch = env
    calls: list[tuple] = []
    original = br.render_waveform_plot

    def spy(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(br, "render_waveform_plot", spy)
    res, _ = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
    )
    assert len(calls) == 1
    traces, signal, x_label, title, legend_title = calls[0]
    assert "min/max envelope" in title and legend_title == "min/max envelope"
    assert x_label == "Time (s)"
    for tr in traces:
        assert len(tr["y"]) <= br.WAVEFORM_MAX_POINTS and len(tr["x"]) == len(tr["y"])
    # mock 파형(리플 = summary ripple)의 띠 두께가 표의 리플 값과 같다
    rows = {r["run"]: r for r in res["data"]["rows"]}
    for tr in traces:
        run = int(tr["label"].split("run ")[1].split()[0])
        assert max(tr["y"]) - min(tr["y"]) == pytest.approx(rows[run]["I(L1).ripple"], rel=1e-4)
