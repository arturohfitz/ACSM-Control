"""add house model review status

Revision ID: 0013_house_model_review_status
Revises: 0012_house_model_documents
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0013_house_model_review_status"
down_revision: Union[str, None] = "0012_house_model_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "house_model_material_requirements",
        sa.Column("validation_status", sa.String(length=40), nullable=False, server_default="pending"),
    )
    op.add_column(
        "house_model_budget_activities",
        sa.Column("validation_status", sa.String(length=40), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("house_model_budget_activities", "validation_status")
    op.drop_column("house_model_material_requirements", "validation_status")
