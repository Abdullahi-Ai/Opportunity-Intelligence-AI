from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '05a08e706193'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
            sa.Column("hashed_password", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("role", sa.String(50), nullable=False, server_default="student"),
            sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
        )

    if "student_profiles" not in existing_tables:
        op.create_table(
            "student_profiles",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("university", sa.String(255), nullable=False),
            sa.Column("field_of_study", sa.String(255), nullable=False),
            sa.Column("degree_level", sa.String(50), nullable=False),
            sa.Column("year_of_study", sa.Integer(), nullable=False),
            sa.Column("graduation_year", sa.Integer(), nullable=True),
            sa.Column("county_of_origin", sa.String(100), nullable=True),
            sa.Column("gpa_or_grade", sa.String(50), nullable=True),
            sa.Column("preferred_categories", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
        )

    if "opportunities" not in existing_tables:
        op.create_table(
            "opportunities",
            sa.Column("id", sa.String(100), primary_key=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("provider", sa.String(255), nullable=False),
            sa.Column("category", sa.String(50), nullable=False, index=True),
            sa.Column("target_audience", sa.String(255), nullable=True),
            sa.Column("fields_of_study", sa.Text(), nullable=True),
            sa.Column("degree_levels", sa.String(255), nullable=True),
            sa.Column("official_url", sa.Text(), nullable=False),
            sa.Column("application_deadline", sa.String(50), nullable=True),
            sa.Column("status", sa.String(50), server_default="open"),
            sa.Column("is_verified", sa.Boolean(), server_default=sa.true()),
            sa.Column("verification_date", sa.String(50), nullable=True),
            sa.Column("source_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now())
        )

    if "tracked_applications" not in existing_tables:
        op.create_table(
            "tracked_applications",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("student_id", sa.String(36), sa.ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("opportunity_id", sa.String(100), sa.ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False),
            sa.Column("stage", sa.String(50), server_default="Saved"),
            sa.Column("target_submission_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.UniqueConstraint("student_id", "opportunity_id", name="uq_student_opportunity")
        )

    if "application_checklists" not in existing_tables:
        op.create_table(
            "application_checklists",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("tracked_application_id", sa.String(36), sa.ForeignKey("tracked_applications.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_description", sa.Text(), nullable=False),
            sa.Column("is_completed", sa.Boolean(), server_default=sa.false()),
            sa.Column("required_document_type", sa.String(100), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True)
        )

    if "conversations" not in existing_tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("anonymous_session_id", sa.String(100), nullable=True, index=True),
            sa.Column("title", sa.String(255), server_default="New Conversation", nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("state_data", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now())
        )

    if "conversation_messages" not in existing_tables:
        op.create_table(
            "conversation_messages",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("role", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("intent", sa.String(50), nullable=True),
            sa.Column("citations", sa.Text(), nullable=True),
            sa.Column("tool_calls", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now())
        )

def downgrade() -> None:
    op.drop_table("conversation_messages")
    op.drop_table("conversations")
    op.drop_table("application_checklists")
    op.drop_table("tracked_applications")
    op.drop_table("opportunities")
    op.drop_table("student_profiles")
    op.drop_table("users")
