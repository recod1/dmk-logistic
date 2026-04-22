"""Add route chat read pointers.

Revision ID: 20260422_0004
Revises: 20260422_0003
Create Date: 2026-04-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260422_0004"
down_revision = "20260422_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_chat_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_read_message_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "route_id", name="uq_route_chat_reads_user_route"),
    )
    op.create_index("ix_route_chat_reads_user_id", "route_chat_reads", ["user_id"], unique=False)
    op.create_index("ix_route_chat_reads_route_id", "route_chat_reads", ["route_id"], unique=False)
    op.create_index("ix_route_chat_reads_updated_at", "route_chat_reads", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_route_chat_reads_updated_at", table_name="route_chat_reads")
    op.drop_index("ix_route_chat_reads_route_id", table_name="route_chat_reads")
    op.drop_index("ix_route_chat_reads_user_id", table_name="route_chat_reads")
    op.drop_table("route_chat_reads")

