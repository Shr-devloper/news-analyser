"""Agent 2 — Deduplication Agent.

Generates embeddings for recent articles, clusters near-duplicate coverage via
greedy cosine-similarity grouping, and produces one ``DeduplicatedEvent`` per
real-world story. The best source article (by source reliability) becomes the
canonical representative; ``publisher_count`` captures breadth of coverage.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.ai.embeddings import cosine_similarity, embed_texts
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import DeduplicatedEvent, NewsSource, RawArticle

log = get_logger(__name__)


def _article_text(a: RawArticle) -> str:
    return " ".join(filter(None, [a.title, a.summary or ""]))[:2000]


def _ensure_embeddings(db: Session, articles: list[RawArticle]) -> None:
    missing = [a for a in articles if not a.embedding]
    if not missing:
        return
    vectors = embed_texts([_article_text(a) for a in missing])
    for art, vec in zip(missing, vectors, strict=False):
        art.embedding = vec
    db.commit()


def _centroid(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    return [sum(v[i] for v in vectors) / len(vectors) for i in range(dim)]


def deduplicate(db: Session, *, lookback_hours: int | None = None) -> dict:
    # Default to the configured fetch window (last 24h per the brief spec), with a
    # small grace buffer so stories published just before the window aren't dropped.
    if lookback_hours is None:
        lookback_hours = settings.FETCH_WINDOW_HOURS + 6
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    articles = (
        db.query(RawArticle)
        .filter(RawArticle.event_id.is_(None))
        .filter((RawArticle.published_at.is_(None)) | (RawArticle.published_at >= cutoff))
        .all()
    )
    if not articles:
        log.info("dedup_no_articles")
        return {"events": 0, "articles": 0}

    _ensure_embeddings(db, articles)

    reliability = {s.id: s.reliability_score for s in db.query(NewsSource).all()}
    threshold = settings.DEDUP_SIMILARITY_THRESHOLD

    clusters: list[list[RawArticle]] = []
    cluster_centroids: list[list[float]] = []

    for art in articles:
        placed = False
        for idx, centroid in enumerate(cluster_centroids):
            if cosine_similarity(art.embedding, centroid) >= threshold:
                clusters[idx].append(art)
                cluster_centroids[idx] = _centroid([a.embedding for a in clusters[idx]])
                placed = True
                break
        if not placed:
            clusters.append([art])
            cluster_centroids.append(list(art.embedding))

    created = 0
    for members, centroid in zip(clusters, cluster_centroids, strict=False):
        best = max(members, key=lambda a: (reliability.get(a.source_id, 0.0), a.published_at or cutoff))
        publishers = {a.source_id for a in members}
        event = DeduplicatedEvent(
            canonical_title=best.title[:2000],
            canonical_url=best.url,
            best_source_id=best.source_id,
            publisher_count=len(publishers),
            combined_text=" \n".join(_article_text(a) for a in members)[:6000],
            centroid=centroid,
            event_date=max((a.published_at for a in members if a.published_at), default=datetime.now(timezone.utc)),
        )
        db.add(event)
        db.flush()
        for a in members:
            a.event_id = event.id
        created += 1

    db.commit()
    log.info("dedup_complete", events=created, articles=len(articles))
    return {"events": created, "articles": len(articles)}
