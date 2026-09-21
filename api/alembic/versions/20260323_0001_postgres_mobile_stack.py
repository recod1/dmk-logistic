"""Initial Postgres schema with mobile stack.

Revision ID: 20260323_0001
Revises:
Create Date: 2026-03-23 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260323_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="driver"),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("legacy_tg_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("login", name="uq_users_login"),
    )
    op.create_index("ix_users_login", "users", ["login"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)
    op.create_index("ix_users_legacy_tg_id", "users", ["legacy_tg_id"], unique=False)

    op.create_table(
        "routes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("legacy_driver_tg_id", sa.BigInteger(), nullable=True),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("number_auto", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("temperature", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("dispatcher_contacts", sa.Text(), nullable=False, server_default=""),
        sa.Column("registration_number", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("trailer_number", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_routes_assigned_user_id", "routes", ["assigned_user_id"], unique=False)
    op.create_index("ix_routes_legacy_driver_tg_id", "routes", ["legacy_driver_tg_id"], unique=False)

    op.create_table(
        "points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type_point", sa.String(length=32), nullable=False),
        sa.Column("place_point", sa.Text(), nullable=False),
        sa.Column("date_point", sa.String(length=64), nullable=False),
        sa.Column("time_accepted", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_departure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_registration", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_put_on_gate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_docs", sa.DateTime(timezone=True), nullable=True),
        sa.Column("photo_docs", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("odometer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_points_route_id", "points", ["route_id"], unique=False)

    op.create_table(
        "route_points",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.UniqueConstraint("route_id", "point_id", name="uq_route_points_route_point"),
        sa.UniqueConstraint("route_id", "order_index", name="uq_route_points_route_order"),
    )
    op.create_index("ix_route_points_route_id", "route_points", ["route_id"], unique=False)
    op.create_index("ix_route_points_point_id", "route_points", ["point_id"], unique=False)

    op.create_table(
        "salary",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_driver", sa.String(length=64), nullable=False),
        sa.Column("date_salary", sa.String(length=64), nullable=False),
        sa.Column("type_route", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("sum_status", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_daily", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("load_2_trips", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("calc_shuttle", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_load_unload", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_curtain", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_return", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_add_shuttle", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_add_point", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_gas_station", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("pallets_hyper", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pallets_metro", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pallets_ashan", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rate_3km", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rate_3_5km", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rate_5km", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rate_10km", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rate_12km", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("rate_12_5km", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("mileage", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_cell_compensation", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("experience", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("percent_10", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_bonus", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("withhold", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("compensation", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("dr", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_without_daily_dr_bonus_exp", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("sum_without_daily_dr_bonus", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("load_address", sa.Text(), nullable=False, server_default=""),
        sa.Column("unload_address", sa.Text(), nullable=False, server_default=""),
        sa.Column("transport", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("trailer_number", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("route_number", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status_driver", sa.String(length=32), nullable=False, server_default=" "),
        sa.Column("comment_driver", sa.Text(), nullable=False, server_default=" "),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_salary_id_driver", "salary", ["id_driver"], unique=False)

    op.create_table(
        "repair",
        sa.Column("id_ticket", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("tg_id", sa.String(length=64), nullable=False),
        sa.Column("number_auto", sa.String(length=64), nullable=False),
        sa.Column("malfunction", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("date_repair", sa.String(length=64), nullable=False, server_default="0"),
        sa.Column("place_repair", sa.Text(), nullable=False, server_default="0"),
        sa.Column("comment_repair", sa.Text(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_repair_tg_id", "repair", ["tg_id"], unique=False)

    op.create_table(
        "route_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("route_id", sa.String(length=64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("points.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("client_event_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at_client", sa.DateTime(timezone=True), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("server_received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "user_id",
            "device_id",
            "client_event_id",
            name="uq_route_events_user_device_event",
        ),
    )
    op.create_index("ix_route_events_route_id", "route_events", ["route_id"], unique=False)
    op.create_index("ix_route_events_point_id", "route_events", ["point_id"], unique=False)
    op.create_index("ix_route_events_user_id", "route_events", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_route_events_user_id", table_name="route_events")
    op.drop_index("ix_route_events_point_id", table_name="route_events")
    op.drop_index("ix_route_events_route_id", table_name="route_events")
    op.drop_table("route_events")

    op.drop_index("ix_repair_tg_id", table_name="repair")
    op.drop_table("repair")

    op.drop_index("ix_salary_id_driver", table_name="salary")
    op.drop_table("salary")

    op.drop_index("ix_route_points_point_id", table_name="route_points")
    op.drop_index("ix_route_points_route_id", table_name="route_points")
    op.drop_table("route_points")

    op.drop_index("ix_points_route_id", table_name="points")
    op.drop_table("points")

    op.drop_index("ix_routes_legacy_driver_tg_id", table_name="routes")
    op.drop_index("ix_routes_assigned_user_id", table_name="routes")
    op.drop_table("routes")

    op.drop_index("ix_users_legacy_tg_id", table_name="users")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_login", table_name="users")
    op.drop_table("users")

