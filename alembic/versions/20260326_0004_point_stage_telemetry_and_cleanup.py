"""Add stage telemetry columns for route points.

Revision ID: 20260326_0004
Revises: 20260324_0003
Create Date: 2026-03-26 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260326_0004"
down_revision = "20260324_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("points") as batch_op:
        batch_op.add_column(sa.Column("departure_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("departure_odometer", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("departure_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("departure_lng", sa.Float(), nullable=True))

        batch_op.add_column(sa.Column("registration_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("registration_odometer", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("registration_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("registration_lng", sa.Float(), nullable=True))

        batch_op.add_column(sa.Column("gate_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("gate_odometer", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("gate_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("gate_lng", sa.Float(), nullable=True))

        batch_op.add_column(sa.Column("docs_time", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("docs_odometer", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("docs_lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("docs_lng", sa.Float(), nullable=True))

    # Backfill from legacy point timeline fields.
    op.execute(
        """
        UPDATE points
        SET
          departure_time = COALESCE(departure_time, time_accepted),
          registration_time = COALESCE(registration_time, time_registration),
          gate_time = COALESCE(gate_time, time_put_on_gate),
          docs_time = COALESCE(docs_time, time_docs)
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("points") as batch_op:
        batch_op.drop_column("docs_lng")
        batch_op.drop_column("docs_lat")
        batch_op.drop_column("docs_odometer")
        batch_op.drop_column("docs_time")

        batch_op.drop_column("gate_lng")
        batch_op.drop_column("gate_lat")
        batch_op.drop_column("gate_odometer")
        batch_op.drop_column("gate_time")

        batch_op.drop_column("registration_lng")
        batch_op.drop_column("registration_lat")
        batch_op.drop_column("registration_odometer")
        batch_op.drop_column("registration_time")

        batch_op.drop_column("departure_lng")
        batch_op.drop_column("departure_lat")
        batch_op.drop_column("departure_odometer")
        batch_op.drop_column("departure_time")
