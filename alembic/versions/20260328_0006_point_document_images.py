"""Point document images for PWA docs stage.

Revision ID: 20260328_0006
Revises: 20260327_0005
Create Date: 2026-03-28 00:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0006"
down_revision = "20260327_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "point_document_images",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("point_id", sa.Integer(), sa.ForeignKey("points.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("route_id", sa.String(64), sa.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("point_document_images")
