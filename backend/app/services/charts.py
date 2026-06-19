"""Chart rendering for the PDF report (matplotlib, headless Agg backend).

Each helper returns PNG bytes that the PDF builder embeds. All functions fail
soft — returning ``None`` if charting is unavailable — so PDF generation never
breaks because of a chart.
"""

from __future__ import annotations

import io

from app.core.logging import get_logger

log = get_logger(__name__)

_BRAND = "#4f46e5"
_PALETTE = ["#4f46e5", "#6366f1", "#818cf8", "#a5b4fc", "#c7d2fe", "#3730a3", "#4338ca"]


def _setup():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#cbd5e1", "figure.dpi": 150})
    return plt


def _save(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", transparent=False)
    buf.seek(0)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return buf.getvalue()


def category_distribution_chart(items: list[dict]) -> bytes | None:
    """Horizontal bar chart of event counts per category."""
    if not items:
        return None
    try:
        plt = _setup()
        labels = [i["category"] for i in items][:10][::-1]
        values = [i["count"] for i in items][:10][::-1]
        fig, ax = plt.subplots(figsize=(6, 3.2))
        ax.barh(labels, values, color=_BRAND)
        ax.set_title("Coverage by Category", fontweight="bold", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        for i, v in enumerate(values):
            ax.text(v, i, f" {v}", va="center", fontsize=8)
        return _save(fig)
    except Exception as exc:  # noqa: BLE001
        log.warning("chart_failed", chart="category_distribution", error=str(exc))
        return None


def top_stories_chart(stories: list[dict]) -> bytes | None:
    """Horizontal bar chart of importance scores for the top stories."""
    if not stories:
        return None
    try:
        plt = _setup()
        top = stories[:10][::-1]
        labels = [
            (s["headline"][:42] + "…") if len(s["headline"]) > 42 else s["headline"]
            for s in top
        ]
        values = [s.get("score") or 0 for s in top]
        fig, ax = plt.subplots(figsize=(6, 3.6))
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(values))]
        ax.barh(labels, values, color=colors)
        ax.set_xlim(0, 100)
        ax.set_title("Top Stories by Importance Score", fontweight="bold", loc="left")
        ax.spines[["top", "right"]].set_visible(False)
        return _save(fig)
    except Exception as exc:  # noqa: BLE001
        log.warning("chart_failed", chart="top_stories", error=str(exc))
        return None
