"""Track when a driver device has fetched an assigned route.

Revision ID: 20260904_0010
Revises: 20260825_0009
Create Date: 2026-09-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260904_0010"
down_revision = "20260825_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routes",
        sa.Column("driver_received_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("routes", "driver_received_at")
