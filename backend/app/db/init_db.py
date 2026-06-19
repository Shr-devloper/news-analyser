"""Idempotent bootstrap: ensure first superuser and default sources exist."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import User, UserPreference
from app.sources.registry import seed_sources

log = get_logger(__name__)


def init_db(db: Session) -> None:
    admin = db.query(User).filter(User.email == settings.FIRST_SUPERUSER_EMAIL).first()
    if not admin:
        admin = User(
            email=settings.FIRST_SUPERUSER_EMAIL,
            full_name=settings.FIRST_SUPERUSER_NAME,
            hashed_password=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
            role="admin",
        )
        admin.preferences = UserPreference(
            interests=["AI", "Startups", "Finance"], categories=[], email_enabled=True
        )
        db.add(admin)
        db.commit()
        log.info("superuser_created", email=settings.FIRST_SUPERUSER_EMAIL)

    added = seed_sources(db)
    if added:
        log.info("sources_seeded", added=added)
