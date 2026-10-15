"""Store driver button-press time on route events.

Revision ID: 20261015_0020
Revises: 20261014_0019
Create Date: 2026-10-15
"""

from alembic import op
import sqlalchemy as sa


revision = "20261015_0020"
down_revision = "20261014_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("route_events", sa.Column("pressed_at_client", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("route_events", "pressed_at_client")
