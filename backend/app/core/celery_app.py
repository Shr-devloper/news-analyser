"""Celery application + Beat schedule for the autonomous daily workflow.

The schedule mirrors the product spec:

    06:00  collect news
    06:10  deduplicate
    06:15  categorize
    06:20  rank
    06:25  summarize
    06:35  generate report
    06:45  send emails

In practice the whole pipeline is a single chained task (``run_daily_pipeline``)
so the stages always run in order with shared state. We still expose the
individual stage schedule for operators who prefer granular control, but the
default Beat entry simply triggers the full pipeline at 06:00 local time.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "news_agent",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.pipeline"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.REPORT_TIMEZONE,
    enable_utc=False,
    task_track_started=True,
    task_time_limit=60 * 30,
    task_soft_time_limit=60 * 25,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
)

if settings.ENABLE_BEAT:
    celery_app.conf.beat_schedule = {
        "dispatch-daily-briefs": {
            # Ticks every 5 minutes. The task reads active users from the DB,
            # converts UTC to each user's timezone, and emails a FRESH brief to any
            # user whose local delivery time has arrived (e.g. 7 AM IST, 7 AM PST).
            # DST-aware via zoneinfo; email_delivery_logs guarantees one send/user/day.
            "task": "app.tasks.pipeline.dispatch_due_briefs",
            "schedule": crontab(minute="*/5"),
        },
        "weekly-recap": {
            "task": "app.tasks.pipeline.generate_weekly_recap",
            "schedule": crontab(hour=8, minute=0, day_of_week="mon"),
        },
        "monthly-recap": {
            "task": "app.tasks.pipeline.generate_monthly_recap",
            "schedule": crontab(hour=8, minute=30, day_of_month="1"),
        },
    }
