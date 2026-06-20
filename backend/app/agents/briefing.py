"""Agent 6 — Personalized Briefing Agent.

Given a user's declared interests (e.g. AI, DSA, Startups, Finance, Career
Growth), select and rank the most relevant events using semantic similarity
between the interest text and event centroids, blended with importance score.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.embeddings import cosine_similarity, embed_text
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DeduplicatedEvent, Ranking

log = get_logger(__name__)

# Map free-form interests to semantic anchor phrases + related categories.
INTEREST_HINTS = {
    "ai": ("artificial intelligence machine learning models", ["AI", "Technology"]),
    "software engineering": ("software engineering programming development", ["Technology"]),
    "dsa": ("data structures algorithms competitive programming", ["Technology"]),
    "programming": ("programming languages software code developers", ["Technology"]),
    "startups": ("startup funding venture capital founders", ["Startups", "Business"]),
    "finance": ("finance markets banking investment economy", ["Finance", "Markets", "Business"]),
    "productivity": ("productivity tools workflow time management", ["Technology"]),
    "career growth": ("career growth jobs hiring skills leadership", ["Business", "Technology"]),
}


def _anchor(interest: str) -> tuple[str, list[str]]:
    key = interest.strip().lower()
    if key in INTEREST_HINTS:
        return INTEREST_HINTS[key]
    return (interest, [])


def build_personalized(
    db: Session, interests: list[str], *, top_k: int = 8
) -> list[dict]:
    if not interests:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.FETCH_WINDOW_HOURS)
    events = (
        db.query(DeduplicatedEvent)
        .join(Ranking, Ranking.event_id == DeduplicatedEvent.id)
        .filter(DeduplicatedEvent.summary.has())
        .filter(DeduplicatedEvent.event_date >= cutoff)
        .order_by(Ranking.score.desc())
        .limit(120)
        .all()
    )
    if not events:
        return []

    anchors = []
    for interest in interests:
        phrase, cats = _anchor(interest)
        anchors.append((interest, embed_text(phrase), {c.lower() for c in cats}))

    scored: list[tuple[float, str, DeduplicatedEvent]] = []
    for event in events:
        event_cats = {c.category.lower() for c in event.categories}
        best_sim = 0.0
        best_interest = interests[0]
        for interest, vec, cats in anchors:
            sim = cosine_similarity(vec, event.centroid or [])
            if cats & event_cats:
                sim += 0.15  # category overlap bonus
            if sim > best_sim:
                best_sim = sim
                best_interest = interest
        importance = (event.ranking.score if event.ranking else 50.0) / 100.0
        relevance = 0.7 * best_sim + 0.3 * importance
        scored.append((relevance, best_interest, event))

    scored.sort(key=lambda x: x[0], reverse=True)
    out = []
    for relevance, interest, event in scored[:top_k]:
        s = event.summary
        out.append(
            {
                "interest": interest,
                "relevance": round(relevance, 3),
                "headline": s.headline if s else event.canonical_title,
                "two_line": s.two_line if s else None,
                "why_it_matters": s.why_it_matters if s else None,
                "url": event.canonical_url,
                "score": event.ranking.score if event.ranking else None,
            }
        )
    log.info("personalized_briefing_built", interests=len(interests), items=len(out))
    return out
