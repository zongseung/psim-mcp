"""run_batch 결과 요약(top)과 PNG 그림(2차 10번).

- :func:`build_top`: rank_by 순위 상위 k행 요약(run, 입력값, rank_by 값).
- :func:`render_metric_plot`: 그림 1 — 조건-지표 그래프.
- :func:`render_waveform_plot`: 그림 2 — 상위 run 파형 두 칸(위: 마지막 몇 주기 원본 해상도 확대,
  아래: 측정 구간 전체 min/max envelope).
- :func:`estimate_period`: 측정 구간 신호의 FFT 최대 성분으로 스위칭 주기 추정.

그림은 MCP 서버(Python 3.12) 쪽에서 matplotlib **Figure 객체 API + Agg 캔버스**로 그린다
(pyplot 전역 상태를 쓰지 않음 — 서버 안에서 동시에 불려도 서로 섞이지 않는다).
한글 글꼴이 없을 수 있으므로 그림 안 글자는 모두 영어다. PNG는 Pillow 팔레트 양자화로
장당 :data:`IMAGE_MAX_BYTES` 이하로 줄인다.
"""

from __future__ import annotations

import io
import math
import re
from typing import Any, Iterable

from psim_mcp.services.storage_policy import RankSpec

DEFAULT_MAX_IMAGES = 2
MAX_IMAGES_LIMIT = 4
IMAGE_MAX_BYTES = 150_000
WAVEFORM_MAX_POINTS = 2000
# 그림 2 위 칸(확대): 마지막 ZOOM_PERIODS 주기를 원본 해상도로. 주기 추정은 측정 구간 끝
# 최대 FFT_MAX_POINTS점(원본 해상도)으로 한다. 확대 구간 점이 ZOOM_MAX_POINTS를 넘으면
# (plot_window_s를 크게 준 경우) 그때만 envelope로 줄인다.
ZOOM_PERIODS = 5
FFT_MAX_POINTS = 32768
ZOOM_MAX_POINTS = 40000
FALLBACK_WINDOW_FRACTION = 0.01  # 주기 추정 실패 시 측정 구간 마지막 1%
LOW_RESOLUTION_SAMPLES = 20  # 주기당 샘플 수가 이보다 적으면 저해상도 경고
ENVELOPE_ALPHA = 0.3
_BAND_GROUPS = 500  # 아래 칸 띠: envelope 점을 이만큼 묶어 위·아래 경계를 만든다
FIG_WIDTH_IN = 9.0  # dpi 100 → 가로 900 px
FIG_DPI = 100
_COLORS = ("#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b")
_SI = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "µ": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "M": 1e6,
    "g": 1e9,
    "G": 1e9,
}
_NUM_RE = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*([A-Za-zµ]*)\s*$")


class ReportInputError(ValueError):
    def __init__(self, code: str, message: str, suggestion: str | None = None):
        super().__init__(message)
        self.code = code
        self.suggestion = suggestion


def validate_max_images(value: Any) -> int:
    """max_images는 1~4 정수. 틀리면 INVALID_INPUT."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportInputError(
            "INVALID_INPUT",
            f"max_images는 1~{MAX_IMAGES_LIMIT} 사이 정수여야 합니다(받은 값: {value!r}).",
            f"예: max_images={DEFAULT_MAX_IMAGES}",
        )
    if not 1 <= value <= MAX_IMAGES_LIMIT:
        raise ReportInputError(
            "INVALID_INPUT",
            f"max_images는 1~{MAX_IMAGES_LIMIT} 사이여야 합니다(받은 값: {value}).",
            f"예: max_images={DEFAULT_MAX_IMAGES}",
        )
    return value


def validate_plot_window_s(value: Any) -> float | None:
    """plot_window_s는 생략(None) 또는 0보다 큰 유한한 숫자(초). 틀리면 INVALID_INPUT."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        bad = True
    else:
        bad = not math.isfinite(float(value)) or float(value) <= 0
    if bad:
        raise ReportInputError(
            "INVALID_INPUT",
            f"plot_window_s는 0보다 큰 숫자(초)여야 합니다(받은 값: {value!r}).",
            "예: plot_window_s=0.001 (마지막 1 ms 확대). 생략하면 스위칭 주기 5개를 자동으로 잡습니다.",
        )
    return float(value)


def signal_unit(signal: str) -> str | None:
    """신호 이름으로 단위 추정: ``I(…)`` → A, ``V(…)`` → V, 그 밖은 모름(None)."""
    if signal.startswith("I("):
        return "A"
    if signal.startswith("V("):
        return "V"
    return None


def with_unit(label: str, signal: str) -> str:
    unit = signal_unit(signal)
    return f"{label} [{unit}]" if unit else label


def estimate_period(
    values: list[float],
    times: list[float] | None,
    min_cycles: int = 3,
    min_peak_fraction: float = 0.01,
) -> dict | None:
    """평균을 뺀 신호의 FFT 최대 성분으로 주기를 추정한다. 실패하면 None.

    반환: ``{"period_s", "dt_s", "samples_per_period"}``. 실패 조건: 점이 64개 미만, 시간 축이
    없거나 간격이 0 이하, 신호가 사실상 일정, 최대 성분이 구간 안 ``min_cycles``주기 미만(너무
    느림)이거나 나이퀴스트 끝, 최대 성분의 전력 비율이 ``min_peak_fraction`` 미만(잡음).
    """
    import numpy as np

    n = len(values)
    if n < 64 or times is None or len(times) != n:
        return None
    t = np.asarray(times, dtype=float)
    dt = float(np.median(np.diff(t)))
    if not math.isfinite(dt) or dt <= 0:
        return None
    x = np.asarray(values, dtype=float)
    x = x - x.mean()
    if not np.isfinite(x).all() or float(np.ptp(x)) <= 1e-12 * max(
        1.0, float(np.abs(values).max())
    ):
        return None
    spec = np.abs(np.fft.rfft(x * np.hanning(n)))
    spec[0] = 0.0
    k = int(np.argmax(spec))
    if k < min_cycles or k >= len(spec) - 1:
        return None
    power = spec**2
    if power[k] / power.sum() < min_peak_fraction:
        return None
    # 이웃 두 칸으로 2차 보간해 칸 사이 주파수를 맞춘다.
    a, b, c = spec[k - 1], spec[k], spec[k + 1]
    denom = a - 2 * b + c
    delta = 0.5 * (a - c) / denom if denom != 0 else 0.0
    freq = float((k + delta) / (n * dt))
    if not freq > 0:
        return None
    period = 1.0 / freq
    # 응답 JSON에 들어가므로 numpy 스칼라가 아닌 Python float로 돌려준다.
    return {
        "period_s": period,
        "dt_s": dt,
        "samples_per_period": round(period / dt, 1),
    }


def parse_number(value: Any) -> float | None:
    """숫자 또는 ``"2m"``·``"220u"`` 같은 SI 접미사 문자열을 float로. 안 되면 None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if not isinstance(value, str):
        return None
    m = _NUM_RE.match(value)
    if not m:
        return None
    number, suffix = float(m.group(1)), m.group(2)
    if not suffix:
        return number
    for key in (suffix, suffix.lower(), suffix[:3].lower(), suffix[:1]):
        if key in _SI:
            return number * _SI[key]
    return None


def metric_value(record: dict, signal: str, metric: str) -> float | None:
    value = ((record.get("summary") or {}).get(signal) or {}).get(metric)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _ok(records: Iterable[dict]) -> list[dict]:
    return [r for r in records if r.get("executed") and r.get("ok")]


def build_top(records: list[dict], rank: RankSpec, top_k: int) -> list[dict]:
    """순위 상위 top_k행: run, rank, inputs, rank_by 값, 파형 보존 여부."""
    ranked = sorted((r for r in records if r.get("rank")), key=lambda r: r["rank"])
    top = []
    for r in ranked[:top_k]:
        value = metric_value(r, rank.signal, rank.metric)
        top.append(
            {
                "rank": r["rank"],
                "run": r["run"],
                "inputs": r["inputs"],
                rank.column: float(f"{value:.6g}") if value is not None else None,
                "smv_kept": bool(r.get("smv_kept")),
            }
        )
    return top


def choose_x_axis(records: list[dict]) -> tuple[str, dict[int, float]]:
    """입력 하나만 바뀌고 모두 숫자면 그 입력을 x축으로, 아니면 run 번호."""
    ok = _ok(records)
    keys: list[str] = []
    for r in ok:
        for k in r["inputs"]:
            if k not in keys:
                keys.append(k)
    varying = []
    for k in keys:
        values = [r["inputs"].get(k) for r in ok]
        if len({repr(v) for v in values}) > 1:
            varying.append(k)
    if len(varying) == 1:
        key = varying[0]
        xs = {r["run"]: parse_number(r["inputs"].get(key)) for r in ok}
        if all(v is not None for v in xs.values()):
            return key, xs  # type: ignore[return-value]
    return "run", {r["run"]: float(r["run"]) for r in ok}


def minmax_envelope_indices(
    values: list[float], max_points: int = WAVEFORM_MAX_POINTS
) -> list[int]:
    """min/max envelope로 줄일 인덱스(시간 순서).

    점 수가 max_points 이하면 전부. 넘으면 약 max_points/2개 구간으로 나눠 구간마다
    최솟값·최댓값 위치를 시간 순서대로 넣는다. 측정 구간에 스위칭 주기가 수만 개 있어도
    전체 최대·최소(peak-to-peak)가 보존돼, 그린 띠 두께가 실제 리플과 같다(등간격 추출은
    에일리어싱으로 리플 크기를 틀리게 보여 준다).
    브리지 ``bridge_script._minmax_envelope_indices``와 같은 알고리즘.
    """
    n = len(values)
    if n <= max_points:
        return list(range(n))
    buckets = max(1, max_points // 2)
    out: list[int] = []
    for k in range(buckets):
        lo, hi = k * n // buckets, (k + 1) * n // buckets
        if hi <= lo:
            continue
        imin = imax = lo
        vmin = vmax = values[lo]
        for i in range(lo + 1, hi):
            v = values[i]
            if v < vmin:
                vmin, imin = v, i
            elif v > vmax:
                vmax, imax = v, i
        if imin == imax:
            out.append(imin)
        else:
            out.extend(sorted((imin, imax)))
    return out


def minmax_envelope(
    values: list[float], times: list[float] | None = None, max_points: int = WAVEFORM_MAX_POINTS
) -> tuple[list[float], list[float] | None, bool]:
    """(줄인 값, 같은 위치의 시간 또는 None, 줄였는지)."""
    idx = minmax_envelope_indices(values, max_points)
    reduced = len(idx) < len(values)
    t = [times[i] for i in idx] if times is not None and len(times) == len(values) else None
    return [values[i] for i in idx], t, reduced


# ---------------------------------------------------------------------------
# 그리기
# ---------------------------------------------------------------------------


def _new_figure(height_in: float):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=(FIG_WIDTH_IN, height_in), dpi=FIG_DPI)
    FigureCanvasAgg(fig)
    return fig


def _to_png(fig, max_bytes: int = IMAGE_MAX_BYTES) -> bytes:
    """Figure → 팔레트 PNG. 색 수를 줄여 가며 max_bytes 이하로 맞춘다."""
    from PIL import Image

    raw = io.BytesIO()
    fig.savefig(raw, format="png", dpi=FIG_DPI)
    raw.seek(0)
    rgb = Image.open(raw).convert("RGB")
    best = b""
    for scale in (1.0, 0.8, 0.6):
        img = rgb
        if scale != 1.0:
            img = rgb.resize((int(rgb.width * scale), int(rgb.height * scale)), Image.LANCZOS)
        for colors in (64, 32, 16):
            out = io.BytesIO()
            # FASTOCTREE + 디더링 없음: 선 색(파랑·빨강·초록)이 회색으로 뭉개지지 않는다.
            img.quantize(
                colors=colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE
            ).save(out, format="PNG", optimize=True)
            best = out.getvalue()
            if len(best) <= max_bytes:
                return best
    return best


def _fmt(value: float) -> str:
    return f"{value:.4g}"


def render_metric_plot(
    records: list[dict],
    series: list[tuple[str, str]],
    x_key: str,
    xs: dict[int, float],
    highlight: list[int],
    title: str,
) -> bytes:
    """그림 1 PNG. 인자는 :func:`build_metric_figure`와 같다."""
    return _to_png(build_metric_figure(records, series, x_key, xs, highlight, title))


def build_metric_figure(
    records: list[dict],
    series: list[tuple[str, str]],
    x_key: str,
    xs: dict[int, float],
    highlight: list[int],
    title: str,
):
    """그림 1 Figure. series = [(신호, 지표)] 1~2개. highlight = 순위 순서의 run 번호(상위 k)."""
    ok = [r for r in _ok(records) if r["run"] in xs]
    fig = _new_figure(2.6 + 2.0 * len(series))
    axes = fig.subplots(len(series), 1, sharex=True, squeeze=False)[:, 0]
    for i, (ax, (signal, metric)) in enumerate(zip(axes, series)):
        pts = sorted(
            (xs[r["run"]], v, r["run"])
            for r in ok
            if (v := metric_value(r, signal, metric)) is not None
        )
        if pts:
            ax.plot(
                [p[0] for p in pts],
                [p[1] for p in pts],
                marker="o",
                markersize=4,
                linewidth=1.2,
                color=_COLORS[i % len(_COLORS)],
            )
        by_run = {p[2]: p for p in pts}
        for rank_no, run in enumerate(highlight, start=1):
            if run in by_run:
                x, y, _ = by_run[run]
                ax.plot(x, y, marker="o", markersize=10, mfc="none", mec="#d62728", mew=1.6)
                ax.annotate(
                    f"#{rank_no} (run {run})",
                    (x, y),
                    textcoords="offset points",
                    # 이웃한 상위 점의 글자가 겹치지 않게 순위마다 높이를 다르게
                    xytext=(6, 6 + 11 * (rank_no - 1)),
                    fontsize=8,
                    color="#d62728",
                )
        ax.set_ylabel(with_unit(f"{signal}.{metric}", signal), fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
    axes[-1].set_xlabel(x_key if x_key != "run" else "run", fontsize=9)
    if x_key != "run":
        from matplotlib.ticker import EngFormatter

        # 입력 축은 공학 표기(1m, 4.5m). 입력 단위는 모르므로 붙이지 않는다.
        axes[-1].xaxis.set_major_formatter(EngFormatter(sep=""))
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


def trace_color(i: int) -> str:
    """그림 2에서 i번째(순위 순서) run의 색. 띠·선·범례가 모두 이 값을 쓴다."""
    return _COLORS[i % len(_COLORS)]


def eng(value: float, unit: str = "", places: int | None = None) -> str:
    """제목용 공학 표기: ``eng(0.0002, "s")`` → ``"200 µs"``."""
    from matplotlib.ticker import EngFormatter

    return EngFormatter(unit=unit, places=places).format_eng(value)  # 단위까지 붙여 준다


def envelope_band(x: list[float], y: list[float], groups: int = _BAND_GROUPS):
    """envelope 점을 ``groups``개 묶음으로 나눠 (중앙 시각, 최솟값, 최댓값) 목록을 만든다.

    묶음마다 최소·최대를 쓰므로 전체 최대·최소(띠 두께 = peak-to-peak)는 그대로다.
    """
    n = min(len(x), len(y))
    if n == 0:
        return [], [], []
    groups = max(1, min(groups, n))
    xs, lo, hi = [], [], []
    for k in range(groups):
        a, b = k * n // groups, (k + 1) * n // groups
        if b <= a:
            continue
        seg = y[a:b]
        xs.append((x[a] + x[b - 1]) / 2.0)
        lo.append(min(seg))
        hi.append(max(seg))
    return xs, lo, hi


def build_waveform_figure(
    traces: list[dict],
    signal: str,
    title: str,
    zoom_title: str,
    envelope_title: str,
    envelope_x_label: str = "Time (s)",
):
    """그림 2 Figure(두 칸). 테스트에서 범례·선·띠 색을 확인할 수 있게 PNG 변환과 분리했다.

    traces(순위 순서) 항목: ``label``, ``env_x``·``env_y``(측정 구간 envelope), 선택 ``zoom_x``·
    ``zoom_y``(확대 구간 원본, x는 run 끝 기준 상대 시간 초), ``mean``(점선, 없으면 생략).
    """
    from matplotlib.patches import Patch
    from matplotlib.ticker import EngFormatter

    fig = _new_figure(6.6)
    ax_zoom, ax_env = fig.subplots(2, 1, gridspec_kw={"height_ratios": [3, 2]})
    ylabel = with_unit(signal, signal)
    handles = []
    # 1위가 맨 위에 보이도록 뒤에서부터 그린다. 범례는 순위 순서.
    for i in reversed(range(len(traces))):
        tr = traces[i]
        color = trace_color(i)
        zx, zy = tr.get("zoom_x") or [], tr.get("zoom_y") or []
        if zx and zy:
            ax_zoom.plot(zx, zy, color=color, linewidth=1.6 if i == 0 else 1.1, gid=f"zoom{i}")
        if tr.get("mean") is not None:
            ax_zoom.axhline(tr["mean"], color=color, linestyle=":", linewidth=1.0, gid=f"mean{i}")
        bx, blo, bhi = envelope_band(tr.get("env_x") or [], tr.get("env_y") or [])
        if bx:
            ax_env.fill_between(
                bx, blo, bhi, color=color, alpha=ENVELOPE_ALPHA, linewidth=0, gid=f"band{i}"
            )
            ax_env.plot(bx, bhi, color=color, linewidth=1.2, gid=f"edge_hi{i}")
            ax_env.plot(bx, blo, color=color, linewidth=1.2, gid=f"edge_lo{i}")
    for i, tr in enumerate(traces):
        handles.append(Patch(facecolor=trace_color(i), edgecolor=trace_color(i), label=tr["label"]))

    ax_zoom.set_title(zoom_title, fontsize=9)
    ax_zoom.set_xlabel("time before end of run", fontsize=9)
    ax_zoom.xaxis.set_major_formatter(EngFormatter(unit="s"))
    ax_zoom.set_ylabel(ylabel, fontsize=9)
    ax_env.set_title(envelope_title, fontsize=9)
    ax_env.set_xlabel(envelope_x_label, fontsize=9)
    ax_env.set_ylabel(ylabel, fontsize=9)
    for ax in (ax_zoom, ax_env):
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
    legend = ax_zoom.legend(
        handles=handles,
        fontsize=8,
        loc="upper left",
        bbox_to_anchor=(1.01, 1.0),
        borderaxespad=0.0,
        title="dotted: mean",
    )
    legend.get_title().set_fontsize(8)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return fig


def render_waveform_plot(
    traces: list[dict],
    signal: str,
    title: str,
    zoom_title: str,
    envelope_title: str,
    envelope_x_label: str = "Time (s)",
) -> bytes:
    """그림 2 PNG. 인자는 :func:`build_waveform_figure`와 같다."""
    fig = build_waveform_figure(traces, signal, title, zoom_title, envelope_title, envelope_x_label)
    return _to_png(fig)


def describe_inputs(inputs: dict, limit: int = 2) -> str:
    """범례용 짧은 입력 표기(영문·숫자만): ``Lx=0.005``."""
    parts = []
    for k, v in list(inputs.items())[:limit]:
        num = parse_number(v)
        parts.append(f"{k}={_fmt(num) if num is not None else v}")
    if len(inputs) > limit:
        parts.append("...")
    return ", ".join(parts)
