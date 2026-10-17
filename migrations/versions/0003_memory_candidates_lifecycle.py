"""Add memory review, project links, reminder recurrence and approval lifecycle."""

import sqlalchemy as sa
from alembic import op

revision = "0003_memory_candidates_lifecycle"
down_revision = "0002_followthrough"
branch_labels = None
depends_on = None


def add_column_if_missing(table_name, column):
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table_name)}
    if column.name not in existing:
        op.add_column(table_name, column)


def upgrade():
    memory_columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("memories")}
    if "project_id" not in memory_columns:
        with op.batch_alter_table("memories") as batch:
            batch.add_column(sa.Column("project_id", sa.String(36), nullable=True))
            batch.create_foreign_key(
                "fk_memories_project_id_projects",
                "projects",
                ["project_id"],
                ["id"],
                ondelete="SET NULL",
            )
    memory_indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("memories")}
    if "ix_memories_project_id" not in memory_indexes:
        op.create_index("ix_memories_project_id", "memories", ["project_id"])

    add_column_if_missing(
        "reminders",
        sa.Column("recurrence", sa.String(20), nullable=False, server_default="none"),
    )
    add_column_if_missing(
        "reminders",
        sa.Column("channel", sa.String(30), nullable=False, server_default="in_app"),
    )
    add_column_if_missing("action_approvals", sa.Column("expires_at", sa.DateTime(timezone=True)))
    add_column_if_missing("action_approvals", sa.Column("correlation_id", sa.String(100)))
    add_column_if_missing("action_approvals", sa.Column("result_resource_type", sa.String(50)))
    add_column_if_missing("action_approvals", sa.Column("result_resource_id", sa.String(36)))
    add_column_if_missing("idempotency_keys", sa.Column("request_hash", sa.String(64)))

    from app.persistence.models import MemoryCandidateRow

    MemoryCandidateRow.__table__.create(op.get_bind(), checkfirst=True)


def downgrade():
    from app.persistence.models import MemoryCandidateRow

    MemoryCandidateRow.__table__.drop(op.get_bind(), checkfirst=True)
    op.drop_column("idempotency_keys", "request_hash")
    op.drop_column("action_approvals", "result_resource_id")
    op.drop_column("action_approvals", "result_resource_type")
    op.drop_column("action_approvals", "correlation_id")
    op.drop_column("action_approvals", "expires_at")
    op.drop_column("reminders", "channel")
    op.drop_column("reminders", "recurrence")
    op.drop_index("ix_memories_project_id", table_name="memories")
    with op.batch_alter_table("memories") as batch:
        batch.drop_constraint("fk_memories_project_id_projects", type_="foreignkey")
        batch.drop_column("project_id")
