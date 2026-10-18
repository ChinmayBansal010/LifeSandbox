"""Keep file attachments available throughout their conversation."""

import sqlalchemy as sa
from alembic import op

revision = "0006_conversation_files"
down_revision = "0005_files_content"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversation_files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id", sa.String(36), sa.ForeignKey("files.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "file_id"),
    )
    op.create_index("ix_conversation_files_conversation_id", "conversation_files", ["conversation_id"])
    op.create_index("ix_conversation_files_file_id", "conversation_files", ["file_id"])
    op.create_index("ix_conversation_files_user_id", "conversation_files", ["user_id"])


def downgrade():
    op.drop_table("conversation_files")
