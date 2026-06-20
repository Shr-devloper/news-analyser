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
    """Collect → dedup → classify → rank → summarize → report → email (all recipients)."""
    try:
        with session_scope() as db:
            stats = run_pipeline(db, send_email=send_email)
        log.info("daily_pipeline_done", **{k: str(v) for k, v in stats.items()})
        return stats
    except Exception as exc:  # noqa: BLE001
        log.error("daily_pipeline_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=120)


DELIVERY_WINDOW_MINUTES = 5  # matches the Beat tick cadence


def _delivered_today(db, user_id: int, local_date) -> bool:
    """True if this user already has a SENT delivery logged for their local date."""
    from app.db.models import EmailDeliveryLog

    row = (
        db.query(EmailDeliveryLog.status)
        .filter(
            EmailDeliveryLog.user_id == user_id,
            EmailDeliveryLog.delivery_date == local_date,
            EmailDeliveryLog.status == "sent",
        )
        .first()
    )
    return row is not None


def _ensure_fresh_core(db) -> dict:
    """Run collect -> dedup -> classify -> rank -> summarize so today's data is fresh."""
    from app.agents import classification, collector, deduplication, ranking, summarization

    stats = {
        "collect": collector.collect(db),
        "deduplicate": deduplication.deduplicate(db),
        "classify": classification.classify(db),
        "rank": ranking.rank(db),
        "summarize": summarization.summarize(db),
    }
    return stats


@shared_task(name="app.tasks.pipeline.dispatch_due_briefs", bind=True, max_retries=1)
def dispatch_due_briefs(self) -> dict:
    """Timezone-aware multi-user dispatcher (runs every 5 minutes via Beat).

    For each active, briefing-enabled user: convert UTC -> their timezone; if the
    local time matches their delivery time and today's report hasn't been delivered
    (per ``email_delivery_logs``), generate a FRESH report + PDF and email it.
    DST-aware via zoneinfo. One delivery per user per local day.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from app.agents import email as email_agent
    from app.agents import report as report_agent
    from app.db.models import User

    now_utc = datetime.now(timezone.utc)
    try:
        with session_scope() as db:
            users = (
                db.query(User)
                .filter(User.briefing_enabled.is_(True), User.is_active.is_(True))
                .all()
            )
            due: list[tuple] = []
            for u in users:
                try:
                    local = now_utc.astimezone(ZoneInfo(u.timezone or "UTC"))
                except Exception:  # noqa: BLE001
                    log.warning("bad_timezone", user=u.email, timezone=u.timezone)
                    continue
                target = u.delivery_minute or 0
                in_window = (
                    local.hour == u.delivery_hour
                    and target <= local.minute < target + DELIVERY_WINDOW_MINUTES
                )
                if in_window and not _delivered_today(db, u.id, local.date()):
                    due.append((u, local))

            if not due:
                return {"checked": len(users), "due": 0}

            # Build today's data ONCE, then a personalized report per due user.
            _ensure_fresh_core(db)

            results = []
            for u, local in due:
                report = report_agent.build_user_report(db, u, report_date=now_utc)
                res = email_agent.send_user_brief(
                    db, u, report,
                    delivery_date=local.date(),
                    local_time=local.strftime("%H:%M %Z"),
                )
                results.append(res)

            sent = sum(1 for r in results if r.get("sent"))
            log.info("briefs_dispatched", due=len(due), sent=sent)
            return {"checked": len(users), "due": len(due), "sent": sent, "results": results}
    except Exception as exc:  # noqa: BLE001
        log.error("dispatch_due_briefs_failed", error=str(exc))
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
