"""Create durable users table for Google/Neon authentication."""

import sqlalchemy as sa
from alembic import op

revision = "0011_users_table"
down_revision = "0010_pgvector_embeddings"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(200), primary_key=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("picture", sa.String(1000), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="google"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])


def downgrade():
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
