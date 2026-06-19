"""Agent 3 — Classification Agent.

Assigns each deduplicated event one or more categories. Uses Groq when
available, otherwise a transparent keyword-scoring fallback.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.groq_client import complete_json
from app.core.logging import get_logger
from app.db.models import ArticleCategory, DeduplicatedEvent

log = get_logger(__name__)

CATEGORIES = [
    "World", "India", "Business", "Finance", "Markets", "Technology",
    "AI", "Cybersecurity", "Startups", "Science", "Health", "Sports",
]

_KEYWORDS: dict[str, list[str]] = {
    "AI": ["ai", "artificial intelligence", "machine learning", "llm", "openai", "neural", "genai", "chatgpt", "model"],
    "Cybersecurity": ["hack", "breach", "ransomware", "malware", "vulnerability", "phishing", "cyber", "exploit"],
    "Startups": ["startup", "seed round", "series a", "series b", "funding", "venture", "vc", "raised"],
    "Technology": ["tech", "software", "app", "device", "gadget", "chip", "semiconductor", "cloud", "developer"],
    "Finance": ["bank", "interest rate", "inflation", "loan", "fintech", "currency", "fed", "rbi"],
    "Markets": ["stocks", "shares", "nasdaq", "sensex", "nifty", "index", "bond", "ipo", "earnings", "market"],
    "Business": ["company", "ceo", "merger", "acquisition", "revenue", "profit", "business", "deal"],
    "Science": ["research", "study", "scientists", "space", "nasa", "physics", "climate", "discovery"],
    "Health": ["health", "covid", "vaccine", "disease", "hospital", "medical", "drug", "who"],
    "Sports": ["match", "cricket", "football", "olympics", "tournament", "league", "championship", "score"],
    "India": ["india", "delhi", "mumbai", "modi", "rupee", "bjp", "lok sabha", "indian"],
    "World": ["world", "global", "un", "president", "war", "election", "country", "international"],
}


def _heuristic(text: str) -> list[tuple[str, float]]:
    lower = text.lower()
    scores: list[tuple[str, float]] = []
    for cat, words in _KEYWORDS.items():
        hits = sum(1 for w in words if w in lower)
        if hits:
            scores.append((cat, min(1.0, 0.4 + 0.15 * hits)))
    if not scores:
        scores.append(("World", 0.4))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:3]


def _llm(text: str) -> list[tuple[str, float]] | None:
    result = complete_json(
        system=(
            "You are a precise news classifier. Choose 1-3 categories from this exact "
            f"list: {CATEGORIES}. Respond as JSON: "
            '{"categories": [{"name": "AI", "confidence": 0.9}]}'
        ),
        user=text[:1500],
        temperature=0.0,
        max_tokens=200,
    )
    if not result or "categories" not in result:
        return None
    out: list[tuple[str, float]] = []
    for item in result["categories"]:
        name = item.get("name")
        if name in CATEGORIES:
            out.append((name, float(item.get("confidence", 0.6))))
    return out or None


def classify(db: Session, *, only_unclassified: bool = True) -> dict:
    query = db.query(DeduplicatedEvent)
    if only_unclassified:
        query = query.filter(~DeduplicatedEvent.categories.any())
    events = query.all()
    classified = 0

    for event in events:
        text = f"{event.canonical_title}. {event.combined_text or ''}"
        cats = _llm(text) or _heuristic(text)
        for i, (name, conf) in enumerate(cats):
            db.add(
                ArticleCategory(
                    event_id=event.id,
                    category=name,
                    confidence=round(conf, 3),
                    is_primary=(i == 0),
                )
            )
        classified += 1

    db.commit()
    log.info("classification_complete", events=classified)
    return {"classified": classified}
