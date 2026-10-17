"""Repair databases missing the memories.updated_at column."""

import sqlalchemy as sa
from alembic import op

revision = "0004_memory_updated_at_repair"
down_revision = "0003_memory_candidates_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("memories")}
    if "updated_at" not in columns:
        op.add_column("memories", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        op.execute("UPDATE memories SET updated_at = created_at WHERE updated_at IS NULL")
        with op.batch_alter_table("memories") as batch:
            batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("memories")}
    if "updated_at" in columns:
        op.drop_column("memories", "updated_at")
