"""Celery tasks: the autonomous daily workflow + recaps.

The full pipeline runs as one task (``run_daily_pipeline``) so the agent stages
share state and ordering. Individual stage tasks are also exposed for operators
who want granular Beat scheduling per the 06:00–06:45 timetable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from celery import shared_task

from app.ai.graph import run_pipeline
from app.core.logging import get_logger
from app.db.session import session_scope

log = get_logger(__name__)


@shared_task(name="app.tasks.pipeline.run_daily_pipeline", bind=True, max_retries=2)
def run_daily_pipeline(self, send_email: bool = True) -> dict:
    """Collect → dedup → classify → rank → summarize → report → email."""
    try:
        with session_scope() as db:
            stats = run_pipeline(db, send_email=send_email)
        log.info("daily_pipeline_done", **{k: str(v) for k, v in stats.items()})
        return stats
    except Exception as exc:  # noqa: BLE001
        log.error("daily_pipeline_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=120)


# ---- Granular stage tasks (optional alternative to the combined pipeline) ----
@shared_task(name="app.tasks.pipeline.collect_news")
def collect_news() -> dict:
    from app.agents import collector

    with session_scope() as db:
        return collector.collect(db)


@shared_task(name="app.tasks.pipeline.deduplicate")
def deduplicate() -> dict:
    from app.agents import deduplication

    with session_scope() as db:
        return deduplication.deduplicate(db)


@shared_task(name="app.tasks.pipeline.categorize")
def categorize() -> dict:
    from app.agents import classification

    with session_scope() as db:
        return classification.classify(db)


@shared_task(name="app.tasks.pipeline.rank")
def rank() -> dict:
    from app.agents import ranking

    with session_scope() as db:
        return ranking.rank(db)


@shared_task(name="app.tasks.pipeline.summarize")
def summarize() -> dict:
    from app.agents import summarization

    with session_scope() as db:
        return summarization.summarize(db)


@shared_task(name="app.tasks.pipeline.generate_report")
def generate_report() -> dict:
    from app.agents import report as report_agent

    with session_scope() as db:
        report = report_agent.generate(db, kind="daily")
        return {"report_id": report.id}


@shared_task(name="app.tasks.pipeline.send_emails")
def send_emails(report_id: int) -> dict:
    from app.agents import email as email_agent
    from app.db.models import Report

    with session_scope() as db:
        report = db.get(Report, report_id)
        return email_agent.send_reports(db, report)


# ---- Recaps (AI feature: weekly / monthly) ----
def _recap(kind: str, days: int) -> dict:
    from app.agents import report as report_agent
    from app.db.models import Report

    with session_scope() as db:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        recent = (
            db.query(Report)
            .filter(Report.kind == "daily", Report.report_date >= since)
            .all()
        )
        # A recap re-summarizes the period's top events via the report agent.
        report = report_agent.generate(db, kind=kind)
        report.title = f"{kind.capitalize()} Recap — {datetime.now(timezone.utc):%d %b %Y}"
        report.data = (report.data or {}) | {"recap_window_days": days, "daily_reports": len(recent)}
        db.commit()
        return {"report_id": report.id, "kind": kind, "daily_reports": len(recent)}


@shared_task(name="app.tasks.pipeline.generate_weekly_recap")
def generate_weekly_recap() -> dict:
    return _recap("weekly", 7)


@shared_task(name="app.tasks.pipeline.generate_monthly_recap")
def generate_monthly_recap() -> dict:
    return _recap("monthly", 30)
