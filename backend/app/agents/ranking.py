"""Agent 4 — Importance Ranking Agent.

Produces a 1–100 importance score for each event from weighted sub-signals:
coverage, global/economic/political/technology impact, audience relevance and
recency. Sub-impacts use keyword heuristics (cheap, deterministic) and can be
refined by Groq when available.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.groq_client import complete_json
from app.core.logging import get_logger
from app.db.models import DeduplicatedEvent, Ranking

log = get_logger(__name__)

WEIGHTS = {
    "coverage": 0.22,
    "global_impact": 0.18,
    "economic_impact": 0.15,
    "political_impact": 0.12,
    "technology_impact": 0.13,
    "audience_relevance": 0.10,
    "recency": 0.10,
}

_IMPACT_KEYWORDS = {
    "global_impact": ["war", "global", "world", "un", "climate", "pandemic", "summit", "treaty", "crisis"],
    "economic_impact": ["inflation", "recession", "gdp", "rate", "market", "trade", "tariff", "jobs", "economy", "stocks"],
    "political_impact": ["election", "president", "parliament", "policy", "government", "minister", "law", "sanction", "vote"],
    "technology_impact": ["ai", "chip", "breakthrough", "launch", "cyber", "quantum", "software", "innovation", "robot"],
}


def _kw_score(text: str, words: list[str]) -> float:
    lower = text.lower()
    hits = sum(1 for w in words if w in lower)
    return min(100.0, hits * 22.0)


def _recency_score(event_date: datetime | None) -> float:
    if not event_date:
        return 50.0
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - event_date).total_seconds() / 3600.0
    if hours <= 6:
        return 100.0
    if hours >= 48:
        return 20.0
    return max(20.0, 100.0 - (hours - 6) * (80.0 / 42.0))


def _coverage_score(publisher_count: int) -> float:
    return min(100.0, 35.0 + (publisher_count - 1) * 18.0)


def _llm_adjust(title: str, text: str) -> dict | None:
    result = complete_json(
        system=(
            "Rate the news story's impact on a 0-100 scale for each dimension. "
            'Respond JSON: {"global_impact":0-100,"economic_impact":0-100,'
            '"political_impact":0-100,"technology_impact":0-100,"audience_relevance":0-100}'
        ),
        user=f"{title}\n\n{text[:1200]}",
        temperature=0.0,
        max_tokens=160,
    )
    if not isinstance(result, dict):
        return None
    return result


def rank(db: Session, *, only_unranked: bool = True) -> dict:
    query = db.query(DeduplicatedEvent)
    if only_unranked:
        query = query.filter(~DeduplicatedEvent.ranking.has())
    events = query.all()
    ranked = 0

    for event in events:
        text = f"{event.canonical_title}. {event.combined_text or ''}"
        sub = {
            "coverage": _coverage_score(event.publisher_count),
            "global_impact": _kw_score(text, _IMPACT_KEYWORDS["global_impact"]),
            "economic_impact": _kw_score(text, _IMPACT_KEYWORDS["economic_impact"]),
            "political_impact": _kw_score(text, _IMPACT_KEYWORDS["political_impact"]),
            "technology_impact": _kw_score(text, _IMPACT_KEYWORDS["technology_impact"]),
            "audience_relevance": 50.0,
            "recency": _recency_score(event.event_date),
        }

        llm = _llm_adjust(event.canonical_title, text)
        if llm:
            for key in ("global_impact", "economic_impact", "political_impact", "technology_impact", "audience_relevance"):
                try:
                    sub[key] = (sub[key] + float(llm[key])) / 2.0
                except (KeyError, TypeError, ValueError):
                    pass

        raw = sum(sub[k] * WEIGHTS[k] for k in WEIGHTS)
        score = max(1.0, min(100.0, round(raw, 1)))

        db.add(
            Ranking(
                event_id=event.id,
                score=score,
                coverage_score=round(sub["coverage"], 1),
                global_impact=round(sub["global_impact"], 1),
                economic_impact=round(sub["economic_impact"], 1),
                political_impact=round(sub["political_impact"], 1),
                technology_impact=round(sub["technology_impact"], 1),
                audience_relevance=round(sub["audience_relevance"], 1),
                recency_score=round(sub["recency"], 1),
                rationale=f"coverage={event.publisher_count} publishers; weighted importance={score}",
            )
        )
        ranked += 1

    db.commit()
    log.info("ranking_complete", events=ranked)
    return {"ranked": ranked}


def category_of(event: DeduplicatedEvent) -> str:
    primary = next((c for c in event.categories if c.is_primary), None)
    if primary:
        return primary.category
    return event.categories[0].category if event.categories else "World"
