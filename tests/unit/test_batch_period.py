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
            "env_x": [0.0, 1.0, 2.0],
            "env_y": [1.0, 2.0, 1.5],
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
    # 아래 칸 띠와 범례는 그대로
    assert any(c.get_gid() == "band0" for c in fig.axes[1].collections)
    assert ax_zoom.get_legend() is not None


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
    assert len(seen) == 6
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
    # 확대 구간 읽기·FFT 없음: envelope 3번만
    assert len(seen) == 3 and all("t_start" not in p for p in seen)
    traces, _, title, zoom_title, _, _, zoom_message = calls[0]
    assert "undersampled: 1.6 samples/period" in title
    assert zoom_message.startswith("undersampled: print interval 1 µs >= switching period 1.6 µs")
    assert "zoom not drawn" in zoom_title
    assert all(not tr.get("zoom_y") for tr in traces)
    assert all(tr["env_y"] for tr in traces)  # 아래 칸 envelope는 그린다
    notes = data["notes"]
    assert any("PRINTSTEP" in n and "그리지 않았습니다" in n for n in notes)
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
