"""Store route cancellation reasons and history.

Revision ID: 20261014_0019
Revises: 20261013_0018
Create Date: 2026-10-14
"""

from alembic import op
import sqlalchemy as sa


revision = "20261014_0019"
down_revision = "20261013_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "route_cancellations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("route_id", sa.String(length=64), nullable=False),
        sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("previous_status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("previous_driver_user_id", sa.Integer(), nullable=True),
        sa.Column("previous_number_auto", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["route_id"], ["routes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cancelled_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_route_cancellations_route_id", "route_cancellations", ["route_id"])
    op.create_index("ix_route_cancellations_cancelled_at", "route_cancellations", ["cancelled_at"])


def downgrade() -> None:
    op.drop_index("ix_route_cancellations_cancelled_at", table_name="route_cancellations")
    op.drop_index("ix_route_cancellations_route_id", table_name="route_cancellations")
    op.drop_table("route_cancellations")
