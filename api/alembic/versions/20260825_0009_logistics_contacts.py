"""Global logistics contacts shown on trip screens.

Revision ID: 20260825_0009
Revises: 20260427_0008
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0009"
down_revision = "20260427_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "logistics_contacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.bulk_insert(
        sa.table(
            "logistics_contacts",
            sa.column("name", sa.String),
            sa.column("phone", sa.String),
            sa.column("sort_order", sa.Integer),
        ),
        [
            {"name": "Гуля", "phone": "+7 (916) 842-01-12", "sort_order": 0},
            {"name": "Александр", "phone": "+7 (989) 150-51-42", "sort_order": 1},
            {"name": "Зураб", "phone": "+7 (985) 046-84-82", "sort_order": 2},
        ],
    )


def downgrade() -> None:
    op.drop_table("logistics_contacts")
