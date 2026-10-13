"""Drop unused daily mileage confirmation table.

Revision ID: 20261013_0018
Revises: 20261012_0017
Create Date: 2026-10-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20261013_0018"
down_revision = "20261012_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_route_daily_mileage_route_id", table_name="route_daily_mileage")
    op.drop_table("route_daily_mileage")


def downgrade() -> None:
    op.create_table(
        "route_daily_mileage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route_id", sa.String(length=64), nullable=False),
        sa.Column("day_msk", sa.String(length=10), nullable=False),
        sa.Column("suggested_odometer_start", sa.Float(), nullable=True),
        sa.Column("suggested_odometer_end", sa.Float(), nullable=True),
        sa.Column("suggested_km", sa.Integer(), nullable=True),
        sa.Column("odometer_start", sa.Float(), nullable=True),
        sa.Column("odometer_end", sa.Float(), nullable=True),
        sa.Column("km", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="confirmed"),
        sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("edits_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("route_id", "day_msk", name="uq_route_daily_mileage_route_day"),
    )
    op.create_index("ix_route_daily_mileage_route_id", "route_daily_mileage", ["route_id"])
