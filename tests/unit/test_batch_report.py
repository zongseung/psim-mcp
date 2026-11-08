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


def test_bridge_extract_bins_full_run_mean_and_response_size(monkeypatch, tmp_path):
    """reduce="bins": hires 회로와 같은 100,000점 run 전체 → 구간 1000개, 응답 한 줄 크기 확인."""
    import json

    from psim_mcp.bridge import STREAM_LIMIT

    n = 100_000
    # 기동 과도(지수 수렴) + 고주파 삼각파
    y = [5.0 * (1 - math.exp(-i / 8000)) + v - 5.0 for i, v in enumerate(_hf_triangle(n))]
    t = [i * 5e-6 for i in range(n)]
    _fake_psim(monkeypatch, [_Curve("Time", t), _Curve("I(L1)", y), _Curve("Vo1", y)])
    smv = tmp_path / "result.smv"
    smv.write_bytes(b"x")
    res = bridge_script.handle_extract_signals(
        {
            "graph_file": str(smv),
            "signals": ["I(L1)"],
            "skip_ratio": 0.0,
            "reduce": "bins",
            "bins": br.BOTTOM_BINS,
        }
    )
    assert res["success"], res
    data = res["data"]
    assert data["reduce"] == "bins" and list(data["bins"]) == ["I(L1)"]  # Time·Vo1 없음
    b = data["bins"]["I(L1)"]
    assert len(b["mean"]) == len(b["t"]) == br.BOTTOM_BINS == data["point_count"]
    assert data["source_points"] == {"I(L1)": n} and data["time_span"] == [0.0, t[-1]]
    assert b["t"][0] == pytest.approx((t[0] + t[99]) / 2)  # 첫 구간 = 0~99번 점
    assert br.bins_mean(b) == pytest.approx(math.fsum(y) / n, abs=1e-9)
    assert max(b["max"]) == round(max(y), 9) and min(b["min"]) == round(min(y), 9)
    line = json.dumps(res, ensure_ascii=False)
    assert len(line.encode("utf-8")) < 150_000 < STREAM_LIMIT  # 실측 약 100 KB
    # 기본 동작은 그대로(reduce 없음 = stride), bins 값이 틀리면 거부
    assert "bins" not in bridge_script.handle_extract_signals({"graph_file": str(smv)})["data"]
    bad = bridge_script.handle_extract_signals(
        {"graph_file": str(smv), "reduce": "bins", "bins": 0}
    )
    assert not bad["success"] and bad["error"]["code"] == "INVALID_INPUT"


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
            "env_x": [i * 1e-6 for i in range(2000)],
            "env_y": [math.sin(i / 7.0) + rnd.uniform(-1, 1) for i in range(2000)],
            "zoom_x": [(i - 4000) * 1e-7 for i in range(4000)],
            "zoom_y": [math.sin(i / 3.0) + rnd.uniform(-1, 1) for i in range(4000)],
            "mean": 0.1 * k,
        }
        for k in range(4)
    ]
    png = br.render_waveform_plot(traces, "I(L1)", "t", "zoom", "envelope")
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
    # 아래 칸: 상위 3개 run 전체(skip_ratio 0) 구간 통계, rank_by 신호만
    bins = [p for p in seen if p.get("reduce") == "bins"]
    assert len(bins) == 3
    for p in bins:
        assert p["skip_ratio"] == 0.0 and p["signals"] == ["I(L1)"]
        assert p["bins"] == br.BOTTOM_BINS and "t_start" not in p
    seen = [p for p in seen if p.get("reduce") != "bins"]
    # 상위 3개 .smv만: 측정 구간 3번 + FFT 1번(1위 run) + 확대 구간 3번
    assert len(seen) == 7
    for p in seen:
        assert p["skip_ratio"] == 0.5
        # 그림용 요청은 rank_by 신호만. 시간 범위가 없는 envelope만 times용 Time을 같이 요청.
        assert p["signals"] == (["I(L1)"] if "t_start" in p else ["I(L1)", "Time"])
        assert p["reduce"] == "minmax"
        assert Path(p["graph_file"]).name == "result.smv"
    envelope = [p for p in seen if "t_start" not in p]
    assert len(envelope) == 3
    assert all(p["max_points"] == br.WAVEFORM_MAX_POINTS for p in envelope)
    fft = [p for p in seen if p.get("max_points") == 2 * br.FFT_MAX_POINTS]
    assert len(fft) == 1 and fft[0]["graph_file"] == envelope[0]["graph_file"]
    zoom = [p for p in seen if p.get("max_points") == br.ZOOM_MAX_POINTS]
    assert len(zoom) == 3 and all("t_start" in p for p in zoom)
    assert [p["graph_file"] for p in zoom] == [p["graph_file"] for p in envelope]
    assert [p["graph_file"] for p in bins] == [p["graph_file"] for p in envelope]


async def test_waveform_bottom_is_full_run_bins_per_run(env, monkeypatch):
    """아래 칸: run 전체(t=0부터) 구간 통계, 확대 음영 = 위 칸 범위, 측정 구간 시작 표시.

    mock 파형은 실제 PSIM처럼 첫 저장 시각이 t=0이 아니라 저장 간격 1개(MOCK_WAVE_T0 = dt)다.
    """
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
    traces, _, _, zoom_title, bottom_title, x_label, zoom_message = calls[0][:7]
    zoom_span, measure_start, xlim = calls[0][7:]
    assert x_label == "Time (s)" and zoom_message is None
    assert "full resolution" in zoom_title
    dt, n, t0 = pool_mod.MOCK_WAVE_DT, pool_mod.MOCK_WAVE_POINTS, pool_mod.MOCK_WAVE_T0
    assert t0 == dt  # 첫 시각이 0이 아님(실제 PSIM과 같음)
    run_end = t0 + (n - 1) * dt
    # 범위: run 전체(첫 시각 = 저장 간격이므로 t=0부터 끝까지로 표시)
    assert xlim == (0.0, pytest.approx(run_end))
    wave = next(p for p in res["data"]["plots"] if p["kind"] == "waveforms")
    window = wave["zoom"]["window_s"]
    # 제목: 두 줄, 공학 표기, 위 칸 대비 배율, envelope임을 명시
    first, second = bottom_title.split("\n")
    ratio = f"{run_end / window:.3g}"
    assert first == f"full run 0 – {br.eng(run_end, 's')} ({ratio}× longer time span than top)"
    assert "per-bin max/min/mean" in second and "not a waveform" in second
    # 측정 구간 시작 = 앞 50% 다음 첫 시각
    assert measure_start == pytest.approx(t0 + int(n * 0.5) * dt)
    # 확대 음영 = 위 칸 범위(1위 run 끝 기준 window_s)
    assert zoom_span[1] == pytest.approx(run_end)
    assert zoom_span[1] - zoom_span[0] == pytest.approx(window)
    assert traces[0]["zoom_x"][0] + zoom_span[1] == pytest.approx(zoom_span[0], abs=dt)
    rows = {r["run"]: r for r in res["data"]["rows"]}
    runs = [int(t["label"].split("run ")[1].split()[0]) for t in traces]
    assert wave["bottom"] == {
        "runs": runs,
        "bins": br.BOTTOM_BINS,
        "time_span": [0.0, pytest.approx(run_end)],
        "measurement_start_s": pytest.approx(measure_start),
        "zoom_span_s": [pytest.approx(zoom_span[0]), pytest.approx(zoom_span[1])],
    }
    for tr, run in zip(traces, runs):
        b = tr["bins"]
        rank = rows[run]["rank"]
        assert tr["short_label"].startswith(f"#{rank} run {run}, Lx=")
        assert len(b["x"]) == len(b["min"]) == len(b["max"]) == len(b["mean"])
        assert len(b["x"]) == br.BOTTOM_BINS
        assert b["x"][0] < 2 * n * dt / br.BOTTOM_BINS  # 첫 구간이 t=0에서 시작
        assert all(lo <= m <= hi for lo, m, hi in zip(b["min"], b["mean"], b["max"]))
        # 측정 구간 안 구간들: 최대-최소 = 표의 리플, 구간 평균(점 수 같음) = 표의 평균
        inside = [k for k, x in enumerate(b["x"]) if x >= measure_start]
        ripple = rows[run]["I(L1).ripple"]
        peak = max(b["max"][k] for k in inside) - min(b["min"][k] for k in inside)
        assert peak == pytest.approx(ripple, rel=1e-4)
        mean = sum(b["mean"][k] for k in inside) / len(inside)
        assert mean == pytest.approx(rows[run]["I(L1).mean"], rel=1e-6)
        # 위 칸 점선 = 그 run의 평균
        assert tr["mean"] == pytest.approx(rows[run]["I(L1).mean"])


async def test_waveform_bottom_keeps_delayed_run_start(env, monkeypatch):
    """저장 시작을 크게 늦춘 run(첫 시각 > 저장 간격 1.5배)은 실제 시작 시각을 그대로 표기."""
    app, cfg, sch = env
    calls: list[tuple] = []
    original = br.render_waveform_plot

    def spy(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(br, "render_waveform_plot", spy)
    dt, n = pool_mod.MOCK_WAVE_DT, pool_mod.MOCK_WAVE_POINTS
    t0 = 0.01  # 10 ms부터 저장(10,000 × 저장 간격)
    monkeypatch.setattr(pool_mod, "MOCK_WAVE_T0", t0)
    res, _ = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
    )
    assert len(calls) == 1
    bottom_title = calls[0][4]
    xlim = calls[0][9]
    run_end = t0 + (n - 1) * dt
    assert xlim == (pytest.approx(t0), pytest.approx(run_end))
    assert bottom_title.split("\n")[0].startswith(
        f"full run {br.eng(t0, 's')} – {br.eng(run_end, 's')} ("
    )
    wave = next(p for p in res["data"]["plots"] if p["kind"] == "waveforms")
    assert wave["bottom"]["time_span"] == [pytest.approx(t0), pytest.approx(run_end)]


async def test_waveform_bottom_caps_at_three_runs_with_note(env, monkeypatch):
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
        conditions=[{"Lx": v} for v in _LX[:6]],
        workers=2,
        rank_by="I(L1).ripple",
        top_k=5,
        plot=True,
    )
    traces = calls[0][0]
    assert len(traces) == 5  # 위 칸은 5개 모두
    assert [bool(tr.get("bins")) for tr in traces] == [True, True, True, False, False]
    fig = br.build_waveform_figure(*calls[0])
    assert len(fig.axes) == 1 + br.BOTTOM_MAX_RUNS
    assert any("상위 3개 run만" in n and "5개 모두" in n for n in res["data"]["notes"])
    wave = next(p for p in res["data"]["plots"] if p["kind"] == "waveforms")
    assert len(wave["bottom"]["runs"]) == 3 and wave["bytes"] <= br.IMAGE_MAX_BYTES


# ---------------------------------------------------------------------------
# 그림 개선(단위·공학 표기·FFT 주기 추정·두 칸 파형·Patch 범례)
# ---------------------------------------------------------------------------


def _triangle(n: int, period_samples: float, mean: float = 5.0, ripple: float = 1.0):
    return [mean + ripple * (abs(((i / period_samples) % 1.0) * 2.0 - 1.0) - 0.5) for i in range(n)]


@pytest.mark.parametrize("freq_hz,dt", [(5000.0, 1e-6), (20000.0, 2e-7), (5000.0, 1e-5)])
def test_estimate_period_known_triangle(freq_hz, dt):
    """알려진 주파수의 삼각파(+느린 변화)에서 주기를 0.5% 안으로 찾는다."""
    n = 32768
    spp = 1.0 / (freq_hz * dt)  # 200, 250, 20 샘플/주기
    y = [v + 0.05 * math.sin(i / n * 3.0) for i, v in enumerate(_triangle(n, spp))]
    t = [2.5 + i * dt for i in range(n)]
    est = br.estimate_period(y, t)
    assert est is not None
    assert est["period_s"] == pytest.approx(1.0 / freq_hz, rel=5e-3)
    assert est["dt_s"] == pytest.approx(dt)
    assert est["samples_per_period"] == pytest.approx(spp, rel=5e-3)


def test_estimate_period_non_integer_samples():
    y = _triangle(20000, 37.3)
    est = br.estimate_period(y, [i * 1e-6 for i in range(20000)])
    assert est["samples_per_period"] == pytest.approx(37.3, rel=5e-3)


def test_estimate_period_failures_return_none():
    t = [i * 1e-6 for i in range(4096)]
    assert br.estimate_period([3.0] * 4096, t) is None  # 일정한 신호
    assert br.estimate_period(_triangle(50, 10), t[:50]) is None  # 점이 너무 적음
    assert br.estimate_period(_triangle(4096, 10), None) is None  # 시간 축 없음
    assert br.estimate_period(_triangle(4096, 10), [0.0] * 4096) is None  # 간격 0
    # 구간 안에 1주기뿐(너무 느림)
    assert br.estimate_period(_triangle(4096, 4096), t) is None
    rnd = random.Random(3)
    assert br.estimate_period([rnd.gauss(0, 1) for _ in range(4096)], t) is None  # 잡음


@pytest.mark.parametrize(
    "signal,unit", [("I(L1)", "A"), ("V(out)", "V"), ("Vo1", None), ("IL1", None)]
)
def test_signal_unit(signal, unit):
    assert br.signal_unit(signal) == unit
    label = br.with_unit(f"{signal}.ripple", signal)
    assert label == (f"{signal}.ripple [{unit}]" if unit else f"{signal}.ripple")


def test_metric_figure_units_and_eng_input_axis():
    from matplotlib.ticker import EngFormatter

    recs = [_rec(i, {"Lx": 0.0005 + i * 0.0005}, 10.0 / (i + 1), rank=i + 1) for i in range(10)]
    key, xs = br.choose_x_axis(recs)
    fig = br.build_metric_figure(recs, [("I(L1)", "ripple")], key, xs, [0, 1, 2], "t")
    ax = fig.axes[0]
    assert ax.get_ylabel() == "I(L1).ripple [A]"
    fmt = ax.xaxis.get_major_formatter()
    assert isinstance(fmt, EngFormatter)
    assert fmt(0.0045) == "4.5m" and fmt(0.001) == "1m"
    assert ax.get_xlabel() == "Lx"  # 입력 단위는 모르므로 붙이지 않음
    # run 축이면 공학 표기를 쓰지 않는다
    two = [_rec(0, {"Lx": 1, "R": 1}, 1.0), _rec(1, {"Lx": 2, "R": 2}, 1.0)]
    key2, xs2 = br.choose_x_axis(two)
    fig2 = br.build_metric_figure(two, [("Vo1", "mean")], key2, xs2, [], "t")
    assert not isinstance(fig2.axes[0].xaxis.get_major_formatter(), EngFormatter)
    assert fig2.axes[0].get_ylabel() == "Vo1.mean"


def _fig_traces(k: int = 3) -> list[dict]:
    return [
        {
            "label": f"#{i + 1} run {i}",
            "env_x": [j * 1e-5 for j in range(1000)],
            "env_y": _triangle(1000, 8, mean=5.0, ripple=1.0 + i),
            "zoom_x": [(j - 200) * 1e-6 for j in range(201)],
            "zoom_y": _triangle(201, 40, mean=5.0, ripple=1.0 + i),
            "mean": 5.0 + 0.01 * i,
            "short_label": f"#{i + 1} run {i}, Lx={i + 1}m",
            "bins": {
                "x": [j * 1e-4 for j in range(1000)],
                "min": [4.0 - i - 2.0 * math.exp(-j / 50) for j in range(1000)],
                "max": [6.0 + i + 3.0 * math.exp(-j / 50) for j in range(1000)],
                "mean": [5.0 + math.exp(-j / 50) for j in range(1000)],
            },
        }
        for i in range(k)
    ]


def test_waveform_figure_legend_patch_colors_match_data():
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Patch

    fig = br.build_waveform_figure(_fig_traces(3), "I(L1)", "t", "zoom", "env")
    ax_zoom, *bottom = fig.axes
    legend = ax_zoom.get_legend()
    handles = legend.legend_handles
    assert len(handles) == 3 and all(isinstance(h, Patch) for h in handles)
    assert [t.get_text() for t in legend.get_texts()] == ["#1 run 0", "#2 run 1", "#3 run 2"]

    for i, h in enumerate(handles):
        color = to_rgb(br.trace_color(i))
        assert to_rgb(h.get_facecolor()) == color and to_rgb(h.get_edgecolor()) == color
        assert to_rgb(_by_gid(ax_zoom, f"zoom{i}").get_color()) == color
        mean_line = _by_gid(ax_zoom, f"mean{i}")
        assert to_rgb(mean_line.get_color()) == color and mean_line.get_linestyle() == ":"
    assert ax_zoom.get_ylabel() == "I(L1) [A]"
    assert len(bottom) == 3 and all(ax.get_ylabel() == "I(L1) [A]" for ax in bottom)


def _by_gid(ax, gid):
    found = [a for a in ax.get_children() if a.get_gid() == gid]
    assert len(found) == 1, gid
    return found[0]


def test_waveform_bottom_one_subplot_per_run_shared_axes_and_colors():
    from matplotlib.colors import to_rgb

    traces = _fig_traces(3)
    fig = br.build_waveform_figure(
        traces,
        "I(L1)",
        "t",
        "zoom",
        "full run\nbins",
        "Time (s)",
        None,
        (0.0989, 0.0999),
        0.05,
        (0.0, 0.0999),
    )
    ax_zoom, *bottom = fig.axes
    assert len(bottom) == 3
    for j, ax in enumerate(bottom):
        # 겹쳐 그리지 않음: 그래프마다 그 run의 선 3종만
        gids = sorted(ln.get_gid() for ln in ax.lines if (ln.get_gid() or "").startswith("bin_"))
        assert gids == [f"bin_max{j}", f"bin_mean{j}", f"bin_min{j}"]
        color = to_rgb(br.trace_color(j))
        for kind in ("max", "min", "mean"):
            line = _by_gid(ax, f"bin_{kind}{j}")
            assert to_rgb(line.get_color()) == color and line.get_linestyle() == "-"
        # 평균은 굵게, 최대·최소는 얇게. 띠(칠하기) 없음
        mean_w = _by_gid(ax, f"bin_mean{j}").get_linewidth()
        assert mean_w > _by_gid(ax, f"bin_max{j}").get_linewidth()
        assert not [c for c in ax.collections if "band" in (c.get_gid() or "")]
        label = _by_gid(ax, f"run_label{j}")
        assert label.get_text() == traces[j]["short_label"]
        assert to_rgb(label.get_color()) == color
        # 확대 구간 음영(위 칸 범위)·측정 구간 시작 점선
        shade = _by_gid(ax, f"zoom_shade{j}")
        # axvspan: matplotlib 3.9+는 Rectangle(x는 데이터 좌표)
        x0, x1 = shade.get_x(), shade.get_x() + shade.get_width()
        assert x0 == pytest.approx(0.0989) and x1 == pytest.approx(0.0999)
        measure = _by_gid(ax, f"measure{j}")
        assert list(measure.get_xdata()) == [0.05, 0.05] and measure.get_linestyle() == "--"
    # 라벨은 첫 그래프에만
    assert _by_gid(bottom[0], "zoom_label").get_text() == "zoomed above (1 ms)"
    assert "measurement window" in _by_gid(bottom[0], "measure_label").get_text()
    for ax in bottom[1:]:
        assert not [a for a in ax.get_children() if a.get_gid() in ("zoom_label", "measure_label")]
    # y·x축 공유, x 범위 = run 전체, 위 칸과는 따로
    for ax in bottom[1:]:
        assert ax.get_shared_y_axes().joined(bottom[0], ax)
        assert ax.get_shared_x_axes().joined(bottom[0], ax)
        assert ax.get_ylim() == bottom[0].get_ylim()
    assert bottom[0].get_xlim() == pytest.approx((0.0, 0.0999))
    assert not ax_zoom.get_shared_x_axes().joined(ax_zoom, bottom[0])
    # 아래 그래프 사이는 좁게(BOTTOM_GAP), 위 칸~아래 묶음 사이는 넓게, 높이는 같게
    pos = [ax.get_position() for ax in bottom]
    for a, b in zip(pos, pos[1:]):
        assert a.y0 - b.y1 == pytest.approx(br.BOTTOM_GAP, abs=1e-6)
        assert a.height == pytest.approx(b.height)
    assert ax_zoom.get_position().y0 - pos[0].y1 > 3 * br.BOTTOM_GAP
    # 마지막 그래프에만 x축 글자
    assert bottom[-1].get_xlabel() == "Time (s)" and bottom[0].get_xlabel() == ""
    assert bottom[0].title.get_text() == "full run\nbins"


def test_waveform_bottom_skips_traces_without_bins_and_caps_three():
    traces = _fig_traces(5)
    traces[1].pop("bins")
    fig = br.build_waveform_figure(traces, "I(L1)", "t", "zoom", "env")
    # 앞 3개 중 bins가 있는 0·2만, 색 번호는 순위 그대로
    assert len(fig.axes) == 3
    assert _by_gid(fig.axes[2], "bin_mean2")
    png = br.render_waveform_plot(_fig_traces(3), "I(L1)", "t", "zoom", "a\nb")
    assert len(png) <= br.IMAGE_MAX_BYTES


def test_bin_stats_matches_bridge_and_preserves_mean():
    rnd = random.Random(7)
    y = [math.sin(i / 13.0) + rnd.uniform(-0.5, 0.5) for i in range(12_345)]
    t = [i * 1e-6 for i in range(12_345)]
    for bins in (1, 7, 1000, 20_000):
        server = br.bin_stats(y, t, bins)
        assert server == bridge_script._bin_stats(y, t, bins)
        assert len(server["mean"]) == min(bins, len(y)) and sum(server["count"]) == len(y)
        # 구간 평균의 점 수 가중 평균 = 원본 평균
        assert br.bins_mean(server) == pytest.approx(sum(y) / len(y), abs=1e-9)
        assert min(server["min"]) == round(min(y), 9) and max(server["max"]) == round(max(y), 9)
    no_t = br.bin_stats(y, None, 10)
    assert no_t["t"] is None and no_t == bridge_script._bin_stats(y, None, 10)
    assert br.bin_stats([], None, 10)["mean"] == []
    assert br.bins_mean({"mean": [], "count": []}) is None


def test_run_start_from_zero():
    # 실제 PSIM: 첫 저장 시각 = 저장 간격(5 µs) → 0부터
    assert br.run_start_from_zero(5e-6, 5e-6) == 0.0
    assert br.run_start_from_zero(0.0, 5e-6) == 0.0
    assert br.run_start_from_zero(7.5e-6, 5e-6) == 0.0  # 경계 1.5배 포함
    # 그보다 크면(저장 시작을 늦춤) 실제 시각 그대로
    assert br.run_start_from_zero(7.6e-6, 5e-6) == 7.6e-6
    assert br.run_start_from_zero(0.1, 5e-6) == 0.1
    # 저장 간격을 모르면 그대로
    assert br.run_start_from_zero(5e-6, None) == 5e-6
    assert br.run_start_from_zero(5e-6, 0.0) == 5e-6


def test_bottom_title_text():
    assert br.bottom_title_text(0.0, 0.5, 0.001) == (
        "full run 0 – 500 ms (500× longer time span than top)\n"
        "per-bin max/min/mean (~1000 bins) - envelope, not a waveform"
    )
    assert br.bottom_title_text(0.0, 0.5, 0.249995).startswith("full run 0 – 500 ms (2× longer")
    assert br.bottom_title_text(0.0, 5.0, None).split("\n")[0] == "full run 0 – 5 s"


def test_describe_inputs_engineering():
    assert br.describe_inputs({"Lx": 0.005000000000000001}, engineering=True) == "Lx=5m"
    assert br.describe_inputs({"Lx": 0.004590909090909092}, engineering=True) == "Lx=4.59m"
    assert br.describe_inputs({"Lx": 0.005}) == "Lx=0.005"  # 범례는 기존 그대로


@pytest.mark.parametrize("value", [0, -1, "1m", True, float("nan"), float("inf")])
def test_validate_plot_window_rejects(value):
    with pytest.raises(br.ReportInputError) as e:
        br.validate_plot_window_s(value)
    assert e.value.code == "INVALID_INPUT" and e.value.suggestion


def test_validate_plot_window_accepts():
    assert br.validate_plot_window_s(None) is None
    assert br.validate_plot_window_s(1) == 1.0 and br.validate_plot_window_s(2e-4) == 2e-4


async def test_invalid_plot_window_rejected_before_run(env):
    app, cfg, sch = env
    res, _ = await _call_raw(
        app, schematic_path=str(sch), conditions=[{"Lx": 0.001}], plot=True, plot_window_s=0
    )
    assert not res["success"] and res["error"]["code"] == "INVALID_INPUT"
    assert not cfg.runs_dir.exists() or not any(cfg.runs_dir.iterdir())
    assert app._services["pool"].pids == []


def _spy_render(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []
    original = br.render_waveform_plot

    def spy(*args):
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(br, "render_waveform_plot", spy)
    return calls


async def _plot_run(app, sch, **extra):
    res, blocks = await _call_raw(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v} for v in _LX[:4]],
        workers=2,
        rank_by="I(L1).ripple",
        plot=True,
        **extra,
    )
    assert res["success"], res
    waves = [p for p in res["data"]["plots"] if p["kind"] == "waveforms"]
    assert len(waves) == 1
    return res["data"], waves[0], blocks


async def test_zoom_uses_fft_period_and_reports_samples(env, monkeypatch):
    """mock 파형: 주기 40 샘플, dt 1 µs → T = 40 µs, 확대 = 5주기 = 200 µs, 원본 해상도."""
    app, cfg, sch = env
    calls = _spy_render(monkeypatch)
    data, wave, _ = await _plot_run(app, sch)
    zoom = wave["zoom"]
    assert zoom["period_source"] == "fft" and zoom["window_source"] == "fft"
    assert zoom["period_s"] == pytest.approx(40e-6, rel=5e-3)
    assert zoom["samples_per_period"] == pytest.approx(40, rel=5e-3)
    assert zoom["window_s"] == pytest.approx(200e-6, rel=5e-3)
    assert zoom["low_resolution"] is False
    assert zoom["window_samples"] == pytest.approx(201, abs=2)
    traces, signal, title, zoom_title = calls[0][:4]
    assert "low resolution" not in title
    assert "5 switching periods" in zoom_title and "40 samples/period" in zoom_title
    assert "full resolution" in zoom_title
    for tr in traces:
        # 원본 해상도(줄이지 않음): 점 간격 = dt, run 끝 기준 상대 시간
        assert len(tr["zoom_y"]) == pytest.approx(201, abs=2)
        assert tr["zoom_x"][-1] == pytest.approx(0.0, abs=1e-12)
        assert tr["zoom_x"][1] - tr["zoom_x"][0] == pytest.approx(1e-6)
    assert not any("PRINTSTEP" in n or "추정하지 못해" in n for n in data.get("notes", []))


async def test_zoom_plot_window_s_sets_length_but_fft_still_runs(env, monkeypatch):
    """plot_window_s는 확대 길이에만 쓰고, FFT 주기·주기당 샘플 수는 그대로 계산한다."""
    app, cfg, sch = env
    calls = _spy_render(monkeypatch)
    seen: list[dict] = []
    original = pool_mod.MockWorker._extract_signals

    def spy(params):
        seen.append(params)
        return original(params)

    monkeypatch.setattr(pool_mod.MockWorker, "_extract_signals", staticmethod(spy))
    data, wave, _ = await _plot_run(app, sch, plot_window_s=0.0005)
    zoom = wave["zoom"]
    assert zoom["window_source"] == "plot_window_s" and zoom["window_s"] == 0.0005
    assert zoom["period_source"] == "fft"
    assert zoom["period_s"] == pytest.approx(40e-6, rel=5e-3)
    assert zoom["samples_per_period"] == pytest.approx(40, rel=5e-3)
    assert zoom["low_resolution"] is False
    # 측정 구간 3 + FFT 1 + 확대 3 (+ 아래 칸 구간 통계 3)
    assert sum(p.get("max_points") == 2 * br.FFT_MAX_POINTS for p in seen) == 1
    assert len([p for p in seen if p.get("reduce") != "bins"]) == 7
    assert len([p for p in seen if p.get("reduce") == "bins"]) == 3
    traces, _, title, zoom_title = calls[0][:4]
    assert "plot_window_s" in zoom_title and "40 samples/period" in zoom_title
    assert "low resolution" not in title
    for tr in traces:
        assert tr["zoom_x"][-1] - tr["zoom_x"][0] == pytest.approx(0.0005, abs=2e-6)
    assert not any("추정하지 못해" in n or "PRINTSTEP" in n for n in data.get("notes", []))


async def test_zoom_plot_window_s_low_resolution_warning(env, monkeypatch):
    app, cfg, sch = env
    monkeypatch.setattr(pool_mod, "MOCK_WAVE_PERIOD", 10)  # 주기당 10 샘플 < 20
    calls = _spy_render(monkeypatch)
    data, wave, _ = await _plot_run(app, sch, plot_window_s=0.0003)
    zoom = wave["zoom"]
    assert zoom["window_source"] == "plot_window_s" and zoom["window_s"] == 0.0003
    assert zoom["samples_per_period"] == pytest.approx(10, abs=0.1)
    assert zoom["low_resolution"] is True
    assert f"low resolution: {zoom['samples_per_period']:g} samples/period" in calls[0][2]
    assert any("PRINTSTEP" in n for n in data["notes"])


async def test_zoom_plot_window_s_fft_failure_gives_null_and_note(env, monkeypatch):
    app, cfg, sch = env
    monkeypatch.setattr(pool_mod, "MOCK_WAVE_PERIOD", 0)  # 일정한 신호 → FFT 실패
    calls = _spy_render(monkeypatch)
    data, wave, _ = await _plot_run(app, sch, plot_window_s=0.0005)
    zoom = wave["zoom"]
    # 확대 길이는 plot_window_s 그대로(1% fallback 아님), 주기 정보는 null
    assert zoom["window_source"] == "plot_window_s" and zoom["window_s"] == 0.0005
    assert zoom["period_source"] is None and zoom["period_s"] is None
    assert zoom["samples_per_period"] is None and zoom["low_resolution"] is False
    assert any("추정하지 못해" in n and "null" in n for n in data["notes"])
    assert not any("1%" in n for n in data["notes"])
    assert "period not found" in calls[0][3] and "plot_window_s" in calls[0][3]


async def test_zoom_plot_window_longer_than_window_is_clamped(env):
    app, cfg, sch = env
    data, wave, _ = await _plot_run(app, sch, plot_window_s=10.0)
    duration = (pool_mod.MOCK_WAVE_POINTS - 1 - pool_mod.MOCK_WAVE_POINTS // 2) * 1e-6
    assert wave["zoom"]["window_s"] == pytest.approx(duration, rel=1e-6)
    assert any("plot_window_s" in n and "측정 구간 전체" in n for n in data["notes"])


async def test_zoom_fft_failure_falls_back_to_last_percent(env, monkeypatch):
    app, cfg, sch = env
    monkeypatch.setattr(pool_mod, "MOCK_WAVE_PERIOD", 0)  # 일정한 신호 → FFT 실패
    calls = _spy_render(monkeypatch)
    data, wave, _ = await _plot_run(app, sch)
    zoom = wave["zoom"]
    duration = (pool_mod.MOCK_WAVE_POINTS - 1 - pool_mod.MOCK_WAVE_POINTS // 2) * 1e-6
    assert zoom["window_source"] == "fallback"
    assert zoom["period_source"] is None and zoom["period_s"] is None
    assert zoom["samples_per_period"] is None
    assert zoom["window_s"] == pytest.approx(0.01 * duration, rel=1e-6)
    assert any("추정하지 못해" in n and "1%" in n for n in data["notes"])
    assert "period not found" in calls[0][3]


async def test_zoom_low_resolution_warning(env, monkeypatch):
    app, cfg, sch = env
    monkeypatch.setattr(pool_mod, "MOCK_WAVE_PERIOD", 10)  # 주기당 10 샘플 < 20
    calls = _spy_render(monkeypatch)
    data, wave, _ = await _plot_run(app, sch)
    zoom = wave["zoom"]
    assert zoom["samples_per_period"] == pytest.approx(10, abs=0.1)
    assert zoom["low_resolution"] is True
    title = calls[0][2]
    assert f"low resolution: {zoom['samples_per_period']:g} samples/period" in title
    assert any("PRINTSTEP" in n for n in data["notes"])


async def test_zoom_read_failure_keeps_envelope(env, monkeypatch):
    app, cfg, sch = env
    original = pool_mod.MockWorker._extract_signals

    def flaky(params):
        if params.get("max_points") == br.ZOOM_MAX_POINTS:
            return {"success": False, "error": {"code": "READ_FAILED", "message": "busy"}}
        return original(params)

    monkeypatch.setattr(pool_mod.MockWorker, "_extract_signals", staticmethod(flaky))
    data, wave, _ = await _plot_run(app, sch)
    assert sum("확대 구간을 읽지 못해" in n and "busy" in n for n in data["notes"]) == 3
    assert wave["bytes"] > 0


def test_bridge_extract_time_range(monkeypatch, tmp_path):
    n = 10_000
    t = [i * 1e-6 for i in range(n)]
    y = _hf_triangle(n)
    _fake_psim(monkeypatch, [_Curve("Time", t), _Curve("I(L1)", y)])
    smv = tmp_path / "result.smv"
    smv.write_bytes(b"x")
    base = {"graph_file": str(smv), "signals": ["I(L1)", "Time"], "skip_ratio": 0.5}
    # minmax + t_start: 원본 그대로(점 수 ≤ max_points), times·source_points·time_span
    res = bridge_script.handle_extract_signals(
        {**base, "t_start": 9.7995e-3, "max_points": 40000, "reduce": "minmax"}
    )
    data = res["data"]
    lo = 9800
    assert data["signals"]["I(L1)"] == [round(v, 9) for v in y[lo:]]
    assert data["times"]["I(L1)"] == [round(v, 12) for v in t[lo:]]
    assert data["reduced"] == {"I(L1)": False}
    assert data["source_points"] == {"I(L1)": n - lo}
    assert data["time_span"] == [round(t[lo], 12), round(t[-1], 12)]
    # Time을 요청하지 않아도 시간 범위면 times를 채운다
    res2 = bridge_script.handle_extract_signals(
        {
            **base,
            "signals": ["I(L1)"],
            "t_start": 9.7995e-3,
            "max_points": 40000,
            "reduce": "minmax",
        }
    )
    assert res2["data"]["times"]["I(L1)"] == data["times"]["I(L1)"]
    # t_start가 skip_ratio 앞이면 측정 구간 시작부터, t_end로 끝 자르기(stride)
    res3 = bridge_script.handle_extract_signals(
        {**base, "t_start": 0.0, "t_end": 5.0995e-3, "max_points": 40000}
    )
    assert res3["data"]["signals"]["Time"] == [round(v, 9) for v in t[5000:5100]]
    # minmax 기본 호출(시간 범위 없음)에도 source_points·time_span이 붙는다
    res4 = bridge_script.handle_extract_signals({**base, "max_points": 2000, "reduce": "minmax"})
    assert res4["data"]["source_points"] == {"I(L1)": 5000}
    assert res4["data"]["time_span"] == [round(t[5000], 12), round(t[-1], 12)]


def test_bridge_extract_time_range_errors(monkeypatch, tmp_path):
    smv = tmp_path / "result.smv"
    smv.write_bytes(b"x")
    _fake_psim(monkeypatch, [_Curve("I(L1)", [1.0, 2.0])])
    res = bridge_script.handle_extract_signals({"graph_file": str(smv), "t_start": 0.0})
    assert not res["success"] and res["error"]["code"] == "NO_TIME_CURVE"
    for bad in ("abc", True, float("nan")):
        res = bridge_script.handle_extract_signals({"graph_file": str(smv), "t_end": bad})
        assert not res["success"] and res["error"]["code"] == "INVALID_INPUT"
