"""Persistent document profiles for fleet vehicles, trailers and drivers.

Revision ID: 20261111_0027
Revises: 20261108_0026
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20261111_0027"
down_revision = "20261108_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fleet_vehicles",
        sa.Column("docs_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "fleet_trailers",
        sa.Column("docs_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "users",
        sa.Column("docs_json", sa.Text(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("users", "docs_json")
    op.drop_column("fleet_trailers", "docs_json")
    op.drop_column("fleet_vehicles", "docs_json")
