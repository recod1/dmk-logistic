"""Driver presence history samples.

Revision ID: 20261022_0024
Revises: 20261022_0023
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20261022_0024"
down_revision = "20261022_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_presence_samples",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("connection_status", sa.String(length=16), nullable=False, server_default="offline"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("location_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_driver_presence_samples_user_id", "driver_presence_samples", ["user_id"])
    op.create_index("ix_driver_presence_samples_recorded_at", "driver_presence_samples", ["recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_driver_presence_samples_recorded_at", table_name="driver_presence_samples")
    op.drop_index("ix_driver_presence_samples_user_id", table_name="driver_presence_samples")
    op.drop_table("driver_presence_samples")
