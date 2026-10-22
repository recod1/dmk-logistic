"""Point late reason and driver shifts.

Revision ID: 20261022_0023
Revises: 20261021_0022
Create Date: 2026-10-22
"""

from alembic import op
import sqlalchemy as sa


revision = "20261022_0023"
down_revision = "20261021_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "points",
        sa.Column("late_reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "driver_shifts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("driver_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_driver_shifts_driver_user_id", "driver_shifts", ["driver_user_id"])
    op.create_index("ix_driver_shifts_started_at", "driver_shifts", ["started_at"])
    op.create_table(
        "driver_shift_images",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "shift_id",
            sa.Integer(),
            sa.ForeignKey("driver_shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("slot", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_driver_shift_images_shift_id", "driver_shift_images", ["shift_id"])


def downgrade() -> None:
    op.drop_index("ix_driver_shift_images_shift_id", table_name="driver_shift_images")
    op.drop_table("driver_shift_images")
    op.drop_index("ix_driver_shifts_started_at", table_name="driver_shifts")
    op.drop_index("ix_driver_shifts_driver_user_id", table_name="driver_shifts")
    op.drop_table("driver_shifts")
    op.drop_column("points", "late_reason")
