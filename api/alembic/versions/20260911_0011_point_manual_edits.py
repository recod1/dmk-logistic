"""Store who manually edited point fields.

Revision ID: 20260911_0011
Revises: 20260904_0010
Create Date: 2026-09-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260911_0011"
down_revision = "20260904_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("points", sa.Column("manual_edits", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("points", "manual_edits")
