"""add opportunity verification integrity and audit logs

Revision ID: 05a08e706196
Revises: 05a08e706195
Create Date: 2026-11-04 12:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '05a08e706196'
down_revision: Union[str, Sequence[str], None] = '05a08e706195'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # Add verification_status to opportunities if missing
    if "opportunities" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("opportunities")}
        if "verification_status" not in existing_cols:
            op.add_column(
                "opportunities",
                sa.Column("verification_status", sa.String(30), nullable=False, server_default="UNVERIFIED")
            )

        # CRIT-01: Multi-pass backfill to enforce complete boolean consistency and protect review history.
        # Pass 1: Quarantine only un-audited legacy rows (NULL or initial UNVERIFIED default)
        op.execute(
            sa.text(
                "UPDATE opportunities "
                "SET is_verified = FALSE, verification_status = 'PENDING_REVIEW' "
                "WHERE verification_status IS NULL OR verification_status = 'UNVERIFIED';"
            )
        )
        # Pass 2: Enforce is_verified = TRUE for legitimate VERIFIED opportunities
        op.execute(
            sa.text(
                "UPDATE opportunities "
                "SET is_verified = TRUE "
                "WHERE verification_status = 'VERIFIED';"
            )
        )
        # Pass 3: Enforce is_verified = FALSE for all non-VERIFIED statuses (preserves NEEDS_REVIEW, REJECTED, PENDING_REVIEW)
        op.execute(
            sa.text(
                "UPDATE opportunities "
                "SET is_verified = FALSE "
                "WHERE verification_status IS NOT NULL AND verification_status != 'VERIFIED';"
            )
        )

    # Create opportunity_verification_logs table if missing
    if "opportunity_verification_logs" not in existing_tables:
        op.create_table(
            "opportunity_verification_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            # CRIT-02: Protect audit logs from cascading destruction.
            # Using RESTRICT guarantees the database rejects deletion of opportunities with active audit history.
            sa.Column("opportunity_id", sa.String(100), sa.ForeignKey("opportunities.id", ondelete="RESTRICT"), nullable=False, index=True),
            sa.Column("admin_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("admin_email", sa.String(255), nullable=True),
            sa.Column("previous_status", sa.String(30), nullable=False),
            sa.Column("new_status", sa.String(30), nullable=False),
            sa.Column("official_source_url", sa.Text(), nullable=True),
            sa.Column("evidence_notes", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )

        # MED-02: Compound index for efficient audit trail queries
        op.create_index(
            "ix_opp_ver_logs_opp_created",
            "opportunity_verification_logs",
            ["opportunity_id", "created_at"]
        )


def downgrade() -> None:
    """
    Reversible downgrade strategy.
    
    WARNING: Executing downgrade drops the 'opportunity_verification_logs' audit table
    and the 'opportunities.verification_status' column. All historical audit logs,
    admin review notes, reviewer IDs, timestamps, and evidence URLs will be PERMANENTLY DESTROYED.
    
    OPERATIONAL REQUIREMENT:
    Prior to executing this rollback in staging or production, an explicit database snapshot
    or audit table export MUST be created:
        pg_dump -t opportunity_verification_logs --data-only "$DATABASE_URL" > opp_verification_logs_backup_$(date +%Y%m%d_%H%M%S).sql
    Or full database snapshot:
        pg_dump "$DATABASE_URL" > pre_downgrade_backup_$(date +%Y%m%d_%H%M%S).sql
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "opportunity_verification_logs" in existing_tables:
        op.drop_index("ix_opp_ver_logs_opp_created", table_name="opportunity_verification_logs")
        op.drop_table("opportunity_verification_logs")

    if "opportunities" in existing_tables:
        existing_cols = {c["name"] for c in inspector.get_columns("opportunities")}
        if "verification_status" in existing_cols:
            op.drop_column("opportunities", "verification_status")
