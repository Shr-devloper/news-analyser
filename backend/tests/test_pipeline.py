"""Integration test for the agent pipeline (collector mocked, no network)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.agents import classification, deduplication, ranking, summarization
from app.agents import report as report_agent
from app.db.models import NewsSource, RawArticle


def _hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _seed_articles(db):
    src = NewsSource(slug="t1", name="Test One", connector="rss", url="http://x", reliability_score=0.9)
    src2 = NewsSource(slug="t2", name="Test Two", connector="rss", url="http://y", reliability_score=0.8)
    db.add_all([src, src2])
    db.flush()

    now = datetime.now(timezone.utc)
    rows = [
        # Two near-duplicate AI stories (different publishers) -> 1 event, 2 publishers
        RawArticle(source_id=src.id, title="OpenAI releases new AI model with reasoning",
                   url="http://a/1", url_hash=_hash("a1"),
                   summary="OpenAI launched a new artificial intelligence model with advanced reasoning.",
                   published_at=now),
        RawArticle(source_id=src2.id, title="New AI model from OpenAI brings advanced reasoning",
                   url="http://b/1", url_hash=_hash("b1"),
                   summary="OpenAI unveiled a new AI model featuring advanced reasoning capabilities.",
                   published_at=now),
        # A finance/markets story
        RawArticle(source_id=src.id, title="Stock market rallies as inflation cools",
                   url="http://a/2", url_hash=_hash("a2"),
                   summary="Equity markets surged today after inflation data showed cooling prices.",
                   published_at=now),
    ]
    db.add_all(rows)
    db.commit()


def test_full_agent_chain(db_session):
    _seed_articles(db_session)

    dedup = deduplication.deduplicate(db_session)
    assert dedup["articles"] == 3
    # The two AI articles should collapse into fewer events than articles.
    assert dedup["events"] <= 3

    classified = classification.classify(db_session)
    assert classified["classified"] == dedup["events"]

    ranked = ranking.rank(db_session)
    assert ranked["ranked"] == dedup["events"]

    summarized = summarization.summarize(db_session)
    assert summarized["summarized"] >= 1

    report = report_agent.generate(db_session, kind="daily")
    assert report.id is not None
    assert report.event_count >= 1
    assert "executive_summary" in (report.data or {})
    assert report.markdown_path  # markdown always rendered
