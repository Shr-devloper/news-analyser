"""Agent 7 — Report Generation Agent (fresh, per-user, executive-grade).

Key guarantees:
  * **Freshness** — only events from the last ``FETCH_WINDOW_HOURS`` are ever
    included, so a report is always built from the current 24h of news and never
    reuses yesterday's stories, summaries, PDFs or HTML.
  * **Per-user** — ``build_user_report`` produces a report + PDF tailored to one
    user's interests, with their own personalized section.
  * **Traceable** — every included story is snapshotted into ``report_articles``
    and the report carries run metadata (timestamp, uid, articles processed, sources).
"""

from __future__ import annotations

import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.briefing import build_personalized
from app.ai.groq_client import complete_json, complete_text
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import (
    DeduplicatedEvent,
    NewsSource,
    RawArticle,
    Ranking,
    Report,
    ReportArticle,
    Summary,
    User,
)
from app.services.pdf_report import build_brief_pdf
from app.services.report_renderer import render_report_files

log = get_logger(__name__)

SECTION_MAP = {
    "World News": {"World"},
    "India News": {"India"},
    "Technology & AI": {"Technology", "AI", "Cybersecurity", "Science"},
    "Business & Markets": {"Business", "Finance", "Markets", "Startups"},
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _cutoff() -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=settings.FETCH_WINDOW_HOURS)


def _fresh_events(db: Session, limit: int = 300) -> list[DeduplicatedEvent]:
    """Only events from the last 24h that have a summary, ranked by importance."""
    cutoff = _cutoff()
    return (
        db.query(DeduplicatedEvent)
        .join(Ranking, Ranking.event_id == DeduplicatedEvent.id)
        .filter(DeduplicatedEvent.summary.has())
        .filter(DeduplicatedEvent.event_date >= cutoff)
        .order_by(Ranking.score.desc())
        .limit(limit)
        .all()
    )


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


def _trending(events: list[DeduplicatedEvent], n: int = 10) -> list[dict]:
    counter: Counter[str] = Counter()
    for e in events:
        for c in e.categories:
            counter[c.category] += 1
    return [{"topic": t, "count": c} for t, c in counter.most_common(n)]


def _run_metadata(db: Session) -> tuple[int, list[str]]:
    """Articles processed and distinct sources used within the freshness window."""
    cutoff = _cutoff()
    articles_processed = (
        db.query(func.count(RawArticle.id)).filter(RawArticle.created_at >= cutoff).scalar() or 0
    )
    rows = (
        db.query(NewsSource.name)
        .join(RawArticle, RawArticle.source_id == NewsSource.id)
        .filter(RawArticle.created_at >= cutoff)
        .distinct()
        .all()
    )
    sources = [r[0] for r in rows]
    return int(articles_processed), sources


def _executive_summary(top: list[dict]) -> str:
    headlines = "\n".join(f"- {t['headline']}" for t in top[:12])
    text = complete_text(
        system=(
            "You are a senior intelligence analyst. Synthesize the last 24h of news into a "
            "sharp 6-8 sentence executive summary. Connect themes; do not just list headlines."
        ),
        user=f"Today's leading stories:\n{headlines}",
        temperature=0.3,
        max_tokens=500,
    )
    if text:
        return text.strip()
    return (
        f"This briefing distills the {len(top)} most significant developments of the last 24 "
        "hours across world affairs, India, technology & AI, and business & markets, ranked by "
        "cross-publisher coverage and estimated impact. Key themes and their implications are "
        "detailed in the sections that follow."
    )


def _fallback_insight(item: dict) -> str:
    return (
        f"Relevant to {item.get('interest', 'your focus areas')}: skim the source, note any "
        "tools/companies named, and connect it to what you're currently learning or building."
    )


def _opportunities_risks(name: str, items: list[dict], interests: list[str]) -> dict:
    """Generate Opportunities / Risks / Emerging / Watch lists for the personalized page."""
    heads = "\n".join(f"- {it['headline']}" for it in items[:8])
    result = complete_json(
        system=(
            f"You advise {name}, whose interests are: {', '.join(interests)}. From today's "
            "stories, produce concise, specific bullets. Respond ONLY as JSON with keys: "
            '{"opportunities": [..3..], "risks": [..3..], "emerging": [..3..], "watch": [..3..]}'
        ),
        user=heads or "No notable stories today.",
        temperature=0.4,
        max_tokens=500,
    )
    if isinstance(result, dict) and "opportunities" in result:
        return {k: (result.get(k) or [])[:4] for k in ("opportunities", "risks", "emerging", "watch")}
    # Heuristic fallback
    tops = [it["headline"] for it in items[:3]]
    return {
        "opportunities": [f"Explore developments related to: {h}" for h in tops] or
                         ["Identify one new tool or trend to try this week."],
        "risks": ["Watch for hype vs. substance in fast-moving stories; verify primary sources."],
        "emerging": [it["headline"] for it in items[3:6]] or ["Monitor recurring themes across publishers."],
        "watch": [it["headline"] for it in items[:3]] or ["Track follow-ups to today's top stories."],
    }


def _personalized_section(db: Session, *, name: str, interests: list[str]) -> dict:
    items_raw = build_personalized(db, interests, top_k=8) if interests else []
    items = []
    for it in items_raw:
        insight = complete_text(
            system=(
                f"You are a sharp mentor for {name} (interests: {', '.join(interests)}). Given a "
                "news item, give ONE concrete, actionable insight (1-2 sentences): what to do, "
                "learn, build or watch. No generic restatement."
            ),
            user=f"{it['headline']}\n{it.get('two_line') or ''}",
            temperature=0.4,
            max_tokens=160,
        )
        items.append({
            "headline": it["headline"],
            "insight": (insight or _fallback_insight(it)).strip(),
            "url": it["url"],
            "interest": it.get("interest"),
        })
    extras = _opportunities_risks(name, items, interests)
    return {
        "title": f"What Should {name} Pay Attention To Today?",
        "items": items,
        **extras,
    }


def _source_references(stories: list[dict]) -> list[dict]:
    seen: dict[str, str] = {}
    for s in stories:
        for src in s.get("sources", []):
            if src["name"] not in seen:
                seen[src["name"]] = src["url"]
    return [{"name": n, "url": u} for n, u in seen.items()]


def _build_data(
    db: Session, *, name: str, interests: list[str], report_date: datetime,
    events: list[DeduplicatedEvent],
) -> dict:
    n = settings.TOP_STORIES_PER_SECTION
    n_overall = min(settings.TOP_STORIES_OVERALL, 25)  # spec: never more than 25

    top_overall = [_serialize(e) for e in events[:n_overall]]
    sections = {sec: _section(events, cats, n) for sec, cats in SECTION_MAP.items()}
    articles_processed, sources = _run_metadata(db)

    return {
        "generated_at": report_date.isoformat(),
        "top_25": top_overall,
        "executive_summary": _executive_summary(top_overall),
        "sections": sections,
        "market_summary": sections["Business & Markets"],
        "trending_topics": _trending(events),
        "category_counts": [{"category": t["topic"], "count": t["count"]} for t in _trending(events, 12)],
        "tomorrow_watchlist": [
            {"headline": t["headline"], "category": t["category"], "url": t["url"]}
            for t in top_overall[5:10]
        ],
        "personalized": _personalized_section(db, name=name, interests=interests),
        "source_references": _source_references(top_overall),
        "metadata": {
            "articles_processed": articles_processed,
            "sources_used": sources,
            "window_hours": settings.FETCH_WINDOW_HOURS,
        },
        "stats": {
            "events": len(events),
            "avg_score": round(
                sum(e.ranking.score for e in events if e.ranking) / max(1, len(events)), 1
            ),
        },
    }


def _persist(
    db: Session, *, data: dict, events: list[DeduplicatedEvent], report_date: datetime,
    kind: str, user: User | None, cover_name: str,
) -> Report:
    uid = f"RPT-{report_date:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    report = Report(
        user_id=user.id if user else None,
        report_uid=uid,
        report_date=report_date,
        title=f"Daily AI News Intelligence Report - {report_date:%d %b %Y}",
        kind=kind,
        executive_summary=data["executive_summary"],
        data=data,
        event_count=len(events),
        articles_processed=data["metadata"]["articles_processed"],
        sources_used=data["metadata"]["sources_used"],
    )
    db.add(report)
    db.flush()

    # Snapshot included stories into report_articles.
    for rank, story in enumerate(data["top_25"], 1):
        db.add(ReportArticle(
            report_id=report.id, event_id=story.get("id"), rank=rank,
            score=story.get("score") or 0.0, section="Top", category=story.get("category"),
            headline=story["headline"][:1000], url=story.get("url"),
        ))

    # Render artifacts (fresh every run; filenames carry the unique report id).
    paths = render_report_files(report)
    report.html_path = paths.get("html")
    report.markdown_path = paths.get("markdown")
    try:
        report.pdf_path = build_brief_pdf(report, recipient_name=cover_name)
    except Exception as exc:  # noqa: BLE001
        log.error("brief_pdf_failed", error=str(exc))
        report.pdf_path = paths.get("pdf")

    db.commit()
    db.refresh(report)
    log.info("report_generated", report_id=report.id, uid=uid, user_id=report.user_id,
             events=len(events), pdf=report.pdf_path)
    return report


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_user_report(db: Session, user: User, *, report_date: datetime | None = None) -> Report:
    """Generate a fresh, personalized report + PDF for a specific user."""
    report_date = report_date or datetime.now(timezone.utc)
    events = _fresh_events(db)
    name = (user.full_name or user.email.split("@")[0]).split(" ")[0]
    interests = user.interests or []
    data = _build_data(db, name=name, interests=interests, report_date=report_date, events=events)
    return _persist(db, data=data, events=events, report_date=report_date, kind="daily",
                    user=user, cover_name=user.full_name or name)


def generate(db: Session, *, kind: str = "daily", report_date: datetime | None = None) -> Report:
    """Generate a shared/dashboard report (not tied to a specific user)."""
    report_date = report_date or datetime.now(timezone.utc)
    events = _fresh_events(db)
    interests = settings.BRIEF_INTERESTS if isinstance(settings.BRIEF_INTERESTS, list) else []
    data = _build_data(db, name="You", interests=interests, report_date=report_date, events=events)
    return _persist(db, data=data, events=events, report_date=report_date, kind=kind,
                    user=None, cover_name="Daily Subscribers")
