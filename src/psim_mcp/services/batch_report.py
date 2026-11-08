"""run_batch 결과 요약(top)과 PNG 그림(2차 10번).

- :func:`build_top`: rank_by 순위 상위 k행 요약(run, 입력값, rank_by 값).
- :func:`render_metric_plot`: 그림 1 — 조건-지표 그래프.
- :func:`render_waveform_plot`: 그림 2 — 상위 run 파형 겹쳐 그리기.

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


def decimate(values: list[float], max_points: int = WAVEFORM_MAX_POINTS) -> list[float]:
    """간격을 두고 뽑아 max_points 이하로 줄인다."""
    n = len(values)
    if n <= max_points:
        return list(values)
    step = math.ceil(n / max_points)
    return list(values[::step])


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
    """그림 1. series = [(신호, 지표)] 1~2개. highlight = 순위 순서의 run 번호(상위 k)."""
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
        ax.set_ylabel(f"{signal}.{metric}", fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
    axes[-1].set_xlabel(x_key if x_key != "run" else "run", fontsize=9)
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
    return _to_png(fig)


def render_waveform_plot(traces: list[dict], signal: str, x_label: str, title: str) -> bytes:
    """그림 2. traces = [{"label", "x", "y"}] — 측정 구간 파형 겹쳐 그리기."""
    fig = _new_figure(4.6)
    ax = fig.subplots()
    # 1위가 맨 위에 보이도록 뒤에서부터 그리고, 범례는 순위 순서로 둔다.
    lines = {}
    for i in reversed(range(len(traces))):
        tr = traces[i]
        (lines[i],) = ax.plot(
            tr["x"],
            tr["y"],
            linewidth=1.4 if i == 0 else 0.9,
            alpha=0.9,
            color=_COLORS[i % len(_COLORS)],
            label=tr["label"],
        )
    ax.set_xlabel(x_label, fontsize=9)
    ax.set_ylabel(signal, fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.tick_params(labelsize=8)
    ordered = [lines[i] for i in range(len(traces))]
    ax.legend(ordered, [ln.get_label() for ln in ordered], fontsize=8, loc="best")
    fig.suptitle(title, fontsize=11)
    fig.tight_layout()
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
