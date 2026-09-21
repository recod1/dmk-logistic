"""Add route chat messages table.

Revision ID: 20260422_0003
Revises: 20260422_0002
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260422_0003"
down_revision = "20260422_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_route_chat_messages_route_id", "route_chat_messages", ["route_id"], unique=False)
    op.create_index("ix_route_chat_messages_user_id", "route_chat_messages", ["user_id"], unique=False)
    op.create_index("ix_route_chat_messages_created_at", "route_chat_messages", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_route_chat_messages_created_at", table_name="route_chat_messages")
    op.drop_index("ix_route_chat_messages_user_id", table_name="route_chat_messages")
    op.drop_index("ix_route_chat_messages_route_id", table_name="route_chat_messages")
    op.drop_table("route_chat_messages")

