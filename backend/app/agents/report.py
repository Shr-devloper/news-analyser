"""Agent 7 — Report Generation Agent.

Assembles the executive report payload (top-20 + sections + trends + watchlist +
personalized actionable insights + source references), persists a ``Report`` row,
and renders HTML / Markdown plus the branded executive PDF.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.briefing import build_personalized
from app.ai.groq_client import complete_text
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DeduplicatedEvent, Ranking, Report, Summary
from app.services.pdf_report import build_brief_pdf
from app.services.report_renderer import render_report_files

log = get_logger(__name__)

# Section name -> set of categories that feed it (per the brief spec).
SECTION_MAP = {
    "Top Global News": {"World"},
    "India News": {"India"},
    "Technology & AI": {"Technology", "AI", "Cybersecurity", "Science"},
    "Business & Markets": {"Business", "Finance", "Markets", "Startups"},
}


def _event_sources(event: DeduplicatedEvent) -> list[dict]:
    seen: dict[str, str] = {}
    for art in event.articles:
        name = art.source.name if art.source else "Unknown"
        if name not in seen:
            seen[name] = art.url
    return [{"name": n, "url": u} for n, u in seen.items()]


def _serialize(event: DeduplicatedEvent) -> dict:
    s: Summary | None = event.summary
    r: Ranking | None = event.ranking
    primary = next((c.category for c in event.categories if c.is_primary), None)
    return {
        "id": event.id,
        "headline": s.headline if s else event.canonical_title,
        "two_line": s.two_line if s else None,
        "detailed": s.detailed if s else None,
        "why_it_matters": s.why_it_matters if s else None,
        "key_takeaways": s.key_takeaways if s else [],
        "future_impact": s.future_impact if s else None,
        "url": event.canonical_url,
        "category": primary or (event.categories[0].category if event.categories else "World"),
        "score": r.score if r else None,
        "publishers": event.publisher_count,
        "sources": _event_sources(event),
    }


def _section(events: list[DeduplicatedEvent], cats: set[str], n: int) -> list[dict]:
    filtered = [e for e in events if any(c.category in cats for c in e.categories)]
    filtered.sort(key=lambda e: (e.ranking.score if e.ranking else 0), reverse=True)
    return [_serialize(e) for e in filtered[:n]]


def _trending(events: list[DeduplicatedEvent], n: int = 8) -> list[dict]:
    counter: Counter[str] = Counter()
    for e in events:
        for c in e.categories:
            counter[c.category] += 1
    return [{"topic": topic, "count": count} for topic, count in counter.most_common(n)]


def _executive_summary(top: list[dict]) -> str:
    headlines = "\n".join(f"- {t['headline']}" for t in top[:10])
    text = complete_text(
        system=(
            "You are an executive editor. Write a concise one-paragraph (5-7 sentence) "
            "executive summary of the most important news in the last 24 hours."
        ),
        user=f"Top stories:\n{headlines}",
        temperature=0.3,
        max_tokens=450,
    )
    if text:
        return text.strip()
    return (
        f"This brief covers the {len(top)} most significant developments of the last 24 hours "
        "across global affairs, India, technology & AI, and business & markets, ranked by "
        "cross-publisher coverage and estimated impact. The leading stories and their "
        "implications are detailed in the sections that follow."
    )


def _fallback_insight(item: dict) -> str:
    return (
        f"Relevant to your focus on {item.get('interest', 'your interests')}. "
        "Skim the source, note any tools/companies mentioned, and consider how it affects "
        "what you're currently learning or building."
    )


def _personalized_section(db: Session) -> dict:
    interests = settings.BRIEF_INTERESTS
    if isinstance(interests, str):
        interests = [i.strip() for i in interests.split(",") if i.strip()]
    items = build_personalized(db, interests, top_k=8)
    out = []
    for it in items:
        insight = complete_text(
            system=(
                "You are a sharp technical mentor for a software engineer focused on AI, DSA, "
                "programming, startups, career growth and productivity. Given a news item, give "
                "ONE concrete, actionable insight (1-2 sentences) — what to do, learn, build, or "
                "watch. Avoid generic restatement."
            ),
            user=f"{it['headline']}\n{it.get('two_line') or ''}",
            temperature=0.4,
            max_tokens=160,
        )
        out.append(
            {
                "headline": it["headline"],
                "insight": (insight or _fallback_insight(it)).strip(),
                "url": it["url"],
                "interest": it.get("interest"),
            }
        )
    return {"title": "What Should Shresth Pay Attention To Today?", "items": out}


def _source_references(stories: list[dict]) -> list[dict]:
    seen: dict[str, str] = {}
    for s in stories:
        for src in s.get("sources", []):
            if src["name"] not in seen:
                seen[src["name"]] = src["url"]
    return [{"name": n, "url": u} for n, u in seen.items()]


def generate(db: Session, *, kind: str = "daily", report_date: datetime | None = None) -> Report:
    report_date = report_date or datetime.now(timezone.utc)
    n = settings.TOP_STORIES_PER_SECTION
    n_overall = settings.TOP_STORIES_OVERALL

    events = (
        db.query(DeduplicatedEvent)
        .join(Ranking, Ranking.event_id == DeduplicatedEvent.id)
        .filter(DeduplicatedEvent.summary.has())
        .order_by(Ranking.score.desc())
        .limit(300)
        .all()
    )

    top_overall = [_serialize(e) for e in events[:n_overall]]
    sections = {name: _section(events, cats, n) for name, cats in SECTION_MAP.items()}

    market_summary = sections["Business & Markets"]
    watchlist = [
        {"headline": t["headline"], "category": t["category"], "url": t["url"]}
        for t in top_overall[5:10]
    ]
    category_counts = [
        {"category": t["topic"], "count": t["count"]} for t in _trending(events, n=12)
    ]

    data = {
        "generated_at": report_date.isoformat(),
        "kind": kind,
        "executive_summary": _executive_summary(top_overall),
        "top_20": top_overall,
        "sections": sections,
        "market_summary": market_summary,
        "trending_topics": _trending(events),
        "category_counts": category_counts,
        "tomorrow_watchlist": watchlist,
        "personalized": _personalized_section(db),
        "source_references": _source_references(top_overall),
        "stats": {
            "events": len(events),
            "avg_score": round(
                sum(e.ranking.score for e in events if e.ranking) / max(1, len(events)), 1
            ),
        },
    }

    report = Report(
        report_date=report_date,
        title=f"Daily News Intelligence Brief - {report_date.strftime('%d %b %Y')}",
        kind=kind,
        executive_summary=data["executive_summary"],
        data=data,
        event_count=len(events),
    )
    db.add(report)
    db.flush()

    # HTML + Markdown (dashboard / archive)
    paths = render_report_files(report)
    report.html_path = paths.get("html")
    report.markdown_path = paths.get("markdown")

    # Branded executive PDF (primary; pure-python, works everywhere)
    try:
        report.pdf_path = build_brief_pdf(report)
    except Exception as exc:  # noqa: BLE001
        log.error("brief_pdf_failed", error=str(exc))
        report.pdf_path = paths.get("pdf")  # fall back to WeasyPrint output if any

    db.commit()
    db.refresh(report)
    log.info("report_generated", report_id=report.id, events=len(events), pdf=report.pdf_path)
    return report
