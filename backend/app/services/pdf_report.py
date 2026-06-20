"""Professional executive PDF builder (fpdf2 — pure Python, no native deps).

Produces a fresh, compact **6-7 page** intelligence brief every run:

  Page 1  Masthead + run metadata + Executive Summary + importance chart
  Page 2  World News
  Page 3  India News
  Page 4  Technology & AI
  Page 5  Business & Markets
  Page 6  Personalized Insights (Opportunities / Risks / Emerging / Watch)
  Page 7  Tomorrow's Watchlist (optional)

Content per section is capped so the document stays within 7 pages.
Works on Windows/macOS/Linux without GTK/Cairo (unlike WeasyPrint).
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

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

SECTION_LIMIT = 5  # stories per section page (keeps each section to ~1 page)

_REPL = {
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u2022": "-",
    "\u00a0": " ", "\u2122": "(TM)", "\u20b9": "Rs ", "\u2192": "->",
}


def _san(text) -> str:
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
        self.set_auto_page_break(True, margin=16)
        self.set_title(title)
        self.set_author("AI News Intelligence Agent")

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(self.epw / 2, 8, _san(f"AI News Intelligence Agent  -  {self.date_str}"))
        self.cell(self.epw / 2, 8, f"Page {self.page_no()}", align="R")

    def h2(self, text: str):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*INK)
        self.set_fill_color(*BRAND_LIGHT)
        self.multi_cell(0, 9, _san(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True, border="L")
        self.ln(2)

    def body(self, text: str, size: int = 9, style: str = "", color=INK, h: float = 4.8):
        if not text:
            return
        self.set_font("Helvetica", style, size)
        self.set_text_color(*color)
        self.multi_cell(0, h, _san(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def bullets(self, label: str, items: list[str], color=INK):
        if not items:
            return
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BRAND)
        self.multi_cell(0, 5.5, _san(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*color)
        for it in items[:4]:
            self.multi_cell(0, 4.6, _san(f"  - {it}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)


def _masthead(pdf: BriefPDF, report: "Report", data: dict, tz: str):
    pdf.set_fill_color(*BRAND)
    pdf.rect(0, 0, pdf.w, 34, style="F")
    pdf.set_y(8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 8, _san(report.title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, "AI-Generated Daily Intelligence Briefing", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    # Metadata block
    meta = data.get("metadata", {})
    try:
        generated = report.report_date.astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:  # noqa: BLE001
        generated = report.report_date.strftime("%Y-%m-%d %H:%M UTC")
    sources = ", ".join(meta.get("sources_used", [])[:10]) or "-"
    pdf.set_text_color(*MUTED)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.multi_cell(0, 4.6, _san(
        f"Generated: {generated}    |    Report ID: {report.report_uid or report.id}\n"
        f"Articles Processed: {meta.get('articles_processed', report.articles_processed)}    |    "
        f"Sources: {sources}"
    ), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)


def _image(pdf: BriefPDF, png: bytes | None, w_frac: float = 0.9):
    if not png:
        return
    try:
        pdf.image(io.BytesIO(png), w=pdf.epw * w_frac)
        pdf.ln(2)
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf_image_failed", error=str(exc))


def _compact_story(pdf: BriefPDF, idx: int, s: dict):
    pdf.set_font("Helvetica", "B", 10.5)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 5.2, _san(f"{idx}. {s.get('headline', '')}"),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    meta = f"{s.get('category', 'World')}  |  Importance {s.get('score', '-')}  |  {s.get('publishers', 1)} publisher(s)"
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(*BRAND)
    pdf.multi_cell(0, 4.2, _san(meta), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.body(s.get("two_line") or s.get("detailed"), size=9, color=(55, 65, 81))
    if s.get("why_it_matters"):
        pdf.set_font("Helvetica", "BI", 8.5)
        pdf.set_text_color(*BRAND)
        pdf.multi_cell(0, 4.4, "Why it matters:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.body(s["why_it_matters"], size=8.5, color=(71, 85, 105), h=4.3)
    sources = s.get("sources") or []
    if sources:
        names = ", ".join(src.get("name", "") for src in sources[:6])
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 4, _san(f"Sources: {names}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2.5)


def _section_page(pdf: BriefPDF, title: str, stories: list[dict]):
    pdf.add_page()
    pdf.h2(title)
    if not stories:
        pdf.body("No significant stories in this category over the last 24 hours.",
                 style="I", color=MUTED)
        return
    for i, s in enumerate(stories[:SECTION_LIMIT], 1):
        _compact_story(pdf, i, s)


def _personalized_page(pdf: BriefPDF, personalized: dict):
    pdf.add_page()
    pdf.h2(personalized.get("title", "Personalized Insights"))
    for it in (personalized.get("items") or [])[:5]:
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 4.8, _san(f"- {it.get('headline', '')}"),
                       new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.body(it.get("insight"), size=8.8, color=(55, 65, 81), h=4.3)
        pdf.ln(0.6)
    pdf.ln(1)
    pdf.bullets("Opportunities", personalized.get("opportunities") or [])
    pdf.bullets("Risks", personalized.get("risks") or [])
    pdf.bullets("Emerging Trends", personalized.get("emerging") or [])
    pdf.bullets("Key Things To Watch", personalized.get("watch") or [])


def build_brief_pdf(report: "Report", *, recipient_name: str | None = None, tz: str | None = None) -> str:
    data = report.data or {}
    tz = tz or settings.REPORT_TIMEZONE
    date_str = report.report_date.strftime("%A, %d %B %Y")
    pdf = BriefPDF(report.title, date_str)

    # ---- Page 1: masthead + executive summary ----
    pdf.add_page()
    _masthead(pdf, report, data, tz)
    pdf.h2("Executive Summary")
    if recipient_name:
        pdf.body(f"Prepared for {recipient_name}.", style="I", color=MUTED, size=9)
    pdf.body(data.get("executive_summary"), size=9.5, color=(31, 41, 55), h=5.0)
    pdf.ln(1)
    _image(pdf, charts.top_stories_chart(data.get("top_25") or []), w_frac=0.82)

    # ---- Pages 2-5: fixed sections ----
    sections = data.get("sections") or {}
    for title in ("World News", "India News", "Technology & AI", "Business & Markets"):
        _section_page(pdf, title, sections.get(title) or [])

    # ---- Page 6: personalized ----
    if data.get("personalized"):
        _personalized_page(pdf, data["personalized"])

    # ---- Page 7 (optional): tomorrow watchlist ----
    watch = data.get("tomorrow_watchlist") or []
    if watch and pdf.page_no() < 7:
        pdf.add_page()
        pdf.h2("Tomorrow's Watchlist")
        for w in watch:
            pdf.body(f"- [{w.get('category')}] {w.get('headline')}", size=9.5)

    # ---- Save (unique per report; never overwrites prior runs) ----
    out_dir = Path(settings.REPORTS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"Daily_News_Brief_{report.report_date.strftime('%Y_%m_%d')}_{report.id}.pdf"
    path = out_dir / filename
    pdf.output(str(path))

    if not path.exists() or path.stat().st_size < 1000:
        raise RuntimeError("PDF generation produced an invalid file")
    if pdf.page_no() > 7:
        log.warning("pdf_exceeded_page_cap", pages=pdf.page_no())

    log.info("brief_pdf_generated", path=str(path), pages=pdf.page_no(), size=path.stat().st_size)
    return str(path)
