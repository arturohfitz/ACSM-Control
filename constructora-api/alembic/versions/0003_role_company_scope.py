"""scope roles by company

Revision ID: 0003_role_company_scope
Revises: 0002_multi_company_licensing
Create Date: 2026-05-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_role_company_scope"
down_revision: Union[str, None] = "0002_multi_company_licensing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("roles", sa.Column("company_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_roles_company_id"), "roles", ["company_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_roles_company_id_companies"), "roles", "companies", ["company_id"], ["id"]
    )
    op.drop_constraint(op.f("uq_roles_name"), "roles", type_="unique")
    op.create_unique_constraint("uq_roles_company_name", "roles", ["company_id", "name"])


def downgrade() -> None:
    op.drop_constraint("uq_roles_company_name", "roles", type_="unique")
    op.create_unique_constraint(op.f("uq_roles_name"), "roles", ["name"])
    op.drop_constraint(op.f("fk_roles_company_id_companies"), "roles", type_="foreignkey")
    op.drop_index(op.f("ix_roles_company_id"), table_name="roles")
    op.drop_column("roles", "company_id")
