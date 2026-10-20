"""Add pgvector embeddings and full text search support to file_chunks and memories."""

from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0010_pgvector_embeddings"
down_revision = "0009_prompt_traces"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    with op.batch_alter_table("file_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding", Vector(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "tsv",
                sa.Text().with_variant(TSVECTOR, "postgresql"),
                nullable=True,
            )
        )

    with op.batch_alter_table("memories") as batch_op:
        batch_op.add_column(sa.Column("embedding", Vector(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "tsv",
                sa.Text().with_variant(TSVECTOR, "postgresql"),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("memories") as batch_op:
        batch_op.drop_column("tsv")
        batch_op.drop_column("embedding")

    with op.batch_alter_table("file_chunks") as batch_op:
        batch_op.drop_column("tsv")
        batch_op.drop_column("embedding")
