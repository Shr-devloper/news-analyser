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
    assert "top_25" in data
    assert len(data["top_25"]) <= 25
    assert set(["World News", "India News", "Technology & AI", "Business & Markets"]).issubset(
        data["sections"].keys()
    )
    assert data["personalized"]["title"] == "What Should You Pay Attention To Today?"
    # Run metadata must be present for every report.
    assert "metadata" in data and "articles_processed" in data["metadata"]
    assert report.report_uid and report.report_uid.startswith("RPT-")


def test_brief_recipients_parsing():
    from app.core.config import Settings

    s = Settings(
        BRIEF_RECIPIENTS=(
            "a@x.com|Asia/Kolkata|Asha|7;b@y.com|America/Los_Angeles|Bob|6"
        )
    )
    recips = s.brief_recipients
    assert len(recips) == 2
    assert recips[0] == {"email": "a@x.com", "timezone": "Asia/Kolkata", "name": "Asha", "hour": 7}
    assert recips[1]["timezone"] == "America/Los_Angeles"
    assert recips[1]["hour"] == 6


def test_brief_recipients_fallback_single():
    from app.core.config import Settings

    s = Settings(BRIEF_RECIPIENTS="", BRIEF_RECIPIENT_EMAIL="solo@x.com",
                 BRIEF_RECIPIENT_NAME="Solo", REPORT_TIMEZONE="Asia/Kolkata")
    recips = s.brief_recipients
    assert len(recips) == 1
    assert recips[0]["email"] == "solo@x.com"
    assert recips[0]["timezone"] == "Asia/Kolkata"


def _make_event(db, *, title, hours_ago, score, category="World"):
    from datetime import timedelta

    from app.db.models import ArticleCategory, DeduplicatedEvent, Ranking, Summary

    ev = DeduplicatedEvent(
        canonical_title=title, canonical_url=f"http://x/{abs(hash(title))}",
        publisher_count=2, event_date=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )
    db.add(ev)
    db.flush()
    db.add(Summary(event_id=ev.id, headline=title, two_line="A two line summary.",
                   why_it_matters="It matters."))
    db.add(Ranking(event_id=ev.id, score=score))
    db.add(ArticleCategory(event_id=ev.id, category=category, is_primary=True))
    db.commit()
    return ev


def test_user_report_excludes_stale_events(db_session):
    from app.db.models import User

    fresh = _make_event(db_session, title="FRESH world story today", hours_ago=2, score=90)
    stale = _make_event(db_session, title="STALE story from days ago", hours_ago=72, score=99)

    user = User(email="u1@test.com", full_name="Test User", hashed_password="x",
                timezone="Asia/Kolkata", delivery_hour=7, interests=["AI"], briefing_enabled=True)
    db_session.add(user)
    db_session.commit()

    report = report_agent.build_user_report(db_session, user)
    ids = {s["id"] for s in report.data["top_25"]}
    assert fresh.id in ids
    assert stale.id not in ids  # stale (>24h) events must never be reused
    assert report.user_id == user.id
    assert report.data["personalized"]["title"] == "What Should Test Pay Attention To Today?"
    # report_articles snapshot persisted
    assert len(report.articles) >= 1


def test_delivery_log_dedup(db_session):
    from datetime import date

    from app.db.models import User
    from app.tasks.pipeline import _delivered_today

    user = User(email="dedupe@test.com", full_name="Dee", hashed_password="x",
                timezone="UTC", delivery_hour=7, interests=[], briefing_enabled=True)
    db_session.add(user)
    db_session.commit()

    today = date(2026, 6, 20)
    assert _delivered_today(db_session, user.id, today) is False
    from app.db.models import EmailDeliveryLog

    db_session.add(EmailDeliveryLog(user_id=user.id, delivery_date=today, status="sent"))
    db_session.commit()
    assert _delivered_today(db_session, user.id, today) is True


def test_brief_email_body():
    report = Report(report_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
                    title="Daily News Intelligence Brief - 20 Jun 2026", kind="daily")
    plain, html = _brief_bodies(report, "Shresth")
    assert "Good Morning Shresth" in plain
    assert "Personalized Insights" in plain
    assert "AI News Intelligence Agent" in plain
    assert "Global News" in html
