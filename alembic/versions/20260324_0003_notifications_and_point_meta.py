"""Add notifications table and point meta fields.

Revision ID: 20260324_0003
Revises: 20260323_0002
Create Date: 2026-03-24 10:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260324_0003"
down_revision = "20260323_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("points") as batch_op:
        batch_op.add_column(sa.Column("point_name", sa.String(length=255), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("point_contacts", sa.String(length=255), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("point_time", sa.String(length=128), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("point_note", sa.Text(), nullable=False, server_default=""))

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_route_id", "notifications", ["route_id"], unique=False)
    op.create_index("ix_notifications_point_id", "notifications", ["point_id"], unique=False)
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"], unique=False)
    op.create_index("ix_notifications_created_at", "notifications", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_created_at", table_name="notifications")
    op.drop_index("ix_notifications_event_type", table_name="notifications")
    op.drop_index("ix_notifications_point_id", table_name="notifications")
    op.drop_index("ix_notifications_route_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

    with op.batch_alter_table("points") as batch_op:
        batch_op.drop_column("point_note")
        batch_op.drop_column("point_time")
        batch_op.drop_column("point_contacts")
        batch_op.drop_column("point_name")
