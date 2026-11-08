"""run_batch 그림 2 주기 판정 — 회로 설정 우선, FFT fallback, undersampled(주기당 < 2점).

2026-11-08 실측: heavy 회로는 저장 간격 250 µs(TIMESTEP 5 µs × PRINTSTEP 50) > 스위칭 주기
200 µs(5 kHz)라 주기당 0.8점. FFT는 이런 경우 에일리어스 주파수를 잡으므로 회로 설정을 먼저 쓴다.
mock 파형: 측정 구간 10000점, 저장 간격 1 µs(MOCK_WAVE_DT).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mcp.types import TextContent

from psim_mcp.config import AppConfig
from psim_mcp.parallel import pool as pool_mod
from psim_mcp.server import create_app
from psim_mcp.services import batch_report as br

_LX = [0.001, 0.002, 0.003, 0.004]

# ---------------------------------------------------------------------------
# 순수 함수
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "spp,expected",
    [
        (None, None),
        (0.8, "undersampled"),
        (1.99, "undersampled"),
        (2, "low"),  # 경계: 2는 undersampled 아님
        (19.9, "low"),
        (20, "ok"),  # 경계: 20은 저해상도 아님
        (40, "ok"),
    ],
)
def test_sampling_class_boundaries(spp, expected):
    assert br.sampling_class(spp) == expected


def test_switching_frequency_candidates_types_values_and_overrides():
    elements = {
        "G0": {"type": "GATING", "params": {"Name": "G0", "Frequency": "5000"}},
        "VTRI1": {"type": "VTRI", "params": {"Name": "VTRI1", "Frequency": "20k"}},
        "VS1": {"type": "VSQU", "params": {"Name": "VS1", "Frequency": "fsw"}},
        "VSIN1": {"type": "VSIN", "params": {"Name": "VSIN1", "Frequency": "60"}},  # 스위칭 아님
        "L1": {"type": "L", "params": {"Name": "L1", "Inductance": "1m"}},
        "G9": {"type": "GATING", "params": {"Name": "G9", "Frequency": "1/Ts"}},  # 수식
        "G8": {"type": "GATING", "params": {"Name": "G8", "Frequency": "0"}},  # 0 이하 제외
    }
    found, unresolved = br.switching_frequency_candidates(
        elements,
        variables={"FSW": 50000},  # 변수 이름은 대소문자 무시
        element_changes=[{"component_id": "g0", "parameter_name": "Frequency", "value": "10k"}],
    )
    got = {c["element"]: c["frequency_hz"] for c in found}
    assert got == {"G0": 10000.0, "VTRI1": 20000.0, "VS1": 50000.0}
    assert unresolved == ["G9.Frequency=1/Ts"]


@pytest.mark.parametrize(
    "etype,params",
    [
        ("GATING", ("Frequency",)),
        ("VTRI", ("Frequency",)),
        ("VSAW", ("Frequency",)),
        ("VSQU", ("Frequency",)),
        ("VTRI_GND", ("Freq2",)),
        ("VSAW_GND", ("Freq3",)),
        ("SVPWM_2L", ("freq",)),
        ("PSM_F28004x_PWM", ("pwm_freq",)),
        ("PSM_F2837x_PHASEPWM", ("pwm_freq",)),
        ("PSM_F28335_CAPPWM", ("pwm_freq",)),
        # 스위칭 주기가 아니거나 다를 수 있는 것은 제외
        ("VSIN", ()),
        ("ZOH", ()),
        ("UDELAY", ()),
        ("DEVICE_MOSFET_EON1", ()),
        ("ISQU", ()),
        ("PSM_F28004x_CANIN", ()),
    ],
)
def test_switching_frequency_params_type_list(etype, params):
    assert br.switching_frequency_params(etype) == params


def test_switching_frequency_candidates_parses_unit_suffix():
    elements = {
        "VSQ1": {"type": "VSQU", "params": {"Frequency": "3kHz"}},
        "P1": {"type": "PSM_F28004x_PWM", "params": {"pwm_freq": "20K"}},
    }
    found, _ = br.switching_frequency_candidates(elements)
    assert {c["element"]: c["frequency_hz"] for c in found} == {"VSQ1": 3000.0, "P1": 20000.0}


def test_switching_frequency_candidates_unresolved_variable():
    elements = {"G0": {"type": "GATING", "params": {"Frequency": "fsw"}}}
    found, unresolved = br.switching_frequency_candidates(elements, variables={})
    assert found == [] and unresolved == ["G0.Frequency=fsw"]


def test_configured_print_interval():
    sc = {"": {"type": "Simulation Control", "params": {"TIMESTEP": "5E-06", "PRINTSTEP": "50"}}}
    assert br.configured_print_interval(sc) == pytest.approx(250e-6)
    # run_batch time_step 덮어쓰기
    assert br.configured_print_interval(sc, time_step=1e-6) == pytest.approx(50e-6)
    assert br.configured_print_interval({}) is None
    bad = {"": {"type": "Simulation Control", "params": {"TIMESTEP": "dt", "PRINTSTEP": "1"}}}
    assert br.configured_print_interval(bad) is None
    assert br.configured_print_interval(bad, {"dt": "2u"}) == pytest.approx(2e-6)


def test_waveform_figure_zoom_message_replaces_zoom_panel():
    traces = [
        {
            "label": "#1 run 0",
            "bins": {
                "x": [0.0, 1.0, 2.0],
                "min": [1.0, 1.2, 1.4],
                "max": [2.0, 2.1, 1.9],
                "mean": [1.5, 1.6, 1.7],
            },
            "mean": 1.5,
            "zoom_x": [-1e-6, 0.0],
            "zoom_y": [1.0, 2.0],
        }
    ]
    fig = br.build_waveform_figure(
        traces, "I(L1)", "t", "zoom not drawn", "env", zoom_message="undersampled: x"
    )
    ax_zoom = fig.axes[0]
    assert [t.get_text() for t in ax_zoom.texts if t.get_gid() == "zoom_message"] == [
        "undersampled: x"
    ]
    assert not [ln for ln in ax_zoom.lines if (ln.get_gid() or "").startswith(("zoom", "mean"))]
    assert not any(gl.get_visible() for gl in ax_zoom.get_xgridlines())
    # 아래 칸(run별 구간 통계)과 범례는 그대로
    assert any(ln.get_gid() == "bin_mean0" for ln in fig.axes[1].lines)
    assert ax_zoom.get_legend() is not None
    # 점선(평균)을 그리지 않으므로 범례 제목 "dotted: mean"도 없음
    assert ax_zoom.get_legend().get_title().get_text() == ""

    # 위 칸을 그릴 때와 비교: 위 칸 높이·그림 전체 높이가 줄고, 아래 칸 run 그래프 높이는 비슷
    normal = br.build_waveform_figure(traces, "I(L1)", "t", "zoom", "env")
    assert normal.axes[0].get_legend().get_title().get_text() == "dotted: mean"
    fig_h, normal_h = fig.get_size_inches()[1], normal.get_size_inches()[1]
    assert fig_h < normal_h - 1.5
    renderer = fig.canvas.get_renderer()
    n_renderer = normal.canvas.get_renderer()
    zoom_px = ax_zoom.get_window_extent(renderer).height
    normal_zoom_px = normal.axes[0].get_window_extent(n_renderer).height
    assert zoom_px < normal_zoom_px / 2
    bottom_px = fig.axes[1].get_window_extent(renderer).height
    normal_bottom_px = normal.axes[1].get_window_extent(n_renderer).height
    assert bottom_px == pytest.approx(normal_bottom_px, rel=0.25)
    # 문구는 축 안에
    message = next(t for t in ax_zoom.texts if t.get_gid() == "zoom_message")
    assert br.text_inside_axes(fig, message, ax_zoom)


@pytest.mark.parametrize(
    "spp,interval,period,expected",
    [
        # heavy 실측(저장 간격 > 주기)
        (
            0.8,
            250e-6,
            200e-6,
            "undersampled: 0.8 samples/period < 2 "
            "(print interval 250 µs, switching period 200 µs) - zoom not drawn; reduce PRINTSTEP",
        ),
        # 저장 간격 < 주기지만 주기당 2점 미만(예전 ">=" 문구가 사실이 아니던 경우)
        (
            1.5,
            1e-6,
            1.5e-6,
            "undersampled: 1.5 samples/period < 2 "
            "(print interval 1 µs, switching period 1.5 µs) - zoom not drawn; reduce PRINTSTEP",
        ),
    ],
)
def test_undersampled_message_states_criterion(spp, interval, period, expected):
    assert interval < period or spp < 1
    msg = br.undersampled_message(spp, interval, period)
    assert msg == expected
    assert ">=" not in msg
    # 그림용은 ")" 뒤에서만 줄바꿈, 내용은 같음
    two = br.undersampled_message(spp, interval, period, multiline=True)
    assert two.replace("\n", " ") == expected
    assert two.count("\n") == 1 and two.split("\n")[1] == "- zoom not drawn; reduce PRINTSTEP"
    # 판정과 문구가 일치: 문구가 나오는 값은 모두 undersampled
    assert br.sampling_class(spp) == "undersampled"


# ---------------------------------------------------------------------------
# run_batch (mock)
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


def _with_elements(monkeypatch, **extra):
    elements = dict(pool_mod.MOCK_ELEMENTS)
    elements.update(extra)
    monkeypatch.setattr(pool_mod, "MOCK_ELEMENTS", elements)


def _gating(freq, name="G1"):
    return {name: {"type": "GATING", "params": {"Name": name, "Frequency": freq}}}


def _spy(monkeypatch):
    calls: list[tuple] = []
    seen: list[dict] = []
    render = br.render_waveform_plot
    extract = pool_mod.MockWorker._extract_signals

    def spy_render(*args):
        calls.append(args)
        return render(*args)

    def spy_extract(params):
        seen.append(params)
        return extract(params)

    monkeypatch.setattr(br, "render_waveform_plot", spy_render)
    monkeypatch.setattr(pool_mod.MockWorker, "_extract_signals", staticmethod(spy_extract))
    return calls, seen


async def _plot_run(app, **kwargs):
    kwargs.setdefault("conditions", [{"Lx": v} for v in _LX])
    kwargs.update(workers=2, rank_by="I(L1).ripple", plot=True)
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    try:
        out = await app.call_tool("run_batch", kwargs)
    finally:
        await app._services["pool"].shutdown()
    blocks = out[0] if isinstance(out, tuple) else out
    assert isinstance(blocks[0], TextContent)
    res = json.loads(blocks[0].text)
    assert res["success"], res
    waves = [p for p in res["data"]["plots"] if p["kind"] == "waveforms"]
    assert len(waves) == 1
    return res["data"], waves[0]["zoom"]


async def test_circuit_frequency_is_used_before_fft(env, monkeypatch):
    app, _, sch = env
    _with_elements(monkeypatch, **_gating("25k"))  # T = 40 µs = mock 파형 주기
    calls, seen = _spy(monkeypatch)
    data, zoom = await _plot_run(app, schematic_path=str(sch))
    assert zoom["period_source"] == "circuit" and zoom["period_element"] == "G1.Frequency"
    assert zoom["period_s"] == pytest.approx(40e-6)
    assert zoom["print_interval_s"] == pytest.approx(1e-6)
    assert zoom["samples_per_period"] == pytest.approx(40)
    assert zoom["period_reliable"] is True and zoom["low_resolution"] is False
    assert zoom["window_source"] == "circuit" and zoom["window_s"] == pytest.approx(200e-6)
    # FFT 호출 없음: envelope 3 + 확대 3
    assert not any(p.get("max_points") == 2 * br.FFT_MAX_POINTS for p in seen)
    # 측정 구간 3 + 확대 3, 아래 칸 run 전체 구간 통계 3
    assert len([p for p in seen if p.get("reduce") != "bins"]) == 6
    assert len([p for p in seen if p.get("reduce") == "bins"]) == 3
    zoom_title = calls[0][3]
    assert "from circuit (G1.Frequency)" in zoom_title and "40 samples/period" in zoom_title
    assert "FFT" not in zoom_title
    assert not any("FFT" in n or "PRINTSTEP" in n for n in data.get("notes", []))


async def test_highest_circuit_frequency_wins_with_note(env, monkeypatch):
    app, _, sch = env
    _with_elements(
        monkeypatch,
        **_gating("5k", "G0"),
        VTRI1={"type": "VTRI", "params": {"Name": "VTRI1", "Frequency": "25000"}},
    )
    data, zoom = await _plot_run(app, schematic_path=str(sch))
    assert zoom["period_element"] == "VTRI1.Frequency"
    assert zoom["period_s"] == pytest.approx(40e-6)
    assert any("후보가 여러 개" in n and "25000 Hz" in n for n in data["notes"])


async def test_element_condition_changes_circuit_frequency(env, monkeypatch):
    app, _, sch = env
    _with_elements(monkeypatch, **_gating("5k"))
    # 모든 run에서 G1 주파수를 25 kHz로 바꾼다 → 1위 run 조건 기준 주기 40 µs
    _, zoom = await _plot_run(
        app,
        schematic_path=str(sch),
        conditions=[{"Lx": v, "G1.Frequency": "25k"} for v in _LX],
    )
    assert zoom["period_source"] == "circuit" and zoom["period_s"] == pytest.approx(40e-6)


async def test_fft_fallback_is_marked_estimated(env, monkeypatch):
    app, _, sch = env  # MOCK_ELEMENTS에는 스위칭 소자가 없다
    calls, seen = _spy(monkeypatch)
    data, zoom = await _plot_run(app, schematic_path=str(sch))
    assert zoom["period_source"] == "fft" and zoom["period_element"] is None
    assert zoom["period_s"] == pytest.approx(40e-6, rel=5e-3)
    assert zoom["print_interval_s"] == pytest.approx(1e-6)
    assert zoom["period_reliable"] is True
    assert sum(p.get("max_points") == 2 * br.FFT_MAX_POINTS for p in seen) == 1
    assert "estimated, may be aliased" in calls[0][3]
    assert any("FFT로 추정" in n and "may be aliased" in n for n in data["notes"])


async def test_unresolved_circuit_frequency_falls_back_to_fft_with_note(env, monkeypatch):
    app, _, sch = env
    _with_elements(monkeypatch, **_gating("1/Ts"))
    data, zoom = await _plot_run(app, schematic_path=str(sch))
    assert zoom["period_source"] == "fft"
    assert any("G1.Frequency=1/Ts" in n for n in data["notes"])


@pytest.mark.parametrize("plot_window_s", [None, 0.0005])
async def test_undersampled_skips_zoom_and_draws_envelope_only(env, monkeypatch, plot_window_s):
    app, _, sch = env
    _with_elements(monkeypatch, **_gating("625k"))  # T = 1.6 µs, 저장 1 µs → 1.6점/주기
    calls, seen = _spy(monkeypatch)
    data, zoom = await _plot_run(app, schematic_path=str(sch), plot_window_s=plot_window_s)
    assert zoom["period_source"] == "circuit"
    assert zoom["samples_per_period"] == pytest.approx(1.6)
    assert zoom["period_reliable"] is False
    assert zoom["window_s"] is None and zoom["window_source"] is None
    assert "window_samples" not in zoom
    # 확대 구간 읽기·FFT 없음: 측정 구간 3번 + 아래 칸 run 전체 구간 통계 3번
    assert all("t_start" not in p for p in seen)
    assert len([p for p in seen if p.get("reduce") != "bins"]) == 3
    assert len([p for p in seen if p.get("reduce") == "bins"]) == 3
    traces, _, title, zoom_title, _, _, zoom_message, zoom_span, measure_start, _ = calls[0]
    assert zoom_span is None  # 위 칸을 그리지 않으므로 음영도 없음
    assert measure_start is not None
    assert "undersampled: 1.6 samples/period" in title
    # 저장 간격(1 µs) < 주기(1.6 µs)인 경우 — 판정 기준(주기당 < 2점) 그대로 표기
    assert zoom_message == (
        "undersampled: 1.6 samples/period < 2 (print interval 1 µs, switching period 1.6 µs)\n"
        "- zoom not drawn; reduce PRINTSTEP"
    )
    assert ">=" not in zoom_message
    assert zoom_title == (
        "zoom not drawn\nT = 1.6 µs from circuit (G1.Frequency), print interval 1 µs"
    )
    assert all(not tr.get("zoom_y") for tr in traces)
    assert all(tr["bins"]["mean"] for tr in traces)  # 아래 칸(run 전체 구간 통계)은 그린다
    notes = data["notes"]
    under = [n for n in notes if "PRINTSTEP" in n]
    assert len(under) == 1
    # 모든 지표를 신뢰 불가로 안내(리플·최대·최소만이 아니라 평균도)
    # note 첫 문장 = 그림 문구(한 줄)
    assert under[0].startswith(
        "undersampled: 1.6 samples/period < 2 (print interval 1 µs, switching period 1.6 µs) "
        "- zoom not drawn; reduce PRINTSTEP. "
    )
    assert ">=" not in under[0] and "절반보다 길어" not in under[0]
    assert "모든 지표(평균·리플·최대·최소)를 신뢰할 수 없습니다" in under[0]
    assert "그리지 않았습니다" in under[0]
    assert "실제보다 작게" not in under[0]
    assert ("plot_window_s는 쓰지 않았습니다" in " ".join(notes)) == (plot_window_s is not None)


@pytest.mark.parametrize(
    "freq,spp,low",
    [("500k", 2.0, True), ("50k", 20.0, False)],  # 경계: 2 → 저해상도, 20 → 정상
)
async def test_sampling_boundaries_in_run_batch(env, monkeypatch, freq, spp, low):
    app, _, sch = env
    _with_elements(monkeypatch, **_gating(freq))
    calls, _ = _spy(monkeypatch)
    data, zoom = await _plot_run(app, schematic_path=str(sch))
    assert zoom["samples_per_period"] == pytest.approx(spp)
    assert zoom["period_reliable"] is True
    assert zoom["low_resolution"] is low
    assert zoom["window_s"] is not None  # 확대는 그린다
    assert ("low resolution" in calls[0][2]) is low
    assert calls[0][6] is None
    assert any("PRINTSTEP" in n for n in data.get("notes", [])) is low


async def test_print_interval_mismatch_note(env, monkeypatch):
    app, _, sch = env
    sc = {"type": "Simulation Control", "params": {"TIMESTEP": "1E-06", "PRINTSTEP": "2"}}
    _with_elements(monkeypatch, **_gating("25k"), **{"": sc})
    data, zoom = await _plot_run(app, schematic_path=str(sch))
    # 주기당 샘플 수는 결과 파일의 실제 간격(1 µs)으로
    assert zoom["print_interval_s"] == pytest.approx(1e-6)
    assert zoom["samples_per_period"] == pytest.approx(40)
    assert any("TIMESTEP×PRINTSTEP" in n for n in data["notes"])


async def test_print_interval_matching_setting_has_no_note(env, monkeypatch):
    app, _, sch = env
    sc = {"type": "Simulation Control", "params": {"TIMESTEP": "1E-06", "PRINTSTEP": "1"}}
    _with_elements(monkeypatch, **_gating("25k"), **{"": sc})
    data, _ = await _plot_run(app, schematic_path=str(sch))
    assert not any("TIMESTEP×PRINTSTEP" in n for n in data.get("notes", []))


# ---------------------------------------------------------------------------
# 위 칸 제목 두 줄·유효숫자 3자리·그림 안에 들어가는지 (2026-11-08 보충 C 실측 C5: 한 줄 제목
# "last 249.995 ms (plot_window_s), T = …, min/max envelope (too many points)"가 왼쪽으로 잘림)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.0002, "200 µs"),
        (0.249995, "250 ms"),  # C5 실측 값
        (0.0004, "400 µs"),
        (0.001, "1 ms"),
        (0.0009996, "1 ms"),  # 반올림이 단위 경계를 넘는 경우
        (1.23456e-6, "1.23 µs"),
        (5e-06, "5 µs"),
    ],
)
def test_eng_three_significant_digits(value, expected):
    assert br.eng(value, "s") == expected


def _zoom(**kw):
    base = {
        "window_s": 0.001,
        "window_source": "circuit",
        "period_source": "circuit",
        "period_element": "G0.Frequency",
        "period_reliable": True,
        "period_s": 2e-4,
        "print_interval_s": 5e-6,
        "samples_per_period": 40.0,
        "low_resolution": False,
    }
    base.update(kw)
    return base


def test_zoom_title_two_lines():
    from psim_mcp.services.batch_service import BatchService

    title = BatchService._zoom_title(_zoom(), reduced=False)
    assert title == (
        "last 5 switching periods (1 ms)\n"
        "T = 200 µs from circuit (G0.Frequency), 40 samples/period, full resolution"
    )
    title = BatchService._zoom_title(
        _zoom(window_s=0.249995, window_source="plot_window_s"), reduced=True
    )
    assert title == (
        "last 250 ms (plot_window_s)\n"
        "T = 200 µs from circuit (G0.Frequency), 40 samples/period, "
        "min/max envelope (too many points)"
    )


def _traces(n=3):
    xs = [i * 1e-3 for i in range(200)]
    return [
        {
            "label": f"#{i + 1} run {10 + i} (Lx=0.00418182)",
            "short_label": f"#{i + 1} run {10 + i}, Lx=4.18m",
            "bins": {
                "x": xs,
                "min": [4.5] * 200,
                "max": [5.5] * 200,
                "mean": [5.0] * 200,
            },
            "mean": 5.0,
            "zoom_x": [-1e-3 + k * 5e-6 for k in range(201)],
            "zoom_y": [5 + 0.5 * ((k // 20) % 2) for k in range(201)],
        }
        for i in range(n)
    ]


_LONG_ELEMENT = "PSM_F2837x_PHASEPWM_with_a_very_long_block_name.pwm_freq"


@pytest.mark.parametrize(
    "zoom,reduced,message",
    [
        # C5 실측 그대로(한 줄일 때 잘리던 제목)
        (_zoom(window_s=0.249995, window_source="plot_window_s"), True, None),
        # 가장 긴 주기 문구(FFT) + envelope
        (
            _zoom(
                window_s=0.249995,
                window_source="plot_window_s",
                period_source="fft",
                period_element=None,
            ),
            True,
            None,
        ),
        # 소자 이름이 아주 길어 두 줄로도 넘치는 경우 → 글꼴을 줄여 맞춘다
        (_zoom(period_element=_LONG_ELEMENT), True, None),
        # undersampled(위 칸 문구만)
        (
            _zoom(
                period_reliable=False,
                window_s=None,
                window_source=None,
                period_s=2e-4,
                print_interval_s=2.5e-4,
                samples_per_period=0.8,
            ),
            False,
            br.undersampled_message(0.8, 2.5e-4, 2e-4, multiline=True),
        ),
        # 저장 간격 < 주기(1.5점/주기)
        (
            _zoom(
                period_reliable=False,
                window_s=None,
                window_source=None,
                period_s=1.5e-6,
                print_interval_s=1e-6,
                samples_per_period=1.5,
            ),
            False,
            br.undersampled_message(1.5, 1e-6, 1.5e-6, multiline=True),
        ),
    ],
)
def test_waveform_titles_stay_inside_figure(zoom, reduced, message):
    from psim_mcp.services.batch_service import BatchService

    zoom_title = BatchService._zoom_title(zoom, reduced)
    fig = br.build_waveform_figure(
        _traces(),
        "I(L1)",
        "I(L1) waveforms (top 3 by I(L1).ripple), low resolution: 19.9 samples/period",
        zoom_title,
        br.bottom_title_text(0.0, 0.5, None if message else 0.249995),
        "Time (s)",
        message,
        None if message else (0.250005, 0.5),
        0.25,
        (0.0, 0.5),
    )
    ax_zoom, ax_env = fig.axes[:2]
    fig.canvas.draw()
    titles = [ax_zoom.title, ax_env.title, fig._suptitle]  # suptitle Text는 공개 getter 없음
    for t in titles:
        assert br.text_inside_figure(fig, t), (t.get_text(), t.get_window_extent())
        assert t.get_fontsize() >= br.TITLE_MIN_FONTSIZE
    assert ax_zoom.title.get_text() == zoom_title  # 내용은 그대로(잘라내지 않음)
    if message:
        # undersampled 문구가 줄인 위 칸 밖(범례 쪽)으로 나가지 않음, 내용 그대로
        text = next(t for t in ax_zoom.texts if t.get_gid() == "zoom_message")
        assert text.get_text() == message
        assert br.text_inside_axes(fig, text, ax_zoom), text.get_window_extent()
        assert text.get_fontsize() >= br.TITLE_MIN_FONTSIZE


def test_fit_titles_shrinks_only_when_needed():
    from psim_mcp.services.batch_service import BatchService

    fig = br.build_waveform_figure(
        _traces(), "I(L1)", "t", BatchService._zoom_title(_zoom(), False), "env", "Time (s)"
    )
    assert fig.axes[0].title.get_fontsize() == 9.5  # 짧은 제목은 원래 크기
    fig = br.build_waveform_figure(
        _traces(),
        "I(L1)",
        "t",
        BatchService._zoom_title(_zoom(period_element=_LONG_ELEMENT), True),
        "env",
        "Time (s)",
    )
    assert fig.axes[0].title.get_fontsize() < 9.5
