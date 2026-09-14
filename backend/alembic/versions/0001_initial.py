"""Create the initial JobPilot schema.

Revision ID: 0001_initial
Revises:
"""

from alembic import op

import app.models  # noqa: F401
from app.core.database import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)
    if bind.dialect.name == "postgresql":
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_resume_chunks_embedding_hnsw "
            "ON resume_chunks USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
            "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) WHERE embedding IS NOT NULL"
        )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
