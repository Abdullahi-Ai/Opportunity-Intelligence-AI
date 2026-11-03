"""add student profile academic fields

Revision ID: 05a08e706195
Revises: 05a08e706194
Create Date: 2026-11-03 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '05a08e706195'
down_revision: Union[str, Sequence[str], None] = '05a08e706194'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_cols = {c["name"] for c in inspector.get_columns("student_profiles")}

    if "degree_title" not in existing_cols:
        op.add_column(
            "student_profiles",
            sa.Column("degree_title", sa.String(255), nullable=True)
        )
    if "specialisations" not in existing_cols:
        op.add_column(
            "student_profiles",
            sa.Column("specialisations", sa.String(255), nullable=True)
        )
    if "expected_graduation" not in existing_cols:
        op.add_column(
            "student_profiles",
            sa.Column("expected_graduation", sa.String(50), nullable=True)
        )
    if "country" not in existing_cols:
        op.add_column(
            "student_profiles",
            sa.Column("country", sa.String(100), nullable=True, server_default="Kenya")
        )


def downgrade() -> None:
    """
    Intentionally non-destructive downgrade.

    Because upgrade() is idempotent and only adds columns that were missing
    at runtime, dropping columns unconditionally during rollback would risk
    deleting columns that pre-existed this migration or destroying student
    academic profile data in production.

    If schema cleanup is explicitly required during a controlled rollback,
    columns may be dropped manually via SQL:
        ALTER TABLE student_profiles DROP COLUMN IF EXISTS country;
        ALTER TABLE student_profiles DROP COLUMN IF EXISTS expected_graduation;
        ALTER TABLE student_profiles DROP COLUMN IF EXISTS specialisations;
        ALTER TABLE student_profiles DROP COLUMN IF EXISTS degree_title;
    """
    pass
