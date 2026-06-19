"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-20

This initial migration provisions the full schema. It builds the tables directly
from the SQLAlchemy metadata to guarantee the database always matches the ORM
models declared in ``app.db.models``. Subsequent schema changes should be
created with ``alembic revision --autogenerate``.
"""

from __future__ import annotations

from alembic import op

from app.db.base import Base
from app.db import models  # noqa: F401  (registers tables on metadata)

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
