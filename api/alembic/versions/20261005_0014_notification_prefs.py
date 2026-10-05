"""Per-user notification mute flags.

Revision ID: 20261005_0014
Revises: 20261005_0013
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20261005_0014"
down_revision = "20261005_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_notification_prefs",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("mute_point", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mute_chat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mute_routes", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_notification_prefs")
