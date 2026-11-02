"""add opportunity_chunks pgvector

Revision ID: 05a08e706194
Revises: 05a08e706193
Create Date: 2026-10-31 14:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import UserDefinedType

# revision identifiers, used by Alembic.
revision: str = '05a08e706194'
down_revision: Union[str, Sequence[str], None] = '05a08e706193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

class PGVectorColumnType(UserDefinedType):
    def __init__(self, dim: int = 384):
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"VECTOR({self.dim})"

def upgrade() -> None:
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if dialect_name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    if "opportunity_chunks" not in existing_tables:
        col_type = PGVectorColumnType(384) if dialect_name == "postgresql" else sa.Text()
        op.create_table(
            "opportunity_chunks",
            sa.Column("chunk_id", sa.String(150), primary_key=True),
            sa.Column("opportunity_id", sa.String(100), nullable=False, index=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("provider", sa.String(255), nullable=False),
            sa.Column("category", sa.String(50), nullable=False, index=True),
            sa.Column("section_title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("official_url", sa.String(500), nullable=False),
            sa.Column("application_deadline", sa.String(100), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="open", index=True),
            sa.Column("verification_status", sa.String(50), nullable=False, server_default="Verified"),
            sa.Column("metadata_json", sa.Text(), nullable=False),
            sa.Column("embedding", col_type, nullable=True)
        )

        if dialect_name == "postgresql":
            op.execute(
                "CREATE INDEX IF NOT EXISTS idx_opp_chunks_embedding "
                "ON opportunity_chunks USING hnsw (embedding vector_cosine_ops);"
            )

def downgrade() -> None:
    op.drop_table("opportunity_chunks")
