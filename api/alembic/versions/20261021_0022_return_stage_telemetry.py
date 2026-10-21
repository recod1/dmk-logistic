"""Store return stage time, coords and odometer.

Revision ID: 20261021_0022
Revises: 20261021_0021
Create Date: 2026-10-21
"""

from alembic import op
import sqlalchemy as sa


revision = "20261021_0022"
down_revision = "20261021_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "route_incidents",
        sa.Column("stages_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("route_incidents", "stages_json")
