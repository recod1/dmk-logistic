"""Driver phone location on routes and salary archive links.

Revision ID: 20260927_0012
Revises: 20260911_0011
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa


revision = "20260927_0012"
down_revision = "20260911_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("routes", sa.Column("driver_lat", sa.Float(), nullable=True))
    op.add_column("routes", sa.Column("driver_lng", sa.Float(), nullable=True))
    op.add_column("routes", sa.Column("driver_location_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("routes", sa.Column("driver_location_requested_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("salary", sa.Column("replaces_salary_id", sa.Integer(), nullable=True))
    op.add_column("salary", sa.Column("replaced_by_salary_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_salary_replaces_salary_id",
        "salary",
        "salary",
        ["replaces_salary_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_salary_replaced_by_salary_id",
        "salary",
        "salary",
        ["replaced_by_salary_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_salary_replaces_salary_id", "salary", ["replaces_salary_id"])
    op.create_index("ix_salary_replaced_by_salary_id", "salary", ["replaced_by_salary_id"])


def downgrade() -> None:
    op.drop_index("ix_salary_replaced_by_salary_id", table_name="salary")
    op.drop_index("ix_salary_replaces_salary_id", table_name="salary")
    op.drop_constraint("fk_salary_replaced_by_salary_id", "salary", type_="foreignkey")
    op.drop_constraint("fk_salary_replaces_salary_id", "salary", type_="foreignkey")
    op.drop_column("salary", "replaced_by_salary_id")
    op.drop_column("salary", "replaces_salary_id")
    op.drop_column("routes", "driver_location_requested_at")
    op.drop_column("routes", "driver_location_at")
    op.drop_column("routes", "driver_lng")
    op.drop_column("routes", "driver_lat")
