"""Driver shift vehicle intake and handover fields.

Revision ID: 20261108_0026
Revises: 20261023_0025
Create Date: 2026-11-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20261108_0026"
down_revision = "20261023_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "driver_shifts",
        sa.Column("workflow_status", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("driver_name", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("truck", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("trailer", sa.String(length=64), nullable=False, server_default=""),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("place", sa.String(length=255), nullable=False, server_default=""),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("intake_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("handover_json", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "driver_shifts",
        sa.Column("refuels_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_driver_shifts_workflow_status", "driver_shifts", ["workflow_status"])
    op.execute(
        sa.text(
            "UPDATE driver_shifts SET workflow_status = CASE WHEN ended_at IS NULL THEN 'active' ELSE 'closed' END"
        )
    )
    op.alter_column(
        "driver_shift_images",
        "slot",
        existing_type=sa.String(length=16),
        type_=sa.String(length=64),
        existing_nullable=False,
        existing_server_default="",
    )


def downgrade() -> None:
    op.alter_column(
        "driver_shift_images",
        "slot",
        existing_type=sa.String(length=64),
        type_=sa.String(length=16),
        existing_nullable=False,
        existing_server_default="",
    )
    op.drop_index("ix_driver_shifts_workflow_status", table_name="driver_shifts")
    op.drop_column("driver_shifts", "refuels_json")
    op.drop_column("driver_shifts", "handover_json")
    op.drop_column("driver_shifts", "intake_json")
    op.drop_column("driver_shifts", "place")
    op.drop_column("driver_shifts", "trailer")
    op.drop_column("driver_shifts", "truck")
    op.drop_column("driver_shifts", "driver_name")
    op.drop_column("driver_shifts", "workflow_status")
