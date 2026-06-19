"""Agent 1 — News Collector.

Pulls articles from every enabled source, stores raw data, tracks source
reliability, and handles per-source failures + retries without aborting the run.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import NewsSource, RawArticle
from app.sources.registry import get_connector

log = get_logger(__name__)

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 2.0


def _fetch_with_retry(source: NewsSource):
    connector = get_connector(source)
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            return connector.fetch()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("source_fetch_retry", source=source.slug, attempt=attempt, error=str(exc))
            if attempt <= MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_exc  # type: ignore[misc]


def _update_reliability(source: NewsSource, *, ok: bool, error: str | None = None) -> None:
    if ok:
        source.success_count += 1
        source.last_error = None
    else:
        source.failure_count += 1
        source.last_error = error
    total = source.success_count + source.failure_count
    source.reliability_score = round(source.success_count / total, 3) if total else 1.0
    source.last_fetched_at = datetime.now(timezone.utc)


def collect(db: Session) -> dict:
    """Run collection across all enabled sources. Returns a run summary."""
    sources = db.query(NewsSource).filter(NewsSource.enabled.is_(True)).all()
    stored = 0
    failures = 0
    seen_hashes: set[str] = set()

    for source in sources:
        try:
            articles = _fetch_with_retry(source)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            _update_reliability(source, ok=False, error=str(exc))
            db.commit()
            log.error("source_failed", source=source.slug, error=str(exc))
            continue

        new_for_source = 0
        for art in articles:
            if not art.is_valid():
                continue
            h = art.url_hash
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            exists = db.query(RawArticle.id).filter(RawArticle.url_hash == h).first()
            if exists:
                continue
            db.add(
                RawArticle(
                    source_id=source.id,
                    title=art.title[:2000],
                    url=art.url,
                    url_hash=h,
                    summary=art.summary,
                    content=art.content,
                    author=art.author,
                    published_at=art.published_at,
                    language=art.language,
                )
            )
            new_for_source += 1

        stored += new_for_source
        _update_reliability(source, ok=True)
        db.commit()
        log.info("source_collected", source=source.slug, new=new_for_source)

    summary = {
        "sources": len(sources),
        "stored": stored,
        "failures": failures,
        "max_per_source": settings.MAX_ARTICLES_PER_SOURCE,
    }
    log.info("collection_complete", **summary)
    return summary
