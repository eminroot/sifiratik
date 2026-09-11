"""Panel columns on companies and declarations

The GÜS panel import added seventeen columns to the models - the product and
data-maturity fields on a company, and the return, exemption, product-tree and
data-quality fields on a declaration - without a migration to match. SQLite
development never noticed, because it builds tables from the models; a
PostgreSQL database built with `alembic upgrade head` was missing all of them
and the first import failed. The anchor's `last_sequence` is also brought in
line with the model, which never leaves it empty.

Revision ID: d51b7a2e9c40
Revises: c3e8f41a7b25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d51b7a2e9c40"
down_revision = "c3e8f41a7b25"
branch_labels = None
depends_on = None

COMPANY_COLUMNS = (
    ("nace_code", sa.String(length=20)),
    ("main_product_group", sa.String(length=80)),
    ("primary_packaging_material", sa.String(length=24)),
    ("operating_since", sa.Integer()),
    ("weight_matrix_vintage_year", sa.Integer()),
    ("data_maturity_score", sa.Float()),
)

DECLARATION_COLUMNS = (
    ("return_volume", sa.Float()),
    ("correction_volume", sa.Float()),
    ("exempt_share", sa.Float()),
    ("bom_expected_tonnage", sa.Float()),
    ("bom_coverage_ratio", sa.Float()),
    ("gekap_amount_try", sa.Float()),
    ("gekap_rate_status", sa.String(length=32)),
    ("data_quality_score", sa.Float()),
    ("data_freshness_days", sa.Integer()),
    ("missing_fields", sa.String(length=400)),
)


def upgrade() -> None:
    with op.batch_alter_table("companies", schema=None) as batch_op:
        for name, column_type in COMPANY_COLUMNS:
            batch_op.add_column(sa.Column(name, column_type, nullable=True))
        # The model allows 32 characters; PostgreSQL enforces the 16 the
        # first migration gave it, which a longer firm token would overflow.
        batch_op.alter_column(
            "tax_identifier",
            existing_type=sa.String(length=16),
            type_=sa.String(length=32),
            existing_nullable=False,
        )

    with op.batch_alter_table("declarations", schema=None) as batch_op:
        for name, column_type in DECLARATION_COLUMNS:
            batch_op.add_column(sa.Column(name, column_type, nullable=True))
        # Existing rows take the model's default rather than being left empty.
        batch_op.add_column(
            sa.Column("exemption_flag", sa.Boolean(), nullable=False, server_default=sa.false())
        )

    with op.batch_alter_table("audit_chain_anchor", schema=None) as batch_op:
        batch_op.alter_column("last_sequence", existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("audit_chain_anchor", schema=None) as batch_op:
        batch_op.alter_column("last_sequence", existing_type=sa.Integer(), nullable=True)

    with op.batch_alter_table("declarations", schema=None) as batch_op:
        batch_op.drop_column("exemption_flag")
        for name, _ in reversed(DECLARATION_COLUMNS):
            batch_op.drop_column(name)

    with op.batch_alter_table("companies", schema=None) as batch_op:
        batch_op.alter_column(
            "tax_identifier",
            existing_type=sa.String(length=32),
            type_=sa.String(length=16),
            existing_nullable=False,
        )
        for name, _ in reversed(COMPANY_COLUMNS):
            batch_op.drop_column(name)
