"""Tests for the daily brief: PDF generation, filename, and email body."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

from app.agents import classification, deduplication, ranking, summarization
from app.agents import report as report_agent
from app.agents.email import _brief_bodies
from app.db.models import NewsSource, RawArticle, Report


def _seed(db):
    src = NewsSource(slug="s1", name="Source One", connector="rss", url="http://s1", reliability_score=0.9)
    db.add(src)
    db.flush()
    now = datetime.now(timezone.utc)
    db.add_all([
        RawArticle(source_id=src.id, title="AI startup raises huge round for new model",
                   url="http://s1/a", url_hash=hashlib.sha256(b"a").hexdigest(),
                   summary="An AI startup raised a large funding round to build a new model.",
                   published_at=now),
        RawArticle(source_id=src.id, title="Global markets rally on rate cut hopes",
                   url="http://s1/b", url_hash=hashlib.sha256(b"b").hexdigest(),
                   summary="Stock markets rallied worldwide on hopes of interest rate cuts.",
                   published_at=now),
    ])
    db.commit()


def test_brief_pdf_generated(db_session):
    _seed(db_session)
    deduplication.deduplicate(db_session)
    classification.classify(db_session)
    ranking.rank(db_session)
    summarization.summarize(db_session)

    report = report_agent.generate(db_session, kind="daily")

    # Filename format Daily_News_Brief_YYYY_MM_DD.pdf
    assert report.pdf_path is not None
    assert os.path.basename(report.pdf_path).startswith("Daily_News_Brief_")
    assert report.pdf_path.endswith(".pdf")
    assert os.path.exists(report.pdf_path)
    assert os.path.getsize(report.pdf_path) > 1000

    # Structured payload contains the required sections
    data = report.data
    assert "top_20" in data
    assert set(["Top Global News", "India News", "Technology & AI", "Business & Markets"]).issubset(
        data["sections"].keys()
    )
    assert data["personalized"]["title"] == "What Should Shresth Pay Attention To Today?"


def test_brief_email_body():
    report = Report(report_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
                    title="Daily News Intelligence Brief - 20 Jun 2026", kind="daily")
    plain, html = _brief_bodies(report, "Shresth")
    assert "Good Morning Shresth" in plain
    assert "Personalized Insights" in plain
    assert "AI News Intelligence Agent" in plain
    assert "Global News" in html
