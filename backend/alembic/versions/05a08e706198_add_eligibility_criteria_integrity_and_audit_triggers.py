"""add eligibility criteria integrity and audit triggers

Revision ID: 05a08e706198
Revises: 05a08e706197
Create Date: 2026-11-04 23:45:00.000000

Phase 2 — Stages 2.2B-1A & 2.2B-1B Remediation.
Adds:
1. event_type, before_snapshot, after_snapshot columns to opportunity_criterion_verification_logs.
2. Database CHECK constraints on opportunity_eligibility_criteria enforcing controlled categories,
   valid operators, verification statuses, non-empty text, and verification invariants.
3. Database CHECK constraints on opportunity_criterion_verification_logs.
4. Database-level immutability triggers (PostgreSQL function & trigger, SQLite triggers)
   preventing direct UPDATE or DELETE operations on audit trail records.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '05a08e706198'
down_revision: Union[str, Sequence[str], None] = '05a08e706197'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # 1. Add audit trail columns to opportunity_criterion_verification_logs
    with op.batch_alter_table("opportunity_criterion_verification_logs") as batch_op:
        batch_op.add_column(
            sa.Column("event_type", sa.String(50), server_default="STATUS_CHANGE", nullable=False)
        )
        batch_op.add_column(
            sa.Column("before_snapshot", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("after_snapshot", sa.Text(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_crit_log_prev_status",
            "previous_status IN ('PENDING_REVIEW', 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED')"
        )
        batch_op.create_check_constraint(
            "ck_crit_log_new_status",
            "new_status IN ('PENDING_REVIEW', 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED')"
        )
        batch_op.create_check_constraint(
            "ck_crit_log_notes_not_empty",
            "length(trim(evidence_notes)) > 0"
        )

    # 2. Add CHECK constraints to opportunity_eligibility_criteria
    with op.batch_alter_table("opportunity_eligibility_criteria") as batch_op:
        batch_op.create_check_constraint(
            "ck_opp_crit_type",
            "criterion_type IN ("
            "'MINIMUM_ACADEMIC_GRADE', 'KCSE_GRADE', 'NUMERIC_GPA', "
            "'COUNTY_RESTRICTION', 'GEOGRAPHIC_ALLOCATION', 'GRADUATION_YEAR_RANGE', "
            "'MONTHS_SINCE_GRADUATION', 'EXPECTED_GRADUATION_WINDOW', 'ACADEMIC_STANDING', 'OTHER'"
            ")"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_operator",
            "operator IN ('GTE', 'LTE', 'EQ', 'IN', 'BETWEEN')"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_status",
            "verification_status IN ('PENDING_REVIEW', 'VERIFIED', 'NEEDS_REVIEW', 'REJECTED')"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_source_text_not_empty",
            "length(trim(source_text)) > 0"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_value_not_empty",
            "length(trim(criterion_value)) > 0"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_numeric_scale_positive",
            "numeric_scale IS NULL OR numeric_scale > 0"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_verified_requirements",
            "(verification_status != 'VERIFIED') OR "
            "(verified_at IS NOT NULL AND evidence_url IS NOT NULL AND length(trim(evidence_url)) > 0)"
        )
        batch_op.create_check_constraint(
            "ck_opp_crit_pending_no_verified_meta",
            "(verification_status != 'PENDING_REVIEW') OR (verified_at IS NULL)"
        )

    # 3. Database-level immutability triggers for audit logs
    if dialect == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION 'Audit records in opportunity_criterion_verification_logs are immutable and cannot be updated or deleted.';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER trg_prevent_audit_log_update_delete
            BEFORE UPDATE OR DELETE ON opportunity_criterion_verification_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
        """)
    elif dialect == "sqlite":
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_update
            BEFORE UPDATE ON opportunity_criterion_verification_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit records in opportunity_criterion_verification_logs are immutable and cannot be updated.');
            END;
        """)
        op.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_prevent_audit_log_delete
            BEFORE DELETE ON opportunity_criterion_verification_logs
            BEGIN
                SELECT RAISE(ABORT, 'Audit records in opportunity_criterion_verification_logs are immutable and cannot be deleted.');
            END;
        """)


def downgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # 1. Drop triggers
    if dialect == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_log_update_delete ON opportunity_criterion_verification_logs;")
        op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_modification();")
    elif dialect == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_log_update;")
        op.execute("DROP TRIGGER IF EXISTS trg_prevent_audit_log_delete;")

    # 2. Drop constraints from opportunity_eligibility_criteria
    with op.batch_alter_table("opportunity_eligibility_criteria") as batch_op:
        batch_op.drop_constraint("ck_opp_crit_pending_no_verified_meta", type_="check")
        batch_op.drop_constraint("ck_opp_crit_verified_requirements", type_="check")
        batch_op.drop_constraint("ck_opp_crit_numeric_scale_positive", type_="check")
        batch_op.drop_constraint("ck_opp_crit_value_not_empty", type_="check")
        batch_op.drop_constraint("ck_opp_crit_source_text_not_empty", type_="check")
        batch_op.drop_constraint("ck_opp_crit_status", type_="check")
        batch_op.drop_constraint("ck_opp_crit_operator", type_="check")
        batch_op.drop_constraint("ck_opp_crit_type", type_="check")

    # 3. Drop constraints and columns from opportunity_criterion_verification_logs
    with op.batch_alter_table("opportunity_criterion_verification_logs") as batch_op:
        batch_op.drop_constraint("ck_crit_log_notes_not_empty", type_="check")
        batch_op.drop_constraint("ck_crit_log_new_status", type_="check")
        batch_op.drop_constraint("ck_crit_log_prev_status", type_="check")
        batch_op.drop_column("after_snapshot")
        batch_op.drop_column("before_snapshot")
        batch_op.drop_column("event_type")
