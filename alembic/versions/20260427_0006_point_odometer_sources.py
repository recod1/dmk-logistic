"""Add per-stage odometer sources.

Revision ID: 20260427_0006
Revises: 20260427_0005
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_0006"
down_revision = "20260427_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("points") as batch:
        batch.add_column(sa.Column("departure_odometer_source", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("registration_odometer_source", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("gate_odometer_source", sa.String(length=16), nullable=True))
        batch.add_column(sa.Column("docs_odometer_source", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("points") as batch:
        batch.drop_column("docs_odometer_source")
        batch.drop_column("gate_odometer_source")
        batch.drop_column("registration_odometer_source")
        batch.drop_column("departure_odometer_source")

