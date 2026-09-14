"""Store user-owned chat model configuration.

Revision ID: 0005_user_model_configs
Revises: 0004_observability
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_user_model_configs"
down_revision = "0004_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not sa.inspect(op.get_bind()).has_table("user_model_configs"):
        op.create_table(
            "user_model_configs",
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("encrypted_api_key", sa.Text(), nullable=True),
            sa.Column("base_url", sa.String(length=500), nullable=True),
            sa.Column("chat_model", sa.String(length=120), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("user_model_configs"):
        op.drop_table("user_model_configs")
