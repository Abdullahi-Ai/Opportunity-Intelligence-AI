"""add opportunity eligibility criteria and criterion audit logs

Revision ID: 05a08e706197
Revises: 05a08e706196
Create Date: 2026-11-04 23:20:00.000000

Phase 2 — Stage 2.2B-1 Baseline Implementation.
Creates:
1. opportunity_eligibility_criteria table with controlled criteria types,
   strict ON DELETE RESTRICT foreign key protection on opportunities.id,
   and ON DELETE SET NULL on users.id.
2. opportunity_criterion_verification_logs audit trail table with
   ON DELETE RESTRICT on criterion_id and composite timestamp index.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '05a08e706197'
down_revision: Union[str, Sequence[str], None] = '05a08e706196'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Create opportunity_eligibility_criteria table
    if "opportunity_eligibility_criteria" not in existing_tables:
        op.create_table(
            "opportunity_eligibility_criteria",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "opportunity_id",
                sa.String(100),
                sa.ForeignKey("opportunities.id", ondelete="RESTRICT"),
                nullable=False
            ),
            sa.Column("criterion_type", sa.String(50), nullable=False),
            sa.Column("operator", sa.String(20), nullable=False),
            sa.Column("criterion_value", sa.String(255), nullable=False),
            sa.Column("grading_system", sa.String(50), nullable=True),
            sa.Column("numeric_scale", sa.Numeric(6, 2), nullable=True),
            sa.Column("is_mandatory", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("source_text", sa.Text(), nullable=False),
            sa.Column("evidence_url", sa.Text(), nullable=True),
            sa.Column(
                "verification_status",
                sa.String(30),
                server_default="PENDING_REVIEW",
                nullable=False
            ),
            sa.Column(
                "verified_by",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True
            ),
            sa.Column("verified_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
                nullable=False
            )
        )
        op.create_index(
            "ix_opp_crit_opp_id",
            "opportunity_eligibility_criteria",
            ["opportunity_id"]
        )
        op.create_index(
            "ix_opp_crit_type",
            "opportunity_eligibility_criteria",
            ["criterion_type"]
        )
        op.create_index(
            "ix_opp_crit_status",
            "opportunity_eligibility_criteria",
            ["verification_status"]
        )
        op.create_index(
            "ix_opp_crit_opp_type",
            "opportunity_eligibility_criteria",
            ["opportunity_id", "criterion_type"]
        )
        op.create_index(
            "ix_opp_crit_opp_status",
            "opportunity_eligibility_criteria",
            ["opportunity_id", "verification_status"]
        )

    # 2. Create opportunity_criterion_verification_logs audit table
    if "opportunity_criterion_verification_logs" not in existing_tables:
        op.create_table(
            "opportunity_criterion_verification_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "criterion_id",
                sa.String(36),
                sa.ForeignKey("opportunity_eligibility_criteria.id", ondelete="RESTRICT"),
                nullable=False
            ),
            sa.Column(
                "admin_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True
            ),
            sa.Column("admin_email", sa.String(255), nullable=True),
            sa.Column("previous_status", sa.String(30), nullable=False),
            sa.Column("new_status", sa.String(30), nullable=False),
            sa.Column("evidence_url", sa.Text(), nullable=True),
            sa.Column("evidence_notes", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False)
        )
        op.create_index(
            "ix_crit_ver_logs_crit_created",
            "opportunity_criterion_verification_logs",
            ["criterion_id", "created_at"]
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if "opportunity_criterion_verification_logs" in existing_tables:
        op.drop_table("opportunity_criterion_verification_logs")

    if "opportunity_eligibility_criteria" in existing_tables:
        op.drop_table("opportunity_eligibility_criteria")
