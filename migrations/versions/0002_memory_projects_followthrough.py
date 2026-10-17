"""Add structured memory policy, projects, tasks, reminders, jobs and approvals."""

import sqlalchemy as sa
from alembic import op

revision = "0002_followthrough"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("memories", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("source_conversation_id", sa.String(36), nullable=True))
    op.add_column(
        "memories", sa.Column("confidence", sa.Float(), nullable=False, server_default="1")
    )
    op.add_column("memories", sa.Column("identity_key", sa.String(200), nullable=True))
    # The declarative metadata remains the single source of constraints and indexes.
    from app.persistence.models import (
        ApprovalRow,
        AuditRow,
        IdempotencyRow,
        JobRow,
        MemoryPolicyRow,
        NotificationRow,
        ProjectRow,
        ReminderRow,
        TaskRow,
    )

    for model in (
        MemoryPolicyRow,
        ProjectRow,
        TaskRow,
        ReminderRow,
        JobRow,
        NotificationRow,
        ApprovalRow,
        AuditRow,
        IdempotencyRow,
    ):
        model.__table__.create(op.get_bind(), checkfirst=True)
    op.execute("UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL")
    with op.batch_alter_table("memories") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade():
    for table in (
        "idempotency_keys",
        "audit_events",
        "action_approvals",
        "notifications",
        "jobs",
        "reminders",
        "tasks",
        "projects",
        "memory_policies",
    ):
        op.drop_table(table)
    op.drop_column("memories", "identity_key")
    op.drop_column("memories", "confidence")
    op.drop_column("memories", "source_conversation_id")
    op.drop_column("memories", "updated_at")
