"""require house models to belong to developer clients

Revision ID: 0006_require_house_model_client
Revises: 0005_house_model_client
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_require_house_model_client"
down_revision: Union[str, None] = "0005_house_model_client"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE house_models AS hm
        SET client_id = first_client.id
        FROM (
            SELECT DISTINCT ON (company_id) id, company_id
            FROM clients
            ORDER BY company_id, id
        ) AS first_client
        WHERE hm.client_id IS NULL
          AND first_client.company_id = hm.company_id
        """
    )
    op.alter_column(
        "house_models",
        "client_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "house_models",
        "client_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
