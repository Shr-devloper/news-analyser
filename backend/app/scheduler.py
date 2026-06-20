"""APScheduler-based scheduler — the autonomous heartbeat (replaces Celery Beat).

Run it as a standalone background worker::

    python -m app.scheduler

Or embed it inside the FastAPI web process by setting ``RUN_SCHEDULER_IN_WEB=true``
(``create_scheduler(blocking=False)`` is started from the app lifespan).

Every ``SCHEDULER_INTERVAL_MINUTES`` it calls ``dispatch_due_briefs`` which:
  1. loads active users from PostgreSQL,
  2. converts UTC -> each user's timezone,
  3. checks whether it's their delivery time and not yet delivered today,
  4. fetches fresh news, builds a fresh report + PDF, emails it, logs delivery.
"""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.tasks.pipeline import (
    dispatch_due_briefs,
    generate_monthly_recap,
    generate_weekly_recap,
)

log = get_logger(__name__)


def _register_jobs(scheduler) -> None:
    interval = max(1, settings.SCHEDULER_INTERVAL_MINUTES)

    scheduler.add_job(
        dispatch_due_briefs,
        trigger=CronTrigger(minute=f"*/{interval}"),
        id="dispatch_due_briefs",
        name="Dispatch due daily briefs",
        replace_existing=True,
        max_instances=1,           # never overlap pipeline runs
        coalesce=True,             # collapse missed ticks into one
        misfire_grace_time=300,
    )
    scheduler.add_job(
        generate_weekly_recap,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0,
                            timezone=settings.REPORT_TIMEZONE),
        id="weekly_recap", name="Weekly recap", replace_existing=True,
    )
    scheduler.add_job(
        generate_monthly_recap,
        trigger=CronTrigger(day=1, hour=8, minute=30, timezone=settings.REPORT_TIMEZONE),
        id="monthly_recap", name="Monthly recap", replace_existing=True,
    )


def create_scheduler(*, blocking: bool):
    """Build and configure a scheduler. Caller is responsible for ``start()``."""
    scheduler = BlockingScheduler(timezone="UTC") if blocking else BackgroundScheduler(timezone="UTC")
    _register_jobs(scheduler)
    return scheduler


def run() -> None:
    """Entrypoint for the dedicated worker process (`python -m app.scheduler`)."""
    configure_logging()

    # Make sure the schema + briefing users exist before the first tick.
    from app.db.init_db import init_db
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        init_db(db)
    except Exception as exc:  # noqa: BLE001
        log.warning("scheduler_init_db_failed", error=str(exc))
    finally:
        db.close()

    scheduler = create_scheduler(blocking=True)
    log.info("scheduler_started", interval_min=settings.SCHEDULER_INTERVAL_MINUTES,
             jobs=[j.id for j in scheduler.get_jobs()])
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("scheduler_stopping")


if __name__ == "__main__":
    run()
