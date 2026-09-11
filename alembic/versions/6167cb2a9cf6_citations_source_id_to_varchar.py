"""citations source_id to varchar

Revision ID: 6167cb2a9cf6
Revises: 92456d9fb166
Create Date: 2026-09-11
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "6167cb2a9cf6"
down_revision: str | None = "92456d9fb166"
branch_labels: str | str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column(
        "citations",
        "source_id",
        existing_type=sa.Uuid(),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "citations",
        "source_id",
        existing_type=sa.String(length=255),
        type_=sa.Uuid(),
        existing_nullable=False,
        postgresql_using="source_id::uuid",
    )
