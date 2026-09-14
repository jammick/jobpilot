"""Add durable analysis job metadata.

Revision ID: 0002_async_queue
Revises: 0001_initial
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_async_queue"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("analyses")}


def _indexes() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes("analyses")}


def upgrade() -> None:
    # 0001 uses metadata.create_all for compatibility with early local builds.
    # Conditional operations keep both fresh and already-existing databases safe.
    columns = _columns()
    if "role_profile_id" not in columns:
        op.add_column("analyses", sa.Column("role_profile_id", sa.String(length=36), nullable=True))
    if "attempt_count" not in columns:
        op.add_column("analyses", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    if "started_at" not in columns:
        op.add_column("analyses", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    if "finished_at" not in columns:
        op.add_column("analyses", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_analyses_role_profile_id" not in _indexes():
        op.create_index("ix_analyses_role_profile_id", "analyses", ["role_profile_id"], unique=False)


def downgrade() -> None:
    indexes = _indexes()
    if "ix_analyses_role_profile_id" in indexes:
        op.drop_index("ix_analyses_role_profile_id", table_name="analyses")
    columns = _columns()
    for name in ("finished_at", "started_at", "attempt_count", "role_profile_id"):
        if name in columns:
            op.drop_column("analyses", name)
