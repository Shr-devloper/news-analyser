"""Professional executive PDF builder (fpdf2 — pure Python, no native deps).

Produces ``Daily_News_Brief_YYYY_MM_DD.pdf`` with:
  - branded cover page
  - auto-generated table of contents (with page numbers)
  - executive summary
  - top stories with charts
  - section breakdowns (Global / India / Tech & AI / Business & Markets)
  - emerging trends, tomorrow's watchlist
  - personalized actionable insights
  - source references

Works on Windows/macOS/Linux without GTK/Cairo (unlike WeasyPrint).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from app.core.config import settings
from app.core.logging import get_logger
from app.services import charts

if TYPE_CHECKING:
    from app.db.models import Report

log = get_logger(__name__)

INK = (17, 24, 39)
MUTED = (100, 116, 139)
BRAND = (79, 70, 229)
BRAND_LIGHT = (238, 242, 255)

_REPL = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
    "\u00a0": " ", "\u2122": "(TM)", "\u20b9": "Rs ", "\u2192": "->",
    "\u2705": "", "\u26a0": "", "\ufe0f": "",
}


def _san(text) -> str:
    """Make text safe for fpdf2 core (latin-1) fonts."""
    if text is None:
        return ""
    s = str(text)
    for k, v in _REPL.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "ignore").decode("latin-1")


class BriefPDF(FPDF):
    def __init__(self, title: str, date_str: str):
        super().__init__(format="A4")
        self.report_title = title
        self.date_str = date_str
        self.set_auto_page_break(True, margin=18)
        self.set_title(title)
        self.set_author("AI News Intelligence Agent")

    def footer(self):
        if self.page_no() == 1:  # no footer on the cover
            return
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(self.epw / 2, 10, _san(f"AI News Intelligence Agent  -  {self.date_str}"))
        self.cell(self.epw / 2, 10, f"Page {self.page_no()}", align="R")

    # -- building blocks --
    def h2(self, text: str):
        self.start_section(_san(text))
        if self.will_page_break(16):
            self.add_page()
        self.ln(2)
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*INK)
        self.set_fill_color(*BRAND_LIGHT)
        self.set_draw_color(*BRAND)
        self.multi_cell(0, 10, _san(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True,
                        border="L")
        self.ln(3)

    def body(self, text: str, size: int = 10, style: str = "", color=INK, h: float = 5.2):
        if not text:
            return
        self.set_font("Helvetica", style, size)
        self.set_text_color(*color)
        self.multi_cell(0, h, _san(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def label_value(self, label: str, value: str):
        if not value:
            return
        self.set_font("Helvetica", "BI", 9)
        self.set_text_color(*BRAND)
        self.multi_cell(0, 5, _san(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.body(value, size=9, color=(55, 65, 81))


def _cover(pdf: BriefPDF, report: "Report", recipient: str):
    pdf.add_page()
    pdf.set_fill_color(*BRAND)
    pdf.rect(0, 0, pdf.w, 90, style="F")
    pdf.set_y(28)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "AI NEWS INTELLIGENCE AGENT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 30)
    pdf.multi_cell(0, 12, "Daily News\nIntelligence Brief", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(110)
    pdf.set_font("Helvetica", "", 13)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, _san(pdf.date_str), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 7, _san(f"Prepared for: {recipient}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    stats = report.data.get("stats", {}) if report.data else {}
    pdf.cell(0, 7, _san(
        f"{stats.get('events', report.event_count)} events analyzed  -  "
        f"average importance {stats.get('avg_score', '-')}"
    ), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_y(-40)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5, _san(
        "Generated autonomously from 12 trusted sources using GroqCloud LLMs, "
        "LangGraph orchestration and embedding-based deduplication."
    ), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _render_toc(pdf: BriefPDF, outline):
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 14, "Table of Contents", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(55, 65, 81)
    for entry in outline:
        link = pdf.add_link()
        pdf.set_link(link, page=entry.page_number)
        indent = (entry.level or 0) * 6
        if indent:
            pdf.cell(indent, 8, "")
        pdf.cell(pdf.epw - indent - 16, 8, _san(entry.name), link=link)
        pdf.cell(16, 8, str(entry.page_number), align="R",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT, link=link)


def _image(pdf: BriefPDF, png: bytes | None):
    if not png:
        return
    try:
        if pdf.will_page_break(70):
            pdf.add_page()
        pdf.image(io.BytesIO(png), w=pdf.epw * 0.92)
        pdf.ln(3)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf_image_failed", error=str(exc))


def _render_story(pdf: BriefPDF, idx: int, s: dict):
    if pdf.will_page_break(30):
        pdf.add_page()
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 6, _san(f"{idx}. {s.get('headline', '')}"),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    meta = (
        f"{s.get('category', 'World')}  |  Importance {s.get('score', '-')}  |  "
        f"{s.get('publishers', 1)} publisher(s)"
    )
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*BRAND)
    pdf.multi_cell(0, 5, _san(meta), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.body(s.get("detailed") or s.get("two_line"), size=9, color=(55, 65, 81))
    if s.get("why_it_matters"):
        pdf.label_value("Why it matters", s["why_it_matters"])
    takeaways = s.get("key_takeaways") or []
    if takeaways:
        pdf.set_font("Helvetica", "BI", 9)
        pdf.set_text_color(*BRAND)
        pdf.multi_cell(0, 5, "Key takeaways", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(55, 65, 81)
        for t in takeaways[:5]:
            pdf.multi_cell(0, 5, _san(f"  - {t}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    sources = s.get("sources") or []
    if sources:
        names = ", ".join(src.get("name", "") for src in sources[:6])
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 4.5, _san(f"Sources: {names}"),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)


def build_brief_pdf(report: "Report", *, recipient_name: str | None = None) -> str:
    """Render the branded PDF and return its absolute path."""
    data = report.data or {}
    recipient = recipient_name or settings.BRIEF_RECIPIENT_NAME
    date_str = report.report_date.strftime("%A, %d %B %Y")

    pdf = BriefPDF(report.title, date_str)

    # 1) Cover
    _cover(pdf, report, recipient)

    # 2) TOC placeholder on its own page
    pdf.add_page()
    pdf.insert_toc_placeholder(_render_toc, pages=1)

    # 3) Executive summary
    pdf.h2("1. Executive Summary")
    pdf.body(data.get("executive_summary"), size=10, color=(31, 41, 55), h=5.6)
    pdf.ln(2)
    _image(pdf, charts.top_stories_chart(data.get("top_20") or []))
    _image(pdf, charts.category_distribution_chart(data.get("category_counts") or []))

    # 4) Top stories (top 20)
    top = data.get("top_20") or []
    if top:
        pdf.h2(f"2. Top {len(top)} Stories")
        for i, s in enumerate(top, 1):
            _render_story(pdf, i, s)

    # 5) Section breakdowns
    section_no = 3
    for title, items in (data.get("sections") or {}).items():
        if not items:
            continue
        pdf.h2(f"{section_no}. {title}")
        for i, s in enumerate(items, 1):
            _render_story(pdf, i, s)
        section_no += 1

    # 6) Emerging trends
    trends = data.get("trending_topics") or []
    if trends:
        pdf.h2(f"{section_no}. Emerging Trends")
        for t in trends:
            pdf.body(f"- {t.get('topic')} ({t.get('count')} stories)", size=10)
        section_no += 1

    # 7) Tomorrow's watchlist
    watch = data.get("tomorrow_watchlist") or []
    if watch:
        pdf.h2(f"{section_no}. What To Watch Tomorrow")
        for w in watch:
            pdf.body(f"- [{w.get('category')}] {w.get('headline')}", size=10)
        section_no += 1

    # 8) Personalized section
    personalized = data.get("personalized") or {}
    items = personalized.get("items") or []
    if items:
        pdf.h2(f"{section_no}. {personalized.get('title', 'Personalized Insights')}")
        for it in items:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*INK)
            pdf.multi_cell(0, 5.5, _san(f"- {it.get('headline', '')}"),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.label_value("Actionable insight", it.get("insight", ""))
            pdf.ln(1)
        section_no += 1

    # 9) Source references
    refs = data.get("source_references") or []
    if refs:
        pdf.h2(f"{section_no}. Source References")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(55, 65, 81)
        for i, r in enumerate(refs, 1):
            pdf.multi_cell(0, 4.6, _san(f"[{i}] {r.get('name', '')} - {r.get('url', '')}"),
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Save
    out_dir = Path(settings.REPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"Daily_News_Brief_{report.report_date.strftime('%Y_%m_%d')}.pdf"
    path = out_dir / filename
    pdf.output(str(path))

    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError("PDF generation produced an invalid file")

    log.info("brief_pdf_generated", path=str(path), size=path.stat().st_size)
    return str(path)
