"""Add anonymous workspace lifecycle and durable source files.

Revision ID: 0006_anonymous_workspaces
Revises: 0005_user_model_configs
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_anonymous_workspaces"
down_revision = "0005_user_model_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_anonymous" not in user_columns:
        op.add_column(
            "users",
            sa.Column("is_anonymous", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_users_is_anonymous", "users", ["is_anonymous"])
    if "expires_at" not in user_columns:
        op.add_column("users", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_users_expires_at", "users", ["expires_at"])

    resume_columns = {column["name"] for column in inspector.get_columns("resumes")}
    if "file_data" not in resume_columns:
        op.add_column("resumes", sa.Column("file_data", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    resume_columns = {column["name"] for column in inspector.get_columns("resumes")}
    if "file_data" in resume_columns:
        op.drop_column("resumes", "file_data")

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "expires_at" in user_columns:
        op.drop_index("ix_users_expires_at", table_name="users")
        op.drop_column("users", "expires_at")
    if "is_anonymous" in user_columns:
        op.drop_index("ix_users_is_anonymous", table_name="users")
        op.drop_column("users", "is_anonymous")
