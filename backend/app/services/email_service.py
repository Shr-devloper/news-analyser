"""SMTP email sending supporting Gmail and Outlook with retry support."""

from __future__ import annotations

import os
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

MAX_ATTEMPTS = 3


class EmailDeliveryError(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def _build_message(
    to: str, subject: str, html: str, text: str | None, attachments: list[str] | None
) -> MIMEMultipart:
    # 'mixed' so we can carry both an alternative body and file attachments.
    outer = MIMEMultipart("mixed")
    outer["Subject"] = subject
    outer["From"] = settings.SMTP_FROM
    outer["To"] = to

    body = MIMEMultipart("alternative")
    body.attach(
        MIMEText(text or "Your news briefing is attached / available in an HTML client.", "plain")
    )
    body.attach(MIMEText(html, "html"))
    outer.attach(body)

    for path in attachments or []:
        if not path or not os.path.exists(path):
            log.warning("attachment_missing", path=path)
            continue
        with open(path, "rb") as fh:
            part = MIMEApplication(fh.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
        outer.attach(part)
    return outer


def send_email(
    to: str,
    subject: str,
    html: str,
    text: str | None = None,
    attachments: list[str] | None = None,
) -> int:
    """Send an email (optionally with attachments), retrying on transient failures.

    Returns the number of attempts used.
    """
    if not is_configured():
        raise EmailDeliveryError("SMTP is not configured (set SMTP_USER / SMTP_PASSWORD).")

    msg = _build_message(to, subject, html, text, attachments)
    last_exc: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
                server.ehlo()
                if settings.SMTP_TLS:
                    server.starttls()
                    server.ehlo()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM, [to], msg.as_string())
            log.info("email_sent", to=to, attempt=attempt)
            return attempt
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log.warning("email_send_retry", to=to, attempt=attempt, error=str(exc))
            if attempt < MAX_ATTEMPTS:
                time.sleep(2.0 * attempt)

    raise EmailDeliveryError(str(last_exc))
