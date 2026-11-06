"""Pictures for the engineer, drawn by code as static SVG (DA-20 AC 4, design 9.3).

Nemotron reads text only: these figures are for the person reading the HTML,
while the agent reads the numbers they are drawn from. No plotting library: a few
hand-written SVG primitives keep the lane free of matplotlib and the output
byte-stable, so the same inputs always give the same file.

    dataset    bars of the QA checks that failed most, per source
    train      loss curves (train, val) and the last loss per action group
    stage1     an image grid: frame, question, the VLM's answer, the expected answer
    stage3     predicted against true action of one dimension, link to the replay video
    inference  RTC timeline: latency per chunk against tau_lat, delay steps, boundary jumps
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

W, H, PAD = 640, 260, 44
_COLORS = ("#2a6fdb", "#d9534f", "#2e9e5b", "#e08a00", "#7a4fd1", "#00838f", "#8d6e63")


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _svg(body: str, title: str, height: int = H) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" '
        f'width="{W}" height="{height}" font-family="sans-serif" font-size="11">'
        f'<title>{_e(title)}</title><rect width="{W}" height="{height}" fill="#fff"/>'
        f'<text x="{PAD}" y="16" font-size="13" font-weight="bold">{_e(title)}</text>'
        f"{body}</svg>\n"
    )


def _finite(values: Sequence[float]) -> list[float]:
    return [v for v in values if math.isfinite(v)]


def _scale(lo: float, hi: float, a: float, b: float) -> tuple[float, float]:
    if hi == lo:
        hi = lo + 1.0
    k = (b - a) / (hi - lo)
    return k, a - k * lo


def line_chart(
    series: Mapping[str, Sequence[tuple[float, float]]],
    title: str,
    *,
    hline: tuple[str, float] | None = None,
    log_y: bool = False,
) -> str:
    """Polylines of (x, y) per named series; non-finite points are drawn as red ticks."""
    points = [(x, y) for s in series.values() for x, y in s if math.isfinite(y)]
    if not points:
        return _svg(f'<text x="{PAD}" y="60">no finite values</text>', title)

    def ty(y: float) -> float:
        return math.log10(max(y, 1e-12)) if log_y else y

    xs = [x for x, _ in points]
    ys = [ty(y) for _, y in points] + ([ty(hline[1])] if hline else [])
    kx, bx = _scale(min(xs), max(xs), PAD, W - 12)
    ky, by = _scale(min(ys), max(ys), H - 30, 28)
    body = [
        f'<line x1="{PAD}" y1="{H - 30}" x2="{W - 12}" y2="{H - 30}" stroke="#888"/>',
        f'<line x1="{PAD}" y1="28" x2="{PAD}" y2="{H - 30}" stroke="#888"/>',
        f'<text x="4" y="32">{max(ys):.3g}</text><text x="4" y="{H - 30}">{min(ys):.3g}</text>',
        f'<text x="{PAD}" y="{H - 14}">{min(xs):g}</text>'
        f'<text x="{W - 60}" y="{H - 14}">{max(xs):g}</text>',
    ]
    for n, (name, s) in enumerate(series.items()):
        color = _COLORS[n % len(_COLORS)]
        pts = " ".join(f"{kx * x + bx:.1f},{ky * ty(y) + by:.1f}" for x, y in s if math.isfinite(y))
        body.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.5" points="{pts}"/>')
        for x, y in s:
            if not math.isfinite(y):
                px = kx * x + bx
                body.append(f'<line x1="{px:.1f}" y1="28" x2="{px:.1f}" y2="40" stroke="#d00"/>')
        body.append(
            f'<text x="{W - 150}" y="{30 + 13 * n}" fill="{color}">{_e(name)}</text>'
        )
    if hline:
        y = ky * ty(hline[1]) + by
        body.append(
            f'<line x1="{PAD}" y1="{y:.1f}" x2="{W - 12}" y2="{y:.1f}" stroke="#d00" '
            f'stroke-dasharray="4 3"/><text x="{PAD + 4}" y="{y - 3:.1f}" fill="#d00">'
            f"{_e(hline[0])}</text>"
        )
    return _svg("".join(body), title)


def bar_chart(bars: Mapping[str, float], title: str, *, unit: str = "") -> str:
    """Horizontal bars, largest first."""
    items = sorted(bars.items(), key=lambda kv: -kv[1])[:12]
    height = 40 + 20 * max(1, len(items))
    top = max((v for _, v in items), default=1.0) or 1.0
    body = []
    for n, (name, value) in enumerate(items):
        y = 30 + 20 * n
        width = (W - 260) * value / top
        body.append(
            f'<text x="{PAD}" y="{y + 12}">{_e(name)}</text>'
            f'<rect x="220" y="{y}" width="{width:.1f}" height="14" fill="{_COLORS[0]}"/>'
            f'<text x="{224 + width:.1f}" y="{y + 12}">{value:g}{_e(unit)}</text>'
        )
    return _svg("".join(body), title, height)


def dataset_figure(failed_by_source: Mapping[str, Mapping[str, int]]) -> str:
    bars = {
        f"{check} · {source}": float(count)
        for source, checks in failed_by_source.items()
        for check, count in checks.items()
    }
    return bar_chart(bars, "QA checks that failed most, by source", unit=" ep")


def train_figure(
    train: Sequence[tuple[float, float]], val: Sequence[tuple[float, float]]
) -> str:
    series = {"train loss": train}
    if val:
        series["val loss"] = val
    positive = all(y > 0 for s in series.values() for _, y in s if math.isfinite(y))
    return line_chart(series, "Loss by step", log_y=positive)


def rtc_figure(
    chunks: Sequence[int], latency_s: Sequence[float], delay_steps: Sequence[int],
    tau_lat_s: float,
) -> str:
    return line_chart(
        {
            "latency (s)": list(zip(map(float, chunks), latency_s, strict=True)),
            "delay steps / 50": [(float(c), d / 50.0) for c, d in zip(chunks, delay_steps,
                                                                       strict=True)],
        },
        "RTC timeline by chunk",
        hline=(f"tau_lat {tau_lat_s:g} s", tau_lat_s),
    )


def action_figure(
    predicted: Sequence[float], true: Sequence[float], dim_name: str, fps: float,
    replay_video: str | None = None,
) -> str:
    """Predicted against true action of one dimension; the replay video is linked, not drawn."""
    svg = line_chart(
        {
            "true": [(i / fps, v) for i, v in enumerate(true)],
            "predicted": [(i / fps, v) for i, v in enumerate(predicted)],
        },
        f"Action {dim_name}: predicted vs true (s)",
    )
    if replay_video:
        link = (
            f'<a href="{_e(replay_video)}"><text x="{W - 200}" y="{H - 4}" fill="#2a6fdb">'
            "replay video (MuJoCo)</text></a>"
        )
        svg = svg.replace("</svg>", link + "</svg>")
    return svg


@dataclass(frozen=True)
class P1Item:
    """One probe P1 question: the frame, what was asked, what the VLM said, the answer key."""

    frame: str  # path of the SIMPLE frame, relative to the report dir
    question_type: str
    question: str
    answer: str
    expected: str

    @property
    def correct(self) -> bool:
        return self.answer.strip().lower() == self.expected.strip().lower()


def stage1_grid(items: Sequence[P1Item], columns: int = 3) -> str:
    """HTML table of frames with the question and both answers; wrong answers in red."""
    cells = []
    for item in items:
        color = "#2e9e5b" if item.correct else "#d9534f"
        cells.append(
            f'<td style="vertical-align:top;padding:6px"><img src="{_e(item.frame)}" '
            f'width="200" alt="{_e(item.question_type)}"/><br/><b>{_e(item.question_type)}'
            f"</b>: {_e(item.question)}<br/>VLM: <span style=\"color:{color}\">"
            f"{_e(item.answer)}</span><br/>expected: {_e(item.expected)}</td>"
        )
    rows = [
        "<tr>" + "".join(cells[i : i + columns]) + "</tr>" for i in range(0, len(cells), columns)
    ]
    return '<table class="p1grid">' + "".join(rows) + "</table>"


def write(svg: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(svg, encoding="utf-8")
    return path
