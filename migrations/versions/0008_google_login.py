"""One-time Google sign-in state for the app session flow."""

import sqlalchemy as sa
from alembic import op

revision = "0008_google_login"
down_revision = "0007_google_connections"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "google_login_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("code_verifier", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("google_login_states")

