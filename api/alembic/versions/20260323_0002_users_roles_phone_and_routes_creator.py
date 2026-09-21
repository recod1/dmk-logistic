"""Add users.role_code/phone and routes.created_by_user_id.

Revision ID: 20260323_0002
Revises: 20260323_0001
Create Date: 2026-03-23 00:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260323_0002"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "role",
            new_column_name="role_code",
            existing_type=sa.String(length=32),
            existing_nullable=False,
        )
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))

    op.drop_index("ix_users_role", table_name="users")
    op.create_index("ix_users_role_code", "users", ["role_code"], unique=False)
    op.create_index("ix_users_phone", "users", ["phone"], unique=False)

    op.execute(
        """
        UPDATE users
        SET role_code = CASE lower(trim(role_code))
          WHEN 'driver' THEN 'driver'
          WHEN 'водитель' THEN 'driver'
          WHEN 'logistic' THEN 'logistic'
          WHEN 'логист' THEN 'logistic'
          WHEN 'accountant' THEN 'accountant'
          WHEN 'бухгалтер' THEN 'accountant'
          WHEN 'admin' THEN 'admin'
          WHEN 'администратор' THEN 'admin'
          WHEN 'superadmin' THEN 'superadmin'
          WHEN 'super-admin' THEN 'superadmin'
          WHEN 'супер-админ' THEN 'superadmin'
          ELSE 'driver'
        END
        """
    )

    with op.batch_alter_table("routes") as batch_op:
        batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_routes_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["id"],
        )
    op.create_index("ix_routes_created_by_user_id", "routes", ["created_by_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_routes_created_by_user_id", table_name="routes")
    with op.batch_alter_table("routes") as batch_op:
        batch_op.drop_constraint("fk_routes_created_by_user_id_users", type_="foreignkey")
        batch_op.drop_column("created_by_user_id")

    op.drop_index("ix_users_phone", table_name="users")
    op.drop_index("ix_users_role_code", table_name="users")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("phone")
        batch_op.alter_column(
            "role_code",
            new_column_name="role",
            existing_type=sa.String(length=32),
            existing_nullable=False,
        )
    op.create_index("ix_users_role", "users", ["role"], unique=False)

