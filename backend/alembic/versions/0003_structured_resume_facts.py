"""Add structured resume fact provenance.

Revision ID: 0003_resume_facts
Revises: 0002_async_queue
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_resume_facts"
down_revision = "0002_async_queue"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    fact_columns = _columns("resume_facts")
    additions = (
        ("char_start", sa.Column("char_start", sa.Integer(), nullable=False, server_default="0")),
        ("char_end", sa.Column("char_end", sa.Integer(), nullable=False, server_default="0")),
        ("strength", sa.Column("strength", sa.String(length=24), nullable=False, server_default="mentioned")),
        ("details", sa.Column("details", sa.JSON(), nullable=False, server_default="{}")),
        ("extractor_version", sa.Column("extractor_version", sa.String(length=40), nullable=False, server_default="rules-v1")),
    )
    for name, column in additions:
        if name not in fact_columns:
            op.add_column("resume_facts", column)

    evidence_columns = _columns("analysis_evidence")
    if "resume_fact_id" not in evidence_columns:
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("analysis_evidence") as batch:
                batch.add_column(sa.Column("resume_fact_id", sa.String(length=36), nullable=True))
                batch.create_foreign_key(
                    "fk_analysis_evidence_resume_fact_id",
                    "resume_facts",
                    ["resume_fact_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
                batch.create_index("ix_analysis_evidence_resume_fact_id", ["resume_fact_id"], unique=False)
        else:
            op.add_column("analysis_evidence", sa.Column("resume_fact_id", sa.String(length=36), nullable=True))
            op.create_foreign_key(
                "fk_analysis_evidence_resume_fact_id",
                "analysis_evidence",
                "resume_facts",
                ["resume_fact_id"],
                ["id"],
                ondelete="SET NULL",
            )
            op.create_index("ix_analysis_evidence_resume_fact_id", "analysis_evidence", ["resume_fact_id"], unique=False)
    elif "ix_analysis_evidence_resume_fact_id" not in _indexes("analysis_evidence"):
        op.create_index("ix_analysis_evidence_resume_fact_id", "analysis_evidence", ["resume_fact_id"], unique=False)


def downgrade() -> None:
    if "ix_analysis_evidence_resume_fact_id" in _indexes("analysis_evidence"):
        op.drop_index("ix_analysis_evidence_resume_fact_id", table_name="analysis_evidence")
    if "resume_fact_id" in _columns("analysis_evidence"):
        op.drop_constraint("fk_analysis_evidence_resume_fact_id", "analysis_evidence", type_="foreignkey")
        op.drop_column("analysis_evidence", "resume_fact_id")
    for name in ("extractor_version", "details", "strength", "char_end", "char_start"):
        if name in _columns("resume_facts"):
            op.drop_column("resume_facts", name)
