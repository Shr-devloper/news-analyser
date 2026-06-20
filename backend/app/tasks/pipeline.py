"""The autonomous daily workflow — plain functions driven by APScheduler.

No Celery, no Redis, no broker. The scheduler (see ``app/scheduler.py``) calls
``dispatch_due_briefs`` every few minutes; everything runs in-process.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.ai.graph import run_pipeline
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import session_scope

log = get_logger(__name__)


def run_daily_pipeline(send_email: bool = True) -> dict:
    """Collect → dedup → classify → rank → summarize → report → email (all recipients)."""
    try:
        with session_scope() as db:
            stats = run_pipeline(db, send_email=send_email)
        log.info("daily_pipeline_done", **{k: str(v) for k, v in stats.items()})
        return stats
    except Exception as exc:  # noqa: BLE001
        log.error("daily_pipeline_failed", error=str(exc))
        return {"error": str(exc)}


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

    return {
        "collect": collector.collect(db),
        "deduplicate": deduplication.deduplicate(db),
        "classify": classification.classify(db),
        "rank": ranking.rank(db),
        "summarize": summarization.summarize(db),
    }


def dispatch_due_briefs() -> dict:
    """Timezone-aware multi-user dispatcher (called every few minutes by APScheduler).

    For each active, briefing-enabled user: convert UTC -> their timezone; if the
    local time matches their delivery time and today's report hasn't been delivered
    (per ``email_delivery_logs``), fetch fresh news, generate a FRESH report + PDF,
    and email it. DST-aware via zoneinfo. One delivery per user per local day.
    """
    from zoneinfo import ZoneInfo

    from app.agents import email as email_agent
    from app.agents import report as report_agent
    from app.db.models import User

    window = settings.SCHEDULER_INTERVAL_MINUTES
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
                    and target <= local.minute < target + window
                )
                if in_window and not _delivered_today(db, u.id, local.date()):
                    due.append((u, local))

            if not due:
                return {"checked": len(users), "due": 0}

            # Fetch fresh news ONCE, then a personalized report per due user.
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
        # APScheduler will simply try again on the next tick — no broker retries needed.
        log.error("dispatch_due_briefs_failed", error=str(exc))
        return {"error": str(exc)}


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
        report = report_agent.generate(db, kind=kind)
        report.title = f"{kind.capitalize()} Recap — {datetime.now(timezone.utc):%d %b %Y}"
        report.data = (report.data or {}) | {"recap_window_days": days, "daily_reports": len(recent)}
        db.commit()
        return {"report_id": report.id, "kind": kind, "daily_reports": len(recent)}


def generate_weekly_recap() -> dict:
    return _recap("weekly", 7)


def generate_monthly_recap() -> dict:
    return _recap("monthly", 30)
