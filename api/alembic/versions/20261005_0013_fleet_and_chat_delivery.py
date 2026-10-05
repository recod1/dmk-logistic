"""Fleet plates and chat delivery watermarks.

Revision ID: 20261005_0013
Revises: 20260927_0012
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20261005_0013"
down_revision = "20260927_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fleet_vehicles",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plate", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("plate", name="uq_fleet_vehicles_plate"),
    )
    op.create_index("ix_fleet_vehicles_plate", "fleet_vehicles", ["plate"])

    op.create_table(
        "fleet_trailers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("plate", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("plate", name="uq_fleet_trailers_plate"),
    )
    op.create_index("ix_fleet_trailers_plate", "fleet_trailers", ["plate"])

    op.create_table(
        "chat_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("chat_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_delivered_message_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("room_id", "user_id", name="uq_chat_deliveries_room_user"),
    )
    op.create_index("ix_chat_deliveries_room_id", "chat_deliveries", ["room_id"])
    op.create_index("ix_chat_deliveries_user_id", "chat_deliveries", ["user_id"])

    op.create_table(
        "route_chat_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("route_id", sa.String(), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_delivered_message_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "route_id", name="uq_route_chat_deliveries_user_route"),
    )
    op.create_index("ix_route_chat_deliveries_user_id", "route_chat_deliveries", ["user_id"])
    op.create_index("ix_route_chat_deliveries_route_id", "route_chat_deliveries", ["route_id"])

    op.create_table(
        "salary_chat_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("salary_id", sa.Integer(), sa.ForeignKey("salary.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_delivered_message_id", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("salary_id", "user_id", name="uq_salary_chat_deliveries_salary_user"),
    )
    op.create_index("ix_salary_chat_deliveries_salary_id", "salary_chat_deliveries", ["salary_id"])
    op.create_index("ix_salary_chat_deliveries_user_id", "salary_chat_deliveries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_salary_chat_deliveries_user_id", table_name="salary_chat_deliveries")
    op.drop_index("ix_salary_chat_deliveries_salary_id", table_name="salary_chat_deliveries")
    op.drop_table("salary_chat_deliveries")
    op.drop_index("ix_route_chat_deliveries_route_id", table_name="route_chat_deliveries")
    op.drop_index("ix_route_chat_deliveries_user_id", table_name="route_chat_deliveries")
    op.drop_table("route_chat_deliveries")
    op.drop_index("ix_chat_deliveries_user_id", table_name="chat_deliveries")
    op.drop_index("ix_chat_deliveries_room_id", table_name="chat_deliveries")
    op.drop_table("chat_deliveries")
    op.drop_index("ix_fleet_trailers_plate", table_name="fleet_trailers")
    op.drop_table("fleet_trailers")
    op.drop_index("ix_fleet_vehicles_plate", table_name="fleet_vehicles")
    op.drop_table("fleet_vehicles")
