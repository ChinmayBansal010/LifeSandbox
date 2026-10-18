"""Persist storage keys, extraction errors, and document chunks."""

import sqlalchemy as sa
from alembic import op

revision = "0005_files_content"
down_revision = "0004_memory_updated_at_repair"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "files", sa.Column("storage_key", sa.String(500), nullable=False, server_default="")
    )
    op.add_column("files", sa.Column("error_message", sa.String(500), nullable=True))
    op.create_table(
        "file_chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
    )
    op.create_index("ix_file_chunks_file_id", "file_chunks", ["file_id"])
    op.create_index("ix_file_chunks_user_id", "file_chunks", ["user_id"])


def downgrade():
    op.drop_table("file_chunks")
    op.drop_column("files", "error_message")
    op.drop_column("files", "storage_key")
