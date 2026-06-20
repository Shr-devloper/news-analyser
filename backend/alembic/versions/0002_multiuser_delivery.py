""multi-user briefing: user delivery config, report linkage, delivery logs

Revision ID: 0002_multiuser_delivery
Revises: 0001_initial
Create Date: 2026-06-20

Additive migration — safe to run on an existing database.
"""
# Alembic's ``op`` is a runtime proxy; its members (add_column, create_table,
# drop_table, ...) are attached dynamically, so static analyzers can't resolve
# them. Silence the false positives from both Pylint and Pyright.
# pylint: disable=no-member
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_multiuser_delivery"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- users: briefing delivery config ---
    op.add_column("users", sa.Column("timezone", sa.String(64), server_default="Asia/Kolkata", nullable=False))
    op.add_column("users", sa.Column("delivery_hour", sa.Integer(), server_default="7", nullable=False))
    op.add_column("users", sa.Column("delivery_minute", sa.Integer(), server_default="0", nullable=False))
    op.add_column("users", sa.Column("interests", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("briefing_enabled", sa.Boolean(), server_default=sa.false(), nullable=False))

    # --- reports: per-user linkage + freshness metadata ---
    op.add_column("reports", sa.Column("user_id", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("report_uid", sa.String(64), nullable=True))
    op.add_column("reports", sa.Column("articles_processed", sa.Integer(), server_default="0", nullable=False))
    op.add_column("reports", sa.Column("sources_used", sa.JSON(), nullable=True))
    op.create_index("ix_reports_user_id", "reports", ["user_id"])
    op.create_index("ix_reports_report_uid", "reports", ["report_uid"])

    # --- report_articles ---
    op.create_table(
        "report_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id", ondelete="CASCADE"), index=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("deduplicated_events.id", ondelete="SET NULL")),
        sa.Column("rank", sa.Integer(), server_default="0"),
        sa.Column("score", sa.Float(), server_default="0"),
        sa.Column("section", sa.String(64)),
        sa.Column("category", sa.String(64)),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- email_delivery_logs ---
    op.create_table(
        "email_delivery_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
        sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id", ondelete="SET NULL")),
        sa.Column("delivery_date", sa.Date(), index=True),
        sa.Column("delivery_time", sa.String(32)),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("attempts", sa.Integer(), server_default="0"),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "delivery_date", name="uq_delivery_user_date"),
    )


def downgrade() -> None:
    op.drop_table("email_delivery_logs")
    op.drop_table("report_articles")
    op.drop_index("ix_reports_report_uid", table_name="reports")
    op.drop_index("ix_reports_user_id", table_name="reports")
    op.drop_column("reports", "sources_used")
    op.drop_column("reports", "articles_processed")
    op.drop_column("reports", "report_uid")
    op.drop_column("reports", "user_id")
    op.drop_column("users", "briefing_enabled")
    op.drop_column("users", "interests")
    op.drop_column("users", "delivery_minute")
    op.drop_column("users", "delivery_hour")
    op.drop_column("users", "timezone")
