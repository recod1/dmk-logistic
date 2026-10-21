"""Driver presence fields and route incidents.

Revision ID: 20261021_0021
Revises: 20261015_0020
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20261021_0021"
down_revision = "20261015_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_lat", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("last_lng", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("last_location_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])
    op.create_table(
        "route_incidents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("points.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("cargo_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("quantity", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("authorized_by", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("return_stage", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("opened_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chat_message_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_route_incidents_route_id", "route_incidents", ["route_id"])
    op.create_index("ix_route_incidents_point_id", "route_incidents", ["point_id"])
    op.create_index("ix_route_incidents_kind", "route_incidents", ["kind"])
    op.create_index("ix_route_incidents_status", "route_incidents", ["status"])
    op.create_index("ix_route_incidents_created_at", "route_incidents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_route_incidents_created_at", table_name="route_incidents")
    op.drop_index("ix_route_incidents_status", table_name="route_incidents")
    op.drop_index("ix_route_incidents_kind", table_name="route_incidents")
    op.drop_index("ix_route_incidents_point_id", table_name="route_incidents")
    op.drop_index("ix_route_incidents_route_id", table_name="route_incidents")
    op.drop_table("route_incidents")
    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.drop_column("users", "last_location_at")
    op.drop_column("users", "last_lng")
    op.drop_column("users", "last_lat")
    op.drop_column("users", "last_seen_at")
