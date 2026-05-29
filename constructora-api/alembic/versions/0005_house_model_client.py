"""link house models to client developers

Revision ID: 0005_house_model_client
Revises: 0004_project_inventory
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_house_model_client"
down_revision: Union[str, None] = "0004_project_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("house_models", sa.Column("client_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_house_models_client_id"), "house_models", ["client_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_house_models_client_id_clients"),
        "house_models",
        "clients",
        ["client_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_house_models_client_id_clients"), "house_models", type_="foreignkey")
    op.drop_index(op.f("ix_house_models_client_id"), table_name="house_models")
    op.drop_column("house_models", "client_id")
