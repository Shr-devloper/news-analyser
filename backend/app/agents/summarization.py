"""Agent 5 — Summarization Agent.

For each important event produces a structured summary: headline, 2-line
summary, detailed summary, why it matters, key takeaways, future impact.
Groq-powered with a deterministic fallback.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.groq_client import complete_json
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DeduplicatedEvent, Ranking, Summary

log = get_logger(__name__)

_SYSTEM = (
    "You are an executive news editor. Given raw coverage of a single story, "
    "write a crisp, factual briefing. Respond ONLY as JSON with keys: "
    "headline (string), two_line (string, max 2 sentences), detailed (string, 3-5 sentences), "
    "why_it_matters (string), key_takeaways (array of 3-5 short strings), "
    "future_impact (string)."
)


def _fallback(event: DeduplicatedEvent) -> dict:
    text = (event.combined_text or event.canonical_title).strip()
    sentences = [s.strip() for s in text.replace("\n", " ").split(". ") if s.strip()]
    two_line = ". ".join(sentences[:2])[:300]
    detailed = ". ".join(sentences[:5])[:800]
    return {
        "headline": event.canonical_title[:200],
        "two_line": two_line or event.canonical_title,
        "detailed": detailed or two_line or event.canonical_title,
        "why_it_matters": (
            f"Covered by {event.publisher_count} publisher(s), indicating notable significance."
        ),
        "key_takeaways": sentences[:3] or [event.canonical_title],
        "future_impact": "Developments are likely to continue; worth monitoring over coming days.",
        "model": "heuristic",
    }


def _llm(event: DeduplicatedEvent) -> dict | None:
    payload = f"TITLE: {event.canonical_title}\n\nCOVERAGE:\n{(event.combined_text or '')[:3000]}"
    result = complete_json(_SYSTEM, payload, temperature=0.3, max_tokens=900)
    if not isinstance(result, dict) or "headline" not in result:
        return None
    result["model"] = settings.GROQ_MODEL
    return result


def summarize(db: Session, *, limit: int = 60) -> dict:
    events = (
        db.query(DeduplicatedEvent)
        .join(Ranking, Ranking.event_id == DeduplicatedEvent.id)
        .filter(~DeduplicatedEvent.summary.has())
        .order_by(Ranking.score.desc())
        .limit(limit)
        .all()
    )
    count = 0
    for event in events:
        data = _llm(event) or _fallback(event)
        takeaways = data.get("key_takeaways") or []
        if isinstance(takeaways, str):
            takeaways = [takeaways]
        db.add(
            Summary(
                event_id=event.id,
                headline=str(data.get("headline", event.canonical_title))[:500],
                two_line=data.get("two_line"),
                detailed=data.get("detailed"),
                why_it_matters=data.get("why_it_matters"),
                key_takeaways=takeaways,
                future_impact=data.get("future_impact"),
                model=data.get("model"),
            )
        )
        count += 1
    db.commit()
    log.info("summarization_complete", summaries=count)
    return {"summarized": count}
