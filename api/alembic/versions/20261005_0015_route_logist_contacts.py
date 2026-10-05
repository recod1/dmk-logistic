"""Per-route logist contacts snapshot.

Revision ID: 20261005_0015
Revises: 20261005_0014
Create Date: 2026-10-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20261005_0015"
down_revision = "20261005_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "routes",
        sa.Column("logist_contacts", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("routes", "logist_contacts")
