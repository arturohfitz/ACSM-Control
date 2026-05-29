"""normalize project material price timestamps

Revision ID: 0008_price_timestamps
Revises: 0007_project_material_prices
Create Date: 2026-05-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0008_price_timestamps"
down_revision: Union[str, None] = "0007_project_material_prices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE project_material_prices SET updated_at = created_at WHERE updated_at IS NULL")
    op.alter_column(
        "project_material_prices",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "project_material_prices",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        server_default=None,
        nullable=True,
    )
