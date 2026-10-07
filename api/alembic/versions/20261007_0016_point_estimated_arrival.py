"""Point estimated arrival time.

Revision ID: 20261007_0016
Revises: 20261005_0015
Create Date: 2026-10-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20261007_0016"
down_revision = "20261005_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "points",
        sa.Column("estimated_arrival", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("points", "estimated_arrival")
