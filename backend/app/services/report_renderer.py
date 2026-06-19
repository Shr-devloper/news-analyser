"""Render reports to HTML, Markdown and PDF.

HTML/email use Jinja2 templates. PDF uses WeasyPrint when its native libs are
available; otherwise PDF generation is skipped gracefully (HTML/MD still work).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.db.models import Report, User

log = get_logger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def _reports_dir() -> Path:
    path = Path(settings.REPORTS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_report_html(report: "Report") -> str:
    template = _env.get_template("report.html")
    return template.render(report=report, data=report.data or {})


def render_email_html(report: "Report", user: "User", personalized: list[dict]) -> str:
    template = _env.get_template("email.html")
    return template.render(
        report=report,
        data=report.data or {},
        user=user,
        personalized=personalized,
        dashboard_url=os.getenv("NEXT_PUBLIC_API_URL", "http://localhost:3000"),
    )


def render_markdown(report: "Report") -> str:
    data = report.data or {}
    lines: list[str] = [f"# {report.title}", "", "## Executive Summary", ""]
    lines.append(data.get("executive_summary", ""))
    lines.append("")

    for section, items in (data.get("sections") or {}).items():
        if not items:
            continue
        lines.append(f"## {section}")
        lines.append("")
        for i, item in enumerate(items, 1):
            score = f" _(score {item.get('score')})_" if item.get("score") else ""
            lines.append(f"{i}. **{item['headline']}**{score}")
            if item.get("two_line"):
                lines.append(f"   - {item['two_line']}")
            if item.get("url"):
                lines.append(f"   - [Read more]({item['url']})")
        lines.append("")

    if data.get("market_summary"):
        lines.append("## Market Summary")
        lines.append("")
        for item in data["market_summary"]:
            lines.append(f"- **{item['headline']}** ({item.get('category')})")
        lines.append("")

    if data.get("trending_topics"):
        lines.append("## Trending Topics")
        lines.append("")
        lines.append(", ".join(f"{t['topic']} ({t['count']})" for t in data["trending_topics"]))
        lines.append("")

    if data.get("tomorrow_watchlist"):
        lines.append("## Tomorrow's Watchlist")
        lines.append("")
        for item in data["tomorrow_watchlist"]:
            lines.append(f"- {item['headline']} ({item.get('category')})")
        lines.append("")

    return "\n".join(lines)


def _write_pdf(html: str, path: Path) -> bool:
    try:
        from weasyprint import HTML  # imported lazily; heavy native deps

        HTML(string=html).write_pdf(str(path))
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf_generation_skipped", error=str(exc))
        return False


def render_report_files(report: "Report") -> dict[str, str | None]:
    """Render and persist HTML/MD/PDF to disk. Returns relative paths."""
    out = _reports_dir()
    stamp = report.report_date.strftime("%Y%m%d")
    base = f"{report.kind}_{stamp}_{report.id}"

    html = render_report_html(report)
    html_path = out / f"{base}.html"
    html_path.write_text(html, encoding="utf-8")

    md = render_markdown(report)
    md_path = out / f"{base}.md"
    md_path.write_text(md, encoding="utf-8")

    pdf_path = out / f"{base}.pdf"
    pdf_ok = _write_pdf(html, pdf_path)

    return {
        "html": str(html_path),
        "markdown": str(md_path),
        "pdf": str(pdf_path) if pdf_ok else None,
    }
