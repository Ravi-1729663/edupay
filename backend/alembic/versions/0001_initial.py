"""initial schema — all tables, constraints, indexes.

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00

Hand-authored (not autogenerate) so every constraint documented in
`docs/DATA_MODEL.md` is explicit and reviewable. Money is NUMERIC(12,2)
everywhere. Floats are forbidden.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_pg() -> bool:
    bind = op.get_bind()
    return bind.dialect.name != "sqlite"


def upgrade() -> None:
    # NOTE: `users` has a circular FK with `students` (users.student_id → students.id,
    # students.created_by → users.id). We create `users` first WITHOUT the student_id
    # FK, create `students`, then add the FK via ALTER. All other tables that
    # reference users.created_by are created after `users` exists.

    # ── users ────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.Enum("STUDENT", "FINANCE_STAFF", "FINANCE_MANAGER", "ADMIN", name="user_role"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        # student_id column added now; its FK is added after `students` exists below.
        sa.Column("student_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_role", "users", ["role"])

    # ── departments ──────────────────────────────────────────────────
    op.create_table(
        "departments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_departments_code"),
    )

    # ── programs ─────────────────────────────────────────────────────
    op.create_table(
        "programs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("department_id", sa.String(length=36), nullable=False),
        sa.Column("duration_years", sa.SmallInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("code", name="uq_programs_code"),
        sa.CheckConstraint("duration_years > 0", name="ck_programs_duration_positive"),
    )
    op.create_index("ix_programs_department_id", "programs", ["department_id"])

    # ── students ──────────────────────────────────────────────────────
    op.create_table(
        "students",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("roll_number", sa.String(length=32), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("program_id", sa.String(length=36), nullable=False),
        sa.Column("batch_year", sa.SmallInteger, nullable=False),
        sa.Column("status", sa.Enum("ACTIVE", "GRADUATED", "WITHDRAWN", name="student_status"), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("roll_number", name="uq_students_roll_number"),
    )
    op.create_index("ix_students_program_id", "students", ["program_id"])
    op.create_index("ix_students_batch_year", "students", ["batch_year"])
    op.create_index("ix_students_status", "students", ["status"])

    # Deferred FK: users.student_id → students.id (circular ref resolved).
    # SQLite can't ALTER ADD CONSTRAINT directly → batch mode.
    if _is_pg():
        op.create_foreign_key(
            "fk_users_student_id",
            "users",
            "students",
            ["student_id"],
            ["id"],
            ondelete="SET NULL",
        )
    else:
        with op.batch_alter_table("users") as batch_op:
            batch_op.create_foreign_key(
                "fk_users_student_id",
                "students",
                ["student_id"],
                ["id"],
                ondelete="SET NULL",
            )

    # ── fee_heads ─────────────────────────────────────────────────────
    op.create_table(
        "fee_heads",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.SmallInteger, nullable=False, server_default="100"),
        sa.Column("is_refundable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("code", name="uq_fee_heads_code"),
    )
    op.create_index("ix_fee_heads_priority", "fee_heads", ["priority"])

    # ── fee_structures ────────────────────────────────────────────────
    op.create_table(
        "fee_structures",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("program_id", sa.String(length=36), nullable=False),
        sa.Column("academic_year", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("program_id", "academic_year", name="uq_fee_structures_program_year"),
    )
    op.create_index("ix_fee_structures_is_active", "fee_structures", ["is_active"])

    # ── fee_structure_lines ───────────────────────────────────────────
    op.create_table(
        "fee_structure_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("fee_structure_id", sa.String(length=36), nullable=False),
        sa.Column("fee_head_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["fee_structure_id"], ["fee_structures.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fee_head_id"], ["fee_heads.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("fee_structure_id", "fee_head_id", name="uq_fsl_structure_head"),
        sa.CheckConstraint("amount > 0", name="ck_fsl_amount_positive"),
    )

    # ── student_fee_assignments ───────────────────────────────────────
    op.create_table(
        "student_fee_assignments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("fee_structure_id", sa.String(length=36), nullable=False),
        sa.Column("academic_year", sa.String(length=16), nullable=False),
        sa.Column("total_invoiced", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fee_structure_id"], ["fee_structures.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("student_id", "academic_year", name="uq_sfa_student_year"),
        sa.CheckConstraint("total_invoiced >= 0", name="ck_sfa_total_nonneg"),
    )
    op.create_index("ix_sfa_student_id", "student_fee_assignments", ["student_id"])

    # ── installments ──────────────────────────────────────────────────
    op.create_table(
        "installments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_fee_assignment_id", sa.String(length=36), nullable=False),
        sa.Column("installment_number", sa.SmallInteger, nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("fee_head_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.Enum("PENDING", "PARTIALLY_PAID", "PAID", "OVERDUE", name="installment_status"), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["student_fee_assignment_id"], ["student_fee_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fee_head_id"], ["fee_heads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("student_fee_assignment_id", "installment_number", name="uq_installments_assignment_number"),
        sa.CheckConstraint("amount > 0", name="ck_installments_amount_positive"),
    )
    op.create_index("ix_installments_due_date", "installments", ["due_date"])
    op.create_index("ix_installments_assignment_id", "installments", ["student_fee_assignment_id"])
    op.create_index("ix_installments_status", "installments", ["status"])

    # ── concessions ───────────────────────────────────────────────────
    op.create_table(
        "concessions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("fee_head_id", sa.String(length=36), nullable=True),
        sa.Column("installment_id", sa.String(length=36), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", name="concession_status"), nullable=False, server_default="PENDING"),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["fee_head_id"], ["fee_heads.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["installment_id"], ["installments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("amount > 0", name="ck_concessions_amount_positive"),
    )
    op.create_index("ix_concessions_student_id", "concessions", ["student_id"])
    op.create_index("ix_concessions_status", "concessions", ["status"])

    # ── payments ──────────────────────────────────────────────────────
    op.create_table(
        "payments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("payer_user_id", sa.String(length=36), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("method", sa.Enum("CASH", "CHEQUE", "ONLINE", name="payment_method"), nullable=False),
        sa.Column("gateway_ref", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Enum("CREATED", "PENDING", "SUCCESS", "FAILED", "UNKNOWN", "REVERSAL_REQUESTED", "REVERSED", name="payment_status"), nullable=False, server_default="CREATED"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("initiated_by", sa.String(length=36), nullable=False),
        sa.Column("callback_received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        # DB-enforced idempotency:
        sa.UniqueConstraint("gateway_ref", name="uq_payments_gateway_ref"),
        sa.UniqueConstraint("idempotency_key", name="uq_payments_idempotency_key"),
        sa.CheckConstraint("method <> 'ONLINE' OR gateway_ref IS NOT NULL", name="ck_payments_online_requires_gateway_ref"),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
    )
    op.create_index("ix_payments_student_id", "payments", ["student_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_created_at", "payments", ["created_at"])

    # ── payment_allocations ───────────────────────────────────────────
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("payment_id", sa.String(length=36), nullable=False),
        sa.Column("installment_id", sa.String(length=36), nullable=False),
        sa.Column("fee_head_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installment_id"], ["installments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["fee_head_id"], ["fee_heads.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("payment_id", "installment_id", "fee_head_id", name="uq_allocations_payment_installment_head"),
        sa.CheckConstraint("amount > 0", name="ck_allocations_amount_positive"),
    )
    op.create_index("ix_allocations_payment_id", "payment_allocations", ["payment_id"])
    op.create_index("ix_allocations_installment_id", "payment_allocations", ["installment_id"])

    # ── payment_reversals ─────────────────────────────────────────────
    op.create_table(
        "payment_reversals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("original_payment_id", sa.String(length=36), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("REQUESTED", "COMPLETED", name="reversal_status"), nullable=False, server_default="REQUESTED"),
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["original_payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("amount > 0", name="ck_reversals_amount_positive"),
    )
    op.create_index("ix_reversals_original_payment_id", "payment_reversals", ["original_payment_id"])

    # ── reconciliation_batches ────────────────────────────────────────
    op.create_table(
        "reconciliation_batches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("uploaded_by", sa.String(length=36), nullable=False),
        sa.Column("source_file_name", sa.String(length=255), nullable=False),
        sa.Column("total_lines", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("matched_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_mismatch_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_internal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_external_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )

    # ── reconciliation_lines ─────────────────────────────────────────
    op.create_table(
        "reconciliation_lines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("external_reference", sa.String(length=128), nullable=False),
        sa.Column("external_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=True),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("classification", sa.Enum("MATCHED", "AMOUNT_MISMATCH", "MISSING_INTERNAL", "MISSING_EXTERNAL", "DUPLICATE", name="recon_class"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["reconciliation_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint("external_amount > 0", name="ck_recon_line_amount_positive"),
    )
    op.create_index("ix_recon_lines_batch_id", "reconciliation_lines", ["batch_id"])
    op.create_index("ix_recon_lines_external_reference", "reconciliation_lines", ["external_reference"])

    # ── idempotency_keys ───────────────────────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["entity_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("key", name="uq_idempotency_keys_key"),
    )
    op.create_index("ix_idempotency_entity", "idempotency_keys", ["entity_type"])

    # ── audit_logs ─────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_entity", "audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_audit_actor", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_ts", "audit_logs", ["ts"])

    # ── Postgres-only trigger: Σ allocations ≤ payment.amount ─────────
    if _is_pg():
        op.execute(
            """
            CREATE OR REPLACE FUNCTION trg_check_allocation_within_payment()
            RETURNS TRIGGER AS $$
            DECLARE
                payment_amount NUMERIC(12,2);
                allocated_total NUMERIC(12,2);
            BEGIN
                SELECT amount INTO payment_amount FROM payments WHERE id = NEW.payment_id;
                SELECT COALESCE(SUM(amount), 0) INTO allocated_total
                  FROM payment_allocations
                 WHERE payment_id = NEW.payment_id;
                IF allocated_total > payment_amount THEN
                    RAISE EXCEPTION 'allocations % exceed payment %', allocated_total, payment_amount
                      USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            "CREATE TRIGGER trg_allocation_within_payment "
            "BEFORE INSERT OR UPDATE ON payment_allocations "
            "FOR EACH ROW EXECUTE FUNCTION trg_check_allocation_within_payment();"
        )


def downgrade() -> None:
    if _is_pg():
        op.execute("DROP TRIGGER IF EXISTS trg_allocation_within_payment ON payment_allocations;")
        op.execute("DROP FUNCTION IF EXISTS trg_check_allocation_within_payment();")
    for table in [
        "audit_logs",
        "idempotency_keys",
        "reconciliation_lines",
        "reconciliation_batches",
        "payment_reversals",
        "payment_allocations",
        "payments",
        "concessions",
        "installments",
        "student_fee_assignments",
        "fee_structure_lines",
        "fee_structures",
        "fee_heads",
        "students",
        "programs",
        "departments",
        "users",
    ]:
        op.drop_table(table)
    # Drop enum types on Postgres
    if _is_pg():
        for enum_name in [
            "recon_class",
            "reversal_status",
            "payment_status",
            "payment_method",
            "concession_status",
            "installment_status",
            "student_status",
            "user_role",
        ]:
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
