"""Web Push subscriptions for PWA.

Revision ID: 20260327_0005
Revises: 20260326_0004
Create Date: 2026-03-27 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260327_0005"
down_revision = "20260326_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "web_push_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint("uq_web_push_user_endpoint", "web_push_subscriptions", ["user_id", "endpoint"])


def downgrade() -> None:
    op.drop_constraint("uq_web_push_user_endpoint", "web_push_subscriptions", type_="unique")
    op.drop_table("web_push_subscriptions")
