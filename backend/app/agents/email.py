"""Agent 8 — Email Delivery Agent.

Builds a personalized HTML email per active user and delivers it via SMTP,
recording an ``EmailLog`` row (status, attempts, errors) for delivery tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.briefing import build_personalized
from app.core.config import settings
from app.core.logging import get_logger
from app.db.models import EmailLog, Report, User
from app.services.email_service import EmailDeliveryError, is_configured, send_email
from app.services.report_renderer import render_email_html

log = get_logger(__name__)


def _brief_bodies(report: Report, name: str) -> tuple[str, str]:
    """Return (plain_text, html) bodies for the daily brief email (per spec)."""
    plain = (
        f"Good Morning {name},\n\n"
        "Attached is your daily AI-generated news intelligence report containing the most "
        "important developments from the last 24 hours.\n\n"
        "This report includes:\n"
        "- Global News\n- India News\n- AI & Technology\n- Business & Markets\n"
        "- Emerging Trends\n- Personalized Insights\n\n"
        "Regards,\nAI News Intelligence Agent"
    )
    html = f"""\
<div style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;max-width:600px;">
  <div style="background:#4f46e5;color:#fff;padding:20px 24px;border-radius:12px 12px 0 0;">
    <div style="font-size:12px;letter-spacing:.1em;opacity:.85;">AI NEWS INTELLIGENCE AGENT</div>
    <div style="font-size:20px;font-weight:bold;margin-top:4px;">{report.title}</div>
  </div>
  <div style="padding:22px 24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;">
    <p>Good Morning {name},</p>
    <p>Attached is your daily AI-generated news intelligence report containing the most important
       developments from the last 24 hours.</p>
    <p>This report includes:</p>
    <ul>
      <li>Global News</li><li>India News</li><li>AI &amp; Technology</li>
      <li>Business &amp; Markets</li><li>Emerging Trends</li><li>Personalized Insights</li>
    </ul>
    <p style="margin-top:18px;">Regards,<br/><strong>AI News Intelligence Agent</strong></p>
  </div>
</div>"""
    return plain, html


def send_daily_brief(db: Session, report: Report) -> dict:
    """Email the branded PDF report to the configured single recipient (per spec)."""
    recipient = settings.BRIEF_RECIPIENT_EMAIL
    name = settings.BRIEF_RECIPIENT_NAME
    date_str = report.report_date.strftime("%d %B %Y")
    subject = f"Daily AI News Intelligence Report - {date_str}"
    plain, html = _brief_bodies(report, name)

    record = EmailLog(
        report_id=report.id, recipient=recipient, subject=subject, status="pending"
    )
    db.add(record)
    db.flush()

    if not is_configured():
        record.status = "failed"
        record.error = "SMTP not configured"
        db.commit()
        log.warning("daily_brief_not_sent_smtp_unconfigured", recipient=recipient)
        return {"sent": False, "reason": "smtp_unconfigured"}

    attachments = [report.pdf_path] if report.pdf_path else []
    try:
        attempts = send_email(recipient, subject, html, text=plain, attachments=attachments)
        record.status = "sent"
        record.attempts = attempts
        record.sent_at = datetime.now(timezone.utc)
        db.commit()
        log.info("daily_brief_sent", recipient=recipient, attempts=attempts)
        return {"sent": True, "recipient": recipient, "attempts": attempts}
    except EmailDeliveryError as exc:
        record.status = "failed"
        record.attempts = 3
        record.error = str(exc)
        db.commit()
        log.error("daily_brief_failed", recipient=recipient, error=str(exc))
        return {"sent": False, "reason": str(exc)}


def send_reports(db: Session, report: Report) -> dict:
    users = (
        db.query(User)
        .filter(User.is_active.is_(True))
        .join(User.preferences, isouter=True)
        .all()
    )
    sent = 0
    failed = 0
    skipped = 0

    for user in users:
        prefs = user.preferences
        if prefs and not prefs.email_enabled:
            skipped += 1
            continue

        interests = prefs.interests if prefs else []
        personalized = build_personalized(db, interests) if interests else []
        subject = report.title
        html = render_email_html(report, user=user, personalized=personalized)

        record = EmailLog(
            user_id=user.id,
            report_id=report.id,
            recipient=user.email,
            subject=subject,
            status="pending",
        )
        db.add(record)
        db.flush()

        if not is_configured():
            record.status = "failed"
            record.error = "SMTP not configured"
            failed += 1
            db.commit()
            continue

        try:
            attempts = send_email(user.email, subject, html)
            record.status = "sent"
            record.attempts = attempts
            record.sent_at = datetime.now(timezone.utc)
            sent += 1
        except EmailDeliveryError as exc:
            record.status = "failed"
            record.error = str(exc)
            record.attempts = 3
            failed += 1
        db.commit()

    result = {"sent": sent, "failed": failed, "skipped": skipped, "recipients": len(users)}
    log.info("email_delivery_complete", **result)
    return result
