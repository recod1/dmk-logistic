"""Return photos on point documents.

Revision ID: 20261023_0025
Revises: 20261022_0024
Create Date: 2026-10-23
"""

from alembic import op
import sqlalchemy as sa


revision = "20261023_0025"
down_revision = "20261022_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "point_document_images",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="docs"),
    )
    op.add_column(
        "point_document_images",
        sa.Column("incident_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_point_document_images_incident_id", "point_document_images", ["incident_id"])
    op.create_foreign_key(
        "fk_point_document_images_incident_id",
        "point_document_images",
        "route_incidents",
        ["incident_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_point_document_images_incident_id", "point_document_images", type_="foreignkey")
    op.drop_index("ix_point_document_images_incident_id", table_name="point_document_images")
    op.drop_column("point_document_images", "incident_id")
    op.drop_column("point_document_images", "kind")
