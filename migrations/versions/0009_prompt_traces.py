"""Add prompt_traces table for tool and prompt execution telemetry."""

import sqlalchemy as sa
from alembic import op

revision = "0009_prompt_traces"
down_revision = "0008_google_login"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "prompt_traces" not in tables:
        op.create_table(
            "prompt_traces",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(200), nullable=False),
            sa.Column("conversation_id", sa.String(36), nullable=True),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="running"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_duration_ms", sa.Float(), nullable=True),
            sa.Column("tools_accessed", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("response_preview", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
        )
        op.create_index("ix_prompt_traces_user_id", "prompt_traces", ["user_id"])
        op.create_index("ix_prompt_traces_conversation_id", "prompt_traces", ["conversation_id"])
    else:
        indexes = {idx["name"] for idx in inspector.get_indexes("prompt_traces")}
        if "ix_prompt_traces_user_id" not in indexes:
            op.create_index("ix_prompt_traces_user_id", "prompt_traces", ["user_id"])
        if "ix_prompt_traces_conversation_id" not in indexes:
            op.create_index("ix_prompt_traces_conversation_id", "prompt_traces", ["conversation_id"])


def downgrade():
    op.drop_index("ix_prompt_traces_conversation_id", table_name="prompt_traces")
    op.drop_index("ix_prompt_traces_user_id", table_name="prompt_traces")
    op.drop_table("prompt_traces")
