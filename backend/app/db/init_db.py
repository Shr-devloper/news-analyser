"""Idempotent bootstrap: ensure first superuser and default sources exist."""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.db.models import User, UserPreference
from app.sources.registry import seed_sources

log = get_logger(__name__)

# Autonomous briefing recipients (read from DB by the scheduler).
BRIEFING_USERS = [
    {
        "email": "shresth.t.123@gmail.com",
        "full_name": "Shresth",
        "timezone": "Asia/Kolkata",
        "delivery_hour": 7,
        "interests": [
            "Artificial Intelligence", "Software Engineering", "DSA", "Programming",
            "Startups", "Career Growth", "Productivity",
        ],
    },
    {
        "email": "supreetkhare2@gmail.com",
        "full_name": "Supreet Khare",
        "timezone": "America/Los_Angeles",
        "delivery_hour": 7,
        "interests": ["Technology", "Business", "World News", "Finance", "AI"],
    },
]


def seed_briefing_users(db: Session) -> int:
    """Create/refresh the autonomous briefing recipients. Returns count created."""
    created = 0
    for spec in BRIEFING_USERS:
        user = db.query(User).filter(User.email == spec["email"]).first()
        if user is None:
            user = User(
                email=spec["email"],
                full_name=spec["full_name"],
                hashed_password=hash_password(secrets.token_urlsafe(16)),
                role="user",
                is_active=True,
            )
            db.add(user)
            created += 1
        # Keep briefing config in sync with the declared spec on every boot.
        user.full_name = spec["full_name"]
        user.timezone = spec["timezone"]
        user.delivery_hour = spec["delivery_hour"]
        user.delivery_minute = spec.get("delivery_minute", 0)
        user.interests = spec["interests"]
        user.briefing_enabled = True
    db.commit()
    return created


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

    created = seed_briefing_users(db)
    log.info("briefing_users_synced", created=created, total=len(BRIEFING_USERS))
