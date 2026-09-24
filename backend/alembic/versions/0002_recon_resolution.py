"""reconciliation resolution columns (Package C).

Revision ID: 0002_recon_resolution
Revises: 0001_initial
Create Date: 2024-01-02 00:00:00

Adds the exception-review workflow columns to `reconciliation_lines`:
  - resolved_classification (nullable) — what a FINANCE_MANAGER set after review
  - resolved_by (FK users.id, nullable)
  - resolved_at (nullable)
  - resolution_notes (nullable)
  - suggested_payment_id (FK payments.id, nullable) — engine's suggested match
    for human review (reference + date-window + amount)

None of these columns ever mutate financial truth (payments / allocations /
installments). They record human decisions about settlement lines only.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_recon_resolution"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name != "sqlite"


def upgrade() -> None:
    # SQLite can't ALTER ADD COLUMN with a FK inline easily → batch mode.
    if _is_pg():
        op.add_column("reconciliation_lines", sa.Column("resolved_classification", sa.Enum("MATCHED", "AMOUNT_MISMATCH", "MISSING_INTERNAL", "MISSING_EXTERNAL", "DUPLICATE", name="recon_class_resolved", create_type=False), nullable=True))
        op.add_column("reconciliation_lines", sa.Column("resolved_by", sa.String(length=36), nullable=True))
        op.add_column("reconciliation_lines", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column("reconciliation_lines", sa.Column("resolution_notes", sa.Text(), nullable=True))
        op.add_column("reconciliation_lines", sa.Column("suggested_payment_id", sa.String(length=36), nullable=True))
        op.create_foreign_key("fk_recon_lines_resolved_by", "reconciliation_lines", "users", ["resolved_by"], ["id"], ondelete="SET NULL")
        op.create_foreign_key("fk_recon_lines_suggested_payment", "reconciliation_lines", "payments", ["suggested_payment_id"], ["id"], ondelete="SET NULL")
        op.create_index("ix_recon_lines_resolved_classification", "reconciliation_lines", ["resolved_classification"])
    else:
        with op.batch_alter_table("reconciliation_lines") as batch_op:
            batch_op.add_column(sa.Column("resolved_classification", sa.String(length=24), nullable=True))
            batch_op.add_column(sa.Column("resolved_by", sa.String(length=36), nullable=True))
            batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column("resolution_notes", sa.Text(), nullable=True))
            batch_op.add_column(sa.Column("suggested_payment_id", sa.String(length=36), nullable=True))
        op.create_index("ix_recon_lines_resolved_classification", "reconciliation_lines", ["resolved_classification"])


def downgrade() -> None:
    if _is_pg():
        op.drop_index("ix_recon_lines_resolved_classification", table_name="reconciliation_lines")
        op.drop_constraint("fk_recon_lines_suggested_payment", "reconciliation_lines", type_="foreignkey")
        op.drop_constraint("fk_recon_lines_resolved_by", "reconciliation_lines", type_="foreignkey")
        for col in ["suggested_payment_id", "resolution_notes", "resolved_at", "resolved_by", "resolved_classification"]:
            op.drop_column("reconciliation_lines", col)
    else:
        with op.batch_alter_table("reconciliation_lines") as batch_op:
            for col in ["suggested_payment_id", "resolution_notes", "resolved_at", "resolved_by", "resolved_classification"]:
                batch_op.drop_column(col)
        op.drop_index("ix_recon_lines_resolved_classification", table_name="reconciliation_lines")
