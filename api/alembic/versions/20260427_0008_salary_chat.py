"""Salary chat (messages, attachments, reads).

Revision ID: 20260427_0008
Revises: 20260427_0007
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0008"
down_revision = "20260427_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "salary_chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("salary_id", sa.Integer(), sa.ForeignKey("salary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_salary_chat_messages_salary_id_id", "salary_chat_messages", ["salary_id", "id"], unique=False)

    op.create_table(
        "salary_chat_attachments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("salary_chat_messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("salary_id", sa.Integer(), sa.ForeignKey("salary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("original_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "salary_chat_reads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("salary_id", sa.Integer(), sa.ForeignKey("salary.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("last_read_message_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("salary_id", "user_id", name="uq_salary_chat_reads_salary_user"),
    )


def downgrade() -> None:
    op.drop_table("salary_chat_reads")
    op.drop_table("salary_chat_attachments")
    op.drop_index("ix_salary_chat_messages_salary_id_id", table_name="salary_chat_messages")
    op.drop_table("salary_chat_messages")
