"""Per-user Google OAuth state and encrypted connection credentials."""

import sqlalchemy as sa
from alembic import op

revision = "0007_google_connections"
down_revision = "0006_conversation_files"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "google_oauth_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_google_oauth_states_user_id", "google_oauth_states", ["user_id"])
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(200), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("account_email", sa.String(320), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("encrypted_credentials", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    for field in ("user_id", "provider", "status"):
        op.create_index(f"ix_integration_connections_{field}", "integration_connections", [field])


def downgrade():
    op.drop_table("integration_connections")
    op.drop_table("google_oauth_states")
