"""Period on each review

A review is a decision about one company's declaration for one period, and the
workflow standing of a filing is read per period. The column was added to the
model and written by the panel import, but no migration created it, so a
PostgreSQL deployment built with `alembic upgrade head` failed on the first
import. SQLite development creates it through `create_all`.

Revision ID: c3e8f41a7b25
Revises: a1c47b0e9d12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3e8f41a7b25"
down_revision = "a1c47b0e9d12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("audit_reviews", schema=None) as batch_op:
        batch_op.add_column(sa.Column("period", sa.String(length=8), nullable=True))
        batch_op.create_index(batch_op.f("ix_audit_reviews_period"), ["period"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_reviews", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_audit_reviews_period"))
        batch_op.drop_column("period")
