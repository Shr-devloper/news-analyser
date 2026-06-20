"""ORM models for the AI News Intelligence Agent.

Tables (per spec):
    users, news_sources, raw_articles, deduplicated_events, article_categories,
    rankings, summaries, reports, email_logs, user_preferences
Plus: audit_logs (security requirement).

Embeddings are stored as JSON float arrays for portability across databases;
similarity is computed in-memory by the deduplication agent.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


# --------------------------------------------------------------------------- #
# Users & preferences
# --------------------------------------------------------------------------- #
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user")  # user | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- Briefing delivery config (drives the autonomous multi-user scheduler) ---
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    delivery_hour: Mapped[int] = mapped_column(Integer, default=7)
    delivery_minute: Mapped[int] = mapped_column(Integer, default=0)
    interests: Mapped[list] = mapped_column(JSON, default=list)
    briefing_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    preferences: Mapped["UserPreference"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    email_logs: Mapped[list["EmailLog"]] = relationship(back_populates="user")
    delivery_logs: Mapped[list["EmailDeliveryLog"]] = relationship(back_populates="user")


class UserPreference(Base, TimestampMixin):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    # Interests like ["AI", "Startups", "Finance", "DSA"]
    interests: Mapped[list] = mapped_column(JSON, default=list)
    # Subset of category names the user wants in their digest.
    categories: Mapped[list] = mapped_column(JSON, default=list)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    send_hour: Mapped[int] = mapped_column(Integer, default=7)  # local hour
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")

    user: Mapped["User"] = relationship(back_populates="preferences")


# --------------------------------------------------------------------------- #
# Sources & raw articles
# --------------------------------------------------------------------------- #
class NewsSource(Base, TimestampMixin):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    connector: Mapped[str] = mapped_column(String(32), default="rss")  # rss | hackernews
    url: Mapped[str] = mapped_column(String(1024))
    category_hint: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Reliability tracking
    reliability_score: Mapped[float] = mapped_column(Float, default=1.0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

    articles: Mapped[list["RawArticle"]] = relationship(back_populates="source")


class RawArticle(Base, TimestampMixin):
    __tablename__ = "raw_articles"
    __table_args__ = (UniqueConstraint("url_hash", name="uq_raw_article_url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("news_sources.id"))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    language: Mapped[str | None] = mapped_column(String(8), default="en")
    embedding: Mapped[list | None] = mapped_column(JSON)  # list[float]
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("deduplicated_events.id", ondelete="SET NULL"), index=True
    )

    source: Mapped["NewsSource"] = relationship(back_populates="articles")
    event: Mapped["DeduplicatedEvent"] = relationship(back_populates="articles")


# --------------------------------------------------------------------------- #
# Deduplicated events (clusters)
# --------------------------------------------------------------------------- #
class DeduplicatedEvent(Base, TimestampMixin):
    __tablename__ = "deduplicated_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_title: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    best_source_id: Mapped[int | None] = mapped_column(ForeignKey("news_sources.id"))
    publisher_count: Mapped[int] = mapped_column(Integer, default=1)
    combined_text: Mapped[str | None] = mapped_column(Text)
    centroid: Mapped[list | None] = mapped_column(JSON)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    articles: Mapped[list["RawArticle"]] = relationship(back_populates="event")
    categories: Mapped[list["ArticleCategory"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    ranking: Mapped["Ranking"] = relationship(
        back_populates="event", uselist=False, cascade="all, delete-orphan"
    )
    summary: Mapped["Summary"] = relationship(
        back_populates="event", uselist=False, cascade="all, delete-orphan"
    )


class ArticleCategory(Base, TimestampMixin):
    __tablename__ = "article_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("deduplicated_events.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(64), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    event: Mapped["DeduplicatedEvent"] = relationship(back_populates="categories")


class Ranking(Base, TimestampMixin):
    __tablename__ = "rankings"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("deduplicated_events.id", ondelete="CASCADE"), unique=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 1..100
    coverage_score: Mapped[float] = mapped_column(Float, default=0.0)
    global_impact: Mapped[float] = mapped_column(Float, default=0.0)
    economic_impact: Mapped[float] = mapped_column(Float, default=0.0)
    political_impact: Mapped[float] = mapped_column(Float, default=0.0)
    technology_impact: Mapped[float] = mapped_column(Float, default=0.0)
    audience_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    recency_score: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str | None] = mapped_column(Text)

    event: Mapped["DeduplicatedEvent"] = relationship(back_populates="ranking")


class Summary(Base, TimestampMixin):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("deduplicated_events.id", ondelete="CASCADE"), unique=True
    )
    headline: Mapped[str] = mapped_column(Text)
    two_line: Mapped[str | None] = mapped_column(Text)
    detailed: Mapped[str | None] = mapped_column(Text)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    key_takeaways: Mapped[list | None] = mapped_column(JSON)
    future_impact: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(String(64))

    event: Mapped["DeduplicatedEvent"] = relationship(back_populates="summary")


# --------------------------------------------------------------------------- #
# Reports & email
# --------------------------------------------------------------------------- #
class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Per-user reports carry the recipient; shared/dashboard reports leave it null.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    report_uid: Mapped[str | None] = mapped_column(String(64), index=True)
    report_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    title: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), default="daily")  # daily | weekly | monthly
    executive_summary: Mapped[str | None] = mapped_column(Text)
    # Structured payload powering the dashboard + templates.
    data: Mapped[dict | None] = mapped_column(JSON)
    html_path: Mapped[str | None] = mapped_column(String(512))
    pdf_path: Mapped[str | None] = mapped_column(String(512))
    markdown_path: Mapped[str | None] = mapped_column(String(512))
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    articles_processed: Mapped[int] = mapped_column(Integer, default=0)
    sources_used: Mapped[list | None] = mapped_column(JSON)

    email_logs: Mapped[list["EmailLog"]] = relationship(back_populates="report")
    articles: Mapped[list["ReportArticle"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )
    delivery_logs: Mapped[list["EmailDeliveryLog"]] = relationship(back_populates="report")


class ReportArticle(Base, TimestampMixin):
    """Snapshot of each story included in a report (decouples report from live data)."""

    __tablename__ = "report_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("deduplicated_events.id", ondelete="SET NULL")
    )
    rank: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    section: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str | None] = mapped_column(String(64))
    headline: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)

    report: Mapped["Report"] = relationship(back_populates="articles")


class EmailLog(Base, TimestampMixin):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"))
    recipient: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|sent|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="email_logs")
    report: Mapped["Report"] = relationship(back_populates="email_logs")


class EmailDeliveryLog(Base, TimestampMixin):
    """Per-user, per-day delivery ledger — the source of truth for de-duplicating sends."""

    __tablename__ = "email_delivery_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "delivery_date", name="uq_delivery_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    report_id: Mapped[int | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"))
    delivery_date: Mapped[Date] = mapped_column(Date, index=True)  # user's LOCAL date
    delivery_time: Mapped[str | None] = mapped_column(String(32))  # local time string
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|sent|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="delivery_logs")
    report: Mapped["Report"] = relationship(back_populates="delivery_logs")


# --------------------------------------------------------------------------- #
# Security: audit log
# --------------------------------------------------------------------------- #
class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSON)
