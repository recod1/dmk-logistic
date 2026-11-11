"""Daily vehicle maintenance checks during an active shift.

Revision ID: 20261111_0028
Revises: 20261111_0027
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20261111_0028"
down_revision = "20261111_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_shift_daily_checks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "shift_id",
            sa.Integer(),
            sa.ForeignKey("driver_shifts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("checks_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("shift_id", "check_date", name="uq_shift_daily_check_date"),
    )
    op.create_index("ix_driver_shift_daily_checks_shift_id", "driver_shift_daily_checks", ["shift_id"])
    op.create_index("ix_driver_shift_daily_checks_check_date", "driver_shift_daily_checks", ["check_date"])


def downgrade() -> None:
    op.drop_index("ix_driver_shift_daily_checks_check_date", table_name="driver_shift_daily_checks")
    op.drop_index("ix_driver_shift_daily_checks_shift_id", table_name="driver_shift_daily_checks")
    op.drop_table("driver_shift_daily_checks")
