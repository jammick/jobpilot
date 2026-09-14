"""Add Agent observability and evaluation history.

Revision ID: 0004_observability
Revises: 0003_resume_facts
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_observability"
down_revision = "0003_resume_facts"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    columns = _columns("agent_runs")
    additions = (
        ("metrics", sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}")),
        ("error_code", sa.Column("error_code", sa.String(length=80), nullable=True)),
        ("started_at", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True)),
        ("finished_at", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True)),
        ("duration_ms", sa.Column("duration_ms", sa.Integer(), nullable=True)),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("agent_runs", column)
    if "ix_agent_runs_error_code" not in _indexes("agent_runs"):
        op.create_index("ix_agent_runs_error_code", "agent_runs", ["error_code"], unique=False)

    bind = op.get_bind()
    if not sa.inspect(bind).has_table("evaluation_runs"):
        op.create_table(
            "evaluation_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
            sa.Column("dataset_version", sa.String(length=40), nullable=False, server_default="ai-product-manager-v1"),
            sa.Column("metrics", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("failures", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"], unique=False)


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("evaluation_runs"):
        op.drop_index("ix_evaluation_runs_status", table_name="evaluation_runs")
        op.drop_table("evaluation_runs")
    if "ix_agent_runs_error_code" in _indexes("agent_runs"):
        op.drop_index("ix_agent_runs_error_code", table_name="agent_runs")
    for name in ("duration_ms", "finished_at", "started_at", "error_code", "metrics"):
        if name in _columns("agent_runs"):
            op.drop_column("agent_runs", name)
