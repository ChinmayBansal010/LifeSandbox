"""Initial owner-scoped conversation, memory and feedback tables."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])
    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("content", sa.String(2000), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("source", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("conversation_id", sa.String(36)),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(2000)),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_table(
        "files",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_files_user_id", "files", ["user_id"])


def downgrade():
    op.drop_table("files")
    op.drop_table("feedback")
    op.drop_table("memories")
    op.drop_table("messages")
    op.drop_table("conversations")
