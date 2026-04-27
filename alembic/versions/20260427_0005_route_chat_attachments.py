"""Add route chat attachments.

Revision ID: 20260427_0005
Revises: 20260422_0004
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0005"
down_revision = "20260422_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_chat_attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("route_chat_messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "route_id",
            sa.String(length=64),
            sa.ForeignKey("routes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("original_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("route_chat_attachments")

