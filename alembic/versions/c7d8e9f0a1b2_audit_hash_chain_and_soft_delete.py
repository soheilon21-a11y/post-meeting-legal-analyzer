"""hash-chained append-only audit events + actor email + user soft-delete

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-14
"""

from __future__ import annotations

from typing import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Soft-delete flag: users are flagged, never hard-deleted, so audit
    # attribution (actor_id + actor_email snapshot below) survives.
    op.add_column(
        "users",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    # Actor identity snapshot at write time.
    op.add_column(
        "audit_events",
        sa.Column("actor_email", sa.String(length=320), nullable=True),
    )

    # Hash chain: row_hash = sha256(prev_hash + canonical JSON of row),
    # seq monotonic across the table.  Existing (pre-chain) rows keep NULLs
    # and are reported as legacy by scripts/verify_audit_chain.py.
    op.add_column(
        "audit_events",
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audit_events",
        sa.Column("row_hash", sa.String(length=64), nullable=True),
    )
    op.add_column("audit_events", sa.Column("seq", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_audit_events_seq"), "audit_events", ["seq"], unique=False
    )

    # DB-level append-only guarantee: UPDATE/DELETE raise, plain clients
    # cannot rewrite history even with direct database access.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_forbid_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_events is append-only: % is not permitted', TG_OP;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_no_mutation
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW
        EXECUTE FUNCTION audit_events_forbid_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_mutation ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_forbid_mutation()")
    op.drop_index(op.f("ix_audit_events_seq"), table_name="audit_events")
    op.drop_column("audit_events", "seq")
    op.drop_column("audit_events", "row_hash")
    op.drop_column("audit_events", "prev_hash")
    op.drop_column("audit_events", "actor_email")
    op.drop_column("users", "is_deleted")
