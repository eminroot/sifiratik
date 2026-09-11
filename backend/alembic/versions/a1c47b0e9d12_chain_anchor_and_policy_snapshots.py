"""Chain anchor and stored scoring policy

Two tables the platform gained when it stopped trusting things it could not
check:

  audit_chain_anchor   where the decision log is supposed to end, so a cut at
                       the tail shows up instead of reading as a clean chain
  policy_snapshots     the active scoring policy, so a restart does not put
                       the old thresholds back and every worker agrees

SQLite development creates these through `create_all`. This migration is what
the PostgreSQL deployment runs.

Revision ID: a1c47b0e9d12
Revises: 9e333fe72908
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1c47b0e9d12"
down_revision = "9e333fe72908"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_anchor",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=True),
        sa.Column("head_hash", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "policy_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("changed_by", sa.String(length=60), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_snapshots_version", "policy_snapshots", ["version"], unique=True)
    op.create_index("ix_policy_snapshots_created_at", "policy_snapshots", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_policy_snapshots_created_at", table_name="policy_snapshots")
    op.drop_index("ix_policy_snapshots_version", table_name="policy_snapshots")
    op.drop_table("policy_snapshots")
    op.drop_table("audit_chain_anchor")
